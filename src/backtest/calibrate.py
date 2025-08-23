import os
import json
import math
from datetime import datetime
from typing import List, Dict
import numpy as np
import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed

from src.data_fetcher import DataFetcher
from src.indicators import IndicatorCalculator
from config.settings import Settings
from src.utils.logger import get_logger

"""Backtest kalibrasyon aracı.

Temel değişiklikler:
 - Dinamik warmup: fast modunda daha düşük bar (over-warmup sebebiyle boş skor oluşmasını engeller)
 - Fonksiyonlar warmup_bars parametresi alır (global sabite bağımlılık azaltıldı)
 - Skor üretilemezse ayrıntılı debug çıktısı döner (None yerine)
 - Yinelenen / eski kod blokları temizlendi
"""

DEFAULT_WARMUP_BARS = 120
FAST_WARMUP_BARS = 40  # fast kalibrasyon için azaltılmış warmup
MAX_BARS_PER_SYMBOL = 400

logger = get_logger("Calibration")

def _slice_recent(df: pd.DataFrame) -> pd.DataFrame:
    if len(df) > MAX_BARS_PER_SYMBOL:
        return df.iloc[-MAX_BARS_PER_SYMBOL:].copy()
    return df.copy()

def _build_indicator_frames(df: pd.DataFrame, calc: IndicatorCalculator) -> Dict[str, pd.Series | dict]:
    return calc.calculate_all_indicators(df)

def _iter_scores(df: pd.DataFrame, indicators_full: Dict, calc: IndicatorCalculator, warmup_bars: int,
                 adx_min: float | None = None):
    close_len = len(df)
    if close_len <= warmup_bars + 5:
        return []
    scores: list[float] = []
    for i in range(warmup_bars, close_len):
        sub_inds = {}
        for name, val in indicators_full.items():
            if isinstance(val, pd.Series):
                sub_inds[name] = val.iloc[: i + 1]
            elif isinstance(val, dict):
                inner = {}
                for k, v in val.items():
                    if isinstance(v, pd.Series):
                        inner[k] = v.iloc[: i + 1]
                    else:
                        inner[k] = v
                sub_inds[name] = inner
            else:
                sub_inds[name] = val
        sub_df = df.iloc[: i + 1]
        scored = calc.score_indicators(sub_df, sub_inds)
        if adx_min is not None:
            adx_val = scored.get('scores', {}).get('ADX')
            try:
                if adx_val is None or float(adx_val) < adx_min:
                    continue  # düşük ADX ortamını dağılıma dahil etmiyoruz
            except Exception:
                pass
        scores.append(scored['total_score'])
    return scores

