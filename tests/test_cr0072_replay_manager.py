"""
Test CR-0072: Determinism Replay Harness
Comprehensive test suite for replay manager functionality
"""

import json
import pytest
import tempfile
from pathlib import Path
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock

from src.utils.replay_manager import (
    ReplayManager, TradeDecision, ReplaySession,
    get_replay_manager, start_replay_recording, record_trade_decision,
    stop_replay_recording, replay_trading_session
)


class TestTradeDecision:
    """Test TradeDecision dataclass"""

    def test_trade_decision_creation(self):
        """Test basic TradeDecision creation"""
        decision = TradeDecision(
            timestamp="2024-01-01T12:00:00Z",
            symbol="BTCUSDT",
            signal={"score": 0.8, "trend": "up"},
            decision="OPEN",
            reason="Strong signal",
            context={"price": 45000.0, "volume": 1000}
        )

        assert decision.symbol == "BTCUSDT"
        assert decision.decision == "OPEN"
        assert decision.signal["score"] == 0.8
        assert decision.context["price"] == 45000.0
        assert decision.outcome is None

    def test_trade_decision_with_outcome(self):
        """Test TradeDecision with outcome"""
        decision = TradeDecision(
            timestamp="2024-01-01T12:00:00Z",
            symbol="ETHUSDT",
            signal={"score": 0.6},
            decision="CLOSE",
            reason="Take profit",
            context={},
            outcome={"filled": True, "fill_price": 3000.0}
        )

        assert decision.outcome["filled"] is True
        assert decision.outcome["fill_price"] == 3000.0


class TestReplaySession:
    """Test ReplaySession dataclass"""

    def test_replay_session_to_dict(self):
        """Test ReplaySession to_dict conversion"""
        decision1 = TradeDecision(
            timestamp="2024-01-01T12:00:00Z",
            symbol="BTCUSDT",
            signal={"score": 0.8},
            decision="OPEN",
            reason="Test",
            context={}
        )

        session = ReplaySession(
            session_id="test_session",
            start_time="2024-01-01T10:00:00Z",
            config_hash="abc123",
            decisions=[decision1],
            metadata={"test": True}
        )

        session_dict = session.to_dict()

        assert session_dict["session_id"] == "test_session"
        assert session_dict["config_hash"] == "abc123"
        assert len(session_dict["decisions"]) == 1
        assert session_dict["decisions"][0]["symbol"] == "BTCUSDT"
        assert session_dict["metadata"]["test"] is True


