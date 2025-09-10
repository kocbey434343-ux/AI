from src.signal_generator import SignalGenerator
import glob, os

def main():
    sg = SignalGenerator()
    csvs = glob.glob('d:/trade bot/data/raw/*_1h.csv')
    print('csv count', len(csvs))
    if not csvs:
        return
    sym = os.path.basename(csvs[0]).split('_')[0]
    sig = sg.generate_pair_signal(sym)
    print('generated symbol:', sym)
    if sig:
        print('total_score:', sig['total_score'])
        p = sg.save_signals({sym: sig})
        print('saved file:', p, 'bytes', os.path.getsize(p))
    else:
        print('No signal produced')

if __name__ == '__main__':
    main()
