"""API health and clock skew checks."""

# ruff: noqa: I001  # import order noise across vendor/local modules

import time

from binance.enums import ORDER_TYPE_MARKET, SIDE_BUY
from binance.exceptions import BinanceAPIException

from config.settings import Settings
from src.api.binance_api import BinanceAPI
from src.utils.prometheus_export import get_exporter_instance
from src.utils.structured_log import slog

# Binance error code for invalid key/permissions
_ERR_PERM_DENIED = -2015

_SLOW_CONN_WARN_SEC = 5.0  # warn if serverTime request slower than this
# If serverTime looks like seconds since epoch (< cutoff), convert to ms
_SECONDS_TO_MS_CUTOFF_MS = 100_000_000_000.0  # 1e11 ms (~1973), well below any realistic current epoch in ms


class HealthChecker:
    def __init__(self):
        self.api = BinanceAPI()
        self.last_check = None
        self.is_healthy = True

    def check_connection(self):
        """Check API connectivity by calling server time and measuring latency."""
        try:
            start_time = time.time()
            self.api.get_server_time()
            response_time = time.time() - start_time

            # Warn on slow connection
            if response_time > _SLOW_CONN_WARN_SEC:
                self.is_healthy = False
                return False, f"Slow connection: {response_time:.2f}s"

            self.is_healthy = True
            self.last_check = time.time()
            return True, "Connection healthy"

        except Exception as e:
            self.is_healthy = False
            return False, f"Connection error: {e!s}"

    def check_clock_skew(self):
        """Measure exchange-vs-local clock skew (ms) and evaluate against guard threshold."""
        try:
            server = self.api.get_server_time() or {}
            server_raw = server.get('serverTime')
            # Normalize server time to milliseconds (Binance is ms; be robust to seconds)
            try:
                server_ms = float(server_raw or 0.0)
            except (TypeError, ValueError):
                server_ms = 0.0
            # If value looks like seconds since epoch (~1e9), convert to ms
            if 0 < server_ms < _SECONDS_TO_MS_CUTOFF_MS:  # treat as seconds, convert to ms
                server_ms *= 1000.0
            local_ms = time.time() * 1000.0
            skew_ms = abs(server_ms - local_ms)

            # Prometheus metric: current skew
            exporter = None
            try:
                exporter = get_exporter_instance()
                if exporter:
                    exporter.record_clock_skew_ms(skew_ms)
            except Exception:
                exporter = None

            # Structured log: measurement
            slog('clock_skew_measure', skew_ms=round(skew_ms, 3), warn_ms=Settings.CLOCK_SKEW_WARN_MS, guard=Settings.CLOCK_SKEW_GUARD_ENABLED)

            if Settings.CLOCK_SKEW_GUARD_ENABLED and skew_ms > Settings.CLOCK_SKEW_WARN_MS:
                # Warning + metric
                try:
                    if exporter:
                        exporter.inc_clock_skew_alert()
                except Exception:
                    pass
                msg = f"Clock skew high: {skew_ms:.0f} ms (> {Settings.CLOCK_SKEW_WARN_MS} ms)"
                slog('clock_skew_alert', skew_ms=round(skew_ms, 3), severity='WARNING')
                return False, msg

            return True, f"Clock skew normal: {skew_ms:.0f} ms"
        except Exception as e:
            # Do not fail the overall health for measurement errors; log and continue
            slog('clock_skew_error', error=str(e))
            return True, f"Clock skew check failed: {e!s}"

    def check_api_permissions(self):
        """Check API permissions."""
        try:
            # Read permission check
            self.api.get_account_info()

            # If not in testnet, try a small dry-run order to check trade permission
            if not Settings.USE_TESTNET:
                try:
                    # This order should not execute; just permission check
                    self.api.place_order(
                        symbol="BTCUSDT",
                        side=SIDE_BUY,
                        order_type=ORDER_TYPE_MARKET,
                        quantity=0.001
                    )
                except Exception as e:
                    if "Permission denied" in str(e):
                        return False, "Trade permission missing"

            return True, "API permissions OK"

        except BinanceAPIException as be:
            # Binance error -2015: Invalid API-key, IP, or permissions for action.
            if getattr(be, 'code', None) == _ERR_PERM_DENIED:
                return False, "API permission error: -2015 (invalid key/IP, or missing trade/futures/spot permission)"
            return False, f"API permission error: {be}"
        except Exception as e:
            if '-2015' in str(e):
                return False, "API permission error: -2015 (auth/IP/permission issue)"
            return False, f"API permission error: {e!s}"

    def run_full_check(self):
        """Run full health check."""
        conn_ok, conn_msg = self.check_connection()
        skew_ok, skew_msg = self.check_clock_skew()
        perm_ok, perm_msg = self.check_api_permissions()

        if conn_ok and skew_ok and perm_ok:
            return True, "System healthy"
        errors = []
        if not conn_ok:
            errors.append(conn_msg)
        if not skew_ok:
            errors.append(skew_msg)
        if not perm_ok:
            errors.append(perm_msg)
        return False, " | ".join(errors)
