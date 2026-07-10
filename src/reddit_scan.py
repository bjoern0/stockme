"""Zählt Ticker-Erwähnungen in konfigurierten Subreddits (r/wallstreetbets etc.) als
zusätzliches, bewusst nachrangiges Signal.

Nutzt PRAW im "read-only" Application-Only-Modus (nur client_id + client_secret, kein
Reddit-Passwort nötig) - reicht für öffentliche Daten, siehe README.

Wichtig: Erwähnungen in diesen Communities sind stark verrauscht und teils gezielt
manipuliert (Pump-and-Dump). Bewusst nur als *ein* Faktor gedacht, nicht als alleiniges
Kaufsignal - siehe Projekt-Disclaimer.
"""
from __future__ import annotations

import logging
import re
from collections import Counter
from datetime import datetime, timedelta, timezone

import praw

logger = logging.getLogger(__name__)


def _search_term(symbol: str) -> str:
    """Wandelt z.B. 'BTC-USD' in 'BTC' um, damit es in Reddit-Texten matcht."""
    return symbol.split("-")[0]


def _build_client(client_id: str, client_secret: str) -> praw.Reddit:
    reddit = praw.Reddit(
        client_id=client_id,
        client_secret=client_secret,
        user_agent="stockme/0.1 (personal alert scanner)",
    )
    reddit.read_only = True
    return reddit


def count_mentions(
    client_id: str | None,
    client_secret: str | None,
    subreddits: list[str],
    symbols: list[str],
    lookback_hours: int = 24,
    limit_per_subreddit: int = 200,
) -> dict[str, int]:
    """Zählt Erwähnungen je Symbol über alle konfigurierten Subreddits summiert."""
    if not client_id or not client_secret:
        logger.warning("Kein REDDIT_CLIENT_ID/REDDIT_CLIENT_SECRET gesetzt, Reddit-Scan wird übersprungen")
        return {}

    terms = {symbol: _search_term(symbol) for symbol in symbols}
    patterns = {
        symbol: re.compile(rf"\b{re.escape(term)}\b", re.IGNORECASE) for symbol, term in terms.items()
    }
    counts: Counter[str] = Counter()
    cutoff = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)

    try:
        reddit = _build_client(client_id, client_secret)
        for subreddit_name in subreddits:
            subreddit = reddit.subreddit(subreddit_name)
            for submission in subreddit.new(limit=limit_per_subreddit):
                created = datetime.fromtimestamp(submission.created_utc, tz=timezone.utc)
                if created < cutoff:
                    break  # .new() ist zeitlich sortiert, ältere Posts können wir abbrechen
                text = f"{submission.title} {submission.selftext or ''}"
                for symbol, pattern in patterns.items():
                    if pattern.search(text):
                        counts[symbol] += 1
    except Exception:
        logger.exception("Reddit-Scan fehlgeschlagen")
        return {}

    return dict(counts)
