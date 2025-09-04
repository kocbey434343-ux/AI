from scripts import secret_scan


def test_secret_scan_detects_key():
    text = "BINANCE_API_KEY = 'ABCDEF1234567890'"  # length triggers pattern
    issues = secret_scan.scan_text(text)
    assert issues, 'Should detect API key assignment'


def test_secret_scan_ignore_comment():
    text = "BINANCE_API_KEY = 'ABCDEF1234567890'  # secret-scan: ignore"
    issues = secret_scan.scan_text(text)
    assert not issues, 'Ignore directive failed'
