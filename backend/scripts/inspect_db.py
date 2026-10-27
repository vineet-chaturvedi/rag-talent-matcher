"""
Prints every table with its columns, foreign keys and row count.
Uses Python's built-in sqlite3 module (no ORM) to look at what was REALLY created on disk.

Run from backend/:   python -m scripts.inspect_db
"""
import sqlite3
from pathlib import Path

DB_PATH = Path("data/app.db")


def main() -> None:
    if not DB_PATH.exists():
        print("No database yet. Start the server once (it creates data/app.db).")
        return

    con = sqlite3.connect(DB_PATH)
    tables = [
        row[0]
        for row in con.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        )
    ]
    for table in tables:
        count = con.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
        print(f"\n{table}  ({count} rows)")
        for _cid, name, col_type, notnull, _default, pk in con.execute(f'PRAGMA table_info("{table}")'):
            flags = " ".join(flag for flag, on in (("PK", pk), ("NOT NULL", notnull)) if on)
            print(f"   {name:<24} {col_type:<14} {flags}")
        for fk in con.execute(f'PRAGMA foreign_key_list("{table}")'):
            # fk columns: id, seq, table, from, to, on_update, on_delete, match
            print(f"   FK  {fk[3]} -> {fk[2]}.{fk[4]}  (on delete {fk[6]})")
    con.close()


if __name__ == "__main__":
    main()