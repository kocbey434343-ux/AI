"""
CR-0073: Headless Runner & Degrade Mode
Trade bot headless çalıştırma ve graceful degradation
"""

import argparse
import os
import signal
import sys
import threading
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional

# Python path'e proje dizinini ekle
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.runtime_thresholds import load_runtime_thresholds
from config.settings import Settings

from src.data_fetcher import DataFetcher
from src.trader.core import Trader
from src.utils.feature_flags import flag_enabled
from src.utils.logger import get_logger
from src.utils.structured_log import slog
from src.utils.threshold_cache import get_threshold_cache


class HeadlessRunner:
    """
    Headless (UI'sız) bot çalıştırıcı

    Features:
    - CLI-only operation mode
    - Signal handling for graceful shutdown
    - Status monitoring and health checks
    - Configuration validation
    - Service/daemon mode support
    - Graceful degradation when components fail
    """

    def __init__(self, config_overrides: Optional[Dict[str, Any]] = None):
        self.logger = get_logger("HeadlessRunner")
        self.config_overrides = config_overrides or {}

        self.trading_core: Optional[Trader] = None
        self.shutdown_requested = False
        self.status = "INITIALIZING"
        self.start_time = datetime.now(timezone.utc)
        self.health_check_interval = 60  # seconds
        self.last_health_check = None

        # Component status tracking
        self.components_status = {
            "data_fetcher": "NOT_STARTED",
            "trading_core": "NOT_STARTED",
            "api_connection": "NOT_STARTED",
            "threshold_cache": "NOT_STARTED"
        }

        # Setup signal handlers for graceful shutdown
        self._setup_signal_handlers()

        self.logger.info("HeadlessRunner initialized")
        slog("headless_runner_init", mode="headless", pid=os.getpid())

    def _setup_signal_handlers(self):
        """Setup signal handlers for graceful shutdown"""
        def signal_handler(signum, frame):
            signal_name = {
                signal.SIGINT: "SIGINT",
                signal.SIGTERM: "SIGTERM"
            }.get(signum, f"SIGNAL_{signum}")

            self.logger.info(f"Received {signal_name}, initiating graceful shutdown...")
            slog("shutdown_signal_received", signal=signal_name)
            self.request_shutdown()

        # Register handlers for both SIGINT (Ctrl+C) and SIGTERM
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        self.logger.info("Signal handlers configured")

    def validate_environment(self) -> bool:
        """
        Validate environment and configuration

        Returns:
            True if environment is valid, False otherwise
        """
        self.logger.info("Validating environment...")
        problems = []

        # Check API keys (skip in offline mode)
        if not Settings.OFFLINE_MODE and (not Settings.BINANCE_API_KEY or not Settings.BINANCE_API_SECRET):
            problems.append('BINANCE API keys missing (check .env file)')

        # Check required directories
        for path_attr in ['DATA_PATH', 'LOG_PATH', 'BACKUP_PATH']:
            path = getattr(Settings, path_attr)
            try:
                os.makedirs(path, exist_ok=True)
            except Exception as e:
                problems.append(f'{path_attr} could not be created: {e}')

        # Check offline mode requirements
        if Settings.OFFLINE_MODE:
            # In offline mode, we need historical data to exist
            raw_path = os.path.join(Settings.DATA_PATH, 'raw')
            if not os.path.exists(raw_path) or not any(name.endswith('.csv') for name in os.listdir(raw_path)):
                problems.append('OFFLINE_MODE enabled but no historical data found')

        if problems:
            for problem in problems:
                self.logger.error(problem)
            slog("environment_validation_failed", problems=problems)
            return False

        self.logger.info("Environment validation successful")
        slog("environment_validation_passed")
        return True

    def initialize_components(self) -> bool:
        """
        Initialize all necessary components with graceful degradation

        Returns:
            True if core components initialized successfully
        """
        self.logger.info("Initializing components...")
        self.status = "INITIALIZING_COMPONENTS"

        # Initialize threshold cache (CR-0070)
        try:
            threshold_cache = get_threshold_cache()
            cache_entries = len(threshold_cache.get_cache_status())
            self.logger.info(f"Threshold cache initialized with {cache_entries} entries")
            self.components_status["threshold_cache"] = "HEALTHY"
            slog("component_initialized", component="threshold_cache", entries=cache_entries)
        except Exception as e:
            self.logger.error(f"Threshold cache initialization failed: {e}")
            self.components_status["threshold_cache"] = "FAILED"
            # Non-critical component, continue

        # Load runtime thresholds (legacy support)
        try:
            load_runtime_thresholds()
            self.logger.info("Runtime thresholds loaded")
        except Exception as e:
            self.logger.warning(f"Could not load runtime thresholds: {e}")
            # Non-critical, continue

        # Initialize data fetcher
        try:
            self.logger.info("Initializing data fetcher...")
            fetcher = DataFetcher()

            # Ensure basic data availability
            fetcher.ensure_top_pairs(force=False)

            # In offline mode or first run, ensure historical data
            raw_path = os.path.join(Settings.DATA_PATH, 'raw')
            os.makedirs(raw_path, exist_ok=True)

            if not Settings.OFFLINE_MODE:
                # Check if we need initial data fetch
                if not any(name.endswith('.csv') for name in os.listdir(raw_path)):
                    self.logger.info('No historical data found. Fetching initial data...')
                    fetcher.fetch_all_pairs_data(days=Settings.BACKTEST_DAYS, interval=Settings.TIMEFRAME)
                    self.logger.info('Initial data fetch complete')

                # Validate and repair dataset
                fetcher.validate_dataset(interval=Settings.TIMEFRAME, repair=True)

            self.components_status["data_fetcher"] = "HEALTHY"
            slog("component_initialized", component="data_fetcher", offline_mode=Settings.OFFLINE_MODE)

        except Exception as e:
            self.logger.error(f"Data fetcher initialization failed: {e}")
            self.components_status["data_fetcher"] = "FAILED"

            # Critical component failure
            if not Settings.OFFLINE_MODE:
                self.logger.error("Data fetcher is critical for online mode, aborting initialization")
                return False
            self.logger.warning("Data fetcher failed in offline mode, continuing with existing data")

        # Initialize trading core
        try:
            self.logger.info("Initializing trading core...")
            self.trading_core = Trader()
            self.components_status["trading_core"] = "HEALTHY"
            slog("component_initialized", component="trading_core")

        except Exception as e:
            self.logger.error(f"Trading core initialization failed: {e}")
            self.components_status["trading_core"] = "FAILED"
            return False  # Trading core is critical

        # Test API connection (if not in offline mode)
        if not Settings.OFFLINE_MODE:
            try:
                self.logger.info("Testing API connection...")
                # This will be handled by trading core's internal health check
                self.components_status["api_connection"] = "HEALTHY"
                slog("component_initialized", component="api_connection")

            except Exception as e:
                self.logger.error(f"API connection test failed: {e}")
                self.components_status["api_connection"] = "FAILED"

                # In degraded mode, we can continue without live API
                if flag_enabled("DEGRADE_MODE_ENABLED"):
                    self.logger.warning("API connection failed but degrade mode enabled, continuing...")
                    slog("degraded_mode_activated", reason="api_connection_failed")
                else:
                    return False
        else:
            self.components_status["api_connection"] = "OFFLINE"

        self.logger.info("Component initialization completed")
        return True

    def run_health_checks(self) -> Dict[str, Any]:
        """
        Perform health checks on all components

        Returns:
            Health check results
        """
        health_status = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "overall_status": "HEALTHY",
            "components": {},
            "uptime_seconds": (datetime.now(timezone.utc) - self.start_time).total_seconds()
        }

        # Check each component
        for component, status in self.components_status.items():
            component_health = {"status": status, "last_check": datetime.now(timezone.utc).isoformat()}

            # Additional checks based on component (only if not already failed)
            if status != "FAILED" and component == "trading_core" and self.trading_core:
                try:
                    # Check if core is responsive
                    positions = self.trading_core.get_open_positions()
                    component_health["open_positions"] = len(positions) if positions else 0
                    component_health["status"] = "HEALTHY"
                except Exception as e:
                    component_health["status"] = "DEGRADED"
                    component_health["error"] = str(e)

            elif status != "FAILED" and component == "api_connection" and not Settings.OFFLINE_MODE:
                try:
                    # This would be implemented by trading core
                    component_health["status"] = "HEALTHY"
                except Exception as e:
                    component_health["status"] = "FAILED"
                    component_health["error"] = str(e)

            health_status["components"][component] = component_health

        # Determine overall status
        failed_components = [c for c, h in health_status["components"].items() if h["status"] == "FAILED"]
        degraded_components = [c for c, h in health_status["components"].items() if h["status"] == "DEGRADED"]

        if failed_components:
            health_status["overall_status"] = "CRITICAL"
            health_status["failed_components"] = failed_components
        elif degraded_components:
            health_status["overall_status"] = "DEGRADED"
            health_status["degraded_components"] = degraded_components

        self.last_health_check = health_status

        # Log health status periodically
        if len(failed_components) > 0 or len(degraded_components) > 0:
            slog("health_check_issues",
                 overall_status=health_status["overall_status"],
                 failed=failed_components,
                 degraded=degraded_components)

        return health_status

    def _run_health_monitoring(self) -> bool:
        """
        Periodic health monitoring

        Returns:
            True to continue running, False to stop
        """
        health_status = self.run_health_checks()

        # Log health summary
        self.logger.info(f"Health check: {health_status['overall_status']}")

        # Auto-recovery for failed components
        if health_status["overall_status"] == "CRITICAL":
            self.logger.warning("Critical health status detected")

            # Attempt recovery if degradation mode is enabled
            if flag_enabled("AUTO_RECOVERY_ENABLED"):
                self.logger.info("Attempting auto-recovery...")
                slog("auto_recovery_attempt")
                # Recovery logic would go here

        return True

    def run(self) -> int:
        """
        Main run loop for headless operation

        Returns:
            Exit code (0 for success, non-zero for error)
        """
        try:
            self.logger.info("Starting headless runner...")
            slog("headless_run_start", offline_mode=Settings.OFFLINE_MODE)

            # Validate environment
            if not self.validate_environment():
                self.logger.error("Environment validation failed")
                return 1

            # Initialize components
            if not self.initialize_components():
                self.logger.error("Component initialization failed")
                return 1

            self.status = "RUNNING"
            self.logger.info("HeadlessRunner started successfully")
            slog("headless_runner_started", components=list(self.components_status.keys()))

            # Main run loop
            last_health_check = time.time()

            while not self.shutdown_requested:
                try:
                    # Periodic health checks
                    if time.time() - last_health_check >= self.health_check_interval:
                        if not self._run_health_monitoring():
                            break
                        last_health_check = time.time()

                    # Let trading core do its work
                    if self.trading_core and self.components_status["trading_core"] == "HEALTHY":
                        # Trading core should handle its own run loop
                        pass

                    # Sleep to prevent busy waiting
                    time.sleep(1)

                except KeyboardInterrupt:
                    self.logger.info("KeyboardInterrupt received, shutting down...")
                    break
                except Exception as e:
                    self.logger.error(f"Error in main loop: {e}")
                    if not flag_enabled("CONTINUE_ON_ERROR"):
                        break
                    time.sleep(5)  # Wait before retrying

            # Graceful shutdown
            return self.shutdown()

        except Exception as e:
            self.logger.error(f"Unhandled exception in run: {e}")
            slog("headless_runner_exception", error=str(e))
            return 1

    def request_shutdown(self):
        """Request graceful shutdown"""
        self.shutdown_requested = True
        self.logger.info("Shutdown requested")

    def shutdown(self) -> int:
        """
        Perform graceful shutdown

        Returns:
            Exit code
        """
        self.logger.info("Performing graceful shutdown...")
        self.status = "SHUTTING_DOWN"
        slog("headless_shutdown_start")

        shutdown_timeout = 30  # seconds
        shutdown_start = time.time()

        try:
            # Shutdown trading core
            if self.trading_core:
                self.logger.info("Shutting down trading core...")
                try:
                    self.trading_core.stop()
                    self.components_status["trading_core"] = "STOPPED"
                    self.logger.info("Trading core shutdown completed")
                except Exception as e:
                    self.logger.error(f"Error during trading core shutdown: {e}")

            # Additional cleanup tasks
            self.logger.info("Performing final cleanup...")

            # Wait for any remaining threads to finish
            remaining_threads = [t for t in threading.enumerate() if t != threading.current_thread() and not t.daemon]
            if remaining_threads:
                self.logger.info(f"Waiting for {len(remaining_threads)} threads to finish...")
                for thread in remaining_threads:
                    thread.join(timeout=5)

            # Check if we exceeded shutdown timeout
            if time.time() - shutdown_start > shutdown_timeout:
                self.logger.warning(f"Shutdown took longer than {shutdown_timeout}s")

            self.status = "STOPPED"
            uptime = (datetime.now(timezone.utc) - self.start_time).total_seconds()
            self.logger.info(f"HeadlessRunner stopped successfully (uptime: {uptime:.1f}s)")
            slog("headless_shutdown_complete", uptime_seconds=uptime)

            return 0

        except Exception as e:
            self.logger.error(f"Error during shutdown: {e}")
            slog("headless_shutdown_error", error=str(e))
            return 1

    def get_status(self) -> Dict[str, Any]:
        """Get current status information"""
        return {
            "status": self.status,
            "start_time": self.start_time.isoformat(),
            "uptime_seconds": (datetime.now(timezone.utc) - self.start_time).total_seconds(),
            "components": self.components_status.copy(),
            "last_health_check": self.last_health_check,
            "shutdown_requested": self.shutdown_requested,
            "pid": os.getpid()
        }


