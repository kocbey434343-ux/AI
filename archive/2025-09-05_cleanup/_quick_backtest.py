from src.backtest.realistic_backtest import RealisticBacktester

if __name__ == "__main__":
    bt = RealisticBacktester()
    symbols = ['BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'ADAUSDT', 'XRPUSDT']
    results = bt.run_backtest(symbols=symbols, lookback_days=120, risk_per_trade=1.0, max_positions=3)
    # Print concise summary
    print("TOTAL_TRADES=", results.get('total_trades'))
    print("WIN_RATE=", results.get('win_rate'))
    print("TOTAL_PNL_PCT=", results.get('total_pnl_pct'))
