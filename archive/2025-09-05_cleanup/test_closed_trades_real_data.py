#!/usr/bin/env python3
"""
Test script to verify closed trades data is now real instead of mock
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.utils.trade_store import TradeStore
from src.ui.main_window import MainWindow
from PyQt5.QtWidgets import QApplication

def test_closed_trades_real_data():
    """Test that closed trades show real data"""
    print("🔍 Testing closed trades real data integration...")

    # Test TradeStore directly
    print("\n1. Testing TradeStore.closed_trades():")
    store = TradeStore()
    closed_trades = store.closed_trades(limit=5)
    print(f"   Found {len(closed_trades)} closed trades")

    for i, trade in enumerate(closed_trades):
        symbol = trade['symbol']
        pnl_pct = trade.get('realized_pnl_pct', 0)
        r_multiple = trade.get('r_multiple', 0)
        print(f"   Trade {i+1}: {symbol}, PnL: {pnl_pct:.2f}%, R: {r_multiple:.2f}R")

    # Test UI data population
    print("\n2. Testing UI MainWindow._update_unified_closed_trades():")
    app = QApplication([])

    try:
        window = MainWindow()

        # Call the updated method
        print("   Calling _update_unified_closed_trades()...")
        window._update_unified_closed_trades()

        # Check if table has data
        if hasattr(window, 'closed_table'):
            row_count = window.closed_table.rowCount()
            print(f"   Unified closed table has {row_count} rows")

            if row_count > 0:
                # Read first row data
                symbol = window.closed_table.item(0, 0)
                pnl = window.closed_table.item(0, 1)
                r_mult = window.closed_table.item(0, 2)
                date = window.closed_table.item(0, 3)

                print(f"   Row 0: {symbol.text() if symbol else 'N/A'}, {pnl.text() if pnl else 'N/A'}, {r_mult.text() if r_mult else 'N/A'}, {date.text() if date else 'N/A'}")
        else:
            print("   Warning: closed_table not found in window")

    except Exception as e:
        print(f"   Error testing UI: {e}")
    finally:
        app.quit()

    print("\n3. Testing UI MainWindow.load_closed_trades():")
    app2 = QApplication([])

    try:
        window2 = MainWindow()

        # Initialize the positions tab to create closed_table
        window2.create_positions_tab()

        print("   Calling load_closed_trades()...")
        count = window2.load_closed_trades(limit=5)

        if hasattr(window2, 'closed_table'):
            row_count = window2.closed_table.rowCount()
            print(f"   Positions closed table has {row_count} rows")

            if row_count > 0:
                # Read first row data
                cols = []
                for c in range(min(8, window2.closed_table.columnCount())):
                    item = window2.closed_table.item(0, c)
                    cols.append(item.text() if item else 'N/A')
                print(f"   Row 0: {' | '.join(cols[:8])}")
        else:
            print("   Warning: closed_table not found in positions tab")

    except Exception as e:
        print(f"   Error testing positions UI: {e}")
    finally:
        app2.quit()

    print("\n✅ Closed trades real data test completed!")

if __name__ == "__main__":
    test_closed_trades_real_data()
