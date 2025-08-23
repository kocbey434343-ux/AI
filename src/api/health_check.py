import time
from src.api.binance_api import BinanceAPI
from config.settings import Settings
from binance.enums import SIDE_BUY, ORDER_TYPE_MARKET
from binance.exceptions import BinanceAPIException

class HealthChecker:
    def __init__(self):
        self.api = BinanceAPI()
        self.last_check = None
        self.is_healthy = True

    def check_connection(self):
        """API bağlantısını kontrol et"""
        try:
            start_time = time.time()
            self.api.get_server_time()
            response_time = time.time() - start_time

            if response_time > 5:  # 5 saniyeden uzunsa yavaş bağlantı
                self.is_healthy = False
                return False, f"Yavaş bağlantı: {response_time:.2f}s"

            self.is_healthy = True
            self.last_check = time.time()
            return True, "Bağlantı sağlıklı"

        except Exception as e:
            self.is_healthy = False
            return False, f"Bağlantı hatası: {str(e)}"

    def check_api_permissions(self):
        """API izinlerini kontrol et"""
        try:
            # Okuma izni kontrolü
            self.api.get_account_info()

            # Test modunda değilsek işlem izni kontrolü
            if not Settings.USE_TESTNET:
                try:
                    # Küçük bir test siparişi denemesi (gerçekleşmeyecek)
                    self.api.place_order(
                        symbol="BTCUSDT",
                        side=SIDE_BUY,
                        order_type=ORDER_TYPE_MARKET,
                        quantity=0.001
                    )
                except Exception as e:
                    if "Permission denied" in str(e):
                        return False, "İşlem izni eksik"

            return True, "API izinleri tam"

        except BinanceAPIException as be:
            # Binance error -2015: Invalid API-key, IP, or permissions for action.
            if getattr(be, 'code', None) == -2015:
                return False, "API izin hatası: -2015 (trade veya futures/spot izni eksik, IP kısıtı veya yanlış anahtar)"
            return False, f"API izin hatası: {be}"
        except Exception as e:
            if '-2015' in str(e):
                return False, "API izin hatası: -2015 (yetki / IP / izin eksikliği)"
            return False, f"API izin hatası: {str(e)}"

    def run_full_check(self):
        """Tam sağlık kontrolü yap"""
        conn_ok, conn_msg = self.check_connection()
        perm_ok, perm_msg = self.check_api_permissions()

        if conn_ok and perm_ok:
            return True, "Sistem sağlıklı"
        else:
            errors = []
            if not conn_ok:
                errors.append(conn_msg)
            if not perm_ok:
                errors.append(perm_msg)
            return False, " | ".join(errors)
