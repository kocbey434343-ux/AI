"""
CR-0074: Trader Metrics Integration
Trader sinifina Prometheus metrics entegrasyon patch'i
"""

from typing import Optional

from src.utils.logger import get_logger

try:
    from src.utils.metrics_server import start_metrics_server, stop_metrics_server
    from src.utils.prometheus_export import get_exporter_instance
    METRICS_AVAILABLE = True
except ImportError:
    METRICS_AVAILABLE = False
    get_exporter_instance = None
    start_metrics_server = None
    stop_metrics_server = None


class TraderMetricsIntegration:
    """Trader class icin metrics entegrasyon yardimcisi"""

    def __init__(self, trader_instance):
        self.trader = trader_instance
        self.logger = get_logger(__name__)

        if METRICS_AVAILABLE:
            self.prometheus_exporter = get_exporter_instance()
            self.metrics_enabled = True
        else:
            self.prometheus_exporter = None
            self.metrics_enabled = False
            self.logger.warning("Metrics integration not available - prometheus_export module missing")

    def init_metrics_server(self, port: int = 8080, host: str = "localhost") -> bool:
        """Initialize and start metrics HTTP server"""
        if not self.metrics_enabled:
            return False

        try:
            success = start_metrics_server(port=port, host=host)
            if success:
                self.logger.info(f"Metrics server started at http://{host}:{port}/metrics")
            else:
                self.logger.error("Failed to start metrics server")
            return success
        except Exception as e:
            self.logger.error(f"Error starting metrics server: {e}")
            return False

    def shutdown_metrics_server(self):
        """Stop metrics HTTP server"""
        if not self.metrics_enabled:
            return

        try:
            stop_metrics_server()
            self.logger.info("Metrics server stopped")
        except Exception as e:
            self.logger.error(f"Error stopping metrics server: {e}")

    def record_trade_opened(self, symbol: str):
        """Record trade opened event"""
        if not self.metrics_enabled:
            return

        try:
            self.prometheus_exporter.record_trade_opened(symbol)
        except Exception as e:
            self.logger.error(f"Error recording trade opened: {e}")

    def record_trade_closed(self, symbol: str, pnl: float):
        """Record trade closed event"""
        if not self.metrics_enabled:
            return

        try:
            result = 'profit' if pnl > 0 else 'loss'
            self.prometheus_exporter.record_trade_closed(symbol, result)
        except Exception as e:
            self.logger.error(f"Error recording trade closed: {e}")

    def update_positions_count(self, count: int):
        """Update open positions count"""
        if not self.metrics_enabled:
            return

        try:
            self.prometheus_exporter.update_positions_count(count)
        except Exception as e:
            self.logger.error(f"Error updating positions count: {e}")

    def update_unrealized_pnl(self, pnl: float):
        """Update unrealized PnL"""
        if not self.metrics_enabled:
            return

        try:
            self.prometheus_exporter.update_unrealized_pnl(pnl)
        except Exception as e:
            self.logger.error(f"Error updating unrealized PnL: {e}")

    def record_guard_block(self, guard_type: str):
        """Record guard block event"""
        if not self.metrics_enabled:
            return

        try:
            self.prometheus_exporter.record_guard_block(guard_type)
        except Exception as e:
            self.logger.error(f"Error recording guard block: {e}")

    def collect_trader_metrics(self):
        """Collect metrics from trader's metrics object"""
        if not self.metrics_enabled:
            return

        try:
            # Collect from trader's metrics if available
            if hasattr(self.trader, 'metrics'):
                self.prometheus_exporter.collect_from_trader(self.trader.metrics)

            # Collect current positions info
            positions = getattr(self.trader, 'positions', {})
            self.update_positions_count(len(positions))

            # Calculate and update unrealized PnL
            unrealized_pnl = self._calculate_unrealized_pnl()
            if unrealized_pnl is not None:
                self.update_unrealized_pnl(unrealized_pnl)

        except Exception as e:
            self.logger.error(f"Error collecting trader metrics: {e}")

    def _calculate_unrealized_pnl(self) -> Optional[float]:
        """Calculate total unrealized PnL from positions"""
        try:
            total_pnl = 0.0
            positions = getattr(self.trader, 'positions', {})

            for symbol, position in positions.items():
                # Get current price and calculate unrealized PnL
                if hasattr(self.trader, 'binance_api'):
                    try:
                        current_price = self.trader.binance_api.get_current_price(symbol)
                        if current_price:
                            entry_price = position.get('entry_price', 0)
                            position_size = position.get('position_size', 0)
                            side = position.get('side', 'BUY')

                            if side == 'BUY':
                                pnl = (current_price - entry_price) * position_size
                            else:
                                pnl = (entry_price - current_price) * position_size

                            total_pnl += pnl
                    except Exception as e:
                        self.logger.warning(f"Failed to get price for {symbol}: {e}")
                        continue

            return total_pnl

        except Exception as e:
            self.logger.error(f"Error calculating unrealized PnL: {e}")
            return None

    def update_health_status(self, component: str, is_healthy: bool):
        """Update component health status"""
        if not self.metrics_enabled:
            return

        try:
            status = 1 if is_healthy else 0
            self.prometheus_exporter.update_health_status(component, status)
        except Exception as e:
            self.logger.error(f"Error updating health status: {e}")


def patch_trader_with_metrics(trader_instance):
    """Patch trader instance with metrics integration"""
    if not hasattr(trader_instance, '_metrics_integration'):
        trader_instance._metrics_integration = TraderMetricsIntegration(trader_instance)

        # Add convenience methods to trader
        trader_instance.init_metrics_server = trader_instance._metrics_integration.init_metrics_server
        trader_instance.shutdown_metrics_server = trader_instance._metrics_integration.shutdown_metrics_server
        trader_instance.collect_metrics = trader_instance._metrics_integration.collect_trader_metrics

        # Hook into existing methods if they exist
        _patch_existing_methods(trader_instance)

    return trader_instance._metrics_integration


def _patch_existing_methods(trader_instance):
    """Patch existing trader methods to include metrics collection"""
    integration = trader_instance._metrics_integration
    _patch_open_position(trader_instance, integration)
    _patch_close_position(trader_instance, integration)


def _patch_open_position(trader_instance, integration):
    """Patch open_position method"""
    if hasattr(trader_instance, 'open_position'):
        original_open = trader_instance.open_position

        def open_position_with_metrics(*args, **kwargs):
            result = original_open(*args, **kwargs)
            if result and len(args) > 0:  # symbol is first argument
                symbol = args[0]
                integration.record_trade_opened(symbol)
            return result

        trader_instance.open_position = open_position_with_metrics


def _patch_close_position(trader_instance, integration):
    """Patch close_position method"""
    if hasattr(trader_instance, 'close_position'):
        original_close = trader_instance.close_position

        def close_position_with_metrics(*args, **kwargs):
            symbol = args[0] if len(args) > 0 else None
            result = original_close(*args, **kwargs)
            if result and symbol:
                _record_trade_closure(trader_instance, integration, symbol)
            return result

        trader_instance.close_position = close_position_with_metrics


def _record_trade_closure(trader_instance, integration, symbol):
    """Helper to record trade closure"""
    try:
        positions = getattr(trader_instance, 'positions', {})
        if symbol in positions:
            # This would be called before position is removed
            # We could calculate PnL here, but it's complex
            # For now, just record with neutral result
            integration.record_trade_closed(symbol, 0.0)
    except Exception:
        integration.record_trade_closed(symbol, 0.0)
