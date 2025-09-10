# isort: skip_file
from datetime import datetime, timedelta, timezone
from typing import cast

import pandas as pd

from config.settings import Settings
from src.data_fetcher import DataFetcher
from src.indicators import IndicatorCalculator
from src.signal_generator import SignalGenerator


class _DummyIndicatorCalc:
    def __init__(self, signal: str, score: float = 60.0):
        self.signal = signal
        self.score = score

    def calculate_all_indicators(self, _df):
        return {}

    def score_indicators(self, _df, _indicators):
        return {
            'signal': self.signal,
            'total_score': self.score,
            'scores': {'DUMMY': self.score},
            'contributions': {'DUMMY': self.score},
        }


class _DummyFetcher:
    def __init__(self, df_1h: pd.DataFrame, df_htf: pd.DataFrame):
        self._df_1h = df_1h
        self._df_htf = df_htf

    def get_pair_data(self, _symbol, interval="1h", auto_fetch=True):
        if interval in (Settings.TIMEFRAME, "1h"):
            return self._df_1h
        # HTF cagrisi: Settings.HTF_EMA_TIMEFRAME varsayilani "4h"
        return self._df_htf

    def load_top_pairs(self):
        return ["TESTUSDT"]


def _mk_df(base=100.0, step=1.0, n=2):
    now = datetime.now(tz=timezone.utc)
    ts = [now - timedelta(minutes=i) for i in range(n - 1, -1, -1)]
    close = [base + i * step for i in range(n)]
    return pd.DataFrame({
        'timestamp': ts,
        'close': close,
    })


def test_htf_filter_noop_when_disabled(monkeypatch):
    # OFFLINE guvenligi ve HTF flag kapali
    monkeypatch.setattr(Settings, 'OFFLINE_MODE', True, raising=False)
    # Ana TF'i deterministik tut
    monkeypatch.setattr(Settings, 'TIMEFRAME', '1h', raising=False)
    monkeypatch.setattr(Settings, 'HTF_FILTER_ENABLED', False, raising=False)

    df_1h = _mk_df(base=100, step=1, n=2)
    df_htf = _mk_df(base=100, step=1, n=20)  # kullanilmayacak

    sg = SignalGenerator()
    sg.indicator_calc = cast(IndicatorCalculator, _DummyIndicatorCalc(signal='AL', score=70))
    sg.data_fetcher = cast(DataFetcher, _DummyFetcher(df_1h, df_htf))

    out = sg.generate_signals()
    assert out['TESTUSDT']['signal_raw'] == 'AL'
    assert out['TESTUSDT']['signal'] == 'AL'  # hysteresis prev=None -> raw gecer


def test_htf_filter_blocks_sell_in_long_bias(monkeypatch):
    # Long bias: close > EMA => SAT bloklanmali

    # Daha agresif patch: tum Settings'leri belirgin sekilde ata
    import importlib
    from config import settings
    importlib.reload(settings)  # Settings modulunu sifirla

    monkeypatch.setattr(Settings, 'OFFLINE_MODE', True, raising=False)
    # Ana TF'i deterministik tut
    monkeypatch.setattr(Settings, 'TIMEFRAME', '1h', raising=False)
    monkeypatch.setattr(Settings, 'HTF_FILTER_ENABLED', True, raising=False)
    monkeypatch.setattr(Settings, 'HTF_EMA_TIMEFRAME', '4h', raising=False)
    monkeypatch.setattr(Settings, 'HTF_EMA_LENGTH', 10, raising=False)  # hizli EMA

    # Debug: dogru atandigini dogrula
    assert Settings.HTF_FILTER_ENABLED, f"HTF_FILTER_ENABLED patch failed: {Settings.HTF_FILTER_ENABLED}"
    assert Settings.HTF_EMA_TIMEFRAME == '4h', f"HTF_EMA_TIMEFRAME patch failed: {Settings.HTF_EMA_TIMEFRAME}"

    print(f"\nDEBUG: Settings after patch - HTF_FILTER_ENABLED={Settings.HTF_FILTER_ENABLED}, TIMEFRAME={Settings.TIMEFRAME}")

    # 1h veri (minimal)
    df_1h = _mk_df(base=100, step=1, n=2)
    # 4h veri: artan trend => close > EMA
    df_htf = _mk_df(base=100, step=1, n=20)

    print(f"DEBUG: df_htf trend: first={df_htf['close'].iloc[0]}, last={df_htf['close'].iloc[-1]} (should be long bias)")

    sg = SignalGenerator()
    sg.indicator_calc = cast(IndicatorCalculator, _DummyIndicatorCalc(signal='SAT', score=30))
    sg.data_fetcher = cast(DataFetcher, _DummyFetcher(df_1h, df_htf))

    out = sg.generate_signals()

    # Debug output
    print(f"DEBUG: Output signal_raw={out['TESTUSDT']['signal_raw']}, signal={out['TESTUSDT']['signal']}")

    # HTF filtresi histerezis oncesinde sinyali BEKLE'ye dusurdugu icin raw da BEKLE olur
    assert out['TESTUSDT']['signal_raw'] == 'BEKLE', f"Expected signal_raw=BEKLE but got {out['TESTUSDT']['signal_raw']}"
    # HTF filtresi SAT'i BEKLE'ye dusurur
    assert out['TESTUSDT']['signal'] == 'BEKLE', f"Expected signal=BEKLE but got {out['TESTUSDT']['signal']}"


