"""
CR-0072 Integration Script: Integrate ReplayManager with Core Trader
Add replay recording to trade decision points in core trader
"""


def integrate_replay_with_core():
    """
    Integration points for replay manager in core trader:

    1. Start recording session in trader __init__ or run loop start
    2. Record decisions in open_position logic
    3. Record decisions in close_position logic
    4. Record decisions in signal evaluation
    5. Stop recording on graceful shutdown
    """

    print("CR-0072 Replay Manager Integration Guide")
    print("=" * 50)

    print("\n1. Core Trader Integration Points:")

    print("\n   a) In trader/__init__.py or start of run loop:")
    print("   ```python")
    print("   from src.utils.replay_manager import start_replay_recording, stop_replay_recording")
    print("   ")
    print("   # In __init__ or run() method")
    print("   self.replay_session_id = start_replay_recording('trading_session')")
    print("   ```")

    print("\n   b) In signal evaluation (signal_generator.py or core.py):")
    print("   ```python")
    print("   from src.utils.replay_manager import record_trade_decision")
    print("   ")
    print("   # After signal evaluation")
    print("   record_trade_decision(")
    print("       symbol=symbol,")
    print("       signal={'score': score, 'trend': trend, 'indicators': indicators},")
    print("       decision='EVALUATE',  # or 'ACCEPT', 'REJECT'")
    print("       reason=f'Signal score: {score}',")
    print("       context={")
    print("           'price': current_price,")
    print("           'volume': volume_24h,")
    print("           'atr': atr_value,")
    print("           'market_conditions': market_state")
    print("       }")
    print("   )")
    print("   ```")

    print("\n   c) In open_position logic (core.py):")
    print("   ```python")
    print("   # Before position opening")
    print("   record_trade_decision(")
    print("       symbol=symbol,")
    print("       signal=signal_data,")
    print("       decision='OPEN',")
    print("       reason=f'Risk check passed, position size: {position_size}',")
    print("       context={")
    print("           'position_size': position_size,")
    print("           'stop_loss': stop_loss,")
    print("           'take_profit': take_profit,")
    print("           'risk_per_trade': risk_amount")
    print("       }")
    print("   )")
    print("   ")
    print("   # After position opened")
    print("   record_trade_decision(")
    print("       symbol=symbol,")
    print("       signal=signal_data,")
    print("       decision='OPENED',")
    print("       reason='Position successfully opened',")
    print("       outcome={")
    print("           'fill_price': fill_price,")
    print("           'order_id': order_id,")
    print("           'filled_qty': filled_qty,")
    print("           'execution_time': execution_time")
    print("       }")
    print("   )")
    print("   ```")

    print("\n   d) In close_position logic (core.py):")
    print("   ```python")
    print("   record_trade_decision(")
    print("       symbol=symbol,")
    print("       signal={'trigger': close_trigger},")
    print("       decision='CLOSE',")
    print("       reason=close_reason,")
    print("       context={")
    print("           'unrealized_pnl': unrealized_pnl,")
    print("           'position_age': position_age,")
    print("           'trailing_triggered': trailing_triggered")
    print("       },")
    print("       outcome={")
    print("           'realized_pnl': realized_pnl,")
    print("           'close_price': close_price,")
    print("           'total_return': total_return")
    print("       }")
    print("   )")
    print("   ```")

    print("\n   e) In guard checks (guards.py):")
    print("   ```python")
    print("   # When guards block a trade")
    print("   record_trade_decision(")
    print("       symbol=symbol,")
    print("       signal=signal_data,")
    print("       decision='BLOCKED',")
    print("       reason=f'Guard blocked: {guard_name} - {block_reason}',")
    print("       context={")
    print("           'guard_name': guard_name,")
    print("           'guard_threshold': threshold,")
    print("           'current_value': current_value,")
    print("           'daily_stats': daily_stats")
    print("       }")
    print("   )")
    print("   ```")

    print("\n   f) In graceful shutdown (core.py):")
    print("   ```python")
    print("   # In shutdown_gracefully() method")
    print("   if hasattr(self, 'replay_session_id') and self.replay_session_id:")
    print("       session_id = stop_replay_recording()")
    print("       self.logger.info(f'Replay session saved: {session_id}')")
    print("   ```")

    print("\n2. Configuration Integration:")

    print("\n   Add to config/settings.py:")
    print("   ```python")
    print("   # Replay settings")
    print("   REPLAY_ENABLED = os.getenv('REPLAY_ENABLED', 'true').lower() == 'true'")
    print("   REPLAY_SESSION_NAME = os.getenv('REPLAY_SESSION_NAME', 'auto')")
    print("   REPLAY_MAX_SESSIONS = int(os.getenv('REPLAY_MAX_SESSIONS', '50'))")
    print("   ```")

    print("\n3. Feature Flag Integration:")

    print("\n   Create conditional recording:")
    print("   ```python")
    print("   from config.settings import REPLAY_ENABLED")
    print("   ")
    print("   def record_if_enabled(symbol, signal, decision, reason, **kwargs):")
    print("       if REPLAY_ENABLED:")
    print("           return record_trade_decision(symbol, signal, decision, reason, **kwargs)")
    print("       return True")
    print("   ```")

    print("\n4. Testing Integration:")

    print("\n   In tests, use isolated replay manager:")
    print("   ```python")
    print("   import tempfile")
    print("   from src.utils.replay_manager import ReplayManager")
    print("   ")
    print("   def test_with_replay():")
    print("       with tempfile.TemporaryDirectory() as temp_dir:")
    print("           replay_manager = ReplayManager(temp_dir)")
    print("           session_id = replay_manager.start_recording_session('test')")
    print("           # ... test logic with recording ...")
    print("           replay_manager.stop_recording_session()")
    print("   ```")

    print("\n5. CLI Integration:")

    print("\n   Add replay commands to main.py or CLI script:")
    print("   ```python")
    print("   from src.utils.replay_manager import get_replay_manager")
    print("   ")
    print("   def show_replay_stats():")
    print("       manager = get_replay_manager()")
    print("       stats = manager.get_statistics()")
    print("       print(f'Total sessions: {stats[\"total_sessions\"]}')")
    print("       print(f'Total decisions: {stats[\"total_decisions\"]}')")
    print("   ")
    print("   def replay_session_command(session_id):")
    print("       manager = get_replay_manager()")
    print("       result = manager.replay_session(session_id)")
    print("       print(f'Replay result: {result}')")
    print("   ```")

    print("\n6. Monitoring Integration:")

    print("\n   Add replay metrics to metrics collection:")
    print("   ```python")
    print("   from src.utils.replay_manager import get_replay_manager")
    print("   ")
    print("   def collect_replay_metrics():")
    print("       manager = get_replay_manager()")
    print("       stats = manager.get_statistics()")
    print("       return {")
    print("           'replay_total_sessions': stats['total_sessions'],")
    print("           'replay_total_decisions': stats['total_decisions'],")
    print("           'replay_recording_active': 1 if stats['recording_active'] else 0,")
    print("           'replay_dir_size_mb': stats['replay_dir_size_mb']")
    print("       }")
    print("   ```")

    print("\n7. SSoT Update:")

    print("\n   Update .github/copilot-instructions.md:")
    print("   - Add MOD-UTILS-REPLAY entry to registry")
    print("   - Update CR-0072 status to 'done'")
    print("   - Update M3 milestone progress to 75%")
    print("   - Add replay metrics to observability section")


