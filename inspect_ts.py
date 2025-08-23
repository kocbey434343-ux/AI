from src.signal_generator import SignalGenerator

sg = SignalGenerator()
signals = sg.generate_signals(pairs=['BTCUSDT'])
ts = signals['BTCUSDT']['timestamp']
print('VALUE:', ts)
print('TYPE :', type(ts))
print('IS_PD_TIMESTAMP:', 'pandas' in type(ts).__module__)
