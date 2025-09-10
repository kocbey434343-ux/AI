from __future__ import annotations

from collections import defaultdict
from typing import Callable, Dict

from .logger import get_logger
from .order_state import OrderState, StateTransition, assert_transition
from .structured_log import slog

LOGGER = get_logger("StateManager")

class StateManager:
    """Symbol bazinda FSM durumlarini yoneten merkezi sinif."""
    def __init__(self, on_transition: Callable[[StateTransition], None] | None = None):
        self._states: Dict[str, OrderState] = defaultdict(lambda: OrderState.INIT)
        self._on_transition = on_transition

    def get_state(self, symbol: str) -> OrderState:
        """Bir sembolun mevcut durumunu dondurur."""
        return self._states[symbol]

    def transition_to(self, symbol: str, new_state: OrderState, reason: str | None = None) -> bool:
        """Bir sembolu yeni bir duruma gecirmeye calisir.

        Gecis gecersiz ise False dondurur ve loglar.
        """
        current_state = self.get_state(symbol)
        try:
            assert_transition(current_state, new_state)
            self._states[symbol] = new_state
            slog(
                "fsm_transition",
                symbol=symbol,
                from_state=current_state.value,
                to_state=new_state.value,
                reason=reason
            )
            if self._on_transition:
                transition_event = StateTransition(
                    trade_id=self._get_trade_id(),  # trade_id bağlama
                    symbol=symbol,
                    from_state=current_state,
                    to_state=new_state,
                    reason=reason
                )
                self._on_transition(transition_event)
            return True
        except ValueError as e:
            LOGGER.warning(f"Gecersiz FSM gecisi {symbol}: {e}")
            slog(
                "fsm_invalid_transition",
                symbol=symbol,
                from_state=current_state.value,
                to_state=new_state.value,
                error=str(e)
            )
            return False
        except Exception as e:
            LOGGER.error(f"FSM gecisi sirasinda beklenmeyen hata {symbol}: {e}")
            return False

    def clear_state(self, symbol: str):
        """Bir sembol icin durum bilgisini temizler."""
        if symbol in self._states:
            del self._states[symbol]
            LOGGER.info(f"FSM durumu temizlendi {symbol}")

    def set_initial_state(self, symbol: str, state: OrderState):
        """Veritabanindan yeniden yuklenen pozisyonlar icin baslangic durumunu ayarlar."""
        if symbol not in self._states:
            self._states[symbol] = state
            LOGGER.info(f"FSM durumu ayarlandi {symbol}: {state.name}")

    def _get_trade_id(self) -> int | None:
        """Bir sembol icin trade_id'yi dondurur. (Varsayilan: None)"""
        # TODO: trade_id'yi sembole baglama mantigini burada tanimlayin
        return None
