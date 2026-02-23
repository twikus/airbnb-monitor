"""Gestion de la base de données SQLite — multi-analyses."""
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
    """Crée les tables et migre les snapshots orphelins existants."""
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS analyses (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                checkin    TEXT NOT NULL,
                checkout   TEXT NOT NULL,
                created_at TEXT NOT NULL,
                UNIQUE(checkin, checkout)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS snapshots (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                scraped_at    TEXT    NOT NULL,
                checkin       TEXT    NOT NULL,
                checkout      TEXT    NOT NULL,
                listing_count INTEGER,
                search_url    TEXT,
                screenshot    TEXT
            )
        """)
        # Migrer les snapshots qui n'ont pas encore d'entrée dans analyses
        conn.execute("""
            INSERT OR IGNORE INTO analyses (checkin, checkout, created_at)
            SELECT DISTINCT checkin, checkout, MIN(scraped_at)
            FROM snapshots GROUP BY checkin, checkout
        """)
        conn.commit()


# ── Analyses ──────────────────────────────────────────────────────────────────

def add_analysis(checkin: str, checkout: str) -> Optional[int]:
    """Ajoute une analyse. Retourne l'id, ou None si elle existe déjà."""
    with get_connection() as conn:
        try:
            cur = conn.execute(
                "INSERT INTO analyses (checkin, checkout, created_at) VALUES (?, ?, ?)",
                (checkin, checkout, datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
            )
            conn.commit()
            return cur.lastrowid
        except sqlite3.IntegrityError:
            return None


def get_all_analyses() -> List[sqlite3.Row]:
    """Retourne toutes les analyses avec leur dernier relevé."""
    with get_connection() as conn:
        return conn.execute("""
            SELECT
                a.id, a.checkin, a.checkout, a.created_at,
                (SELECT listing_count FROM snapshots
                 WHERE checkin=a.checkin AND checkout=a.checkout
                 ORDER BY scraped_at DESC LIMIT 1) AS latest_count,
                (SELECT scraped_at FROM snapshots
                 WHERE checkin=a.checkin AND checkout=a.checkout
                 ORDER BY scraped_at DESC LIMIT 1) AS latest_scraped_at,
                (SELECT COUNT(*) FROM snapshots
                 WHERE checkin=a.checkin AND checkout=a.checkout) AS total_snapshots
            FROM analyses a ORDER BY a.checkin
        """).fetchall()


def delete_analysis(analysis_id: int) -> bool:
    """Supprime une analyse et tous ses relevés."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT checkin, checkout FROM analyses WHERE id=?", (analysis_id,)
        ).fetchone()
        if not row:
            return False
        conn.execute(
            "DELETE FROM snapshots WHERE checkin=? AND checkout=?",
            (row["checkin"], row["checkout"]),
        )
        conn.execute("DELETE FROM analyses WHERE id=?", (analysis_id,))
        conn.commit()
        return True


# ── Snapshots ─────────────────────────────────────────────────────────────────

def insert_snapshot(
    checkin: str, checkout: str, count: Optional[int], url: str, screenshot: Optional[str] = None
) -> int:
    with get_connection() as conn:
        cur = conn.execute(
            """INSERT INTO snapshots
               (scraped_at, checkin, checkout, listing_count, search_url, screenshot)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), checkin, checkout, count, url, screenshot),
        )
        conn.commit()
        return cur.lastrowid


def get_snapshots_for_analysis(checkin: str, checkout: str) -> List[sqlite3.Row]:
    with get_connection() as conn:
        return conn.execute(
            "SELECT * FROM snapshots WHERE checkin=? AND checkout=? ORDER BY scraped_at",
            (checkin, checkout),
        ).fetchall()
