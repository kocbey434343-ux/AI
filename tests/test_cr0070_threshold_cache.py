"""
Tests for CR-0070: Threshold overrides caching system
"""

import json
import os
import tempfile
import time
import unittest
from unittest.mock import patch

from src.utils.threshold_cache import (
    ThresholdCache,
    get_cached_threshold, set_threshold_override,
    get_threshold_statistics
)


class TestThresholdCache(unittest.TestCase):

    def setUp(self):
        """Set up test environment"""
        self.temp_dir = tempfile.mkdtemp()
        self.override_file = os.path.join(self.temp_dir, "test_overrides.json")

        # Mock Settings values
        self.mock_settings_patcher = patch('src.utils.threshold_cache.Settings')
        self.mock_settings = self.mock_settings_patcher.start()
        self.mock_settings.BUY_SIGNAL_THRESHOLD = 75.0
        self.mock_settings.SELL_SIGNAL_THRESHOLD = 25.0
        self.mock_settings.BUY_EXIT_THRESHOLD = 70.0
        self.mock_settings.SELL_EXIT_THRESHOLD = 30.0

        # Create cache instance
        self.cache = ThresholdCache(
            override_file=self.override_file,
            default_ttl=10,
            max_history=100
        )

    def tearDown(self):
        """Clean up after tests"""
        self.mock_settings_patcher.stop()

        # Clean up temp files
        if os.path.exists(self.override_file):
            os.remove(self.override_file)
        os.rmdir(self.temp_dir)

    def test_cache_initialization(self):
        """Test cache initializes with Settings values"""
        self.assertEqual(self.cache.get_threshold('BUY_SIGNAL_THRESHOLD'), 75.0)
        self.assertEqual(self.cache.get_threshold('SELL_SIGNAL_THRESHOLD'), 25.0)
        self.assertEqual(self.cache.get_threshold('BUY_EXIT_THRESHOLD'), 70.0)
        self.assertEqual(self.cache.get_threshold('SELL_EXIT_THRESHOLD'), 30.0)

    def test_cache_hit_performance(self):
        """Test cache hit performance"""
        # First access (cache miss)
        value1 = self.cache.get_threshold('BUY_SIGNAL_THRESHOLD')

        # Second access (cache hit)
        value2 = self.cache.get_threshold('BUY_SIGNAL_THRESHOLD')

        self.assertEqual(value1, value2)

        stats = self.cache.get_statistics()
        self.assertGreater(stats['cache_hits'], 0)
        self.assertGreater(stats['hit_rate_percent'], 0)

    def test_override_functionality(self):
        """Test threshold override operations"""
        original_value = self.cache.get_threshold('BUY_SIGNAL_THRESHOLD')

        # Set override
        new_value = 80.0
        self.cache.set_override('BUY_SIGNAL_THRESHOLD', new_value, reason="test_override")

        # Check override applied
        self.assertEqual(self.cache.get_threshold('BUY_SIGNAL_THRESHOLD'), new_value)

        # Check history recorded
        history = self.cache.get_history('BUY_SIGNAL_THRESHOLD', limit=1)
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]['old_value'], original_value)
        self.assertEqual(history[0]['new_value'], new_value)
        self.assertEqual(history[0]['reason'], "test_override")

    def test_override_persistence(self):
        """Test override persistence to JSON file"""
        # Set override
        self.cache.set_override('BUY_SIGNAL_THRESHOLD', 80.0, persist=True)

        # Check file created
        self.assertTrue(os.path.exists(self.override_file))

        # Check file contents
        with open(self.override_file, 'r') as f:
            data = json.load(f)
            self.assertEqual(data['BUY_SIGNAL_THRESHOLD'], 80.0)

        # Create new cache instance - should load overrides
        new_cache = ThresholdCache(
            override_file=self.override_file,
            default_ttl=10
        )
        self.assertEqual(new_cache.get_threshold('BUY_SIGNAL_THRESHOLD'), 80.0)

    def test_override_removal(self):
        """Test removing overrides"""
        # Set override
        self.cache.set_override('BUY_SIGNAL_THRESHOLD', 80.0)
        self.assertEqual(self.cache.get_threshold('BUY_SIGNAL_THRESHOLD'), 80.0)

        # Remove override
        self.cache.remove_override('BUY_SIGNAL_THRESHOLD')

        # Should revert to Settings value
        self.assertEqual(self.cache.get_threshold('BUY_SIGNAL_THRESHOLD'), 75.0)

        # Check history
        history = self.cache.get_history('BUY_SIGNAL_THRESHOLD')
        revert_entry = next((h for h in history if h['source'] == 'revert'), None)
        self.assertIsNotNone(revert_entry)
        if revert_entry:
            self.assertEqual(revert_entry['reason'], "override_removed")

    def test_cache_expiration_and_refresh(self):
        """Test cache TTL expiration and refresh"""
        # Create cache with short TTL
        cache = ThresholdCache(
            override_file=self.override_file,
            default_ttl=0.1,  # 100ms
            max_history=100
        )

        # Get initial value
        value1 = cache.get_threshold('BUY_SIGNAL_THRESHOLD')

        # Wait for expiration
        time.sleep(0.2)

        # Change Settings value
        self.mock_settings.BUY_SIGNAL_THRESHOLD = 85.0

        # Get value again - should refresh from Settings
        value2 = cache.get_threshold('BUY_SIGNAL_THRESHOLD')

        self.assertEqual(value1, 75.0)
        self.assertEqual(value2, 85.0)

    def test_cache_invalidation(self):
        """Test manual cache invalidation"""
        # Get initial value
        self.cache.get_threshold('BUY_SIGNAL_THRESHOLD')

        # Change Settings value
        self.mock_settings.BUY_SIGNAL_THRESHOLD = 85.0

        # Invalidate cache
        self.cache.invalidate_cache('BUY_SIGNAL_THRESHOLD')

        # Should get new value
        value = self.cache.get_threshold('BUY_SIGNAL_THRESHOLD')
        self.assertEqual(value, 85.0)

    def test_unknown_threshold_error(self):
        """Test error handling for unknown thresholds"""
        # Remove the threshold from Settings mock to trigger error
        if hasattr(self.mock_settings, 'UNKNOWN_THRESHOLD'):
            delattr(self.mock_settings, 'UNKNOWN_THRESHOLD')

        with self.assertRaises(ValueError) as cm:
            self.cache.get_threshold('UNKNOWN_THRESHOLD')

        self.assertIn("Unknown threshold", str(cm.exception))

    def test_cache_statistics(self):
        """Test cache statistics reporting"""
        # Generate some cache activity
        self.cache.get_threshold('BUY_SIGNAL_THRESHOLD')  # miss
        self.cache.get_threshold('BUY_SIGNAL_THRESHOLD')  # hit
        self.cache.set_override('SELL_SIGNAL_THRESHOLD', 20.0)

        stats = self.cache.get_statistics()

        self.assertIn('cache_hits', stats)
        self.assertIn('cache_misses', stats)
        self.assertIn('hit_rate_percent', stats)
        self.assertIn('override_sets', stats)
        self.assertGreater(stats['cache_hits'], 0)
        self.assertGreater(stats['override_sets'], 0)

    def test_cache_status_detailed(self):
        """Test detailed cache status reporting"""
        # Set an override
        self.cache.set_override('BUY_SIGNAL_THRESHOLD', 80.0)

        status = self.cache.get_cache_status()

        self.assertIn('BUY_SIGNAL_THRESHOLD', status)
        entry = status['BUY_SIGNAL_THRESHOLD']

        self.assertEqual(entry['value'], 80.0)
        self.assertEqual(entry['source'], 'override')
        self.assertTrue(entry['has_override'])
        self.assertFalse(entry['expired'])
        self.assertIn('age_seconds', entry)

    def test_history_tracking(self):
        """Test comprehensive history tracking"""
        # Multiple changes
        self.cache.set_override('BUY_SIGNAL_THRESHOLD', 80.0, reason="first_change")
        time.sleep(0.01)  # Ensure different timestamps
        self.cache.set_override('BUY_SIGNAL_THRESHOLD', 85.0, reason="second_change")
        time.sleep(0.01)
        self.cache.remove_override('BUY_SIGNAL_THRESHOLD')

        # Check history
        history = self.cache.get_history('BUY_SIGNAL_THRESHOLD')
        self.assertEqual(len(history), 3)

        # Should be in reverse chronological order
        self.assertEqual(history[0]['source'], 'revert')
        self.assertEqual(history[1]['new_value'], 85.0)
        self.assertEqual(history[2]['new_value'], 80.0)

    def test_thread_safety_simulation(self):
        """Test basic thread safety (simulation)"""
        import threading

        results = []

        def worker():
            for i in range(10):
                value = self.cache.get_threshold('BUY_SIGNAL_THRESHOLD')
                results.append(value)
                if i % 3 == 0:
                    self.cache.set_override('BUY_SIGNAL_THRESHOLD', 80.0 + i)

        threads = [threading.Thread(target=worker) for _ in range(3)]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Should complete without errors
        self.assertGreater(len(results), 0)


