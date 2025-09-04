import pytest

# Proje modulleri
from config.settings import Settings
from src.api.binance_api import BinanceAPI
import src.api.binance_api as binance_api_mod


class _FakeClient:
    def __init__(self, api_key=None, api_secret=None, testnet=None):
        self.api_key = api_key
        self.api_secret = api_secret
        self.testnet = testnet

    # Kullanilan bazi helperlar icin stub
    def get_server_time(self):
        return {"serverTime": 0}


def test_endpoint_safety_blocks_prod_when_not_allowed(monkeypatch):
    # OFFLINE kapali, TESTNET kapali, ALLOW_PROD kapali => RuntimeError beklenir
    monkeypatch.setattr(Settings, "OFFLINE_MODE", False, raising=False)
    monkeypatch.setattr(Settings, "USE_TESTNET", False, raising=False)
    monkeypatch.setattr(Settings, "ALLOW_PROD", False, raising=False)

    with pytest.raises(RuntimeError):
        BinanceAPI()


def test_endpoint_allows_prod_when_explicitly_allowed(monkeypatch):
    # OFFLINE kapali, TESTNET kapali, ALLOW_PROD acik => baglanti serbest
    # Gercek Client'a gitmemek icin Client'i fake ile degistiriyoruz
    monkeypatch.setattr(binance_api_mod, "Client", _FakeClient, raising=True)
    monkeypatch.setattr(Settings, "OFFLINE_MODE", False, raising=False)
    monkeypatch.setattr(Settings, "USE_TESTNET", False, raising=False)
    monkeypatch.setattr(Settings, "ALLOW_PROD", True, raising=False)

    api = BinanceAPI()
    assert isinstance(api.client, _FakeClient)
    # testnet False beklenir
    assert api.client.testnet is False


def test_endpoint_uses_testnet_by_default(monkeypatch):
    # OFFLINE kapali, TESTNET acik (default guvenli), ALLOW_PROD onemsiz => testnet kullanilmali
    monkeypatch.setattr(binance_api_mod, "Client", _FakeClient, raising=True)
    monkeypatch.setattr(Settings, "OFFLINE_MODE", False, raising=False)
    monkeypatch.setattr(Settings, "USE_TESTNET", True, raising=False)
    monkeypatch.setattr(Settings, "ALLOW_PROD", False, raising=False)

    api = BinanceAPI()
    assert isinstance(api.client, _FakeClient)
    assert api.client.testnet is True
