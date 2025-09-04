import os
import math

from config.settings import Settings
from src.trader import Trader
from src.trader.execution import SizeInputs, position_size


def make_trader(tmp_path):
    os.environ['TRADES_DB_PATH'] = str(tmp_path / 'atrsize_edge.db')
    t = Trader()
    t.risk_manager.max_positions = 100
    return t


def test_position_size_adaptive_edge_clamps_and_low_score(tmp_path, monkeypatch):
    t = make_trader(tmp_path)
    balance = 5_000
    price = 50.0
    monkeypatch.setattr(t.api, 'quantize', lambda _s, q, p: (q, p))

    def compute(atr_value, score):
        dist = atr_value * t.risk_manager.atr_multiplier
        stop_loss = price - dist
        signal = {'indicators': {'ATR': atr_value}, 'total_score': score}
        return position_size(t, SizeInputs('EDGEUSDT', balance, price, stop_loss, signal))

    risk_amount = balance * (t.risk_manager.risk_percent / 100.0)

    # Asiri dusuk ATR (referansin 5% * 0.05'i) -> inverse cok buyuk olur; MAX_MULT'a clamp edilmeli
    very_low_atr = price * Settings.ADAPTIVE_RISK_ATR_REF_PCT / 100 * 0.05
    base_low = risk_amount / (very_low_atr * t.risk_manager.atr_multiplier)
    size_low_score50 = compute(very_low_atr, 50)  # skor 50 -> strength 0 -> çarpan 0.9
    expected_low = base_low * Settings.ADAPTIVE_RISK_MAX_MULT * 0.9
    assert math.isclose(size_low_score50, expected_low, rel_tol=0.05), f"low clamp fail got={size_low_score50} exp≈{expected_low}"

    # Asiri yuksek ATR (referansin 10x'i) -> inverse kucuk; MIN_MULT'a clamp
    very_high_atr = price * Settings.ADAPTIVE_RISK_ATR_REF_PCT / 100 * 10
    base_high = risk_amount / (very_high_atr * t.risk_manager.atr_multiplier)
    size_high_score50 = compute(very_high_atr, 50)
    expected_high = base_high * Settings.ADAPTIVE_RISK_MIN_MULT * 0.9
    assert math.isclose(size_high_score50, expected_high, rel_tol=0.05), f"high clamp fail got={size_high_score50} exp≈{expected_high}"

    # Dusuk skor (30) -> strength negatif -> 0; yine 0.9 carpani
    size_low_score30 = compute(very_low_atr, 30)
    expected_low_30 = base_low * Settings.ADAPTIVE_RISK_MAX_MULT * 0.9
    assert math.isclose(size_low_score30, expected_low_30, rel_tol=0.05)

    # Skor yüksek (100) -> ratio ~1.444x nötre göre
    size_low_score100 = compute(very_low_atr, 100)
    ratio = size_low_score100 / size_low_score50
    expected_ratio = (0.9 + 1.0 * 0.4) / 0.9
    assert math.isclose(ratio, expected_ratio, rel_tol=0.05), f"score ratio mismatch got={ratio} exp≈{expected_ratio}"