def _simulate_trades(df: pd.DataFrame, indicators_full: Dict, calc: IndicatorCalculator,
                     buy_thr: float, sell_thr: float, buy_exit: float, sell_exit: float,
                     use_next_bar_fill: bool = False,
                     commission_pct_per_side: float | None = None,
                     slippage_pct_per_side: float | None = None,
                     warmup_bars: int = DEFAULT_WARMUP_BARS,
                     adx_min: float | None = None):
    close_len = len(df)
    # Eşikler NaN ise direkt boş sonuç dön
    if any(isinstance(x, float) and math.isnan(x) for x in (buy_thr, sell_thr, buy_exit, sell_exit)):
        return {'total_trades': 0,'wins': 0,'losses': 0,'winrate': 0.0,'avg_gain_pct': 0.0,'avg_loss_pct': 0.0,'expectancy_pct': 0.0,'max_consec_losses': 0}
    if close_len <= warmup_bars + 5:
        return {'total_trades': 0,'wins': 0,'losses': 0,'winrate': 0.0,'avg_gain_pct': 0.0,'avg_loss_pct': 0.0,'expectancy_pct': 0.0,'max_consec_losses': 0}
    position = None
    entry_price = None
    trades = []
    consec_losses = 0
    max_consec_losses = 0
    for i in range(warmup_bars, close_len):
        sub_inds = {}
        for name, val in indicators_full.items():
            if isinstance(val, pd.Series):
                sub_inds[name] = val.iloc[: i + 1]
            elif isinstance(val, dict):
                inner = {}
                for k, v in val.items():
                    if isinstance(v, pd.Series):
                        inner[k] = v.iloc[: i + 1]
                    else:
                        inner[k] = v
                sub_inds[name] = inner
            else:
                sub_inds[name] = val
        sub_df = df.iloc[: i + 1]
        scored = calc.score_indicators(sub_df, sub_inds)
        score_val = scored['total_score']
        adx_val = None
        if adx_min is not None:
            try:
                adx_val = scored.get('scores', {}).get('ADX')
                if adx_val is not None:
                    adx_val = float(adx_val)
            except Exception:
                adx_val = None
        price = float(sub_df['close'].iloc[-1])
        if position == 'LONG':
            if score_val < buy_exit or score_val <= sell_thr:
                exit_price = price
                if use_next_bar_fill and i + 1 < close_len:
                    exit_price = float(df.iloc[i + 1]['open'])
                pnl = (exit_price - entry_price) / entry_price * 100.0
                trades.append(pnl)
                if pnl < 0:
                    consec_losses += 1
                    max_consec_losses = max(max_consec_losses, consec_losses)
                else:
                    consec_losses = 0
                position = None
        elif position == 'SHORT':
            if score_val > sell_exit or score_val >= buy_thr:
                exit_price = price
                if use_next_bar_fill and i + 1 < close_len:
                    exit_price = float(df.iloc[i + 1]['open'])
                pnl = (entry_price - exit_price) / entry_price * 100.0
                trades.append(pnl)
                if pnl < 0:
                    consec_losses += 1
                    max_consec_losses = max(max_consec_losses, consec_losses)
                else:
                    consec_losses = 0
                position = None
        if position is None:
            # Düşük ADX ortamında yeni pozisyon açma
            if adx_min is not None and adx_val is not None and adx_val < adx_min:
                continue
            if score_val >= buy_thr:
                fill = price
                if use_next_bar_fill and i + 1 < close_len:
                    fill = float(df.iloc[i + 1]['open'])
                position = 'LONG'
                entry_price = fill
            elif score_val <= sell_thr:
                fill = price
                if use_next_bar_fill and i + 1 < close_len:
                    fill = float(df.iloc[i + 1]['open'])
                position = 'SHORT'
                entry_price = fill
    if position and entry_price is not None:
        last_price = float(df['close'].iloc[-1])
        pnl = (last_price - entry_price) / entry_price * 100.0 if position == 'LONG' else (entry_price - last_price) / entry_price * 100.0
        trades.append(pnl)
        if pnl < 0:
            consec_losses += 1
            max_consec_losses = max(max_consec_losses, consec_losses)
    total = len(trades)
    if not total:
        return {'total_trades': 0,'wins': 0,'losses': 0,'winrate': 0.0,'avg_gain_pct': 0.0,'avg_loss_pct': 0.0,'expectancy_pct': 0.0,'max_consec_losses': 0}
    wins = [t for t in trades if t > 0]
    losses = [t for t in trades if t <= 0]
    winrate = len(wins)/total
    avg_gain = float(np.mean(wins)) if wins else 0.0
    avg_loss = float(abs(np.mean(losses))) if losses else 0.0
    expectancy = winrate * avg_gain - (1 - winrate) * avg_loss
    commission = commission_pct_per_side if commission_pct_per_side is not None else getattr(Settings,'COMMISSION_PCT_PER_SIDE',0.0)
    slippage = slippage_pct_per_side if slippage_pct_per_side is not None else getattr(Settings,'SLIPPAGE_PCT_PER_SIDE',0.0)
    cost_per_round = 2.0 * (commission + slippage)
    adjusted_trades = [t - cost_per_round for t in trades]
    wins_adj = [t for t in adjusted_trades if t > 0]
    losses_adj = [t for t in adjusted_trades if t <= 0]
    winrate_adj = len(wins_adj)/total if total else 0.0
    avg_gain_adj = float(np.mean(wins_adj)) if wins_adj else 0.0
    avg_loss_adj = float(abs(np.mean(losses_adj))) if losses_adj else 0.0
    expectancy_adj = winrate_adj * avg_gain_adj - (1 - winrate_adj) * avg_loss_adj
    return {'total_trades': total,'wins': len(wins),'losses': len(losses),'winrate': round(winrate*100,2),'avg_gain_pct': round(avg_gain,2),'avg_loss_pct': round(avg_loss,2),'expectancy_pct': round(expectancy,2),'max_consec_losses': int(max_consec_losses),'cost_per_round_pct': round(cost_per_round,4),'winrate_after_costs': round(winrate_adj*100,2),'expectancy_after_costs_pct': round(expectancy_adj,2)}

