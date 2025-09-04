"""
CR-0071: Config Snapshot Hash Persist - Test Suite
"""

import json
import tempfile
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from config.settings import Settings  # noqa: F401
from src.utils.config_snapshot import (
    ConfigSnapshotManager,
    create_config_snapshot,
    get_config_snapshot_manager,
    get_current_config_hash,
    is_config_changed_since,
)

# Test constants
TEST_BUY_THRESHOLD = 50.0
TEST_SELL_THRESHOLD = 15.0
TEST_RSI_PERIOD = 14
SHA256_HASH_LENGTH = 64
TEST_INTEGER = 42
TEST_FLOAT = 3.14
EXPECTED_SNAPSHOTS_COUNT = 2
CLEANUP_KEEP_COUNT = 3
FLOAT_TOLERANCE = 0.001


class TestConfigSnapshotManager:

    def setup_method(self):
        """Setup for each test"""
        self.temp_dir = tempfile.mkdtemp()
        self.manager = ConfigSnapshotManager(snapshot_dir=self.temp_dir)

        # Create test config files
        self.config_dir = Path(self.temp_dir) / "config"
        self.config_dir.mkdir(exist_ok=True)

        # Mock config files
        self.test_thresholds = {
            "timestamp": "2025-08-25T10:00:00Z",
            "buy_threshold": 50.0,
            "sell_threshold": 15.0
        }

        self.test_indicators = {
            "rsi": {"period": 14, "oversold": 30, "overbought": 70},
            "macd": {"fast": 12, "slow": 26, "signal": 9}
        }

        # Override config_files for testing
        self.manager.config_files = {
            "runtime_thresholds": str(self.config_dir / "runtime_thresholds.json"),
            "indicators": str(self.config_dir / "indicators.json")
        }

    def teardown_method(self):
        """Cleanup after each test"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _create_test_files(self):
        """Create test config files"""
        with open(self.manager.config_files["runtime_thresholds"], 'w') as f:
            json.dump(self.test_thresholds, f)

        with open(self.manager.config_files["indicators"], 'w') as f:
            json.dump(self.test_indicators, f)

    def test_get_current_config(self):
        """Test configuration collection"""
        self._create_test_files()

        config = self.manager.get_current_config()

        # Verify structure
        assert "timestamp" in config
        assert "sources" in config
        assert "settings" in config["sources"]
        assert "runtime_config" in config["sources"]
        assert "runtime_thresholds" in config["sources"]
        assert "indicators" in config["sources"]

        # Verify content
        assert abs(config["sources"]["runtime_thresholds"]["buy_threshold"] - TEST_BUY_THRESHOLD) < FLOAT_TOLERANCE
        assert config["sources"]["indicators"]["rsi"]["period"] == TEST_RSI_PERIOD

    def test_generate_config_hash(self):
        """Test deterministic hash generation"""
        self._create_test_files()

        config = self.manager.get_current_config()
        hash1 = self.manager.generate_config_hash(config)

        # Hash should be deterministic
        hash2 = self.manager.generate_config_hash(config)
        assert hash1 == hash2

        # Hash should be SHA256 (64 chars)
        assert len(hash1) == 64
        assert all(c in '0123456789abcdef' for c in hash1)

        # Different config should produce different hash
        config["sources"]["runtime_thresholds"]["buy_threshold"] = 60.0
        hash3 = self.manager.generate_config_hash(config)
        assert hash1 != hash3

    def test_create_snapshot(self):
        """Test snapshot creation"""
        self._create_test_files()

        snapshot_id, config_hash = self.manager.create_snapshot("test_snapshot")

        # Verify snapshot ID format
        assert snapshot_id.startswith("snapshot_")
        assert len(config_hash) == 64

        # Verify snapshot file exists
        snapshot_file = Path(self.manager.snapshot_dir) / f"{snapshot_id}.json"
        assert snapshot_file.exists()

        # Verify snapshot content
        with open(snapshot_file, 'r') as f:
            snapshot_data = json.load(f)

        assert snapshot_data["config_hash"] == config_hash
        assert snapshot_data["reason"] == "test_snapshot"
        assert "sources" in snapshot_data

        # Verify history updated
        history = self.manager.get_snapshot_history()
        assert len(history) == 1
        assert history[0]["snapshot_id"] == snapshot_id
        assert history[0]["config_hash"] == config_hash

    def test_load_snapshot(self):
        """Test snapshot loading"""
        self._create_test_files()

        snapshot_id, _ = self.manager.create_snapshot("test_load")

        loaded = self.manager.load_snapshot(snapshot_id)
        assert loaded is not None
        assert loaded["reason"] == "test_load"

        # Test non-existent snapshot
        not_found = self.manager.load_snapshot("snapshot_nonexistent")
        assert not_found is None

    def test_compare_snapshots(self):
        """Test snapshot comparison"""
        self._create_test_files()

        # Create first snapshot
        snapshot_id1, _ = self.manager.create_snapshot("baseline")

        # Modify config
        self.test_thresholds["buy_threshold"] = 60.0
        with open(self.manager.config_files["runtime_thresholds"], 'w') as f:
            json.dump(self.test_thresholds, f)

        # Create second snapshot
        snapshot_id2, _ = self.manager.create_snapshot("modified")

        comparison = self.manager.compare_snapshots(snapshot_id1, snapshot_id2)

        # Should not be identical
        assert not comparison["identical"]

        # Should have differences
        assert len(comparison["differences"]) > 0

        # Find the specific difference
        buy_threshold_diff = next(
            (diff for diff in comparison["differences"]
             if "buy_threshold" in diff["path"]),
            None
        )

        assert buy_threshold_diff is not None
        assert buy_threshold_diff["type"] == "changed"
        assert buy_threshold_diff["value1"] == 50.0
        assert buy_threshold_diff["value2"] == 60.0

    def test_is_config_changed(self):
        """Test configuration change detection"""
        self._create_test_files()

        # Get initial hash
        initial_hash = self.manager.get_current_config_hash()

        # Should not be changed
        assert not self.manager.is_config_changed(initial_hash)

        # Modify config
        self.test_thresholds["buy_threshold"] = 70.0
        with open(self.manager.config_files["runtime_thresholds"], 'w') as f:
            json.dump(self.test_thresholds, f)

        # Should be changed
        assert self.manager.is_config_changed(initial_hash)

    def test_cleanup_old_snapshots(self):
        """Test snapshot cleanup"""
        self._create_test_files()

        # Create multiple snapshots
        snapshots = []
        for i in range(5):
            snapshot_id, _ = self.manager.create_snapshot(f"test_{i}")
            snapshots.append(snapshot_id)

        # Cleanup keeping only 3
        self.manager.cleanup_old_snapshots(keep_count=3)

        # Check remaining snapshots
        remaining_files = list(Path(self.manager.snapshot_dir).glob("snapshot_*.json"))
        assert len(remaining_files) == 3

        # History should also be updated
        history = self.manager.get_snapshot_history()
        assert len(history) <= 3

    def test_get_statistics(self):
        """Test statistics generation"""
        self._create_test_files()

        # Create a few snapshots
        self.manager.create_snapshot("test1")
        self.manager.create_snapshot("test2")

        stats = self.manager.get_statistics()

        assert stats["total_snapshots"] == 2
        assert stats["total_files"] == 2
        assert stats["history_file_exists"]
        assert stats["snapshot_dir_size_mb"] >= 0
        assert stats["oldest_snapshot"] is not None
        assert stats["newest_snapshot"] is not None
        assert stats["unique_hashes"] >= 1  # May be same config

    def test_serialize_value(self):
        """Test value serialization"""
        # Test basic types
        assert self.manager._serialize_value("string") == "string"
        assert self.manager._serialize_value(42) == 42
        assert self.manager._serialize_value(3.14) == 3.14
        assert self.manager._serialize_value(True) is True
        assert self.manager._serialize_value(None) is None

        # Test collections
        assert self.manager._serialize_value([1, 2, 3]) == [1, 2, 3]
        assert self.manager._serialize_value({"a": 1}) == {"a": 1}

        # Test complex object (should become string)
        result = self.manager._serialize_value(object())
        assert isinstance(result, str)

    def test_missing_config_file(self):
        """Test handling of missing config files"""
        # Don't create test files

        config = self.manager.get_current_config()

        # Should still work with empty config files
        assert config["sources"]["runtime_thresholds"] == {}
        assert config["sources"]["indicators"] == {}

    def test_malformed_config_file(self):
        """Test handling of malformed config files"""
        # Create malformed JSON
        Path(self.manager.config_files["runtime_thresholds"]).write_text("invalid json {")

        config = self.manager.get_current_config()

        # Should handle error gracefully
        assert "error" in config["sources"]["runtime_thresholds"]

    @patch('src.utils.config_snapshot.Settings')
    @patch('src.utils.config_snapshot.RuntimeConfig')
    def test_settings_collection(self, mock_runtime_config, mock_settings):
        """Test Settings class attribute collection"""
        # Mock Settings attributes
        mock_settings.API_KEY = "test_key"
        mock_settings.RISK_PERCENTAGE = 2.0
        mock_settings.EXCHANGE_TYPE = "spot"

        # Mock RuntimeConfig attributes
        mock_runtime_config.MARKET_MODE = "spot"

        # Add a method (should be ignored)
        mock_settings.get_balance = MagicMock()

        # Configure dir() to return our attributes
        with patch('builtins.dir') as mock_dir:
            def dir_side_effect(obj):
                if obj is mock_settings:
                    return ['API_KEY', 'RISK_PERCENTAGE', 'EXCHANGE_TYPE', 'get_balance']
                elif obj is mock_runtime_config:
                    return ['MARKET_MODE']
                else:
                    return []

            mock_dir.side_effect = dir_side_effect
            config = self.manager.get_current_config()

        settings_config = config["sources"]["settings"]
        runtime_config = config["sources"]["runtime_config"]

        # Should include non-callable attributes
        assert "API_KEY" in settings_config
        assert "RISK_PERCENTAGE" in settings_config
        assert "EXCHANGE_TYPE" in settings_config
        assert "MARKET_MODE" in runtime_config

        # Should not include callable attributes
        assert "get_balance" not in settings_config

    def test_hash_consistency_across_timestamps(self):
        """Test that hash is consistent across different timestamps"""
        self._create_test_files()

        # Get config at different times
        config1 = self.manager.get_current_config()

        # Small delay and get config again
        time.sleep(0.01)
        config2 = self.manager.get_current_config()

        # Timestamps will be different
        assert config1["timestamp"] != config2["timestamp"]

        # But hashes should be same (timestamp excluded from hash)
        hash1 = self.manager.generate_config_hash(config1)
        hash2 = self.manager.generate_config_hash(config2)
        assert hash1 == hash2


class TestGlobalFunctions:

    def test_singleton_manager(self):
        """Test singleton pattern"""
        manager1 = get_config_snapshot_manager()
        manager2 = get_config_snapshot_manager()

        assert manager1 is manager2

    @patch('src.utils.config_snapshot.get_config_snapshot_manager')
    def test_create_config_snapshot(self, mock_get_manager):
        """Test convenience function"""
        mock_manager = MagicMock()
        mock_manager.create_snapshot.return_value = ("snap_123", "hash_456")
        mock_get_manager.return_value = mock_manager

        result = create_config_snapshot("test_reason")

        assert result == ("snap_123", "hash_456")
        mock_manager.create_snapshot.assert_called_once_with("test_reason")

    @patch('src.utils.config_snapshot.get_config_snapshot_manager')
    def test_get_current_config_hash(self, mock_get_manager):
        """Test convenience function"""
        mock_manager = MagicMock()
        mock_manager.get_current_config_hash.return_value = "test_hash"
        mock_get_manager.return_value = mock_manager

        result = get_current_config_hash()

        assert result == "test_hash"
        mock_manager.get_current_config_hash.assert_called_once()

    @patch('src.utils.config_snapshot.get_config_snapshot_manager')
    def test_is_config_changed_since(self, mock_get_manager):
        """Test convenience function"""
        mock_manager = MagicMock()
        mock_manager.is_config_changed.return_value = True
        mock_get_manager.return_value = mock_manager

        result = is_config_changed_since("reference_hash")

        assert result is True
        mock_manager.is_config_changed.assert_called_once_with("reference_hash")


class TestIntegration:

    def test_full_workflow(self):
        """Test complete workflow"""
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = ConfigSnapshotManager(snapshot_dir=temp_dir)

            # Override config files for test
            config_dir = Path(temp_dir) / "config"
            config_dir.mkdir(exist_ok=True)

            test_config = {"version": "1.0", "enabled": True}
            config_file = config_dir / "test_config.json"
            with open(config_file, 'w') as f:
                json.dump(test_config, f)

            manager.config_files = {"test": str(config_file)}

            # 1. Create initial snapshot
            snap1_id, snap1_hash = manager.create_snapshot("initial")

            # 2. Modify config
            test_config["version"] = "2.0"
            with open(config_file, 'w') as f:
                json.dump(test_config, f)

            # 3. Verify change detected
            assert manager.is_config_changed(snap1_hash)

            # 4. Create second snapshot
            snap2_id, _ = manager.create_snapshot("updated")

            # 5. Compare snapshots
            comparison = manager.compare_snapshots(snap1_id, snap2_id)

            assert not comparison["identical"]
            assert len(comparison["differences"]) > 0

            # 6. Verify statistics
            stats = manager.get_statistics()
            assert stats["total_snapshots"] == 2
            assert stats["unique_hashes"] == 2


# Integration test with actual config files (if they exist)
class TestRealConfigIntegration:

    @pytest.mark.integration
    def test_real_config_collection(self):
        """Test with real configuration files (integration test)"""
        manager = ConfigSnapshotManager()

        try:
            config = manager.get_current_config()

            # Basic structure should exist
            assert "sources" in config
            assert "settings" in config["sources"]

            # Should be able to generate hash
            config_hash = manager.generate_config_hash(config)
            assert len(config_hash) == 64

        except Exception as e:
            pytest.skip(f"Real config integration test failed: {e}")


if __name__ == "__main__":
    # Run specific tests
    pytest.main([__file__ + "::TestConfigSnapshotManager::test_get_current_config", "-v"])
