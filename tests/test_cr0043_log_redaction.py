from src.utils.logger import get_logger, _LOGGER_CACHE  # type: ignore
import os, re, importlib, time

def test_cr0043_api_key_redaction(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv('BINANCE_API_KEY','ABCD1234EFGH')
    monkeypatch.setenv('BINANCE_API_SECRET','SECRETXYZ987654')
    log_dir = tmp_path / 'logs'
    log_dir.mkdir()
    monkeypatch.setenv('LOG_PATH', str(log_dir))
    import config.settings as cs
    importlib.reload(cs)
    # Clear cache to force new handlers with redaction
    _LOGGER_CACHE.clear()  # type: ignore
    from config.settings import Settings as S2

    logger = get_logger('redaction_test')
    key = S2.BINANCE_API_KEY
    secret = S2.BINANCE_API_SECRET
    logger.error(f"API key={key} secret={secret} should be redacted")

    # Capture stderr which is where the console handler writes
    captured = capsys.readouterr()
    log_content = captured.err

    # Test redaction worked in captured output
    assert key not in log_content, f"Original API key found in log: {log_content}"
    assert secret not in log_content, f"Original secret found in log: {log_content}"

    # Test that masked versions are present
    import re
    assert re.search(r'ABCD\*+GH', log_content), f"Masked API key not found in log: {log_content}"
    assert re.search(r'SECR\*+54', log_content), f"Masked secret not found in log: {log_content}"
