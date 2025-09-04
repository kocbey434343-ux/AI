"""
Tests for CR-0064: Lookahead Bias Prevention

Test Coverage:
- Incomplete bar detection and rejection
- Closed bar acceptance
- Signal generation with lookahead protection
- Guard metrics and logging
- Edge cases (missing timestamps, malformed data)
"""
import pytest
import pandas as pd
from datetime import datetime, timedelta
import time
from unittest.mock import patch, MagicMock
import tempfile
import os

from src.utils.lookahead_guard import LookaheadGuard, get_lookahead_guard
from src.signal_generator import SignalGenerator
from config.settings import Settings


class TestLookaheadGuard:
    """Test core lookahead guard functionality"""

    def setup_method(self):
        """Setup fresh guard instance for each test"""
        self.guard = LookaheadGuard()

    def test_complete_bar_accepted(self):
        """Complete bar should be accepted for signals"""
        now = datetime.now()
        past_time = now - timedelta(minutes=5)

        signal_data = {
            'symbol': 'BTCUSDT',
            'timestamp': past_time.isoformat(),
            'close_price': 50000.0,
            'signal': 'BUY'
        }

        # Should pass validation
        result = self.guard.validate_signal_data(signal_data)
        assert result is True
        assert self.guard.violation_count == 0

    def test_incomplete_bar_rejected(self):
        """Current/incomplete bar should be rejected"""
        # Current time - this would be incomplete bar
        current_time = datetime.now()

        signal_data = {
            'symbol': 'BTCUSDT',
            'timestamp': current_time.isoformat(),
            'close_price': 50000.0,
            'signal': 'BUY'
        }

        result = self.guard.validate_signal_data(signal_data)
        assert result is False
        assert self.guard.violation_count == 1

    def test_violation_metrics_increment(self):
        """Violation metrics should increment properly"""
        current_time = datetime.now()

        signal_data = {
            'symbol': 'BTCUSDT',
            'timestamp': current_time.isoformat(),
            'signal': 'BUY'
        }

        # Multiple violations
        self.guard.validate_signal_data(signal_data)
        self.guard.validate_signal_data(signal_data)

        assert self.guard.violation_count == 2
        assert 'BTCUSDT' in self.guard.violations_by_symbol
        assert self.guard.violations_by_symbol['BTCUSDT'] == 2

    def test_missing_timestamp_rejected(self):
        """Signal without timestamp should be rejected"""
        signal_data = {
            'symbol': 'BTCUSDT',
            'close_price': 50000.0,
            'signal': 'BUY'
        }

        result = self.guard.validate_signal_data(signal_data)
        assert result is False

    def test_invalid_timestamp_format_rejected(self):
        """Signal with invalid timestamp format should be rejected"""
        signal_data = {
            'symbol': 'BTCUSDT',
            'timestamp': 'invalid-timestamp',
            'close_price': 50000.0,
            'signal': 'BUY'
        }

        result = self.guard.validate_signal_data(signal_data)
        assert result is False

    def test_grace_period_boundary(self):
        """Test grace period boundary conditions"""
        # Just outside grace period - should be accepted
        past_time = datetime.now() - timedelta(seconds=65)  # 65s ago

        signal_data = {
            'symbol': 'BTCUSDT',
            'timestamp': past_time.isoformat(),
            'close_price': 50000.0,
            'signal': 'BUY'
        }

        result = self.guard.validate_signal_data(signal_data)
        assert result is True

        # Just inside grace period - should be rejected
        recent_time = datetime.now() - timedelta(seconds=30)  # 30s ago

        signal_data['timestamp'] = recent_time.isoformat()
        result = self.guard.validate_signal_data(signal_data)
        assert result is False


