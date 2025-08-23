from src.utils.structured_log import clear_slog_events, get_slog_events, slog


def test_slog_buffer_accumulates_and_filters():
    clear_slog_events()
    EXPECT_TOTAL = 3
    EXPECT_PARTIAL = 2
    slog("partial_exit", symbol="AAAUSDT", qty=1)
    slog("trailing_atr_update", symbol="BBBUSDT", new_sl=10)
    slog("partial_exit", symbol="AAAUSDT", qty=0.5)
    all_events = get_slog_events()
    assert len(all_events) == EXPECT_TOTAL
    partials = get_slog_events("partial_exit")
    assert len(partials) == EXPECT_PARTIAL
    symbols = {e['symbol'] for e in partials}
    assert symbols == {"AAAUSDT"}
