"""Global exception hook installer (CR-0042).

Purpose: Capture unhandled exceptions (main thread + threading) and emit
structured log events so they surface in monitoring / UI layers.

Usage:
    from src.utils.exception_hook import install_global_exception_hook
    install_global_exception_hook()

Idempotent: multiple calls reuse same hook.
"""
from __future__ import annotations
import sys, threading, traceback
from types import TracebackType
from typing import Type
from src.utils.structured_log import slog
from src.utils.logger import get_logger

_LOGGER = get_logger("ExceptionHook")
_INSTALLED = False


def _format_tb(tb: TracebackType | None, limit: int = 20) -> str:
    if not tb:
        return ""
    return ''.join(traceback.format_tb(tb, limit))


def _emit(event: str, exc_type: Type[BaseException], exc: BaseException, tb: TracebackType | None):
    try:
        slog(event,
             exc_type=getattr(exc_type, '__name__', str(exc_type)),
             message=str(exc),
             traceback=_format_tb(tb))
    except Exception:  # pragma: no cover - logging should not break app
        pass


def _excepthook(exc_type: Type[BaseException], exc: BaseException, tb: TracebackType | None):
    _LOGGER.error(f"UNHANDLED:{exc_type.__name__}:{exc}")
    _emit('unhandled_exception', exc_type, exc, tb)
    if _ORIG_SYS_HOOK and _ORIG_SYS_HOOK is not _excepthook:
        try:
            _ORIG_SYS_HOOK(exc_type, exc, tb)
        except Exception:  # pragma: no cover
            pass


def _threading_hook(args: threading.ExceptHookArgs):  # Python >=3.8
    _LOGGER.error(f"THREAD_UNHANDLED:{args.exc_type.__name__}:{args.exc_value}")
    _emit('thread_unhandled_exception', args.exc_type, args.exc_value, args.exc_traceback)
    if _ORIG_THREADING_HOOK and _ORIG_THREADING_HOOK is not _threading_hook:
        try:
            _ORIG_THREADING_HOOK(args)
        except Exception:  # pragma: no cover
            pass

_ORIG_SYS_HOOK = sys.excepthook
_ORIG_THREADING_HOOK = getattr(threading, 'excepthook', None)


def install_global_exception_hook():
    global _INSTALLED, _ORIG_SYS_HOOK, _ORIG_THREADING_HOOK
    if _INSTALLED:
        return False
    try:
        sys.excepthook = _excepthook  # type: ignore
        if hasattr(threading, 'excepthook'):
            threading.excepthook = _threading_hook  # type: ignore[attr-defined]
        _INSTALLED = True
        _LOGGER.info("Global exception hook installed")
        slog('exception_hook_installed')
        return True
    except Exception as e:  # pragma: no cover
        _LOGGER.error(f"Exception hook install failed: {e}")
        return False

__all__ = ["install_global_exception_hook"]