class TestReplayManager:
    """Test ReplayManager class"""

    def setup_method(self):
        """Setup test environment"""
        self.temp_dir = tempfile.mkdtemp()
        self.replay_manager = ReplayManager(self.temp_dir)

    def teardown_method(self):
        """Cleanup test environment"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_replay_manager_initialization(self):
        """Test ReplayManager initialization"""
        assert self.replay_manager.replay_dir == Path(self.temp_dir)
        assert self.replay_manager._recording is False
        assert self.replay_manager._current_session is None

        # Directory should be created
        assert Path(self.temp_dir).exists()

    @patch('src.utils.config_snapshot.get_current_config_hash')
    def test_start_recording_session(self, mock_config_hash):
        """Test starting a recording session"""
        mock_config_hash.return_value = "test_hash_12345"

        # Test auto session name
        session_id = self.replay_manager.start_recording_session()

        assert self.replay_manager._recording is True
        assert self.replay_manager._current_session is not None
        assert self.replay_manager._current_session.config_hash == "test_hash_12345"
        assert session_id.startswith("session_")

    @patch('src.utils.config_snapshot.get_current_config_hash')
    def test_start_custom_recording_session(self, mock_config_hash):
        """Test starting recording with custom name"""
        mock_config_hash.return_value = "test_hash_12345"

        session_id = self.replay_manager.start_recording_session("custom_test")

        assert "custom_test_" in session_id
        assert self.replay_manager._recording is True

    @patch('src.utils.config_snapshot.get_current_config_hash')
    def test_record_trade_decision(self, mock_config_hash):
        """Test recording trade decision"""
        mock_config_hash.return_value = "test_hash_12345"

        # Start session
        self.replay_manager.start_recording_session("test")

        # Record decision
        signal = {"score": 0.8, "trend": "bullish"}
        context = {"price": 50000.0, "volume": 1500}
        outcome = {"filled": True, "fill_price": 50100.0}

        success = self.replay_manager.record_trade_decision(
            symbol="BTCUSDT",
            signal=signal,
            decision="OPEN",
            reason="Strong bullish signal",
            context=context,
            outcome=outcome
        )

        assert success is True
        assert len(self.replay_manager._current_session.decisions) == 1

        decision = self.replay_manager._current_session.decisions[0]
        assert decision.symbol == "BTCUSDT"
        assert decision.decision == "OPEN"
        assert decision.signal["score"] == 0.8
        assert decision.context["price"] == 50000.0
        assert decision.outcome["filled"] is True

    def test_record_without_session(self):
        """Test recording without active session"""
        success = self.replay_manager.record_trade_decision(
            symbol="BTCUSDT",
            signal={"score": 0.5},
            decision="SKIP",
            reason="No active session"
        )

        assert success is False

    @patch('src.utils.config_snapshot.get_current_config_hash')
    def test_stop_recording_session(self, mock_config_hash):
        """Test stopping recording session"""
        mock_config_hash.return_value = "test_hash_12345"

        # Start and record some decisions
        session_id = self.replay_manager.start_recording_session("test")

        self.replay_manager.record_trade_decision(
            symbol="BTCUSDT",
            signal={"score": 0.8},
            decision="OPEN",
            reason="Test decision 1"
        )

        self.replay_manager.record_trade_decision(
            symbol="ETHUSDT",
            signal={"score": 0.3},
            decision="SKIP",
            reason="Weak signal"
        )

        # Stop session
        saved_session_id = self.replay_manager.stop_recording_session()

        assert saved_session_id == session_id
        assert self.replay_manager._recording is False
        assert self.replay_manager._current_session is None

        # Check file was created
        session_file = Path(self.temp_dir) / f"{session_id}.json"
        assert session_file.exists()

        # Load and verify content
        with open(session_file, 'r') as f:
            data = json.load(f)

        assert data["session_id"] == session_id
        assert data["config_hash"] == "test_hash_12345"
        assert len(data["decisions"]) == 2
        assert data["metadata"]["total_decisions"] == 2
        assert "decision_types" in data["metadata"]
        assert data["metadata"]["decision_types"]["OPEN"] == 1
        assert data["metadata"]["decision_types"]["SKIP"] == 1

    def test_stop_without_session(self):
        """Test stopping without active session"""
        result = self.replay_manager.stop_recording_session()
        assert result is None

    @patch('src.utils.config_snapshot.get_current_config_hash')
    def test_load_session(self, mock_config_hash):
        """Test loading session from disk"""
        mock_config_hash.return_value = "test_hash_12345"

        # Create and save session
        session_id = self.replay_manager.start_recording_session("load_test")
        self.replay_manager.record_trade_decision(
            symbol="ADAUSDT",
            signal={"score": 0.7},
            decision="OPEN",
            reason="Load test"
        )
        self.replay_manager.stop_recording_session()

        # Load session
        loaded_session = self.replay_manager.load_session(session_id)

        assert loaded_session is not None
        assert loaded_session.session_id == session_id
        assert loaded_session.config_hash == "test_hash_12345"
        assert len(loaded_session.decisions) == 1
        assert loaded_session.decisions[0].symbol == "ADAUSDT"

    def test_load_nonexistent_session(self):
        """Test loading non-existent session"""
        result = self.replay_manager.load_session("non_existent_session")
        assert result is None

    @patch('src.utils.config_snapshot.get_current_config_hash')
    def test_replay_session(self, mock_config_hash):
        """Test replaying a session"""
        mock_config_hash.return_value = "test_hash_12345"

        # Create session
        session_id = self.replay_manager.start_recording_session("replay_test")
        self.replay_manager.record_trade_decision(
            symbol="DOTUSDT",
            signal={"score": 0.9},
            decision="OPEN",
            reason="Replay test"
        )
        self.replay_manager.stop_recording_session()

        # Replay session
        result = self.replay_manager.replay_session(session_id)

        assert result["success"] is True
        assert result["session_id"] == session_id
        assert result["original_decisions"] == 1
        assert result["config_match"] is True
        assert result["determinism_verified"] is True
        assert len(result["validation_errors"]) == 0

    @patch('src.utils.config_snapshot.get_current_config_hash')
    def test_replay_config_mismatch(self, mock_config_hash):
        """Test replaying with config mismatch"""
        # Create session with one config
        mock_config_hash.return_value = "old_hash_12345"
        session_id = self.replay_manager.start_recording_session("mismatch_test")
        self.replay_manager.record_trade_decision(
            symbol="LINKUSDT",
            signal={"score": 0.6},
            decision="OPEN",
            reason="Mismatch test"
        )
        self.replay_manager.stop_recording_session()

        # Replay with different config
        mock_config_hash.return_value = "new_hash_67890"
        result = self.replay_manager.replay_session(session_id, verify_config=True)

        assert result["success"] is True
        assert result["config_match"] is False
        assert len(result["validation_errors"]) == 1
        assert result["validation_errors"][0]["type"] == "config_mismatch"

    def test_replay_nonexistent_session(self):
        """Test replaying non-existent session"""
        result = self.replay_manager.replay_session("non_existent")

        assert result["success"] is False
        assert "Session not found" in result["error"]

    @patch('src.utils.config_snapshot.get_current_config_hash')
    def test_get_session_list(self, mock_config_hash):
        """Test getting session list"""
        mock_config_hash.return_value = "test_hash_12345"

        # Create multiple sessions
        session1_id = self.replay_manager.start_recording_session("test1")
        self.replay_manager.record_trade_decision(
            symbol="BTCUSDT", signal={"score": 0.8},
            decision="OPEN", reason="Test 1"
        )
        self.replay_manager.stop_recording_session()

        session2_id = self.replay_manager.start_recording_session("test2")
        self.replay_manager.record_trade_decision(
            symbol="ETHUSDT", signal={"score": 0.7},
            decision="OPEN", reason="Test 2"
        )
        self.replay_manager.record_trade_decision(
            symbol="ETHUSDT", signal={"score": 0.2},
            decision="CLOSE", reason="Close test 2"
        )
        self.replay_manager.stop_recording_session()

        # Get session list
        sessions = self.replay_manager.get_session_list()

        assert len(sessions) == 2

        # Should be sorted by start_time descending (newest first)
        assert sessions[0]["session_id"] == session2_id  # More recent
        assert sessions[1]["session_id"] == session1_id

        # Check session details
        session2 = sessions[0]
        assert session2["total_decisions"] == 2
        assert session2["config_hash"] == "test_hash_12345"[:16]
        assert session2["file_size"] > 0

    @patch('src.utils.config_snapshot.get_current_config_hash')
    def test_generate_session_hash(self, mock_config_hash):
        """Test generating session hash"""
        mock_config_hash.return_value = "test_hash_12345"

        # Create session with specific decisions
        session_id = self.replay_manager.start_recording_session("hash_test")
        self.replay_manager.record_trade_decision(
            symbol="BTCUSDT",
            signal={"score": 0.8, "trend": "up"},
            decision="OPEN",
            reason="Hash test",
            context={"price": 50000}
        )
        self.replay_manager.record_trade_decision(
            symbol="ETHUSDT",
            signal={"score": 0.3},
            decision="SKIP",
            reason="Weak signal"
        )
        session = self.replay_manager._current_session
        self.replay_manager.stop_recording_session()

        # Generate hash
        hash1 = self.replay_manager.generate_session_hash(session)

        # Create identical session
        session_id2 = self.replay_manager.start_recording_session("hash_test2")
        self.replay_manager.record_trade_decision(
            symbol="BTCUSDT",
            signal={"score": 0.8, "trend": "up"},
            decision="OPEN",
            reason="Hash test",
            context={"price": 50000}
        )
        self.replay_manager.record_trade_decision(
            symbol="ETHUSDT",
            signal={"score": 0.3},
            decision="SKIP",
            reason="Weak signal"
        )
        session2 = self.replay_manager._current_session
        self.replay_manager.stop_recording_session()

        hash2 = self.replay_manager.generate_session_hash(session2)

        # Hashes should be identical (deterministic)
        assert hash1 == hash2
        assert len(hash1) == 64  # SHA256 hex length

    @patch('src.utils.config_snapshot.get_current_config_hash')
    def test_compare_sessions(self, mock_config_hash):
        """Test comparing two sessions"""
        mock_config_hash.return_value = "test_hash_12345"

        # Create two identical sessions
        session1_id = self.replay_manager.start_recording_session("compare1")
        self.replay_manager.record_trade_decision(
            symbol="BTCUSDT", signal={"score": 0.8},
            decision="OPEN", reason="Compare test"
        )
        self.replay_manager.stop_recording_session()

        session2_id = self.replay_manager.start_recording_session("compare2")
        self.replay_manager.record_trade_decision(
            symbol="BTCUSDT", signal={"score": 0.8},
            decision="OPEN", reason="Compare test"
        )
        self.replay_manager.stop_recording_session()

        # Compare sessions
        result = self.replay_manager.compare_sessions(session1_id, session2_id)

        assert result["success"] is True
        assert result["identical"] is True
        assert result["config_match"] is True
        assert result["session1"]["decisions"] == 1
        assert result["session2"]["decisions"] == 1

    @patch('src.utils.config_snapshot.get_current_config_hash')
    def test_compare_different_sessions(self, mock_config_hash):
        """Test comparing different sessions"""
        mock_config_hash.return_value = "test_hash_12345"

        # Create different sessions
        session1_id = self.replay_manager.start_recording_session("diff1")
        self.replay_manager.record_trade_decision(
            symbol="BTCUSDT", signal={"score": 0.8},
            decision="OPEN", reason="Different test 1"
        )
        self.replay_manager.stop_recording_session()

        session2_id = self.replay_manager.start_recording_session("diff2")
        self.replay_manager.record_trade_decision(
            symbol="ETHUSDT", signal={"score": 0.7},  # Different symbol and score
            decision="OPEN", reason="Different test 2"
        )
        self.replay_manager.stop_recording_session()

        # Compare sessions
        result = self.replay_manager.compare_sessions(session1_id, session2_id)

        assert result["success"] is True
        assert result["identical"] is False  # Should be different
        assert result["config_match"] is True  # Same config hash

    @patch('src.utils.config_snapshot.get_current_config_hash')
    def test_statistics(self, mock_config_hash):
        """Test getting statistics"""
        mock_config_hash.return_value = "test_hash_12345"

        # Create some sessions
        session1_id = self.replay_manager.start_recording_session("stats1")
        self.replay_manager.record_trade_decision(
            symbol="BTCUSDT", signal={"score": 0.8},
            decision="OPEN", reason="Stats test 1"
        )
        self.replay_manager.record_trade_decision(
            symbol="BTCUSDT", signal={"score": 0.2},
            decision="CLOSE", reason="Stats close 1"
        )
        self.replay_manager.stop_recording_session()

        session2_id = self.replay_manager.start_recording_session("stats2")
        self.replay_manager.record_trade_decision(
            symbol="ETHUSDT", signal={"score": 0.7},
            decision="OPEN", reason="Stats test 2"
        )
        # Keep session 2 active

        stats = self.replay_manager.get_statistics()

        assert stats["total_sessions"] == 1  # Only completed sessions
        assert stats["total_decisions"] == 2
        assert stats["recording_active"] is True
        assert stats["current_session_decisions"] == 1
        assert stats["replay_dir_size_mb"] > 0
        assert stats["newest_session"] is not None

    @patch('src.utils.config_snapshot.get_current_config_hash')
    def test_session_cleanup(self, mock_config_hash):
        """Test automatic session cleanup"""
        mock_config_hash.return_value = "test_hash_12345"

        # Create manager with small limit for testing
        original_max = ReplayManager.__dict__.get('MAX_REPLAY_SESSIONS', 50)

        # Temporarily set low limit
        with patch('src.utils.replay_manager.MAX_REPLAY_SESSIONS', 2):
            # Create 3 sessions (should trigger cleanup)
            for i in range(3):
                session_id = self.replay_manager.start_recording_session(f"cleanup_{i}")
                self.replay_manager.record_trade_decision(
                    symbol="BTCUSDT", signal={"score": 0.5},
                    decision="OPEN", reason=f"Cleanup test {i}"
                )
                self.replay_manager.stop_recording_session()

            # Should only have 2 sessions left (newest kept)
            sessions = self.replay_manager.get_session_list()
            assert len(sessions) <= 2

    def test_thread_safety_recording(self):
        """Test thread safety of recording operations"""
        import threading
        import time

        with patch('src.utils.config_snapshot.get_current_config_hash') as mock_config_hash:
            mock_config_hash.return_value = "test_hash_12345"

            # Start session
            session_id = self.replay_manager.start_recording_session("thread_test")

            # Define concurrent recording function
            def record_decisions(thread_id):
                for i in range(5):
                    self.replay_manager.record_trade_decision(
                        symbol=f"SYMBOL{thread_id}",
                        signal={"score": 0.5 + i * 0.1},
                        decision="OPEN",
                        reason=f"Thread {thread_id} decision {i}"
                    )
                    time.sleep(0.001)  # Small delay to encourage race conditions

            # Run concurrent threads
            threads = []
            for t_id in range(3):
                thread = threading.Thread(target=record_decisions, args=(t_id,))
                threads.append(thread)
                thread.start()

            # Wait for all threads
            for thread in threads:
                thread.join()

            # Stop session
            self.replay_manager.stop_recording_session()

            # Should have exactly 15 decisions (3 threads * 5 decisions each)
            loaded_session = self.replay_manager.load_session(session_id)
            assert loaded_session is not None
            assert len(loaded_session.decisions) == 15

            # Check we have decisions from all threads
            symbols = {d.symbol for d in loaded_session.decisions}
            assert len(symbols) == 3
            assert "SYMBOL0" in symbols
            assert "SYMBOL1" in symbols
            assert "SYMBOL2" in symbols


class TestGlobalFunctions:
    """Test global convenience functions"""

    def setup_method(self):
        """Setup test environment"""
        self.temp_dir = tempfile.mkdtemp()
        # Reset global instance
        import src.utils.replay_manager
        src.utils.replay_manager._replay_manager = None

    def teardown_method(self):
        """Cleanup test environment"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        # Reset global instance
        import src.utils.replay_manager
        src.utils.replay_manager._replay_manager = None

    @patch('src.utils.config_snapshot.get_current_config_hash')
    def test_global_functions_workflow(self, mock_config_hash):
        """Test complete workflow using global functions"""
        mock_config_hash.return_value = "global_test_hash"

        # Override replay manager directory for test
        with patch('src.utils.replay_manager.REPLAY_SESSION_DIR', self.temp_dir):
            # Start recording
            session_id = start_replay_recording("global_test")
            assert session_id is not None

            # Record some decisions
            success1 = record_trade_decision(
                symbol="BTCUSDT",
                signal={"score": 0.9, "trend": "bullish"},
                decision="OPEN",
                reason="Global function test",
                context={"price": 45000.0}
            )
            assert success1 is True

            success2 = record_trade_decision(
                symbol="ETHUSDT",
                signal={"score": 0.2},
                decision="SKIP",
                reason="Weak signal",
                outcome={"action": "no_action"}
            )
            assert success2 is True

            # Stop recording
            saved_session_id = stop_replay_recording()
            assert saved_session_id == session_id

            # Replay session
            result = replay_trading_session(session_id)
            assert result["success"] is True
            assert result["original_decisions"] == 2
            assert result["config_match"] is True

    def test_global_manager_singleton(self):
        """Test global manager is singleton"""
        # Override replay manager directory for test
        with patch('src.utils.replay_manager.REPLAY_SESSION_DIR', self.temp_dir):
            manager1 = get_replay_manager()
            manager2 = get_replay_manager()

            # Should be same instance
            assert manager1 is manager2