class TestConvenienceFunctions(unittest.TestCase):

    def setUp(self):
        """Set up test environment"""
        # Mock Settings
        self.mock_settings_patcher = patch('src.utils.threshold_cache.Settings')
        self.mock_settings = self.mock_settings_patcher.start()
        self.mock_settings.BUY_SIGNAL_THRESHOLD = 75.0

        # Reset global cache state and clean override file
        import src.utils.threshold_cache as tc
        tc._threshold_cache = None

        # Clean override file if exists
        override_file = "data/param_overrides.json"
        if os.path.exists(override_file):
            os.remove(override_file)

    def tearDown(self):
        """Clean up after tests"""
        self.mock_settings_patcher.stop()

    def test_convenience_functions(self):
        """Test convenience functions work correctly"""
        # Test cached threshold access
        value = get_cached_threshold('BUY_SIGNAL_THRESHOLD')
        self.assertEqual(value, 75.0)

        # Test override setting
        set_threshold_override('BUY_SIGNAL_THRESHOLD', 80.0, reason="test")
        value = get_cached_threshold('BUY_SIGNAL_THRESHOLD')
        self.assertEqual(value, 80.0)

        # Test statistics
        stats = get_threshold_statistics()
        self.assertIn('cache_hits', stats)


class TestPerformance(unittest.TestCase):
    """Performance tests for caching system"""

    def setUp(self):
        """Set up performance test environment"""
        self.mock_settings_patcher = patch('utils.threshold_cache.Settings')
        self.mock_settings = self.mock_settings_patcher.start()
        self.mock_settings.BUY_SIGNAL_THRESHOLD = 75.0

        self.cache = ThresholdCache(
            override_file="/tmp/test_perf.json",
            default_ttl=300
        )

    def tearDown(self):
        """Clean up performance tests"""
        self.mock_settings_patcher.stop()

    def test_lookup_performance(self):
        """Test threshold lookup performance"""
        # Warm up cache
        self.cache.get_threshold('BUY_SIGNAL_THRESHOLD')

        # Time multiple lookups
        start_time = time.time()
        for _ in range(1000):
            self.cache.get_threshold('BUY_SIGNAL_THRESHOLD')
        end_time = time.time()

        # Performance target: < 1ms per lookup on average
        avg_time_ms = (end_time - start_time) * 1000 / 1000
        self.assertLess(avg_time_ms, 1.0, f"Average lookup time {avg_time_ms}ms exceeds 1ms target")

    def test_override_performance(self):
        """Test override setting performance"""
        start_time = time.time()
        for i in range(100):
            self.cache.set_override('BUY_SIGNAL_THRESHOLD', 75.0 + i, persist=False)
        end_time = time.time()

        # Performance target: < 10ms per override on average
        avg_time_ms = (end_time - start_time) * 1000 / 100
        self.assertLess(avg_time_ms, 10.0, f"Average override time {avg_time_ms}ms exceeds 10ms target")


if __name__ == '__main__':
    unittest.main()
