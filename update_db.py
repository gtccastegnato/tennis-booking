import sqlite3

DB_FILE = "bookings.db"

def add_reserved_until_column():
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    # Controlla se la colonna reserved_until esiste
    cur.execute("PRAGMA table_info(bookings)")
    columns = [col[1] for col in cur.fetchall()]
    if "reserved_until" in columns:
        print("Colonna 'reserved_until' già presente. Nessuna modifica effettuata.")
    else:
        print("Aggiungo colonna 'reserved_until'...")
        cur.execute("ALTER TABLE bookings ADD COLUMN reserved_until INTEGER DEFAULT NULL")
        print("Colonna aggiunta correttamente.")

    conn.commit()
    conn.close()

if __name__ == "__main__":
    add_reserved_until_column()