class TestReplayManagerEdgeCases:
    """Test edge cases and error conditions"""

    def setup_method(self):
        """Setup test environment"""
        self.temp_dir = tempfile.mkdtemp()
        self.replay_manager = ReplayManager(self.temp_dir)

    def teardown_method(self):
        """Cleanup test environment"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    @patch('src.utils.config_snapshot.get_current_config_hash')
    def test_empty_session(self, mock_config_hash):
        """Test session with no decisions"""
        mock_config_hash.return_value = "empty_hash"

        session_id = self.replay_manager.start_recording_session("empty")
        saved_session_id = self.replay_manager.stop_recording_session()

        assert saved_session_id == session_id

        # Load and verify
        loaded_session = self.replay_manager.load_session(session_id)
        assert loaded_session is not None
        assert len(loaded_session.decisions) == 0
        assert loaded_session.metadata["total_decisions"] == 0

    @patch('src.utils.config_snapshot.get_current_config_hash')
    def test_decision_with_none_values(self, mock_config_hash):
        """Test recording decision with None values"""
        mock_config_hash.return_value = "none_hash"

        self.replay_manager.start_recording_session("none_test")

        success = self.replay_manager.record_trade_decision(
            symbol="TESTUSDT",
            signal={"score": None, "trend": None},
            decision="SKIP",
            reason="None values test",
            context=None,
            outcome=None
        )

        assert success is True

        decision = self.replay_manager._current_session.decisions[0]
        assert decision.signal["score"] is None
        assert decision.context == {}
        assert decision.outcome is None

    @patch('src.utils.config_snapshot.get_current_config_hash')
    def test_large_signal_data(self, mock_config_hash):
        """Test recording decision with large signal data"""
        mock_config_hash.return_value = "large_hash"

        self.replay_manager.start_recording_session("large_test")

        # Create large signal data
        large_signal = {
            "indicators": {f"indicator_{i}": i * 0.1 for i in range(1000)},
            "ohlc_data": [{"o": i, "h": i+1, "l": i-1, "c": i+0.5} for i in range(100)],
            "metadata": {"data_size": "large", "timestamp": "2024-01-01T12:00:00Z"}
        }

        success = self.replay_manager.record_trade_decision(
            symbol="LARGEUSDT",
            signal=large_signal,
            decision="OPEN",
            reason="Large data test"
        )

        assert success is True

        # Stop and reload to test serialization
        session_id = self.replay_manager.stop_recording_session()
        loaded_session = self.replay_manager.load_session(session_id)

        assert loaded_session is not None
        assert len(loaded_session.decisions) == 1
        assert len(loaded_session.decisions[0].signal["indicators"]) == 1000
        assert len(loaded_session.decisions[0].signal["ohlc_data"]) == 100

    def test_corrupted_session_file(self):
        """Test loading corrupted session file"""
        # Create corrupted file
        corrupted_file = Path(self.temp_dir) / "corrupted_session.json"
        with open(corrupted_file, 'w') as f:
            f.write("{ invalid json content")

        result = self.replay_manager.load_session("corrupted_session")
        assert result is None

    @patch('src.utils.config_snapshot.get_current_config_hash')
    def test_concurrent_session_starts(self, mock_config_hash):
        """Test starting multiple sessions concurrently"""
        mock_config_hash.return_value = "concurrent_hash"

        # Start first session
        session1_id = self.replay_manager.start_recording_session("session1")
        assert self.replay_manager._recording is True

        # Start second session (should stop first)
        session2_id = self.replay_manager.start_recording_session("session2")
        assert self.replay_manager._recording is True
        assert session1_id != session2_id

        # Current session should be session2
        assert self.replay_manager._current_session.session_id == session2_id

    @patch('src.utils.config_snapshot.get_current_config_hash')
    def test_hash_consistency(self, mock_config_hash):
        """Test hash consistency across multiple generations"""
        mock_config_hash.return_value = "consistency_hash"

        # Create session with specific decisions
        session_id = self.replay_manager.start_recording_session("consistency")
        self.replay_manager.record_trade_decision(
            symbol="BTCUSDT",
            signal={"score": 0.8, "data": [1, 2, 3]},
            decision="OPEN",
            reason="Consistency test",
            context={"price": 50000, "volume": 1000}
        )
        session = self.replay_manager._current_session
        self.replay_manager.stop_recording_session()

        # Generate hash multiple times
        hash1 = self.replay_manager.generate_session_hash(session)
        hash2 = self.replay_manager.generate_session_hash(session)
        hash3 = self.replay_manager.generate_session_hash(session)

        # All hashes should be identical
        assert hash1 == hash2 == hash3
        assert len(hash1) == 64  # SHA256 hex


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
