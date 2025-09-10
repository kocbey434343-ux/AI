# TEST FAILURE ANALİZ RAPORU (v2.45)

## Özet
**Test Durumu**: 677 tests collected, 663 PASS + 1 SKIPPED, **13 FAILED** (%98+ başarı oranı)  
**Kritik Sorunlar**: Partial exit DB operations, FSM state transitions, structured logging gaps

## Failed Test Analysis

### 1. **Partial Exit DB Context Manager Failures (5 tests)**

**Pattern**: `'NoneType' object does not support the context manager protocol`

**Affected Tests**:
- `test_cr0037_scaled_out_persist_and_reload`
- `test_cr0013_scale_out_single_execution_and_persistence` 
- `test_scaleout_persist_and_reload`
- `test_cr0030_partial_exit_interaction`
- `test_cr0014_unrealized_partial_weight`

**Error Source**: 
```
ERROR Trader - Partial exit DB operation failed for SYMBOL level X.X: 'NoneType' object does not support the context manager protocol
```

**Analysis**: TradeStore context manager integration broken in partial exit operations, likely in `trailing.py` or related DB transaction handling.

### 2. **FSM Invalid Transitions (4 tests)**

**Pattern**: `Illegal transition OrderState.ACTIVE -> OrderState.SUBMITTING`

**Affected Tests**:
- `test_cr0037_scaled_out_persist_and_reload`
- `test_cr0030_partial_exit_interaction`
- `test_cr0013_scale_out_single_execution_and_persistence`
- `test_reconciliation_auto_heal`

**Error Source**:
```
WARNING StateManager - Gecersiz FSM gecisi SYMBOL: Illegal transition OrderState.ACTIVE -> OrderState.SUBMITTING
```

**Analysis**: FSM state machine logic allows invalid transitions during test scenarios, state persistence/reload may corrupt state tracking.

### 3. **Structured Logging Event Gaps (2 tests)**

**Pattern**: Missing expected events in structured logging

**Affected Tests**:
- `test_cr0028_structured_log_end_to_end` - Missing 'partial_exit' event
- `test_cr0028_structured_log_trade_lifecycle` - Missing lifecycle events

**Analysis**: Structured logging implementation incomplete for partial exit and some trade lifecycle events.

### 4. **Position Size & Risk Calculation (2 tests)**

**Pattern**: Position sizing logic failures

**Affected Tests**:
- `test_position_size_adaptive_edge_clamps_and_low_score` - Clamp logic failure (got=506.25 exp≈2250.0)
- `test_cr0014_unrealized_long_short_aggregate` - Database lock issue during aggregation

**Analysis**: Adaptive edge position sizing clamp logic incorrect, concurrent DB access issues.

## Critical Action Items

### Phase 1: DB Context Manager Fix (P1)
- **Target**: `src/utils/trade_store.py`, `src/trader/trailing.py`
- **Issue**: Context manager protocol implementation broken
- **Action**: Review DB transaction patterns in partial exit operations

### Phase 2: FSM State Validation (P1)  
- **Target**: `src/utils/state_manager.py`, `src/trader/core.py`
- **Issue**: Invalid state transitions allowed
- **Action**: Strengthen FSM validation logic, fix state persistence

### Phase 3: Structured Logging Coverage (P1)
- **Target**: `src/utils/structured_log.py`, partial exit event generation
- **Issue**: Missing 'partial_exit' and lifecycle events
- **Action**: Complete event coverage for all trade operations

### Phase 4: Position Sizing Logic (P2)
- **Target**: `src/risk_manager.py`, adaptive edge calculations
- **Issue**: Clamp logic and concurrent access issues
- **Action**: Fix clamp calculations, add DB concurrency safety

## Test Environment Impact

### Offline Mode Testing
- All failures occur in OFFLINE_MODE with realistic simulator
- TESTNET MODE active with conservative parameters
- Database isolation strategy (CR-0057) may be contributing to context manager issues

### Database Concurrency
- Multiple tests show "database is locked" errors
- Concurrent Trader instance creation causing lock contention
- Context manager protocol failures may be related to transaction handling

## Recommended Investigation Order

1. **Partial Exit Context Manager** - Highest impact, affects 5 tests
2. **FSM State Logic** - Affects 4 tests, may cause cascading issues  
3. **Structured Logging** - Lower impact but affects observability
4. **Position Sizing** - Isolated issues, lower priority

## Success Metrics

- Target: <5 failed tests (99%+ pass rate)
- Zero context manager protocol errors
- All FSM transitions valid and logged
- Complete structured logging event coverage
- Stable position sizing under all conditions

**Next Action**: Start with Phase 1 DB Context Manager investigation in `trailing.py` and `trade_store.py` integration.
