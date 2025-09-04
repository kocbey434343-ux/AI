import pytest


def _filters_stub():
    return {
        'LOT_SIZE': {'filterType': 'LOT_SIZE', 'minQty': '0.001', 'stepSize': '0.001'},
        'PRICE_FILTER': {'filterType': 'PRICE_FILTER', 'minPrice': '0.01', 'tickSize': '0.01'},
        # MIN_NOTIONAL kasitli olarak eklenmedi ki notional kontrolu tetiklenmesin
    }


class _FakeClientOK:
    def __init__(self):
        self.calls = []

    def create_oco_order(self, **_):
        # OCO'yu hataya dusurmek icin exception firlat
        raise RuntimeError("OCO not supported in fake client")

    def create_order(self, **kwargs):
        # Cagrilari kaydet ve basarili bir orderId dondur
        self.calls.append(kwargs)
    # Stabil orderId icin basit sayac
        oid = 1000 + len(self.calls)
        return {'orderId': oid, 'echo': kwargs}


class _FakeClientTPFail(_FakeClientOK):
    def create_order(self, **kwargs):
        # LIMIT ise hata; STOP_LOSS_LIMIT ise basarili
        if kwargs.get('type') == 'LIMIT':
            raise RuntimeError('LIMIT failed')
        return super().create_order(**kwargs)


@pytest.mark.parametrize(
    "fake_client, expected_count",
    [(_FakeClientOK, 2), (_FakeClientTPFail, 1)],
)
def test_spot_oco_fallback_creates_limit_and_stop(monkeypatch, fake_client, expected_count):
    # OFFLINE modunu ac
    from config.settings import Settings
    monkeypatch.setattr(Settings, 'OFFLINE_MODE', True, raising=False)
    monkeypatch.setattr(Settings, 'USE_TESTNET', True, raising=False)

    # API'yi kur ve client/filters'i stubla
    from src.api.binance_api import BinanceAPI
    api = BinanceAPI(mode='spot')

    fc = fake_client()
    api.client = fc
    # Filters cache bypass
    monkeypatch.setattr(api, '_get_filters_cached', lambda _symbol, _force_refresh=False: _filters_stub())

    symbol = 'BTCUSDT'
    side = 'BUY'  # cikis SELL olacak
    qty = 0.01  # minQty 0.001'in uzerinde
    tp = 120.0
    sl = 80.0

    resp = api.place_oco_order(symbol, side, qty, tp, sl)

    assert isinstance(resp, dict), "Response dict olmali"
    assert resp.get('fallback') is True, "Fallback bayragi bekleniyor"
    reports = resp.get('orderReports') or []
    assert len(reports) == expected_count

    # Cagrilari incele: SELL LIMIT ve SELL STOP_LOSS_LIMIT beklenir (side BUY ise cikis SELL)
    order_types = [c.get('type') for c in getattr(fc, 'calls', [])]
    sides = [c.get('side') for c in getattr(fc, 'calls', [])]
    # LIMIT varsa SELL olmalidir; STOP_LOSS_LIMIT varsa SELL olmalidir
    for t, s in zip(order_types, sides):
        assert s == 'SELL'
        assert t in ('LIMIT', 'STOP_LOSS_LIMIT')
