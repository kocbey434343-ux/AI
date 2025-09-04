from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

"""Backtest Orchestrator Skeleton (CR-0028)

Purpose:
 - Minimal entry point for future backtest pipeline.
 - Supplies run() used by test_backtest_skeleton.
"""

@dataclass
class BacktestResult:
	symbols: List[str]
	signals: Dict[str, Dict[str, Any]]
	trades: int
	pnl_pct: float
	stats: Dict[str, Any] = field(default_factory=dict)


class BacktestOrchestrator:
	"""Simple orchestrator with injectable fetcher & signal_gen."""

	def __init__(self) -> None:  # pragma: no cover - trivial
		self.fetcher = None
		self.signal_gen = None

	def run(self, params: Dict[str, Any] | None = None) -> BacktestResult:
		params = params or {}
		symbols: List[str] = []
		if self.fetcher and hasattr(self.fetcher, "ensure_top_pairs"):
			try:
				symbols = list(self.fetcher.ensure_top_pairs(force=False))  # type: ignore[attr-defined]
			except Exception:
				symbols = []
		if not symbols:
			symbols = ["BTCUSDT", "ETHUSDT"]
		if self.signal_gen and hasattr(self.signal_gen, "generate_signals"):
			try:
				signals = self.signal_gen.generate_signals(symbols)  # type: ignore[attr-defined]
			except Exception:
				signals = {s: {"signal": "AL"} for s in symbols}
		else:
			signals = {s: {"signal": "AL"} for s in symbols}
		trades = len(signals)
		pnl_pct = 0.0
		stats = {"signals": trades, "params_passed": bool(params)}
		return BacktestResult(symbols=symbols, signals=signals, trades=trades, pnl_pct=pnl_pct, stats=stats)

__all__ = ["BacktestOrchestrator", "BacktestResult"]
