## Modül Bağımlılık Diyagramı (Güncel - v1.60)

Bu dosya SSoT ( `.github/copilot-instructions.md` ) mimari özetine paralel modüller arası ilişkileri gösterir.

### 1. Üst Düzey Katmanlar

```mermaid
flowchart TD
  subgraph Entry/UI
    MAIN[main.py]
    RUNS[run_trade_bot*.bat|sh]
    UI_MAIN[ui.main_window]
    UI_SIGNAL[ui.signal_window]
  end
  subgraph Core
    TR[trader.core.Trader]
    SHIM[trader.py (shim)]
  end
  subgraph Domain
    EXEC[trader.execution]
    GUARDS[trader.guards]
    TRAIL[trader.trailing]
    METRICS[trader.metrics]
    RISK[risk_manager]
    SIGNAL[signal_generator]
    FETCH[data_fetcher]
    INDS[indicators]
  end
  subgraph Infra
    API[api.binance_api]
    STREAM[api.price_stream]
    STORE[utils.trade_store]
    CORR[utils.correlation_cache]
    CFG[config.settings]
    LOG[utils.logger]
    SLOG[utils.structured_log]
    FLAGS[utils.feature_flags]
    HELP[utils.helpers]
    WSUTIL[utils.ws_utils]
    EXHOOK[utils.exception_hook]
  end
  subgraph External
    BINANCE[(Binance REST/WS)]
    SQLITE[(SQLite trades.db)]
    FS[(File System)]
  end

  MAIN --> TR
  RUNS --> MAIN
  SHIM --> TR
  UI_MAIN --> TR
  UI_SIGNAL --> SIGNAL

  SIGNAL --> TR
  SIGNAL --> INDS
  SIGNAL --> FETCH

  FETCH --> API
  FETCH --> CFG
  FETCH --> LOG

  TR --> EXEC
  TR --> GUARDS
  TR --> TRAIL
  TR --> METRICS
  TR --> RISK
  TR --> CORR
  TR --> STORE
  TR --> CFG
  TR --> LOG
  TR --> SLOG
  TR --> EXHOOK

  EXEC --> RISK
  EXEC --> API
  EXEC --> STORE
  EXEC --> CFG
  EXEC --> LOG
  EXEC --> SLOG

  GUARDS --> CORR
  GUARDS --> CFG
  GUARDS --> SLOG

  TRAIL --> STORE
  TRAIL --> CFG
  TRAIL --> LOG
  TRAIL --> SLOG

  METRICS --> STORE
  METRICS --> CFG
  METRICS --> RISK
  METRICS --> LOG
  METRICS --> SLOG

  RISK --> CFG

  API --> CFG
  API --> LOG
  API --> BINANCE

  STREAM --> BINANCE
  STREAM --> LOG
  STREAM --> CFG
  STREAM --> WSUTIL

  STORE --> SQLITE
  STORE --> CFG
  STORE --> LOG
  STORE --> SLOG

  CORR --> LOG
  CORR --> CFG

  CFG --> FS
  EXHOOK --> SLOG
```

### 2. Position State Alanları
`Trader.positions` sözlüğündeki tipik alanlar: `side, entry_price, position_size, remaining_size, stop_loss, take_profit, atr, trade_id, scaled_out[(r, qty)], oco_resp|futures_protection, scaled_out_json (persist), trailing history (runtime)`.

### 3. Temel Akışlar (Güncel)
- Açılış: `signal_generator` → `Trader.execute_trade` → `guards` → `execution` → `trade_store.recompute` → `metrics/anomaly` → `structured_log(trade_open)`.
- Fiyat Güncellemesi: `process_price_update` → `trailing` (partial + trailing) → `trade_store` (partial persist) → `structured_log(trailing_update|partial_exit)`.
- Partial Fill: `execution` → state update → protection revizyon → `slog(partial_exit)`.
- Kapanış: `close_position` → `execution.close_position` → `trade_store.close_trade` → `slog(trade_close)`.
- Reconciliation: `_reconcile_open_orders` → diff event `slog(reconciliation)` → (auto-heal attempt/success events).
- Günlük Reset: `_maybe_daily_risk_reset` → counters clear → `slog(daily_risk_reset)`.
- Exception: Global `exception_hook` yakalar → `slog(unhandled_exception|thread_unhandled_exception)`.

### 4. Geliştirme Önerileri (Özet)
| Konu | Sorun | Öneri |
|------|-------|-------|
| Execution karmaşıklığı | Çok sorumluluk | ProtectionManager ayrımı |
| Anomaly-Risk coupling | Sıkı bağ | EventBus / observer |
| Position dict serbest | Tip güvencesi yok | Dataclass / model |
| Reconciliation pasif | Sadece log | Auto-heal faz3 (tam restore) |
| Scale-out tab UI | Manuel feed | Trader event integration |
| Threshold persistence | Param overrides ayrı | Merge + versionlama |

### 5. Güncelleme Prosedürü
Her yapısal revizyon + yeni structured event eklendiğinde ilgili ok ve düğümler eklenip revizyon yükseltilmelidir.

---
Revizyon: v1.60 (CR-0036 senkronizasyon güncellemesi)