def _simulate_for_symbol(dfetch: DataFetcher, calc: IndicatorCalculator, sym: str,
                         buy: float, sell: float, be: float, se: float,
                         warmup_bars: int) -> dict | None:
    try:
        df = dfetch.get_pair_data(sym, Settings.TIMEFRAME, auto_fetch=False)
        if df is None or df.empty or 'close' not in df.columns:
            return None
        df = df.sort_values('timestamp')
        df_slice = _slice_recent(df)
        indicators_full = _build_indicator_frames(df_slice, calc)
        return _simulate_trades(
            df_slice, indicators_full, calc,
            buy, sell, be, se,
            use_next_bar_fill=Settings.USE_NEXT_BAR_FILL,
            warmup_bars=warmup_bars
        )
    except Exception:
        return None

def _optimize_thresholds(dfetch: DataFetcher, calc: IndicatorCalculator, symbols: list[str],
                         suggested_buy: float, suggested_sell: float, buy_exit_suggest: float, sell_exit_suggest: float,
                         percentiles: dict, warmup_bars: int) -> list[dict]:
    buy_candidates = sorted({suggested_buy, percentiles.get(75, suggested_buy - 5), percentiles.get(85, suggested_buy), percentiles.get(90, suggested_buy + 2), percentiles.get(95, suggested_buy + 4)})
    sell_candidates = sorted({suggested_sell, percentiles.get(25, suggested_sell + 5), percentiles.get(15, suggested_sell), percentiles.get(10, suggested_sell - 2), percentiles.get(5, suggested_sell - 4)})
    combos = []
    for b in buy_candidates:
        if b is None: continue
        for s in sell_candidates:
            if s is None: continue
            if b - s < 5: continue
            combos.append((b,s))
    results = []
    symbols_use = symbols[:20]
    for b, s in combos:
        be = max(s + 1, b - 5)
        se = min(b - 1, s + 5)
        futures = []
        with ThreadPoolExecutor(max_workers=min(len(symbols_use), Settings.CALIB_PARALLEL_WORKERS)) as ex:
            for sym in symbols_use:
                futures.append(ex.submit(_simulate_for_symbol, dfetch, calc, sym, b, s, be, se, warmup_bars))
            global_wins = global_losses = global_trades = 0
            expectancies = []
            expectancies_after = []
            wins_after_weighted = 0.0
            max_consec = 0
            for f in as_completed(futures):
                sim_res = f.result()
                if not sim_res: continue
                global_trades += sim_res['total_trades']
                global_wins += sim_res['wins']
                global_losses += sim_res['losses']
                expectancies.append(sim_res['expectancy_pct'])
                expectancies_after.append(sim_res.get('expectancy_after_costs_pct', 0.0))
                try:
                    wins_after_weighted += (sim_res.get('winrate_after_costs', 0.0)/100.0) * sim_res['total_trades']
                except Exception: pass
                max_consec = max(max_consec, sim_res['max_consec_losses'])
        if global_trades == 0: continue
        winrate = (global_wins / global_trades * 100) if global_trades else 0.0
        expectancy_avg = float(np.mean(expectancies)) if expectancies else 0.0
        expectancy_after_avg = float(np.mean(expectancies_after)) if expectancies_after else 0.0
        winrate_after = (wins_after_weighted / global_trades * 100) if global_trades else 0.0
        results.append({'buy': round(b,2), 'sell': round(s,2), 'buy_exit': round(be,2), 'sell_exit': round(se,2), 'winrate': round(winrate,2), 'expectancy_pct': round(expectancy_avg,2), 'winrate_after_costs': round(winrate_after,2), 'expectancy_after_costs_pct': round(expectancy_after_avg,2), 'total_trades': global_trades, 'max_consec_losses': int(max_consec)})
    results.sort(key=lambda x: (x.get('expectancy_after_costs_pct', x['expectancy_pct']), x.get('winrate_after_costs', x['winrate'])), reverse=True)
    baseline = {'buy': round(suggested_buy,2), 'sell': round(suggested_sell,2), 'buy_exit': round(buy_exit_suggest,2), 'sell_exit': round(sell_exit_suggest,2), 'baseline': True}
    final = [baseline]
    for r in results:
        if r['buy'] == baseline['buy'] and r['sell'] == baseline['sell']: continue
        final.append(r)
        if len(final) >= 9: break
    return final

