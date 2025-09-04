"""
Test CR-0073: Headless Runner & Degrade Mode
Test suite for headless runner functionality
"""

import os
import sys
import tempfile
import threading
import time
from unittest.mock import MagicMock, patch

import pytest

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.headless_runner import HeadlessRunner

# Test constants
DEFAULT_HEALTH_CHECK_INTERVAL = 60
CUSTOM_HEALTH_CHECK_INTERVAL = 30


class TestHeadlessRunner:
    """Test HeadlessRunner class"""

    def setup_method(self):
        """Setup test environment"""
        self.temp_dir = tempfile.mkdtemp()

        # Mock environment variables
        self.env_patches = {}
        self.env_patches['BINANCE_API_KEY'] = patch.dict(os.environ, {'BINANCE_API_KEY': 'test_key'})
        self.env_patches['BINANCE_API_SECRET'] = patch.dict(os.environ, {'BINANCE_API_SECRET': 'test_secret'})
        self.env_patches['DATA_PATH'] = patch.dict(os.environ, {'DATA_PATH': self.temp_dir})
        self.env_patches['LOG_PATH'] = patch.dict(os.environ, {'LOG_PATH': f'{self.temp_dir}/logs'})
        self.env_patches['BACKUP_PATH'] = patch.dict(os.environ, {'BACKUP_PATH': f'{self.temp_dir}/backup'})

        # Start patches
        for patch_obj in self.env_patches.values():
            patch_obj.start()

    def teardown_method(self):
        """Cleanup test environment"""
        # Stop patches
        for patch_obj in self.env_patches.values():
            patch_obj.stop()

        # Cleanup temp directory
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_headless_runner_initialization(self):
        """Test HeadlessRunner initialization"""
        runner = HeadlessRunner()

        assert runner.status == "INITIALIZING"
        assert not runner.shutdown_requested
        assert runner.trading_core is None
        assert runner.health_check_interval == DEFAULT_HEALTH_CHECK_INTERVAL

        # Check component status initialized
        expected_components = ["data_fetcher", "trading_core", "api_connection", "threshold_cache"]
        for component in expected_components:
            assert component in runner.components_status
            assert runner.components_status[component] == "NOT_STARTED"

    def test_environment_validation_success(self):
        """Test successful environment validation"""
        with patch('src.headless_runner.Settings') as mock_settings:
            mock_settings.BINANCE_API_KEY = 'test_key'
            mock_settings.BINANCE_API_SECRET = 'test_secret'
            mock_settings.DATA_PATH = self.temp_dir
            mock_settings.LOG_PATH = f'{self.temp_dir}/logs'
            mock_settings.BACKUP_PATH = f'{self.temp_dir}/backup'
            mock_settings.OFFLINE_MODE = False

            runner = HeadlessRunner()

            result = runner.validate_environment()

            assert result is True
            # Directories should be created
            assert os.path.exists(f'{self.temp_dir}/logs')
            assert os.path.exists(f'{self.temp_dir}/backup')

    def test_environment_validation_missing_api_keys(self):
        """Test environment validation with missing API keys"""
        with patch('src.headless_runner.Settings') as mock_settings:
            mock_settings.BINANCE_API_KEY = ''
            mock_settings.BINANCE_API_SECRET = ''
            mock_settings.DATA_PATH = self.temp_dir
            mock_settings.LOG_PATH = f'{self.temp_dir}/logs'
            mock_settings.BACKUP_PATH = f'{self.temp_dir}/backup'
            mock_settings.OFFLINE_MODE = False

            runner = HeadlessRunner()

            result = runner.validate_environment()

            assert result is False

    def test_offline_mode_validation_no_data(self):
        """Test offline mode validation without historical data"""
        with patch('src.headless_runner.Settings') as mock_settings:
            mock_settings.BINANCE_API_KEY = 'test_key'
            mock_settings.BINANCE_API_SECRET = 'test_secret'
            mock_settings.DATA_PATH = self.temp_dir
            mock_settings.LOG_PATH = f'{self.temp_dir}/logs'
            mock_settings.BACKUP_PATH = f'{self.temp_dir}/backup'
            mock_settings.OFFLINE_MODE = True

            runner = HeadlessRunner()

            result = runner.validate_environment()

            # Should fail because no historical data exists
            assert result is False

    def test_offline_mode_validation_with_data(self):
        """Test offline mode validation with historical data"""
        # Create dummy CSV file
        raw_dir = os.path.join(self.temp_dir, 'raw')
        os.makedirs(raw_dir)
        with open(os.path.join(raw_dir, 'BTCUSDT.csv'), 'w') as f:
            f.write("timestamp,open,high,low,close,volume\n")

        with patch('src.headless_runner.Settings') as mock_settings:
            mock_settings.BINANCE_API_KEY = 'test_key'
            mock_settings.BINANCE_API_SECRET = 'test_secret'
            mock_settings.DATA_PATH = self.temp_dir
            mock_settings.LOG_PATH = f'{self.temp_dir}/logs'
            mock_settings.BACKUP_PATH = f'{self.temp_dir}/backup'
            mock_settings.OFFLINE_MODE = True

            runner = HeadlessRunner()

            result = runner.validate_environment()

            assert result is True

    @patch('src.headless_runner.get_threshold_cache')
    @patch('src.headless_runner.DataFetcher')
    @patch('src.headless_runner.Trader')
    def test_initialize_components_success(self, mock_trading_core, mock_data_fetcher,
                                         mock_threshold_cache):
        """Test successful component initialization"""
        # Setup mocks
        mock_cache = MagicMock()
        mock_cache.get_cache_status.return_value = {'test': 'value'}
        mock_threshold_cache.return_value = mock_cache

        mock_fetcher = MagicMock()
        mock_data_fetcher.return_value = mock_fetcher

        mock_core = MagicMock()
        mock_trading_core.return_value = mock_core

        # Create dummy raw directory to avoid data fetch
        raw_dir = os.path.join(self.temp_dir, 'raw')
        os.makedirs(raw_dir)
        with open(os.path.join(raw_dir, 'dummy.csv'), 'w') as f:
            f.write("data\n")

        runner = HeadlessRunner()

        result = runner.initialize_components()

        assert result is True
        assert runner.components_status["threshold_cache"] == "HEALTHY"
        assert runner.components_status["data_fetcher"] == "HEALTHY"
        assert runner.components_status["trading_core"] == "HEALTHY"
        assert runner.trading_core == mock_core

        # Verify mocks were called
        mock_threshold_cache.assert_called_once()
        mock_data_fetcher.assert_called_once()
        mock_trading_core.assert_called_once()

    @patch('src.headless_runner.get_threshold_cache')
    @patch('src.headless_runner.DataFetcher')
    @patch('src.headless_runner.Trader')
    def test_initialize_components_trading_core_failure(self, mock_trading_core, mock_data_fetcher,
                                                       mock_threshold_cache):
        """Test component initialization with trading core failure"""
        # Setup mocks
        mock_threshold_cache.return_value = MagicMock()
        mock_data_fetcher.return_value = MagicMock()
        mock_trading_core.side_effect = Exception("Trading core init failed")

        runner = HeadlessRunner()

        result = runner.initialize_components()

        assert result is False
        assert runner.components_status["trading_core"] == "FAILED"
        assert runner.trading_core is None

    def test_health_checks_basic(self):
        """Test basic health checks functionality"""
        runner = HeadlessRunner()

        health_status = runner.run_health_checks()

        assert "timestamp" in health_status
        assert "overall_status" in health_status
        assert "components" in health_status
        assert "uptime_seconds" in health_status

        # All components should be in health status
        for component in runner.components_status:
            assert component in health_status["components"]

    def test_health_checks_with_failed_components(self):
        """Test health checks with failed components"""
        runner = HeadlessRunner()
        runner.components_status["api_connection"] = "FAILED"

        health_status = runner.run_health_checks()

        assert health_status["overall_status"] == "CRITICAL"
        assert "failed_components" in health_status
        assert "api_connection" in health_status["failed_components"]

    def test_health_checks_with_degraded_components(self):
        """Test health checks with degraded components"""
        runner = HeadlessRunner()
        runner.components_status["trading_core"] = "DEGRADED"

        health_status = runner.run_health_checks()

        assert health_status["overall_status"] == "DEGRADED"
        assert "degraded_components" in health_status

    @patch('src.headless_runner.Trader')
    def test_health_checks_with_trading_core(self, mock_trading_core):
        """Test health checks with active trading core"""
        mock_core = MagicMock()
        mock_core.get_open_positions.return_value = [{"symbol": "BTCUSDT"}]
        mock_trading_core.return_value = mock_core

        runner = HeadlessRunner()
        runner.trading_core = mock_core
        runner.components_status["trading_core"] = "HEALTHY"

        health_status = runner.run_health_checks()

        assert health_status["components"]["trading_core"]["open_positions"] == 1
        assert health_status["components"]["trading_core"]["status"] == "HEALTHY"

    def test_signal_handlers_setup(self):
        """Test signal handlers are properly setup"""
        runner = HeadlessRunner()

        # Verify signal handlers are registered
        # Note: This test is limited because we can't easily test actual signal delivery
        assert runner.shutdown_requested is False

        # Simulate signal handler call
        runner.request_shutdown()
        assert runner.shutdown_requested is True

    def test_request_shutdown(self):
        """Test shutdown request functionality"""
        runner = HeadlessRunner()

        assert runner.shutdown_requested is False

        runner.request_shutdown()

        assert runner.shutdown_requested is True

    @patch('src.headless_runner.Trader')
    def test_shutdown_with_trading_core(self, mock_trading_core):
        """Test shutdown with active trading core"""
        mock_core = MagicMock()
        mock_trading_core.return_value = mock_core

        runner = HeadlessRunner()
        runner.trading_core = mock_core
        runner.status = "RUNNING"

        exit_code = runner.shutdown()

        assert exit_code == 0
        assert runner.status == "STOPPED"
        mock_core.stop.assert_called_once()

    def test_shutdown_without_trading_core(self):
        """Test shutdown without trading core"""
        runner = HeadlessRunner()
        runner.status = "RUNNING"

        exit_code = runner.shutdown()

        assert exit_code == 0
        assert runner.status == "STOPPED"

    @patch('src.headless_runner.Trader')
    def test_shutdown_with_error(self, mock_trading_core):
        """Test shutdown with error in trading core"""
        mock_core = MagicMock()
        mock_core.stop.side_effect = Exception("Shutdown error")
        mock_trading_core.return_value = mock_core

        runner = HeadlessRunner()
        runner.trading_core = mock_core
        runner.status = "RUNNING"

        # Should still return 0 despite error (graceful degradation)
        exit_code = runner.shutdown()

        assert exit_code == 0  # Graceful even with errors
        assert runner.status == "STOPPED"

    def test_get_status(self):
        """Test status information retrieval"""
        runner = HeadlessRunner()

        status = runner.get_status()

        required_keys = ["status", "start_time", "uptime_seconds", "components",
                        "shutdown_requested", "pid"]

        for key in required_keys:
            assert key in status

        assert status["status"] == "INITIALIZING"
        assert status["shutdown_requested"] is False
        assert status["pid"] == os.getpid()
        assert isinstance(status["uptime_seconds"], (int, float))
        assert status["uptime_seconds"] >= 0

    def test_config_overrides(self):
        """Test configuration overrides"""
        config_overrides = {"offline_mode": True, "degrade_mode": True}

        runner = HeadlessRunner(config_overrides)

        assert runner.config_overrides == config_overrides

    @patch('src.headless_runner.time.sleep')
    @patch.object(HeadlessRunner, 'validate_environment')
    @patch.object(HeadlessRunner, 'initialize_components')
    @patch.object(HeadlessRunner, 'run_health_checks')
    def test_run_success_quick_shutdown(self, mock_health, mock_init, mock_validate, _mock_sleep):
        """Test successful run with quick shutdown"""
        mock_validate.return_value = True
        mock_init.return_value = True
        mock_health.return_value = {"overall_status": "HEALTHY"}

        runner = HeadlessRunner()

        # Setup to shutdown immediately
        def request_shutdown():
            time.sleep(0.1)
            runner.request_shutdown()

        shutdown_thread = threading.Thread(target=request_shutdown)
        shutdown_thread.start()

        exit_code = runner.run()
        shutdown_thread.join()

        assert exit_code == 0
        mock_validate.assert_called_once()
        mock_init.assert_called_once()

    @patch.object(HeadlessRunner, 'validate_environment')
    def test_run_environment_validation_failure(self, mock_validate):
        """Test run with environment validation failure"""
        mock_validate.return_value = False

        runner = HeadlessRunner()

        exit_code = runner.run()

        assert exit_code == 1
        mock_validate.assert_called_once()

    @patch.object(HeadlessRunner, 'validate_environment')
    @patch.object(HeadlessRunner, 'initialize_components')
    def test_run_component_initialization_failure(self, mock_init, mock_validate):
        """Test run with component initialization failure"""
        mock_validate.return_value = True
        mock_init.return_value = False

        runner = HeadlessRunner()

        exit_code = runner.run()

        assert exit_code == 1
        mock_validate.assert_called_once()
        mock_init.assert_called_once()

    def test_component_status_tracking(self):
        """Test component status is properly tracked"""
        runner = HeadlessRunner()

        # Initial status
        assert runner.components_status["trading_core"] == "NOT_STARTED"

        # Update status
        runner.components_status["trading_core"] = "HEALTHY"
        assert runner.components_status["trading_core"] == "HEALTHY"

        # Status should be reflected in get_status
        status = runner.get_status()
        assert status["components"]["trading_core"] == "HEALTHY"

    def test_health_check_interval_setting(self):
        """Test health check interval can be configured"""
        runner = HeadlessRunner()

        # Default interval
        assert runner.health_check_interval == DEFAULT_HEALTH_CHECK_INTERVAL

        # Set custom interval
        runner.health_check_interval = CUSTOM_HEALTH_CHECK_INTERVAL
        assert runner.health_check_interval == CUSTOM_HEALTH_CHECK_INTERVAL


