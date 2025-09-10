from src.backtest.calibrate import run_calibration
import json

# Fast small sample with ADX filter
r1 = run_calibration(fast=True, pairs_limit=5, use_adx_filter=True)
# Fast small sample without ADX filter
r2 = run_calibration(fast=True, pairs_limit=5, use_adx_filter=False)

def extract(tag, r):
    g = r.get('global', {})
    ts = g.get('trade_stats', {})
    return {
        'tag': tag,
        'pairs_used': r.get('pairs_used'),
        'points': r.get('total_points'),
        'winrate': ts.get('winrate'),
        'winrate_after_costs': ts.get('winrate_after_costs'),
        'trades': ts.get('total_trades'),
        'suggested_buy': g.get('suggested_buy_threshold'),
        'suggested_sell': g.get('suggested_sell_threshold'),
        'adx_filter_used': tag == 'with_adx'
    }

print(json.dumps({
    'with_adx': extract('with_adx', r1),
    'without_adx': extract('without_adx', r2)
}, indent=2, ensure_ascii=False))
