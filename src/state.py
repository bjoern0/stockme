"""SQLite-Dedup: verhindert, dass derselbe Alert bei jedem Lauf erneut geschickt wird.

Die DB-Datei wird in GitHub Actions nach jedem Lauf zurück ins Repo committet (siehe Workflow),
damit der State zwischen den (ephemeren) Runner-Läufen erhalten bleibt.
"""
from __future__ import annotations

import sqlite3
from datetime import date, datetime
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "state.db"


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS sent_alerts (
            symbol TEXT NOT NULL,
            kind TEXT NOT NULL,
            alert_date TEXT NOT NULL,
            sent_at TEXT NOT NULL,
            message TEXT,
            PRIMARY KEY (symbol, kind, alert_date)
        )
        """
    )
    return conn


def already_sent(symbol: str, kind: str, on_date: date | None = None) -> bool:
    on_date = on_date or date.today()
    with _connect() as conn:
        row = conn.execute(
            "SELECT 1 FROM sent_alerts WHERE symbol=? AND kind=? AND alert_date=?",
            (symbol, kind, on_date.isoformat()),
        ).fetchone()
        return row is not None


def mark_sent(symbol: str, kind: str, on_date: date | None = None, message: str | None = None) -> None:
    on_date = on_date or date.today()
    with _connect() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO sent_alerts (symbol, kind, alert_date, sent_at, message) VALUES (?, ?, ?, ?, ?)",
            (symbol, kind, on_date.isoformat(), datetime.utcnow().isoformat(), message),
        )
        conn.commit()


def get_recent_alerts(limit: int = 50) -> list[sqlite3.Row]:
    with _connect() as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT symbol, kind, alert_date, sent_at, message FROM sent_alerts "
            "ORDER BY sent_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return rows
