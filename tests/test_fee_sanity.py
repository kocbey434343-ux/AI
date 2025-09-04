# ruff: noqa: I001
import math

from config.settings import Settings
from src.utils.helpers import Costs, calculate_net_pnl


def test_settings_fee_sanity_clamp():
    # Values over 1.0 should be clamped to 1.0 (i.e., 1%)
    assert 0.0 <= Settings.COMMISSION_PCT_PER_SIDE <= 1.0
    assert 0.0 <= Settings.SLIPPAGE_PCT_PER_SIDE <= 1.0
    assert 0.0 <= Settings.MAKER_COMMISSION_PCT_PER_SIDE <= 1.0
    assert 0.0 <= Settings.TAKER_COMMISSION_PCT_PER_SIDE <= 1.0


def test_calculate_net_pnl_basic_buy():
    # entry 100, exit 101, qty 10 => gross = 10
    # default costs ~ (0.04 + 0.02)% * (100+101)*10 ~= 0.06% * 2010 ~= 1.206
    net = calculate_net_pnl(100.0, 101.0, "BUY", 10.0)
    assert net > 0
    GROSS = 10.0
    assert net < GROSS


def test_calculate_net_pnl_custom_costs_sell():
    costs = Costs(commission_pct_per_side=0.1, slippage_pct_per_side=0.0)  # %0.1 her taraf
    # entry 100, exit 99, qty 5 => gross SELL = (100-99)*5 = 5
    # costs = 0.1% * (199)*5 = 0.001 * 995 = 0.995
    net = calculate_net_pnl(100.0, 99.0, "SELL", 5.0, costs=costs)
    assert math.isclose(net, 5.0 - 0.995, rel_tol=1e-6)
