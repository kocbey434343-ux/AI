from src.utils.logger import get_logger, _LOGGER_CACHE  # type: ignore
import os, re, importlib, time

def test_cr0043_api_key_redaction(monkeypatch, tmp_path):
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
    log_file = os.path.join(str(log_dir), 'redaction_test.log')
    for _ in range(10):
        if os.path.exists(log_file):
            break
        time.sleep(0.01)
    assert os.path.exists(log_file), 'log file not created'
    with open(log_file,'r',encoding='utf-8') as f:
        content = f.read()
    assert key not in content
    assert secret not in content
    assert re.search(r'ABCD\*+GH', content)
    assert re.search(r'SECR\*+54', content)
