import unittest
import pandas as pd
import numpy as np
from src.indicators import IndicatorCalculator

class TestIndicators(unittest.TestCase):
    def setUp(self):
        self.indicator_calc = IndicatorCalculator()

        # Test verisi oluştur
        np.random.seed(42)
        dates = pd.date_range('2023-01-01', periods=100)
        self.df = pd.DataFrame({
            'timestamp': dates,
            'open': np.random.uniform(100, 200, 100),
            'high': np.random.uniform(200, 250, 100),
            'low': np.random.uniform(50, 100, 100),
            'close': np.random.uniform(100, 200, 100),
            'volume': np.random.uniform(1000, 10000, 100)
        })

    def test_rsi(self):
        """RSI hesaplama testi"""
        rsi = self.indicator_calc.calculate_rsi(self.df)
        self.assertEqual(len(rsi), 100)
        self.assertTrue(all(0 <= x <= 100 for x in rsi[14:] if not np.isnan(x)))

    def test_macd(self):
        """MACD hesaplama testi"""
        macd = self.indicator_calc.calculate_macd(self.df)
        self.assertIn('macd', macd)
        self.assertIn('signal', macd)
        self.assertIn('histogram', macd)
        self.assertEqual(len(macd['macd']), 100)

    def test_bollinger_bands(self):
        """Bollinger Bantları hesaplama testi"""
        bb = self.indicator_calc.calculate_bollinger_bands(self.df)
        self.assertIn('upper', bb)
        self.assertIn('middle', bb)
        self.assertIn('lower', bb)
        self.assertEqual(len(bb['upper']), 100)

    def test_adx_in_all_indicators(self):
        indicators = self.indicator_calc.calculate_all_indicators(self.df)
        # ADX config eklendi ise sözlükte bulunmalı
        if 'ADX' in [ic['name'] for ic in self.indicator_calc.indicators_config['indicators']]:
            self.assertIn('ADX', indicators)
            self.assertIn('adx', indicators['ADX'])
            self.assertEqual(len(indicators['ADX']['adx']), 100)

    def test_score_indicators(self):
        """İndikatör puanlama testi"""
        indicators = self.indicator_calc.calculate_all_indicators(self.df)
        scores = self.indicator_calc.score_indicators(self.df, indicators)

        self.assertIn('scores', scores)
        self.assertIn('total_score', scores)
        self.assertIn('signal', scores)
        self.assertTrue(0 <= scores['total_score'] <= 100)
        self.assertIn(scores['signal'], ['AL', 'SAT', 'BEKLE'])

if __name__ == '__main__':
    unittest.main()