class TestSignalGeneratorLookaheadIntegration:
    """Test lookahead guard integration with SignalGenerator"""

    def setup_method(self):
        """Setup test environment"""
        # Create temporary config for testing
        self.temp_dir = tempfile.mkdtemp()
        self.config_file = os.path.join(self.temp_dir, 'test_settings.py')

        # Mock settings
        self.settings = MagicMock(spec=Settings)
        self.settings.FEATURE_LOOKAHEAD_GUARD = True
        self.settings.LOOKAHEAD_GRACE_SECONDS = 60

    def teardown_method(self):
        """Cleanup"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    @patch('src.signal_generator.get_lookahead_guard')
    def test_signal_generation_with_current_bar_blocked(self, mock_guard_factory):
        """SignalGenerator should block signals from current bar"""
        # Setup mock guard that rejects current bar
        mock_guard = MagicMock()
        mock_guard.validate_signal_data.return_value = False
        mock_guard_factory.return_value = mock_guard

        # Mock data with current timestamp
        current_data = pd.DataFrame({
            'timestamp': [datetime.now()],
            'close': [50000.0],
            'volume': [1000.0],
            'high': [51000.0],
            'low': [49000.0],
            'open': [49500.0]
        })

        signal_gen = SignalGenerator()

        # Mock the indicator calculations
        with patch.object(signal_gen, '_calculate_indicators') as mock_calc:
            mock_calc.return_value = {
                'rsi': 70,
                'macd': 0.5,
                'bb_position': 0.8,
                'atr': 1000,
                'final_score': 0.7
            }

            # Generate signal - should be None due to lookahead guard
            signal = signal_gen.generate_pair_signal('BTCUSDT', current_data)

            # Verify guard was called
            mock_guard.validate_signal_data.assert_called_once()

            # Signal should be blocked
            assert signal is None or signal.get('signal') == 'HOLD'

    @patch('src.signal_generator.get_lookahead_guard')
    def test_signal_generation_with_historical_bar_allowed(self, mock_guard_factory):
        """SignalGenerator should allow signals from historical bars"""
        # Setup mock guard that accepts historical data
        mock_guard = MagicMock()
        mock_guard.validate_signal_data.return_value = True
        mock_guard_factory.return_value = mock_guard

        # Mock data with historical timestamp
        past_time = datetime.now() - timedelta(minutes=5)
        historical_data = pd.DataFrame({
            'timestamp': [past_time],
            'close': [50000.0],
            'volume': [1000.0],
            'high': [51000.0],
            'low': [49000.0],
            'open': [49500.0]
        })

        signal_gen = SignalGenerator()

        # Mock the indicator calculations to return BUY signal
        with patch.object(signal_gen, '_calculate_indicators') as mock_calc:
            mock_calc.return_value = {
                'rsi': 30,  # Oversold
                'macd': 0.5,
                'bb_position': 0.2,  # Lower band
                'atr': 1000,
                'final_score': 0.8  # Strong buy
            }

            # Generate signal - should be allowed
            signal = signal_gen.generate_pair_signal('BTCUSDT', historical_data)

            # Verify guard was called and passed
            mock_guard.validate_signal_data.assert_called_once()

            # Signal should be generated
            assert signal is not None
            assert signal.get('signal') in ['BUY', 'SELL']  # Not HOLD


class TestLookaheadGuardSingleton:
    """Test singleton pattern for guard instance"""

    def test_singleton_instance(self):
        """get_lookahead_guard should return same instance"""
        guard1 = get_lookahead_guard()
        guard2 = get_lookahead_guard()

        assert guard1 is guard2
        assert isinstance(guard1, LookaheadGuard)

    def test_singleton_state_persistence(self):
        """Singleton state should persist across calls"""
        guard1 = get_lookahead_guard()

        # Trigger violation
        current_time = datetime.now()
        signal_data = {
            'symbol': 'BTCUSDT',
            'timestamp': current_time.isoformat(),
            'signal': 'BUY'
        }
        guard1.validate_signal_data(signal_data)

        # Get guard again
        guard2 = get_lookahead_guard()

        # State should be preserved
        assert guard2.violation_count == 1
        assert 'BTCUSDT' in guard2.violations_by_symbol


class TestLookaheadEdgeCases:
    """Test edge cases and error conditions"""

    def test_none_signal_data(self):
        """None signal data should be rejected safely"""
        guard = LookaheadGuard()
        result = guard.validate_signal_data(None)
        assert result is False

    def test_empty_dict_signal_data(self):
        """Empty dict should be rejected"""
        guard = LookaheadGuard()
        result = guard.validate_signal_data({})
        assert result is False

    def test_timezone_aware_timestamps(self):
        """Should handle timezone-aware timestamps"""
        guard = LookaheadGuard()

        # Past time with timezone
        from datetime import timezone
        past_time = datetime.now(timezone.utc) - timedelta(minutes=5)

        signal_data = {
            'symbol': 'BTCUSDT',
            'timestamp': past_time.isoformat(),
            'close_price': 50000.0,
            'signal': 'BUY'
        }

        result = guard.validate_signal_data(signal_data)
        assert result is True

    def test_millisecond_precision_timestamps(self):
        """Should handle millisecond precision in timestamps"""
        guard = LookaheadGuard()

        # Past time with milliseconds
        past_time = datetime.now() - timedelta(minutes=2)
        timestamp_ms = past_time.isoformat() + '.123Z'

        signal_data = {
            'symbol': 'BTCUSDT',
            'timestamp': timestamp_ms,
            'close_price': 50000.0,
            'signal': 'BUY'
        }

        result = guard.validate_signal_data(signal_data)
        assert result is True


# Integration test with actual signal pipeline
class TestFullPipelineLookaheadIntegration:
    """End-to-end testing of lookahead guard in trading pipeline"""

    def test_pre_trade_pipeline_blocks_current_bar(self):
        """Full pipeline should block current bar signals"""
        # This would test the actual trader.guards.pre_trade_pipeline
        # integration when that's implemented
        pass  # TODO: Implement when pre_trade_pipeline integration is complete


if __name__ == '__main__':
    # Run basic tests
    pytest.main([__file__, '-v'])