def run_calibration(pairs_limit: int = 40, save: bool = True, fast: bool = False, verbose: bool = False,
                    buy_threshold: float | None = None,
                    sell_threshold: float | None = None,
                    buy_exit_threshold: float | None = None,
                    sell_exit_threshold: float | None = None,
                    skip_optimize: bool = False,
                    apply_best: bool = False,
                    use_persisted: bool = True,
                    use_adx_filter: bool = True):
    dfetch = DataFetcher()
    pairs = dfetch.load_top_pairs()
    if pairs_limit and len(pairs) > pairs_limit:
        pairs = pairs[:pairs_limit]
    calc = IndicatorCalculator()
    all_scores: List[float] = []
    all_adx: List[float] = []
    all_atr_risk: List[float] = []
    symbol_stats = {}
    max_bars = 150 if fast else MAX_BARS_PER_SYMBOL
    warmup_bars = FAST_WARMUP_BARS if fast else DEFAULT_WARMUP_BARS
    per_symbol_meta: dict[str, dict] = {}
    adx_min_filter = getattr(Settings, 'ADX_MIN_THRESHOLD', None) if use_adx_filter else None
    for sym in pairs:
        try:
            df = dfetch.get_pair_data(sym, Settings.TIMEFRAME, auto_fetch=False)
            if df is None or df.empty or 'close' not in df.columns: continue
            df = df.sort_values('timestamp')
            if len(df) > max_bars: df = df.iloc[-max_bars:].copy()
            else: df = df.copy()
            indicators_full = _build_indicator_frames(df, calc)
            raw_scores = _iter_scores(df, indicators_full, calc, warmup_bars, adx_min=adx_min_filter)
            # NaN temizle
            sym_scores = [s for s in raw_scores if not (isinstance(s, float) and math.isnan(s))]
            if not sym_scores:
                continue
            all_scores.extend(sym_scores)
            try:
                scored_last = calc.score_indicators(df, indicators_full)
                adx_val = scored_last['scores'].get('ADX')
                if adx_val is not None: all_adx.append(float(adx_val))
                atr_rm = scored_last['scores'].get('ATR_RiskMult')
                if atr_rm is not None: all_atr_risk.append(float(atr_rm))
            except Exception: pass
            # İstatistikler
            sym_arr = np.array(sym_scores, dtype=float)
            symbol_stats[sym] = {
                'count': int(len(sym_scores)),
                'mean': float(np.mean(sym_arr)),
                'std': float(np.std(sym_arr)),
                'p25': float(np.percentile(sym_arr,25)),
                'p50': float(np.percentile(sym_arr,50)),
                'p75': float(np.percentile(sym_arr,75))
            }
            per_symbol_meta[sym] = {'bars_after_slice': len(df), 'warmup_bars': warmup_bars}
        except Exception as e:
            logger.error(f"{sym} kalibrasyon hata: {e}")
    if not all_scores:
        logger.error("Hiç skor üretilemedi")
        debug = {
            'error': 'no_scores',
            'pairs_checked': len(pairs),
            'pairs_with_scores': len(symbol_stats),
            'warmup_bars': warmup_bars,
            'fast': fast,
            'symbol_meta': per_symbol_meta
        }
        if verbose:
            logger.error(json.dumps(debug, indent=2, ensure_ascii=False))
        return debug
    # Global NaN filtreleme (her ihtimale karşı)
    cleaned = [s for s in all_scores if not (isinstance(s,float) and math.isnan(s))]
    if not cleaned:
        debug = {'error': 'only_nan_scores', 'pairs_with_scores': len(symbol_stats), 'warmup_bars': warmup_bars}
        if verbose:
            logger.error(json.dumps(debug, indent=2, ensure_ascii=False))
        return debug
    all_scores_np = np.array(cleaned, dtype=float)
    percentiles = {p: float(np.percentile(all_scores_np,p)) for p in [5,10,15,25,50,75,85,90,95]}
    suggested_buy = percentiles.get(85,80.0)
    suggested_sell = percentiles.get(15,40.0)
    buy_exit_suggest = max(suggested_sell + 1, suggested_buy - 5)
    sell_exit_suggest = min(suggested_buy - 1, suggested_sell + 5)
    if buy_exit_suggest >= suggested_buy: buy_exit_suggest = suggested_buy - 1
    if sell_exit_suggest <= suggested_sell: sell_exit_suggest = suggested_sell + 1

    overrides_used = False  # Manuel dışarıdan parametre verildiyse
    persisted_thresholds_loaded = False  # threshold_overrides.json'dan yüklendiyse
    if buy_threshold is not None and sell_threshold is not None:
        overrides_used = True
        # Use provided thresholds
        suggested_buy = float(buy_threshold)
        suggested_sell = float(sell_threshold)
        if buy_exit_threshold is not None:
            buy_exit_suggest = float(buy_exit_threshold)
        else:
            buy_exit_suggest = max(suggested_sell + 1, suggested_buy - 5)
        if sell_exit_threshold is not None:
            sell_exit_suggest = float(sell_exit_threshold)
        else:
            sell_exit_suggest = min(suggested_buy - 1, suggested_sell + 5)
        if buy_exit_suggest >= suggested_buy:
            buy_exit_suggest = suggested_buy - 1
        if sell_exit_suggest <= suggested_sell:
            sell_exit_suggest = suggested_sell + 1
    adx_percentiles = atr_risk_percentiles = None
    if all_adx:
        adx_np = np.array(all_adx)
        adx_percentiles = {p: float(np.percentile(adx_np,p)) for p in [5,25,50,75,95]}
    if all_atr_risk:
        atr_np = np.array(all_atr_risk)
        atr_risk_percentiles = {p: float(np.percentile(atr_np,p)) for p in [5,25,50,75,95]}
    # Persist edilmiş eşikleri (threshold_overrides.json) baseline olarak kullan (manuel override yoksa)
    persisted_path = os.path.join(Settings.DATA_PATH, 'processed', 'threshold_overrides.json')
    if use_persisted and not overrides_used and os.path.exists(persisted_path):
        try:
            with open(persisted_path, 'r', encoding='utf-8') as f:
                persisted = json.load(f)
            # Beklenen alanlar mevcutsa uygula
            if all(k in persisted for k in ('buy', 'sell', 'buy_exit', 'sell_exit')):
                suggested_buy = float(persisted['buy'])
                suggested_sell = float(persisted['sell'])
                buy_exit_suggest = float(persisted['buy_exit'])
                sell_exit_suggest = float(persisted['sell_exit'])
                persisted_thresholds_loaded = True
                if verbose:
                    logger.info(f"Persist edilmiş eşikler yüklendi (baseline olarak): {persisted}")
        except Exception as e:
            if verbose:
                logger.warning(f"Persist edilmiş eşikler okunamadı: {e}")

    global_trades = []
    global_wins = global_losses = 0
    global_expectancies = []
    global_expectancies_after = []
    global_wins_after_costs = 0.0
    max_consec_losses_global = 0
    trade_syms = list(symbol_stats.keys())
    if fast: trade_syms = trade_syms[:min(5,len(trade_syms))]
    for sym in trade_syms:
        try:
            df = dfetch.get_pair_data(sym, Settings.TIMEFRAME, auto_fetch=False)
            if df is None or df.empty or 'close' not in df.columns: continue
            df = df.sort_values('timestamp')
            if len(df) > max_bars: df = df.iloc[-max_bars:].copy()
            else: df = df.copy()
            indicators_full = _build_indicator_frames(df, calc)
            sim_res = _simulate_trades(
                df, indicators_full, calc,
                suggested_buy, suggested_sell, buy_exit_suggest, sell_exit_suggest,
                use_next_bar_fill=Settings.USE_NEXT_BAR_FILL,
                warmup_bars=warmup_bars,
                adx_min=adx_min_filter
            )
            symbol_stats[sym]['trades'] = sim_res
            global_trades.append(sim_res['total_trades'])
            global_wins += sim_res['wins']
            global_losses += sim_res['losses']
            global_expectancies.append(sim_res['expectancy_pct'])
            global_expectancies_after.append(sim_res.get('expectancy_after_costs_pct',0.0))
            try: global_wins_after_costs += (sim_res.get('winrate_after_costs',0.0)/100.0) * sim_res['total_trades']
            except Exception: pass
            max_consec_losses_global = max(max_consec_losses_global, sim_res['max_consec_losses'])
        except Exception as e:
            logger.error(f"{sym} trade sim hata: {e}")
    total_trades_global = sum(global_trades)
    winrate_global = (global_wins / total_trades_global * 100) if total_trades_global else 0.0
    avg_expectancy_global = float(np.mean(global_expectancies)) if global_expectancies else 0.0
    winrate_after_costs_global = (global_wins_after_costs / total_trades_global * 100) if total_trades_global else 0.0
    avg_expectancy_after_global = float(np.mean(global_expectancies_after)) if global_expectancies_after else 0.0
    optimization_candidates: list[dict] = []
    if (not fast) and (not skip_optimize) and (not overrides_used):  # persisted baseline olsa bile optimize et
        optimization_candidates = _optimize_thresholds(
            dfetch, calc, list(symbol_stats.keys()),
            suggested_buy, suggested_sell, buy_exit_suggest, sell_exit_suggest,
            percentiles, warmup_bars
        )
        try:
            out_dir = os.path.join(Settings.DATA_PATH,'processed')
            os.makedirs(out_dir, exist_ok=True)
            cand_path = os.path.join(out_dir,'optimization_candidates.json')
            with open(cand_path,'w',encoding='utf-8') as f: json.dump(optimization_candidates,f,indent=2,ensure_ascii=False)
        except Exception: pass
    applied_thresholds: dict | None = None
    # Eğer apply_best istenir ve optimize sonuçları var ise (ve override verilmemişse) ilk non-baseline adayı uygula
    if apply_best and not overrides_used:
        best_candidate = None
        if optimization_candidates:
            for c in optimization_candidates:
                if not c.get('baseline'):
                    best_candidate = c
                    break
        if best_candidate:
            suggested_buy = best_candidate['buy']
            suggested_sell = best_candidate['sell']
            buy_exit_suggest = best_candidate['buy_exit']
            sell_exit_suggest = best_candidate['sell_exit']
            applied_thresholds = {
                'buy': suggested_buy,
                'sell': suggested_sell,
                'buy_exit': buy_exit_suggest,
                'sell_exit': sell_exit_suggest,
                'source': 'best_candidate'
            }
        else:
            if verbose:
                logger.warning("apply_best istendi fakat baseline dışı alternatif aday bulunamadı (tüm kombinasyonlar baseline ile aynı olabilir / filtreler eliyor). Winrate değişmemesi normal.")
    if overrides_used and not applied_thresholds:
        applied_thresholds = {
            'buy': suggested_buy,
            'sell': suggested_sell,
            'buy_exit': buy_exit_suggest,
            'sell_exit': sell_exit_suggest,
            'source': 'overrides'
        }

    summary = {
        'generated_at': datetime.utcnow().isoformat(),
        'fast': fast,
        'warmup_bars': warmup_bars,
        'pairs_used': len(symbol_stats),
        'total_points': int(len(all_scores)),
    'threshold_overrides_used': overrides_used,
    'persisted_thresholds_loaded': persisted_thresholds_loaded,
        'overrides': {
            'buy': suggested_buy if overrides_used else None,
            'sell': suggested_sell if overrides_used else None,
            'buy_exit': buy_exit_suggest if overrides_used else None,
            'sell_exit': sell_exit_suggest if overrides_used else None
        } if overrides_used else None,
        'applied_thresholds': applied_thresholds,
        'global': {
            'mean': float(np.mean(all_scores_np)),
            'std': float(np.std(all_scores_np)),
            'min': float(np.min(all_scores_np)),
            'max': float(np.max(all_scores_np)),
            'percentiles': percentiles,
            'suggested_buy_threshold': suggested_buy,
            'suggested_sell_threshold': suggested_sell,
            'adx_percentiles': adx_percentiles,
            'atr_risk_percentiles': atr_risk_percentiles,
            'suggested_buy_exit_threshold': float(buy_exit_suggest),
            'suggested_sell_exit_threshold': float(sell_exit_suggest),
            'trade_stats': {
                'total_trades': total_trades_global,
                'wins': global_wins,
                'losses': global_losses,
                'winrate': round(winrate_global, 2),
                'avg_expectancy_pct': round(avg_expectancy_global, 2),
                'winrate_after_costs': round(winrate_after_costs_global, 2),
                'avg_expectancy_after_costs_pct': round(avg_expectancy_after_global, 2),
                'max_consec_losses': int(max_consec_losses_global),
                'commission_pct_per_side': Settings.COMMISSION_PCT_PER_SIDE,
                'slippage_pct_per_side': Settings.SLIPPAGE_PCT_PER_SIDE,
                'next_bar_fill': Settings.USE_NEXT_BAR_FILL
            },
            'optimization': {
                'candidates': optimization_candidates
            }
        },
        'symbols': symbol_stats
    }
    if save:
        out_dir = os.path.join(Settings.DATA_PATH,'processed')
        os.makedirs(out_dir, exist_ok=True)
        out_path = os.path.join(out_dir,'calibration.json')
        try:
            with open(out_path,'w',encoding='utf-8') as f: json.dump(summary,f,indent=2,ensure_ascii=False)
            logger.info(f"Kalibrasyon kaydedildi: {out_path}")
        except Exception as e: logger.error(f"Kalibrasyon dosyası yazılamadı: {e}")

    # Seçilen eşikleri persist etmek için ayrı bir dosya yaz (settings.py yeniden yükleme ile devreye girecek)
    if applied_thresholds or (overrides_used and apply_best):
        try:
            th = applied_thresholds or {
                'buy': suggested_buy,
                'sell': suggested_sell,
                'buy_exit': buy_exit_suggest,
                'sell_exit': sell_exit_suggest,
                'source': 'overrides'
            }
            out_dir = os.path.join(Settings.DATA_PATH,'processed')
            os.makedirs(out_dir, exist_ok=True)
            th_path = os.path.join(out_dir,'threshold_overrides.json')
            with open(th_path,'w',encoding='utf-8') as f:
                json.dump(th, f, indent=2, ensure_ascii=False)
            if verbose:
                logger.info(f"Threshold overrides yazıldı: {th_path}")
        except Exception as e:
            logger.error(f"Threshold overrides yazılamadı: {e}")
    return summary

def run_threshold_evaluation(buy: float, sell: float, buy_exit: float | None = None, sell_exit: float | None = None,
                             pairs_limit: int = 40, fast: bool = False, verbose: bool = False) -> dict:
    """Sadece verilen eşiklerle hızlı değerlendirme döndürür (optimizasyon yapmaz)."""
    return run_calibration(pairs_limit=pairs_limit, save=False, fast=fast, verbose=verbose,
                           buy_threshold=buy, sell_threshold=sell,
                           buy_exit_threshold=buy_exit, sell_exit_threshold=sell_exit,
                           skip_optimize=True)

if __name__ == "__main__":
    # Örnek: override eşik ile çalıştır
    out = run_threshold_evaluation(50.19, 16.66, 45.19, 21.66, pairs_limit=30, fast=False, verbose=True)
    if out and 'error' not in out:
        print(json.dumps(out['global']['trade_stats'], indent=2, ensure_ascii=False))
