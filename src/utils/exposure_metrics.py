"""Global exposure metrigi hesaplayicisi.

Risk yonetimi icin pozisyon dagilim analizi:
- Sembol bazli risk dagilimi
- Yon (LONG/SHORT) dagilimi
- Toplam exposure orani
- Konsantrasyon risk skorlari
"""

from typing import Any, Dict


def calculate_global_exposure(positions: list[dict]) -> Dict[str, Any]:
    """Global exposure metrik hesapla.

    Args:
        positions: Acik pozisyon listesi [{'symbol','side','position_size','entry_price',...}]

    Returns:
        {
            'total_exposure_usdt': float,
            'by_symbol': {'BTCUSDT': {'exposure_usdt': float, 'percentage': float}, ...},
            'by_side': {'LONG': {'count': int, 'exposure_usdt': float}, 'SHORT': {...}},
            'concentration_score': float,  # 0-1, higher = more concentrated risk
            'diversification_score': float,  # 0-1, higher = better diversified
            'max_single_exposure_pct': float,  # Largest single position %
            'risk_warnings': [str]  # List of risk warnings
        }
    """
    if not positions:
        return {
            'total_exposure_usdt': 0.0,
            'by_symbol': {},
            'by_side': {'LONG': {'count': 0, 'exposure_usdt': 0.0},
                       'SHORT': {'count': 0, 'exposure_usdt': 0.0}},
            'concentration_score': 0.0,
            'diversification_score': 1.0,
            'max_single_exposure_pct': 0.0,
            'risk_warnings': []
        }

    # Calculate exposure by symbol and side
    by_symbol = {}
    by_side = {'LONG': {'count': 0, 'exposure_usdt': 0.0},
               'SHORT': {'count': 0, 'exposure_usdt': 0.0}}

    total_exposure = 0.0

    for pos in positions:
        symbol = pos.get('symbol', 'UNKNOWN')
        side = pos.get('side', 'UNKNOWN')
        size = float(pos.get('remaining_size', 0) or pos.get('position_size', 0))
        entry_price = float(pos.get('entry_price', 0))

        exposure_usdt = size * entry_price
        total_exposure += exposure_usdt

        # By symbol
        if symbol not in by_symbol:
            by_symbol[symbol] = {'exposure_usdt': 0.0, 'count': 0}
        by_symbol[symbol]['exposure_usdt'] += exposure_usdt
        by_symbol[symbol]['count'] += 1

        # By side
        if side in by_side:
            by_side[side]['count'] += 1
            by_side[side]['exposure_usdt'] += exposure_usdt

    # Calculate percentages for symbols
    for symbol_data in by_symbol.values():
        if total_exposure > 0:
            symbol_data['percentage'] = (symbol_data['exposure_usdt'] / total_exposure) * 100
        else:
            symbol_data['percentage'] = 0.0

    # Calculate concentration and diversification scores
    concentration_score = 0.0
    max_single_exposure_pct = 0.0

    if total_exposure > 0 and by_symbol:
        # Concentration: sum of squares of percentages (Herfindahl index style)
        percentages = [data['percentage'] / 100 for data in by_symbol.values()]
        concentration_score = sum(p**2 for p in percentages)
        max_single_exposure_pct = max(data['percentage'] for data in by_symbol.values())

        # Diversification: inverse of concentration, normalized
        diversification_score = max(0.0, 1.0 - concentration_score)

    # Generate risk warnings
    risk_warnings = []

    if max_single_exposure_pct > 30.0:
        risk_warnings.append(f"Yuksek konsantrasyon riski: En buyuk pozisyon %{max_single_exposure_pct:.1f}")

    if concentration_score > 0.5:
        risk_warnings.append("Dusuk diversifikasyon: Risk dagilimi yetersiz")

    if len(by_symbol) < 3 and total_exposure > 1000:  # Arbitrary threshold
        risk_warnings.append("Az sembol cesitliligi: Daha fazla diversifikasyon onerilir")

    long_short_ratio = 0.0
    if by_side['SHORT']['exposure_usdt'] > 0:
        long_short_ratio = by_side['LONG']['exposure_usdt'] / by_side['SHORT']['exposure_usdt']
    elif by_side['LONG']['exposure_usdt'] > 0:
        long_short_ratio = float('inf')

    if long_short_ratio > 5.0 or (long_short_ratio < 0.2 and long_short_ratio > 0):
        risk_warnings.append("Dengesiz LONG/SHORT dagilimi")

    return {
        'total_exposure_usdt': round(total_exposure, 2),
        'by_symbol': {k: {**v, 'exposure_usdt': round(v['exposure_usdt'], 2)}
                     for k, v in by_symbol.items()},
        'by_side': {k: {**v, 'exposure_usdt': round(v['exposure_usdt'], 2)}
                   for k, v in by_side.items()},
        'concentration_score': round(concentration_score, 3),
        'diversification_score': round(diversification_score, 3),
        'max_single_exposure_pct': round(max_single_exposure_pct, 1),
        'risk_warnings': risk_warnings
    }


def format_exposure_summary(exposure_data: Dict[str, Any]) -> str:
    """Format exposure data for logging/display."""
    total = exposure_data['total_exposure_usdt']
    by_side = exposure_data['by_side']
    conc = exposure_data['concentration_score']
    div = exposure_data['diversification_score']
    warnings = len(exposure_data['risk_warnings'])

    long_pct = (by_side['LONG']['exposure_usdt'] / total * 100) if total > 0 else 0
    short_pct = (by_side['SHORT']['exposure_usdt'] / total * 100) if total > 0 else 0

    summary = f"Global Exposure: ${total:,.0f} | "
    summary += f"L/S: {long_pct:.1f}%/{short_pct:.1f}% | "
    summary += f"Diversifikasyon: {div:.2f} | "
    if warnings > 0:
        summary += f"⚠️ {warnings} risk uyarisi"
    else:
        summary += "✅ Risk dengeli"

    return summary
