from src.utils.ws_utils import should_restart_ws


def test_should_restart_ws_basic_changes():
    # Initial load (no current, new has symbols) even within debounce
    assert should_restart_ws(10.0, 10.5, 2.0, [], ['AAA']) is True
    # Within debounce, sets differ but we already had symbols -> no restart
    assert should_restart_ws(10.0, 10.5, 2.0, ['AAA'], ['BBB']) is False
    # Outside debounce and sets differ -> restart
    assert should_restart_ws(10.0, 13.0, 2.0, ['AAA'], ['BBB']) is True
    # Outside debounce, sets same -> no restart
    assert should_restart_ws(10.0, 13.0, 2.0, ['AAA','BBB'], ['BBB','AAA']) is False
    # Both empty always false
    assert should_restart_ws(0.0, 5.0, 1.0, [], []) is False


def test_should_restart_ws_edge_cases():
    # None handling
    assert should_restart_ws(0.0, 5.0, 1.0, None, ['X']) is True
    assert should_restart_ws(0.0, 0.2, 2.0, None, ['X']) is True  # initial inside debounce
    assert should_restart_ws(1.0, 1.5, 2.0, ['A'], None) is False
    # Debounce window prevents restart when already had symbols
    assert should_restart_ws(100.0, 101.0, 5.0, ['A'], ['A','B']) is False