def generate_integration_patch():
    """Generate minimal integration patch for core.py"""

    integration_code = '''
# CR-0072 Replay Integration Example
# Add these imports to core.py:
from src.utils.replay_manager import start_replay_recording, record_trade_decision, stop_replay_recording

class TradingCore:
    def __init__(self, ...):
        # ... existing init code ...

        # CR-0072: Start replay recording
        if Settings.REPLAY_ENABLED:
            self.replay_session_id = start_replay_recording(Settings.REPLAY_SESSION_NAME)
            self.logger.info(f"Started replay recording session: {self.replay_session_id}")
        else:
            self.replay_session_id = None

    def open_position(self, symbol, signal_data, ...):
        # ... existing validation code ...

        # CR-0072: Record opening decision
        if Settings.REPLAY_ENABLED:
            record_trade_decision(
                symbol=symbol,
                signal=signal_data,
                decision="OPEN",
                reason=f"Position opening: size={position_size}",
                context={
                    "position_size": position_size,
                    "stop_loss": stop_loss,
                    "take_profit": take_profit,
                    "atr": atr_value
                }
            )

        # ... existing position opening code ...

        # CR-0072: Record execution outcome
        if Settings.REPLAY_ENABLED and order_result:
            record_trade_decision(
                symbol=symbol,
                signal=signal_data,
                decision="OPENED",
                reason="Position successfully opened",
                outcome={
                    "fill_price": fill_price,
                    "order_id": order_result.get("orderId"),
                    "filled_qty": filled_qty
                }
            )

    def close_position(self, symbol, reason="Manual close", ...):
        # ... existing close logic ...

        # CR-0072: Record closing decision
        if Settings.REPLAY_ENABLED:
            record_trade_decision(
                symbol=symbol,
                signal={"trigger": reason},
                decision="CLOSE",
                reason=reason,
                context={
                    "unrealized_pnl": unrealized_pnl,
                    "position_age": position_age
                },
                outcome={
                    "realized_pnl": realized_pnl,
                    "close_price": close_price
                }
            )

    def shutdown_gracefully(self):
        # ... existing shutdown code ...

        # CR-0072: Stop replay recording
        if Settings.REPLAY_ENABLED and self.replay_session_id:
            saved_session = stop_replay_recording()
            self.logger.info(f"Replay session saved: {saved_session}")
            self.slog("replay_session_completed", session_id=saved_session)

        # ... rest of shutdown ...
'''

    return integration_code


if __name__ == "__main__":
    integrate_replay_with_core()

    print("\n" + "=" * 50)
    print("INTEGRATION PATCH PREVIEW")
    print("=" * 50)
    print(generate_integration_patch())

    print("\n" + "=" * 50)
    print("NEXT STEPS")
    print("=" * 50)
    print("1. Run tests: pytest tests/test_cr0072_replay_manager.py -v")
    print("2. Add Settings.REPLAY_* configs to config/settings.py")
    print("3. Integrate recording calls in core.py at decision points")
    print("4. Update SSoT documentation")
    print("5. Test end-to-end replay workflow")
    print("6. Add replay commands to CLI")
    print("7. Complete CR-0072 acceptance criteria")
