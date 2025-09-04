"""Settings yardimci fonksiyonlari icin basit dogrulama testleri."""

# ruff: noqa: I001
from config.settings import Settings


def test_get_commission_rates_returns_tuple_and_matches_settings():
    maker, taker = Settings.get_commission_rates()
    assert isinstance(maker, float)
    assert isinstance(taker, float)
    assert maker == Settings.MAKER_COMMISSION_PCT_PER_SIDE
    assert taker == Settings.TAKER_COMMISSION_PCT_PER_SIDE


def test_round_trip_cost_pct_formula_matches_settings_fields():
    expected = 2.0 * (Settings.COMMISSION_PCT_PER_SIDE + Settings.SLIPPAGE_PCT_PER_SIDE)
    assert Settings.round_trip_cost_pct() == expected
