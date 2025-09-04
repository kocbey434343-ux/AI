import os
import math
import pandas as pd
from config.settings import Settings
from src.trader import Trader
from src.trader.execution import SizeInputs, position_size


def make_trader(tmp_path):
    os.environ['TRADES_DB_PATH'] = str(tmp_path / 'atrsize.db')
    t = Trader()
    # Koruma guard kisitlarini azalt
    t.risk_manager.max_positions = 100
    return t


def test_position_size_adaptive_atr_and_score(tmp_path, monkeypatch):
    t = make_trader(tmp_path)
    balance = 10_000
    price = 100.0
    # Quantize deterministik: qty olduğu gibi, price döndür
    monkeypatch.setattr(t.api, 'quantize', lambda symbol, q, p: (q, p))

    def compute_size(atr_value, total_score):
        signal = {
            'indicators': {'ATR': atr_value},
            'total_score': total_score
        }
    # Stop_loss hesaplama mantigini yeniden kullanmak yerine approx: fallback_stop_pct veya atr_multiplier
    # Burada position_size fonksiyonu stop_loss'u parametre olarak beklemiyor; uste prepare_order_context kullaniyor normalde.
    # Test icin stop_loss'u ATR tabanli emulate edelim.
        dist = atr_value * t.risk_manager.atr_multiplier
        stop_loss = price - dist
        inputs = SizeInputs('TESTUSDT', balance, price, stop_loss, signal)
        return position_size(t, inputs)

    # Dusuk ATR (atr_pct << ref) => multiplier ust banda yakin (≈ ADAPTIVE_RISK_MAX_MULT)
    low_atr = price * Settings.ADAPTIVE_RISK_ATR_REF_PCT / 100 * 0.3  # referansin %30'u
    size_low = compute_size(low_atr, 50)  # score nötr

    # Yuksek ATR (atr_pct >> ref) => multiplier min banda yakin
    high_atr = price * Settings.ADAPTIVE_RISK_ATR_REF_PCT / 100 * 2.5  # referansin 2.5x
    size_high = compute_size(high_atr, 50)

    assert size_low > 0 and size_high > 0
    # low ATR daha buyuk olmali (ters oranti)
    assert size_low > size_high * 1.5, f"Beklenen ters orantı yok: low={size_low} high={size_high}"

    # Skor etkisi: total_score 100 iken ~ +%40 * strength eklenir (strength = (score-50)/50 =1)
    size_low_highscore = compute_size(low_atr, 100)
    # Teoride carpani (0.9 + 1*0.4)=1.3; tolerans payi (quantize vb) olmadigindan ~%28+ fark beklenir
    assert size_low_highscore > size_low * 1.25

    # Beklenen teorik boyutlari dogrudan formülden türet:
    # base_size = risk_amount / (ATR * atr_multiplier)  (entry price sadeleşir)
    risk_amount = balance * (t.risk_manager.risk_percent / 100.0)
    base_size_low = risk_amount / (low_atr * t.risk_manager.atr_multiplier)
    base_size_high = risk_amount / (high_atr * t.risk_manager.atr_multiplier)

    # Adaptif çarpanlar (düşük ATR -> MAX, yüksek ATR -> MIN banda clamp edilir)
    expected_size_low = base_size_low * Settings.ADAPTIVE_RISK_MAX_MULT * 0.9  # skor nötr => 0.9
    expected_size_high = base_size_high * Settings.ADAPTIVE_RISK_MIN_MULT * 0.9

    # %5 tolerans düşük ATR, %10 tolerans yüksek ATR (ileride kuantizasyon/yuvarlama değişiklikleri için buffer)
    assert math.isclose(size_low, expected_size_low, rel_tol=0.05), f"low mismatch got={size_low} exp≈{expected_size_low}"
    assert math.isclose(size_high, expected_size_high, rel_tol=0.10), f"high mismatch got={size_high} exp≈{expected_size_high}"

    # Skor 100 oldugunda skor carpani 1.3; notr 0.9 -> oran ≈ 1.444..; %5 tolerans
    expected_ratio = (0.9 + 1.0 * 0.4) / 0.9  # 1.3 / 0.9
    actual_ratio = size_low_highscore / size_low
    assert math.isclose(actual_ratio, expected_ratio, rel_tol=0.05), f"score ratio mismatch got={actual_ratio} exp≈{expected_ratio}"
