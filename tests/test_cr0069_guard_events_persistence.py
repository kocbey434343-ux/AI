"""Tests for CR-0069 Guard Events Persistence

Guard event recording and querying functionality tests.
"""
import json
import sqlite3
import tempfile
from pathlib import Path
from typing import Any, Dict

import pytest

from src.utils.guard_events import GuardEvent, GuardEventRecorder


class TestGuardEventRecorder:
    """Test guard event persistence functionality."""

    def test_init_creates_schema(self):
        """Test that initialization creates guard_events table."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
            db_path = tmp.name

        recorder = GuardEventRecorder(db_path)

        # Verify table exists
        with sqlite3.connect(db_path) as conn:
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='guard_events'"
            )
            assert cursor.fetchone() is not None

        Path(db_path).unlink()

    def test_record_simple_guard_event(self):
        """Test simple guard event recording."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
            db_path = tmp.name

        try:
            recorder = GuardEventRecorder(db_path)

            # Record simple event
            recorder.record_guard_event_simple("halt_flag", "Daily halt flag exists", "BTCUSDT")

            # Verify record exists
            with sqlite3.connect(db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute("SELECT * FROM guard_events")
                row = cursor.fetchone()

                assert row is not None
                assert row['guard'] == 'halt_flag'
                assert row['reason'] == 'Daily halt flag exists'
                assert row['symbol'] == 'BTCUSDT'
                assert row['severity'] == 'INFO'
                assert row['blocked'] == 1
        finally:
            # Force cleanup
            try:
                Path(db_path).unlink()
            except Exception:
                pass

    def test_record_complex_guard_event(self):
        """Test complex guard event with extra data."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
            db_path = tmp.name

        recorder = GuardEventRecorder(db_path)

        # Create complex event
        event = GuardEvent(
            guard="daily_loss",
            reason="Daily loss exceeded threshold",
            symbol="ETHUSDT",
            extra_data={"daily_pnl_pct": -5.2, "threshold": -5.0},
            severity="CRITICAL",
            blocked=True,
            session_id="session123"
        )

        recorder.record_guard_event(event)

        # Verify record with extra data
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("SELECT * FROM guard_events")
            row = cursor.fetchone()

            assert row is not None
            assert row['guard'] == 'daily_loss'
            assert row['symbol'] == 'ETHUSDT'
            assert row['severity'] == 'CRITICAL'
            assert row['session_id'] == 'session123'

            extra_data = json.loads(row['extra'])
            assert extra_data['daily_pnl_pct'] == -5.2
            assert extra_data['threshold'] == -5.0

        Path(db_path).unlink()

    def test_get_guard_events_filters(self):
        """Test guard event querying with filters."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
            db_path = tmp.name

        recorder = GuardEventRecorder(db_path)

        # Record multiple events
        events = [
            GuardEvent("halt_flag", "Halt active", "BTCUSDT"),
            GuardEvent("daily_loss", "Loss threshold", "ETHUSDT", severity="CRITICAL"),
            GuardEvent("correlation_block", "High correlation", "ADAUSDT"),
            GuardEvent("daily_loss", "Another loss", "BTCUSDT", severity="CRITICAL"),
        ]

        for event in events:
            recorder.record_guard_event(event)

        # Test guard filter
        daily_loss_events = recorder.get_guard_events(guard="daily_loss")
        assert len(daily_loss_events) == 2
        assert all(e['guard'] == 'daily_loss' for e in daily_loss_events)

        # Test symbol filter
        btc_events = recorder.get_guard_events(symbol="BTCUSDT")
        assert len(btc_events) == 2
        assert all(e['symbol'] == 'BTCUSDT' for e in btc_events)

        # Test combined filter
        btc_daily_events = recorder.get_guard_events(guard="daily_loss", symbol="BTCUSDT")
        assert len(btc_daily_events) == 1
        assert btc_daily_events[0]['guard'] == 'daily_loss'
        assert btc_daily_events[0]['symbol'] == 'BTCUSDT'

        Path(db_path).unlink()

    def test_get_guard_stats(self):
        """Test guard statistics generation."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
            db_path = tmp.name

        recorder = GuardEventRecorder(db_path)

        # Record events for stats
        events = [
            GuardEvent("halt_flag", "Halt 1", "BTCUSDT"),
            GuardEvent("halt_flag", "Halt 2", "ETHUSDT"),
            GuardEvent("daily_loss", "Loss", "ADAUSDT", severity="CRITICAL"),
            GuardEvent("correlation_block", "Correlation", "BTCUSDT"),
        ]

        for event in events:
            recorder.record_guard_event(event)

        stats = recorder.get_guard_stats()

        assert stats['total_events'] == 4
        assert stats['guard_counts']['halt_flag'] == 2
        assert stats['guard_counts']['daily_loss'] == 1
        assert stats['guard_counts']['correlation_block'] == 1

        # Top blocked symbols
        assert 'BTCUSDT' in stats['top_blocked_symbols']
        assert stats['top_blocked_symbols']['BTCUSDT'] == 2

        Path(db_path).unlink()

    def test_cleanup_old_events(self):
        """Test old event cleanup functionality."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
            db_path = tmp.name

        recorder = GuardEventRecorder(db_path)

        # Insert old events by manipulating timestamp
        with sqlite3.connect(db_path) as conn:
            # Insert old event (40 days ago)
            conn.execute("""
                INSERT INTO guard_events (ts, guard, reason, symbol)
                VALUES (datetime('now', '-40 days'), 'old_guard', 'Old event', 'BTCUSDT')
            """)
            # Insert recent event
            conn.execute("""
                INSERT INTO guard_events (ts, guard, reason, symbol)
                VALUES (datetime('now', '-1 days'), 'recent_guard', 'Recent event', 'ETHUSDT')
            """)

        # Verify both events exist
        all_events = recorder.get_guard_events(hours_back=24*50)  # 50 days
        assert len(all_events) == 2

        # Cleanup events older than 30 days
        deleted = recorder.cleanup_old_events(days_to_keep=30)
        assert deleted == 1

        # Verify only recent event remains
        remaining_events = recorder.get_guard_events(hours_back=24*50)
        assert len(remaining_events) == 1
        assert remaining_events[0]['guard'] == 'recent_guard'

        Path(db_path).unlink()

    def test_error_handling(self):
        """Test error handling in guard event recording."""
        # Test with invalid DB path
        recorder = GuardEventRecorder("/invalid/path/db.sqlite")

        # Should not raise exception, just log warning
        recorder.record_guard_event_simple("test", "test reason")

        # Queries should return empty results on error
        events = recorder.get_guard_events()
        assert events == []

        stats = recorder.get_guard_stats()
        assert 'error' in stats


class TestGuardEventIntegration:
    """Integration tests with TradeStore."""

    def test_trade_store_integration(self):
        """Test that TradeStore initializes GuardEventRecorder."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
            db_path = tmp.name

        # Import here to avoid circular dependencies in tests
        from src.utils.trade_store import TradeStore

        store = TradeStore(db_path)

        # Verify guard_events attribute exists
        assert hasattr(store, 'guard_events')
        assert isinstance(store, TradeStore)

        # Verify guard_events table was created
        with sqlite3.connect(db_path) as conn:
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='guard_events'"
            )
            assert cursor.fetchone() is not None

        store.close()
        Path(db_path).unlink()


# CR-0069 Acceptance Criteria Tests
class TestCR0069AcceptanceCriteria:
    """Tests for CR-0069 acceptance criteria."""

    def test_guard_event_persistence_working(self):
        """Acceptance: Guard events are persisted with structured data."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
            db_path = tmp.name

        recorder = GuardEventRecorder(db_path)

        # Test all guard types from SSoT
        guard_types = [
            "halt_flag", "daily_loss", "consecutive_losses",
            "outlier_bar", "low_volume", "max_positions",
            "correlation_block", "lookahead"
        ]

        for guard_type in guard_types:
            recorder.record_guard_event_simple(
                guard_type, f"Test {guard_type} reason", "TESTUSDT"
            )

        # Verify all events recorded
        all_events = recorder.get_guard_events(hours_back=24)
        assert len(all_events) == len(guard_types)

        recorded_guards = {event['guard'] for event in all_events}
        assert recorded_guards == set(guard_types)

        Path(db_path).unlink()

    def test_queryable_guard_events(self):
        """Acceptance: Guard events are queryable for analysis."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
            db_path = tmp.name

        recorder = GuardEventRecorder(db_path)

        # Record various events
        test_data = [
            ("daily_loss", "BTCUSDT", "CRITICAL"),
            ("daily_loss", "ETHUSDT", "CRITICAL"),
            ("correlation_block", "BTCUSDT", "WARNING"),
            ("outlier_bar", "ADAUSDT", "INFO"),
        ]

        for guard, symbol, severity in test_data:
            event = GuardEvent(
                guard=guard,
                reason=f"Test {guard}",
                symbol=symbol,
                severity=severity
            )
            recorder.record_guard_event(event)

        # Test various queries
        assert len(recorder.get_guard_events(guard="daily_loss")) == 2
        assert len(recorder.get_guard_events(symbol="BTCUSDT")) == 2
        assert len(recorder.get_guard_events(guard="daily_loss", symbol="BTCUSDT")) == 1

        # Test stats
        stats = recorder.get_guard_stats()
        assert stats['total_events'] == 4
        assert stats['guard_counts']['daily_loss'] == 2

        Path(db_path).unlink()

    def test_minimal_performance_impact(self):
        """Acceptance: Guard event recording has minimal performance impact."""
        import time

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
            db_path = tmp.name

        recorder = GuardEventRecorder(db_path)

        # Measure batch recording time
        start_time = time.perf_counter()

        for i in range(100):
            recorder.record_guard_event_simple(
                "test_guard", f"Test reason {i}", f"TEST{i}USDT"
            )

        elapsed = time.perf_counter() - start_time

        # Should complete 100 records in reasonable time (< 1 second)
        assert elapsed < 1.0, f"Guard event recording too slow: {elapsed:.3f}s for 100 events"

        # Verify all recorded
        events = recorder.get_guard_events(hours_back=24)
        assert len(events) == 100

        Path(db_path).unlink()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
