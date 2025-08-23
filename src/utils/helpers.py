import json
import pandas as pd
from datetime import datetime
from config.settings import Settings

def save_json(data, filename):
    """Veriyi JSON olarak kaydet"""
    filepath = f"{Settings.DATA_PATH}/processed/{filename}"
    with open(filepath, 'w') as f:
        json.dump(data, f, indent=2, default=str)
    return filepath

def load_json(filename):
    """JSON veriyi yükle"""
    filepath = f"{Settings.DATA_PATH}/processed/{filename}"
    try:
        with open(filepath, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return None

def save_csv(df, filename):
    """DataFrame'i CSV olarak kaydet"""
    filepath = f"{Settings.DATA_PATH}/processed/{filename}"
    df.to_csv(filepath, index=False)
    return filepath

def format_timestamp(ts):
    """Zaman damgasını formatla"""
    if isinstance(ts, pd.Timestamp):
        return ts.strftime('%Y-%m-%d %H:%M:%S')
    elif isinstance(ts, str):
        return ts
    else:
        return datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S')

def calculate_pnl(entry_price, exit_price, side, quantity):
    """Kar/zarar hesapla"""
    if side == "BUY":
        pnl = (exit_price - entry_price) * quantity
    else:  # SELL
        pnl = (entry_price - exit_price) * quantity
    return pnl

def calculate_win_rate(trades):
    """Kazanma oranını hesapla"""
    if not trades:
        return 0

    wins = sum(1 for trade in trades if trade['pnl'] > 0)
    return wins / len(trades) * 100

def calculate_sharpe_ratio(returns, risk_free_rate=0.01):
    """Sharpe oranı hesapla"""
    if len(returns) < 2:
        return 0

    excess_returns = [r - risk_free_rate for r in returns]
    return (sum(excess_returns) / len(excess_returns)) / (pd.Series(excess_returns).std() * (252 ** 0.5))
