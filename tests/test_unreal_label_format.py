from src.ui.unreal_label import format_total_unreal_label

def test_format_total_unreal_label_positive():
    text, color = format_total_unreal_label(30.0, 15.0)
    assert '30.00 USDT' in text
    assert '(15.00%)' in text
    assert color == 'green'

def test_format_total_unreal_label_zero():
    text, color = format_total_unreal_label(0.0, 0.0)
    assert '0.00 USDT' in text
    assert '(0.00%)' in text
    assert color == 'gray'

def test_format_total_unreal_label_negative():
    text, color = format_total_unreal_label(-12.3456, -5.4321)
    assert '-12.35 USDT' in text  # rounded
    assert '(-5.43%)' in text
    assert color == 'red'