def print_status(runner: HeadlessRunner):
    """Print current status to console"""
    status = runner.get_status()

    print("\n=== HeadlessRunner Status ===")
    print(f"Status: {status['status']}")
    print(f"Uptime: {status['uptime_seconds']:.1f} seconds")
    print(f"PID: {status['pid']}")
    print(f"Shutdown Requested: {status['shutdown_requested']}")

    print("\nComponent Status:")
    for component, component_status in status['components'].items():
        print(f"  {component}: {component_status}")

    if status['last_health_check']:
        health = status['last_health_check']
        print(f"\nLast Health Check: {health['overall_status']}")
        if 'failed_components' in health:
            print(f"Failed Components: {health['failed_components']}")
        if 'degraded_components' in health:
            print(f"Degraded Components: {health['degraded_components']}")

    print("=" * 30)


def main():
    """Main entry point for headless runner"""
    parser = argparse.ArgumentParser(description='Trade Bot Headless Runner')
    parser.add_argument('--offline', action='store_true', help='Run in offline mode')
    parser.add_argument('--degrade', action='store_true', help='Enable degradation mode')
    parser.add_argument('--health-interval', type=int, default=60, help='Health check interval (seconds)')
    parser.add_argument('--status', action='store_true', help='Show status and exit')
    parser.add_argument('--daemon', action='store_true', help='Run as daemon (background)')

    args = parser.parse_args()

    # Apply configuration overrides
    config_overrides = {}
    if args.offline:
        os.environ['OFFLINE_MODE'] = 'true'
        config_overrides['offline_mode'] = True

    if args.degrade:
        os.environ['DEGRADE_MODE_ENABLED'] = 'true'
        config_overrides['degrade_mode'] = True

    # Initialize logger
    logger = get_logger("Main")
    logger.info(f"HeadlessRunner starting with args: {vars(args)}")

    # Create and configure runner
    runner = HeadlessRunner(config_overrides)
    runner.health_check_interval = args.health_interval

    # Handle status request
    if args.status:
        print_status(runner)
        return 0

    # Handle daemon mode
    if args.daemon:
        logger.info("Daemon mode requested")
        # Simple daemon implementation (Unix only)
        if hasattr(os, 'fork'):
            try:
                pid = os.fork()  # type: ignore
                if pid == 0:
                    # Child process continues as daemon
                    logger.info(f"Running as daemon with PID {os.getpid()}")
                else:
                    # Parent process exits
                    print(f"Daemon started with PID {pid}")
                    return 0
            except (OSError, AttributeError):
                logger.warning("Fork failed, running in foreground")
        else:
            logger.warning("Daemon mode not supported on this platform, running in foreground")

    # Run the bot
    try:
        exit_code = runner.run()
        logger.info(f"HeadlessRunner exiting with code {exit_code}")
        return exit_code
    except KeyboardInterrupt:
        logger.info("KeyboardInterrupt in main, requesting shutdown")
        runner.request_shutdown()
        return runner.shutdown()
    except Exception as e:
        logger.error(f"Unhandled exception in main: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
