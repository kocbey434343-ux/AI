from src.utils.exception_hook import install_global_exception_hook
from src.utils.structured_log import get_slog_events, clear_slog_events
import sys

def test_cr0042_install_and_capture():
    clear_slog_events()
    install_global_exception_hook()
    # ikinci çağrı idempotent
    install_global_exception_hook()
    try:
        raise RuntimeError("hook-test")
    except RuntimeError as e:
        sys.excepthook(type(e), e, e.__traceback__)
    events = get_slog_events()
    names = [e['event'] for e in events]
    assert 'exception_hook_installed' in names
    assert 'unhandled_exception' in names
