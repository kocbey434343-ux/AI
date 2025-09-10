import json
import warnings

import numpy as np
import pandas as pd
from config.settings import Settings
from ta.momentum import RSIIndicator, StochasticOscillator, WilliamsRIndicator
from ta.trend import MACD, ADXIndicator, CCIIndicator, EMAIndicator
from ta.volatility import AverageTrueRange, BollingerBands


class IndicatorCalculator:
    def __init__(self):
        self.indicators_config = self.load_config()

    def load_config(self):
        with open(Settings.INDICATORS_CONFIG, "r") as f:
            return json.load(f)

    def calculate_all_indicators(self, df: pd.DataFrame):
        """
        Calculate all technical indicators for the given DataFrame.

        Args:
            df (pd.DataFrame): The input DataFrame containing market data.

        Returns:
            dict: A dictionary containing the calculated indicator values.
        """
        df = df.copy()
        results = {
            'close': df['close']  # Add close price series for signal calculations
        }
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", category=RuntimeWarning, module=r"ta\.trend")
            with np.errstate(divide='ignore', invalid='ignore'):
                for ic in self.indicators_config['indicators']:
                    name = ic.get('name')
                    params = ic.get('params', {})
                    try:
                        if name == "RSI":
                            results[name] = RSIIndicator(close=df['close'], window=params.get('timeperiod', 14)).rsi()
                        elif name == "MACD":
                            macd = MACD(close=df['close'],
                                        window_slow=params.get('slowperiod', 26),
                                        window_fast=params.get('fastperiod', 12),
                                        window_sign=params.get('signalperiod', 9))
                            results[name] = {
                                'macd': macd.macd(),
                                'signal': macd.macd_signal(),
                                'histogram': macd.macd_diff()
                            }
                        elif name == "Bollinger Bands":
                            bb = BollingerBands(close=df['close'],
                                                window=params.get('timeperiod', 20),
                                                window_dev=params.get('nbdevup', 2))
                            results[name] = {
                                'upper': bb.bollinger_hband(),
                                'middle': bb.bollinger_mavg(),
                                'lower': bb.bollinger_lband()
                            }
                        elif name == "Stochastic":
                            st = StochasticOscillator(
                                high=df['high'], low=df['low'], close=df['close'],
                                window=params.get('fastk_period', 14),
                                smooth_window=params.get('slowk_period', 3)
                            )
                            results[name] = {
                                'slowk': st.stoch(),
                                'slowd': st.stoch_signal()
                            }
                        elif name == "Williams %R":
                            wr = WilliamsRIndicator(
                                high=df['high'], low=df['low'], close=df['close'],
                                lbp=params.get('timeperiod', 14)
                            )
                            results[name] = wr.williams_r()
                        elif name == "CCI":
                            cci = CCIIndicator(
                                high=df['high'], low=df['low'], close=df['close'],
                                window=params.get('timeperiod', 20), constant=0.015
                            )
                            results[name] = cci.cci()
                        elif name == "ATR":
                            atr = AverageTrueRange(
                                high=df['high'], low=df['low'], close=df['close'],
                                window=params.get('timeperiod', 14)
                            )
                            results[name] = atr.average_true_range()
                        elif name == "EMA":
                            ema = EMAIndicator(close=df['close'], window=params.get('timeperiod', 50)).ema_indicator()
                            results[name] = ema
                        elif name == "ADX":
                            adx = ADXIndicator(high=df['high'], low=df['low'], close=df['close'], window=params.get('timeperiod', 14))
                            adx_dict = {
                                'adx': adx.adx(),
                                'plus_di': adx.adx_pos(),
                                'minus_di': adx.adx_neg()
                            }
                            # Sanitize ADX outputs to avoid inf/NaN propagation
                            for k, v in list(adx_dict.items()):
                                if hasattr(v, 'replace'):
                                    v = v.replace([np.inf, -np.inf], np.nan).bfill().ffill()
                                    adx_dict[k] = v
                            results[name] = adx_dict
                    except Exception:
                        # Process individual indicator error and continue
                        continue
        return results

    def score_indicators(self, df: pd.DataFrame, indicators: dict):
        """Gelistirilmis puanlama (agirliklar + ATR penaltesi + osilator birlestirme)."""
        price = df['close'].iloc[-1]
        scores = {}

        # Weights (easy configuration dict)
        base_weights = {
            'MACD': 1.3,
            'EMA': 1.1,
            'RSI': 1.0,
            'Bollinger Bands': 0.9,
            'Oscillator': 0.9,
            'CCI': 0.6,
            'ADX': 0.0  # ADX not directly added, modulates weight of others
        }

        # Raw normalization helpers
        def norm_macd():
            try:
                hist = indicators['MACD']['histogram'].iloc[-1]
                # Scale with ATR (normalize very small/large histograms)
                atr_pct = None
                if 'ATR' in indicators:
                    atr_val = indicators['ATR'].iloc[-1]
                    atr_pct = (atr_val / max(price, 1e-12))
                scale = 1.0
                if atr_pct and atr_pct > 0:
                    scale = max(0.5, min(3.0, 1.0 / (atr_pct * 10)))  # higher volatility weakens histogram effect slightly
                return float(np.clip(50 + 50 * np.tanh(hist * scale), 0, 100))
            except Exception:
                return 50.0

        def norm_bbands():
            try:
                upper = indicators['Bollinger Bands']['upper'].iloc[-1]
                lower = indicators['Bollinger Bands']['lower'].iloc[-1]
                band = max(upper - lower, 1e-12)
                pos = (price - lower) / band
                pos = float(np.clip(pos, 0, 1))
                # Narrow band filter (squeeze) -> reduce its effect
                squeeze = (band / max(price, 1e-12))
                if squeeze < 0.01:  # band width less than 1%
                    base = 50 + (pos - 0.5) * 40  # reduce effect
                else:
                    base = pos * 100
                return float(np.clip(base, 0, 100))
            except Exception:
                return 50.0

        def norm_rsi():
            try:
                return float(np.clip(indicators['RSI'].iloc[-1], 0, 100))
            except Exception:
                return 50.0

        def norm_ema():
            try:
                ema = indicators['EMA'].iloc[-1]
                diff = (price - ema) / max(price, 1e-12)
                # Softer scale (previous *10 was too aggressive)
                return float(np.clip(50 + 50 * np.tanh(diff * 5), 0, 100))
            except Exception:
                return 50.0

        def norm_cci():
            try:
                cci = indicators['CCI'].iloc[-1]
                return float(np.clip(50 + (cci / 250) * 50, 0, 100))  # wider band
            except Exception:
                return 50.0
        def norm_oscillator():
            st_val = None
            wr_val = None
            try:
                if 'Stochastic' in indicators:
                    st_val = float(np.clip(indicators['Stochastic']['slowk'].iloc[-1], 0, 100))
            except Exception:
                st_val = None
            try:
                if 'Williams %R' in indicators:
                    wr = indicators['Williams %R'].iloc[-1]
                    wr_val = float(np.clip(100 + wr, 0, 100))
            except Exception:
                wr_val = None
            vals = [v for v in [st_val, wr_val] if v is not None]
            if not vals:
                return 50.0
            return float(sum(vals) / len(vals))

        def norm_adx():
            try:
                adx_val = indicators['ADX']['adx'].iloc[-1]
                return float(np.clip(adx_val, 0, 100))
            except Exception:
                return 50.0

        # Hesapla
        component_scores = {}
        if 'MACD' in indicators:
            component_scores['MACD'] = norm_macd()
        if 'EMA' in indicators:
            component_scores['EMA'] = norm_ema()
        if 'RSI' in indicators:
            component_scores['RSI'] = norm_rsi()
        if 'Bollinger Bands' in indicators:
            component_scores['Bollinger Bands'] = norm_bbands()
        # Combined oscillator
        if 'Stochastic' in indicators or 'Williams %R' in indicators:
            component_scores['Oscillator'] = norm_oscillator()
        if 'CCI' in indicators:
            component_scores['CCI'] = norm_cci()
        if 'ADX' in indicators:
            component_scores['ADX'] = norm_adx()

        # Weighted average
        # ADX regime-based adaptation (if trend is weak, reduce trend-focused weights, increase mean-reversion components)
        weights = base_weights.copy()
        adx_level = component_scores.get('ADX')
        if adx_level is not None:
            if adx_level < 20:  # weak trend
                weights['MACD'] *= 0.7
                weights['EMA'] *= 0.7
                weights['Bollinger Bands'] *= 1.2
                weights['Oscillator'] *= 1.1
            elif adx_level > 35:  # strong trend
                weights['MACD'] *= 1.2
                weights['EMA'] *= 1.1
                weights['Oscillator'] *= 0.9
                weights['Bollinger Bands'] *= 0.85
        # Normalized weighted average
        contributions = {}
        w_sum = 0.0
        w_total = 0.0
        for name, val in component_scores.items():
            w = weights.get(name, 1.0)
            contributions[name] = val * w
            w_sum += val * w
            w_total += w
        core_score = (w_sum / w_total) if w_total else 50.0

        # ATR risk penalty (trim slightly if volatility is high)
        risk_multiplier = 1.0
        if 'ATR' in indicators:
            try:
                atr_val = indicators['ATR'].iloc[-1]
                atr_pct = atr_val / max(price, 1e-12)
                # 0 -> 1.0 (no penalty) ; 0.05 and above -> up to 30% reduction
                penalty = min(0.30, max(0.0, (atr_pct - 0.01) * (0.30 / 0.04)))  # 1% üstü artan ceza ~5% tepe
                risk_multiplier = 1.0 - penalty
            except Exception:
                pass

        final_score = core_score * risk_multiplier

        # Skorlar donerken orijinal indikator isimlerini de kullaniciya gostermek icin
        # component_scores + ATR risk ayri dondur.
        out_scores = {}
        out_scores.update(component_scores)
        if 'ATR' in indicators:
            out_scores['ATR_RiskMult'] = risk_multiplier * 100  # bilgilendirme için %

        return {
            'scores': out_scores,
            'total_score': final_score,
            'contributions': contributions,
            'signal': self.get_signal(final_score)
        }

    def get_signal(self, score: float) -> str:
        """
        Determine the trading signal based on the overall score.

        Args:
            score (float): The overall score calculated from the indicator scores.

        Returns:
            str: The trading signal ('AL', 'SAT', or 'BEKLE').
        """
        # Histerezis icin onceki sinyal (state) tutulabilir; basit versiyonda direkt threshold + exit threshold.
        # Burada sadece ana esikleri kullaniyoruz; GUI / caller katmaninda state eklenebilir.
        if score >= Settings.BUY_SIGNAL_THRESHOLD:
            return "AL"
        if score <= Settings.SELL_SIGNAL_THRESHOLD:
            return "SAT"
        return "BEKLE"

    def _calculate_bollinger_signal(self, indicators):
        """Bollinger Bands sinyal hesaplama"""
        try:
            bb_data = indicators.get('Bollinger Bands', {})
            if not bb_data:
                return {'value': 50, 'signal': 'NEUTRAL', 'error': 'No BB data'}

            upper = bb_data['upper'].iloc[-1] if hasattr(bb_data.get('upper'), 'iloc') else bb_data.get('upper')
            lower = bb_data['lower'].iloc[-1] if hasattr(bb_data.get('lower'), 'iloc') else bb_data.get('lower')
            middle = bb_data['middle'].iloc[-1] if hasattr(bb_data.get('middle'), 'iloc') else bb_data.get('middle')

            # Close price from indicators (now available)
            close = indicators['close'].iloc[-1] if 'close' in indicators else middle

            if not all([upper, lower, middle, close]):
                return {'value': 50, 'signal': 'NEUTRAL', 'error': 'Missing BB values'}

            # Band position
            band_width = upper - lower
            if band_width <= 0:
                position = 0.5
            else:
                position = (close - lower) / band_width
                position = max(0, min(1, position))  # Clamp 0-1

            # Bollinger signal - more dynamic
            if position < 0.2:
                value = 20  # Near lower band - potential buy
                signal = 'BUY'
            elif position > 0.8:
                value = 80  # Near upper band - potential sell
                signal = 'SELL'
            elif position > 0.6:
                value = 65  # Above middle - bullish
                signal = 'BUY'
            elif position < 0.4:
                value = 35  # Below middle - bearish
                signal = 'SELL'
            else:
                value = 50  # Around middle - neutral
                signal = 'NEUTRAL'

            return {
                'value': value,
                'band_position': position,
                'close': close,
                'upper': upper,
                'lower': lower,
                'middle': middle,
                'band_width': band_width,
                'signal': signal
            }
        except Exception as e:
            return {'value': 50, 'signal': 'NEUTRAL', 'error': f'BB calc error: {e!s}'}

    def calculate_confluence_score(self, df):
        """Calculate confluence score from RSI+MACD+BB"""
        try:
            indicators = self.calculate_all_indicators(df)

            # Calculate individual component signals
            rsi_value = indicators.get('RSI', pd.Series([50])).iloc[-1]
            macd_hist = indicators.get('MACD', {}).get('histogram', pd.Series([0])).iloc[-1]
            bb_signal = self._calculate_bollinger_signal(indicators)

            # Convert to 0-100 scale signals
            rsi_signal = {'value': rsi_value, 'signal': 'BUY' if rsi_value < 30 else 'SELL' if rsi_value > 70 else 'NEUTRAL'}

            # MACD histogram signal
            macd_value = 75 if macd_hist > 0 else 25 if macd_hist < 0 else 50
            macd_signal = {'value': macd_value, 'signal': 'BUY' if macd_hist > 0 else 'SELL' if macd_hist < 0 else 'NEUTRAL'}

            # Average the three signals
            total_value = (rsi_signal['value'] + macd_signal['value'] + bb_signal['value']) / 3
            confluence_score = min(100, max(0, total_value))

            # Determine overall signal direction
            buy_signals = sum(1 for sig in [rsi_signal, macd_signal, bb_signal] if sig['signal'] == 'BUY')
            sell_signals = sum(1 for sig in [rsi_signal, macd_signal, bb_signal] if sig['signal'] == 'SELL')

            if buy_signals >= 2:
                direction = 'AL'
            elif sell_signals >= 2:
                direction = 'SAT'
            else:
                direction = 'BEKLE'

            return {
                'confluence_score': confluence_score,
                'signal_direction': direction,
                'component_signals': {
                    'rsi': rsi_signal,
                    'macd': macd_signal,
                    'bollinger': bb_signal
                }
            }

        except Exception as e:
            return {
                'confluence_score': 0.0,
                'signal_direction': 'BEKLE',
                'error': f'Confluence calc error: {e!s}',
                'component_signals': {}
            }

    # ---- Legacy test wrapper methods ----
    def calculate_rsi(self, df: pd.DataFrame):
        return RSIIndicator(close=df['close'], window=14).rsi()

    def calculate_macd(self, df: pd.DataFrame):
        macd = MACD(close=df['close'], window_slow=26, window_fast=12, window_sign=9)
        return {
            'macd': macd.macd(),
            'signal': macd.macd_signal(),
            'histogram': macd.macd_diff()
        }

    def calculate_bollinger_bands(self, df: pd.DataFrame):
        bb = BollingerBands(close=df['close'], window=20, window_dev=2)
        return {
            'upper': bb.bollinger_hband(),
            'middle': bb.bollinger_mavg(),
            'lower': bb.bollinger_lband()
        }

    @staticmethod
    def calculate_moving_average(data, window_size):
        if window_size <= 0:
            raise ValueError("window_size > 0 olmali")
        data = list(data)
        if len(data) < window_size:
            return []
        out = []
        cumsum = 0.0
        for i, v in enumerate(data):
            cumsum += v
            if i >= window_size:
                cumsum -= data[i - window_size]
            if i >= window_size - 1:
                out.append(cumsum / window_size)
        return out
