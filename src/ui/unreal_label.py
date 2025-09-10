"""Pure helper for formatting unrealized total PnL label (CR-0021).

Separated so tests can import without pulling heavy PyQt MainWindow.
"""
from __future__ import annotations


def format_total_unreal_label(total_unreal: float, pct: float) -> tuple[str, str]:
    """Return (text, color) for total unrealized pnl label.

    color green if total_unreal >= 0 else red.
    pct and total_unreal rounded to 2 decimals in output.
    """
    try:
        tu = float(total_unreal)
    except Exception:
        tu = 0.0
    try:
        p = float(pct)
    except Exception:
        p = 0.0
    if tu > 0:
        color = 'green'
    elif tu < 0:
        color = 'red'
    else:
        color = 'gray'
    text = f"Toplam Unrealized: {tu:.2f} USDT ({p:.2f}%)"
    return text, color

__all__ = ["format_total_unreal_label"]