def test_htf_filter_blocks_buy_in_short_bias(monkeypatch):
    # Short bias: close < EMA => AL bloklanmali

    # Daha agresif patch: tum Settings'leri belirgin sekilde ata
    import importlib
    from config import settings
    importlib.reload(settings)  # Settings modulunu sifirla

    monkeypatch.setattr(Settings, 'OFFLINE_MODE', True, raising=False)
    # Ana TF'i deterministik tut
    monkeypatch.setattr(Settings, 'TIMEFRAME', '1h', raising=False)
    monkeypatch.setattr(Settings, 'HTF_FILTER_ENABLED', True, raising=False)
    monkeypatch.setattr(Settings, 'HTF_EMA_TIMEFRAME', '4h', raising=False)
    monkeypatch.setattr(Settings, 'HTF_EMA_LENGTH', 10, raising=False)

    # Debug: dogru atandigini dogrula
    assert Settings.HTF_FILTER_ENABLED, f"HTF_FILTER_ENABLED patch failed: {Settings.HTF_FILTER_ENABLED}"
    assert Settings.HTF_EMA_TIMEFRAME == '4h', f"HTF_EMA_TIMEFRAME patch failed: {Settings.HTF_EMA_TIMEFRAME}"

    print(f"\nDEBUG: Settings after patch - HTF_FILTER_ENABLED={Settings.HTF_FILTER_ENABLED}, TIMEFRAME={Settings.TIMEFRAME}")

    df_1h = _mk_df(base=200, step=-1, n=2)
    # 4h veri: azalan trend => close < EMA (EMA arkadan gelir)
    # EMA'nin uzerinde kalma riskini azaltmak icin once yuksek degerler, sonra dusus
    df_htf = _mk_df(base=300, step=-1, n=20)

    print(f"DEBUG: df_htf trend: first={df_htf['close'].iloc[0]}, last={df_htf['close'].iloc[-1]} (should be short bias)")

    sg = SignalGenerator()
    sg.indicator_calc = cast(IndicatorCalculator, _DummyIndicatorCalc(signal='AL', score=70))
    sg.data_fetcher = cast(DataFetcher, _DummyFetcher(df_1h, df_htf))

    out = sg.generate_signals()

    # Debug output
    print(f"DEBUG: Output signal_raw={out['TESTUSDT']['signal_raw']}, signal={out['TESTUSDT']['signal']}")

    # HTF filtresi histerezis oncesinde sinyali BEKLE'ye dusurdugu icin raw da BEKLE olur
    assert out['TESTUSDT']['signal_raw'] == 'BEKLE', f"Expected signal_raw=BEKLE but got {out['TESTUSDT']['signal_raw']}"
    # HTF filtresi AL'i BEKLE'ye dusurur
    assert out['TESTUSDT']['signal'] == 'BEKLE', f"Expected signal=BEKLE but got {out['TESTUSDT']['signal']}"
