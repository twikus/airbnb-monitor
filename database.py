"""
Gestion de la base de données SQLite pour le suivi Airbnb.
"""
import sqlite3
import os
from datetime import datetime
from typing import List, Optional

import config as cfg


def get_connection() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(cfg.DB_PATH), exist_ok=True)
    conn = sqlite3.connect(cfg.DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Crée les tables si elles n'existent pas."""
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS snapshots (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                scraped_at    TEXT    NOT NULL,
                checkin       TEXT    NOT NULL,
                checkout      TEXT    NOT NULL,
                listing_count INTEGER,
                search_url    TEXT,
                screenshot    TEXT,
                notes         TEXT
            )
        """)
        conn.commit()


def insert_snapshot(count: Optional[int], url: str, screenshot: Optional[str] = None) -> int:
    """Insère un relevé et retourne son id."""
    with get_connection() as conn:
        cur = conn.execute(
            """INSERT INTO snapshots
               (scraped_at, checkin, checkout, listing_count, search_url, screenshot)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                cfg.CHECKIN_DATE,
                cfg.CHECKOUT_DATE,
                count,
                url,
                screenshot,
            ),
        )
        conn.commit()
        return cur.lastrowid


def get_all_snapshots() -> List[sqlite3.Row]:
    """Retourne tous les relevés triés par date."""
    with get_connection() as conn:
        return conn.execute(
            "SELECT * FROM snapshots WHERE checkin = ? ORDER BY scraped_at",
            (cfg.CHECKIN_DATE,),
        ).fetchall()


def get_latest_snapshot() -> Optional[sqlite3.Row]:
    with get_connection() as conn:
        return conn.execute(
            "SELECT * FROM snapshots WHERE checkin = ? ORDER BY scraped_at DESC LIMIT 1",
            (cfg.CHECKIN_DATE,),
        ).fetchone()