class TestHeadlessRunnerIntegration:
    """Integration tests for HeadlessRunner"""

    @patch('src.headless_runner.Settings.OFFLINE_MODE', True)
    @patch('src.headless_runner.get_threshold_cache')
    @patch('src.headless_runner.DataFetcher')
    def test_offline_mode_integration(self, mock_data_fetcher, mock_threshold_cache):
        """Test headless runner in offline mode"""
        # Setup mocks
        mock_threshold_cache.return_value = MagicMock()
        mock_fetcher = MagicMock()
        mock_data_fetcher.return_value = mock_fetcher

        # Create temporary environment
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create dummy data
            raw_dir = os.path.join(temp_dir, 'raw')
            os.makedirs(raw_dir)
            with open(os.path.join(raw_dir, 'BTCUSDT.csv'), 'w') as f:
                f.write("timestamp,open,high,low,close,volume\n")

            with patch.dict(os.environ, {
                'BINANCE_API_KEY': 'test_key',
                'BINANCE_API_SECRET': 'test_secret',
                'DATA_PATH': temp_dir,
                'LOG_PATH': f'{temp_dir}/logs',
                'BACKUP_PATH': f'{temp_dir}/backup',
                'OFFLINE_MODE': 'true'
            }):
                runner = HeadlessRunner()

                # Should validate successfully in offline mode with data
                assert runner.validate_environment() is True

                # API connection should be marked as offline
                runner.components_status["api_connection"] = "OFFLINE"

                health_status = runner.run_health_checks()
                assert health_status["components"]["api_connection"]["status"] == "OFFLINE"


class TestHeadlessRunnerCLI:
    """Test CLI functionality (would be tested separately in integration)"""

    def test_cli_argument_structure(self):
        """Test that CLI arguments are properly structured"""
        # This would test the argparse setup in main()
        # For now, just verify the main function exists and is callable
        from src.headless_runner import main

        assert callable(main)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
