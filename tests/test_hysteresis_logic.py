import pandas as pd
import os
from datetime import datetime, timedelta
from src.signal_generator import SignalGenerator
from config.settings import Settings

class DummyIndicatorCalc:
    def __init__(self, scripted):
        self.scripted = scripted
        self.idx = 0
    def calculate_all_indicators(self, df):
        return {}
    def score_indicators(self, df, indicators):
        # scripted: list of (signal, total_score)
        sig, score = self.scripted[self.idx]
        self.idx += 1
        return {
            'signal': sig,
            'total_score': score,
            'scores': {'DUMMY': score},
            'contributions': {'DUMMY': score}
        }

class DummyFetcher:
    def __init__(self):
        pass
    def get_pair_data(self, symbol, timeframe):
        now = datetime.utcnow()
        # two rows so percent_change hesaplanabilsin
        data = {
            'timestamp': [now - timedelta(minutes=1), now],
            'close': [100.0, 101.0]
        }
        return pd.DataFrame(data)
    def load_top_pairs(self):
        return ['TESTUSDT']


def test_hysteresis_buy_sell_hold(monkeypatch, tmp_path):
    # Thresholdları test için daralt
    monkeypatch.setattr(Settings, 'BUY_SIGNAL_THRESHOLD', 60, raising=False)
    monkeypatch.setattr(Settings, 'BUY_EXIT_THRESHOLD', 55, raising=False)
    monkeypatch.setattr(Settings, 'SELL_SIGNAL_THRESHOLD', 20, raising=False)
    monkeypatch.setattr(Settings, 'SELL_EXIT_THRESHOLD', 25, raising=False)  # exit > threshold (mevcut mantığa uyumlu)

    # Senaryo: AL -> BEKLE (hold) -> BEKLE (drop) -> SAT -> BEKLE (hold) -> BEKLE (drop)
    script = [
        ('AL', 65),      # raw AL -> final AL
        ('BEKLE', 58),   # within hysteresis band -> stay AL
        ('BEKLE', 54),   # below exit -> drop to BEKLE
        ('SAT', 15),     # raw SAT -> final SAT
        ('BEKLE', 22),   # <= sell_exit => hold SAT
        ('BEKLE', 28),   # > sell_exit => drop to BEKLE
    ]

    sg = SignalGenerator()
    # Monkeypatch components
    sg.indicator_calc = DummyIndicatorCalc(script)
    sg.data_fetcher = DummyFetcher()

    results = []
    raws = []
    scores = []
    for _ in script:
        res = sg.generate_signals()
        results.append(res['TESTUSDT']['signal'])
        raws.append(res['TESTUSDT']['signal_raw'])
        scores.append(res['TESTUSDT']['total_score'])

    assert results == ['AL','AL','BEKLE','SAT','SAT','BEKLE'], (results, raws, scores)
    assert sg._prev_signals['TESTUSDT'] == 'BEKLE'
