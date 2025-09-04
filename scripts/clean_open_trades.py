import sqlite3

def clean_open_trades(db_path):
    """Veritabanindaki acik islemleri temizler."""
    conn = None
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM trades WHERE exit_price IS NULL;")
        conn.commit()
        print("Acik islemler basariyla temizlendi.")
    except sqlite3.Error as e:
        print(f"Veritabani hatasi: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    db_path = "d:/trade_bot/data/trades.db"
    clean_open_trades(db_path)
