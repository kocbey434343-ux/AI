import json, pprint
from src.backtest.calibrate import run_calibration

def summarize(tag, res):
    g = res.get('global', {})
    ts = g.get('trade_stats', {})
    return {
        'tag': tag,
        'fast': res.get('fast'),
        'pairs_used': res.get('pairs_used'),
        'total_points': res.get('total_points'),
        'persisted_loaded': res.get('persisted_thresholds_loaded'),
        'applied_thresholds': res.get('applied_thresholds'),
        'suggested_buy': g.get('suggested_buy_threshold'),
        'suggested_sell': g.get('suggested_sell_threshold'),
        'winrate': ts.get('winrate'),
        'winrate_after_costs': ts.get('winrate_after_costs'),
        'trades': ts.get('total_trades'),
    }

# Fast runs with and without ADX filter to show effect
res_with_adx = run_calibration(fast=True, verbose=False, pairs_limit=20, use_adx_filter=True)
res_without_adx = run_calibration(fast=True, verbose=False, pairs_limit=20, use_adx_filter=False)
# Full small sample optimization with apply_best
res_full = run_calibration(fast=False, verbose=False, pairs_limit=25, apply_best=True)

out = {
    'with_adx': summarize('with_adx', res_with_adx),
    'without_adx': summarize('without_adx', res_without_adx),
    'full_apply_best': summarize('full', res_full),
    'candidates_count_full': len((res_full.get('global', {}).get('optimization') or {}).get('candidates') or []),
}
print(json.dumps(out, indent=2, ensure_ascii=False))
