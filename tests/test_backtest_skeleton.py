from src.backtest.orchestrator import BacktestOrchestrator


EXPECTED_COUNT = 2
EXPECTED_PNL = 0.0
FLOAT_EPS = 1e-9


def test_backtest_skeleton_runs():
    orch = BacktestOrchestrator()
    # Gercek sinyal/fetcher'i override etmek yerine public API'lar patchlenir
    class DummyFetcher:
        def ensure_top_pairs(self, force=False):  # noqa: ARG002
            return ['BTCUSDT','ETHUSDT']
    class DummySignalGen:
        def generate_signals(self, symbols):
            return {s: {'signal':'AL'} for s in symbols}
    orch.fetcher = DummyFetcher()  # type: ignore[assignment]
    orch.signal_gen = DummySignalGen()  # type: ignore[assignment]
    res = orch.run()
    assert res.trades == EXPECTED_COUNT
    assert res.stats['signals'] == EXPECTED_COUNT
    assert abs(res.pnl_pct - EXPECTED_PNL) < FLOAT_EPS
