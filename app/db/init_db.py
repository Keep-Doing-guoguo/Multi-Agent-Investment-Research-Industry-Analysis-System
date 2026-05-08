from __future__ import annotations

import sys
from pathlib import Path

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.memory.sqlite_store import SQLiteStore


def main() -> None:
    store = SQLiteStore()
    store.init_db()
    print(f"Initialized SQLite database at {store.db_path}")


if __name__ == "__main__":
    main()
