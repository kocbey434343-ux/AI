from src.data_fetcher import DataFetcher
from src.utils.structured_log import clear_slog_events, get_slog_events
import os, json

class DummyAPI:
    def get_top_pairs(self, limit):
        return ['AAAUSDT','BBBUSDT','CCCUSDT']
    def get_historical_data(self, symbol, interval, days):
        import pandas as pd, datetime as dt
        rows = [{'timestamp': dt.datetime.utcnow(), 'open':1,'high':1,'low':1,'close':1,'volume':1}]
        return pd.DataFrame(rows)


def _make_fetcher(tmp):
    os.makedirs(f"{tmp}/raw", exist_ok=True)
    class _Settings:
        DATA_PATH = tmp
        TOP_PAIRS_COUNT = 3
        BACKTEST_DAYS = 30
    import src.data_fetcher as df_mod
    df_mod.Settings = _Settings  # type: ignore
    f = DataFetcher()
    f.api = DummyAPI()
    return f


def test_cr0041_auto_refresh_basic(tmp_path):
    f = _make_fetcher(str(tmp_path))
    top_file = f"{f.data_path}/top_150_pairs.json"
    with open(top_file,'w',encoding='utf-8') as fp:
        json.dump(['AAAUSDT','BBBUSDT','CCCUSDT'], fp)
    fresh_path = f"{f.data_path}/raw/AAAUSDT_1h.csv"
    with open(fresh_path,'w',encoding='utf-8') as fp:
        fp.write('timestamp,open,high,low,close,volume\n')
    os.utime(fresh_path, None)
    clear_slog_events()
    summary = f.auto_refresh_stale(interval='1h', max_age_minutes=120, batch_limit=5, days=1)
    assert summary['attempted']
    evts = get_slog_events()
    assert any(e['event']=='stale_refresh' for e in evts)
    for sym in summary['attempted']:
        assert os.path.exists(f"{f.data_path}/raw/{sym}_1h.csv")
