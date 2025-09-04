"""
Test suite for Reconciliation v2 (CR-0067)
"""
import time
from unittest.mock import MagicMock, Mock, patch

import pytest

from src.trader.core import Trader


class TestReconciliationV2:
    """Test reconciliation v2 features: orderId mapping, partial fill sync, performance"""

    # Test constants
    PERFORMANCE_TOLERANCE_S = 1.0  # Expected completion time with mocks
    SYNC_TOLERANCE = 0.01  # Float comparison tolerance
    EXPECTED_ORDER_MAP_COUNT = 2  # Expected orders with IDs
    E2E_PERFORMANCE_LIMIT_S = 2.0  # End-to-end performance limit

    @pytest.fixture
    def trader(self):
        """Create trader instance with mocked dependencies"""
        with patch.multiple(
            'src.trader.core',
            slog=MagicMock(),
        ):
            trader = Trader()
            trader.api = Mock()
            trader.positions = {}
            trader.logger = Mock()
            trader.state_manager = Mock()
            return trader

    def test_reconciliation_performance_boundary(self, trader):
        """Test reconciliation completes within 5s performance boundary (CR-0067 AC1)"""
        # Mock fast exchange responses
        trader.api.get_open_orders.return_value = []
        trader.api.get_positions.return_value = []

        start_time = time.time()
        trader._reconcile_open_orders()
        duration = time.time() - start_time

        # Should complete well under 5s with mocked API
        assert duration < self.PERFORMANCE_TOLERANCE_S, \
            f"Reconciliation took {duration:.2f}s, expected < {self.PERFORMANCE_TOLERANCE_S}s with mocks"
        trader.logger.info.assert_called()

    def test_reconciliation_performance_breach_logging(self, trader):
        """Test performance breach logging when > 5s (CR-0067 AC1)"""
        # Mock slow response by adding delay
        def slow_get_orders():
            time.sleep(0.1)  # Small delay to test timing logic
            return []

        trader.api.get_open_orders.side_effect = slow_get_orders
        trader.api.get_positions.return_value = []

        with patch('time.time') as mock_time:
            # Mock time to simulate >5s duration
            mock_time.side_effect = [0, 6.0]  # start=0, end=6s

            trader._reconcile_open_orders()

            # Should log performance breach
            breach_logs = [call for call in trader.logger.warning.call_args_list
                          if 'performance_breach' in str(call)]
            assert len(breach_logs) > 0, "Should log performance breach when >5s"

    def test_orphan_exchange_position_corrective_action(self, trader):
        """Test orphan exchange position detection + corrective action (CR-0067 AC2)"""
        # Mock exchange has position not in local
        trader.api.get_open_orders.return_value = []
        trader.api.get_positions.return_value = [
            {'symbol': 'ORPHANUSDT', 'side': 'BUY', 'size': 10.0}
        ]
        trader.positions = {}  # No local positions

        trader._reconcile_open_orders()

        # Should log orphan and take corrective action
        orphan_logs = [call for call in trader.logger.info.call_args_list
                      if 'orphan_exchange_position' in str(call)]
        assert len(orphan_logs) > 0, "Should log orphan exchange position"

        corrective_logs = [call for call in trader.logger.info.call_args_list
                          if 'CORRECTIVE_ACTION' in str(call)]
        assert len(corrective_logs) > 0, "Should take corrective action for orphan"

    def test_orphan_local_position_auto_close(self, trader):
        """Test local orphan position auto-close corrective action (CR-0067 AC3)"""
        # Mock local has position not on exchange
        trader.api.get_open_orders.return_value = []
        trader.api.get_positions.return_value = []  # No exchange positions
        trader.positions = {
            'LOCALUSDT': {
                'side': 'BUY',
                'remaining_size': 5.0,
                'trade_id': 'test_123'
            }
        }

        trader._reconcile_open_orders()

        # Should detect local orphan and mark for closure
        orphan_logs = [call for call in trader.logger.info.call_args_list
                      if 'orphan_local_position' in str(call)]
        assert len(orphan_logs) > 0, "Should log orphan local position"

        # Should have reconciliation_close flag
        pos = trader.positions.get('LOCALUSDT', {})
        assert pos.get('reconciliation_close') is True, "Should mark local orphan for closure"

    def test_partial_fill_sync_with_mismatch(self, trader):
        """Test partial fill sync when exchange/local quantities differ (CR-0067 AC4)"""
        # Mock exchange order with different fill than local
        trader.api.get_open_orders.return_value = [
            {'orderId': '12345', 'symbol': 'TESTUSDT', 'executedQty': '7.5'}  # 75% filled
        ]
        trader.api.get_positions.return_value = [
            {'symbol': 'TESTUSDT', 'side': 'BUY', 'size': 10.0}
        ]

        trader.positions = {
            'TESTUSDT': {
                'order_id': '12345',
                'position_size': 10.0,
                'remaining_size': 5.0,  # Only 50% filled locally
                'trade_id': 'test_456',
                'side': 'BUY'
            }
        }

        trader._reconcile_open_orders()

        # Should sync partial fill
        pos = trader.positions['TESTUSDT']
        expected_remaining = 10.0 - 7.5  # position_size - exchange_filled
        assert abs(pos['remaining_size'] - expected_remaining) < self.SYNC_TOLERANCE, \
            f"Should sync remaining_size to {expected_remaining}, got {pos['remaining_size']}"

        # Should log partial fill sync
        sync_logs = [call for call in trader.logger.info.call_args_list
                    if 'PARTIAL_FILL_SYNC' in str(call)]
        assert len(sync_logs) > 0, "Should log partial fill sync"

    def test_partial_fill_fsm_transition(self, trader):
        """Test FSM transition during partial fill sync (CR-0067 AC4)"""
        trader.api.get_open_orders.return_value = [
            {'orderId': '67890', 'symbol': 'FSMTEST', 'executedQty': '10.0'}  # Fully filled
        ]
        trader.api.get_positions.return_value = [
            {'symbol': 'FSMTEST', 'side': 'BUY', 'size': 10.0}
        ]

        trader.positions = {
            'FSMTEST': {
                'order_id': '67890',
                'position_size': 10.0,
                'remaining_size': 3.0,  # Not fully synced
                'trade_id': 'fsm_test_789',
                'side': 'BUY'
            }
        }

        trader._reconcile_open_orders()

        # Should trigger FSM transition to OPEN (fully filled)
        pos = trader.positions['FSMTEST']
        assert abs(pos['remaining_size']) < self.SYNC_TOLERANCE, "Should sync to fully filled"

        # Should call FSM transition
        trader.state_manager.transition_to.assert_called()
        calls = trader.state_manager.transition_to.call_args_list
        fsm_calls = [call for call in calls if call[0][0] == 'fsm_test_789']
        assert len(fsm_calls) > 0, "Should call FSM transition for trade"

    def test_reconciliation_fallback_to_v1_on_error(self, trader):
        """Test fallback to v1 when v2 encounters errors"""
        # Mock v2 method to raise exception
        trader.api.get_open_orders.side_effect = Exception("API Error")

        # Mock v1 methods
        with patch.object(trader, '_reconcile_open_orders_v1') as mock_v1:
            trader._reconcile_open_orders()

            # Should fallback to v1
            mock_v1.assert_called_once()

            # Should log error
            error_logs = [call for call in trader.logger.error.call_args_list
                         if 'RECON_V2:error' in str(call)]
            assert len(error_logs) > 0, "Should log v2 error before fallback"

    def test_order_id_mapping_functionality(self, trader):
        """Test v2 order ID mapping build functionality"""
        orders = [
            {'orderId': 'abc123', 'symbol': 'TEST1', 'side': 'BUY'},
            {'orderId': 'def456', 'symbol': 'TEST2', 'side': 'SELL'},
            {'symbol': 'TEST3'},  # No orderId
        ]

        orders_by_id = trader._build_order_id_map(orders)

        assert len(orders_by_id) == self.EXPECTED_ORDER_MAP_COUNT, "Should map 2 orders with IDs"
        assert 'abc123' in orders_by_id, "Should include abc123"
        assert 'def456' in orders_by_id, "Should include def456"
        assert orders_by_id['abc123']['symbol'] == 'TEST1', "Should map correctly"

    @pytest.mark.timeout(10)
    def test_reconciliation_v2_end_to_end_timing(self, trader):
        """End-to-end timing test to ensure < 5s requirement with realistic mocks"""
        # Mock realistic exchange responses
        trader.api.get_open_orders.return_value = [
            {'orderId': f'order_{i}', 'symbol': f'PAIR{i}USDT', 'executedQty': '1.0'}
            for i in range(50)  # 50 open orders
        ]
        trader.api.get_positions.return_value = [
            {'symbol': f'PAIR{i}USDT', 'side': 'BUY', 'size': 10.0}
            for i in range(20)  # 20 positions
        ]

        # Some local positions for processing
        trader.positions = {
            f'PAIR{i}USDT': {
                'order_id': f'order_{i}',
                'position_size': 10.0,
                'remaining_size': 9.0,
                'trade_id': f'trade_{i}',
                'side': 'BUY'
            }
            for i in range(10)  # 10 local positions
        }

        start_time = time.time()
        trader._reconcile_open_orders()
        duration = time.time() - start_time

        # Should complete well under performance boundary
        assert duration < self.E2E_PERFORMANCE_LIMIT_S, \
            f"End-to-end reconciliation took {duration:.2f}s, expected < {self.E2E_PERFORMANCE_LIMIT_S}s"

        # Should not log performance breach
        breach_logs = [call for call in trader.logger.warning.call_args_list
                      if 'performance_breach' in str(call)]
        assert len(breach_logs) == 0, "Should not breach performance with realistic load"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
