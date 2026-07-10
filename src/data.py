"""Marktdaten-Zugriff über yfinance (kostenlos, kein API-Key nötig)."""
from __future__ import annotations

import logging

import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)


def fetch_history(symbol: str, period: str = "6mo", interval: str = "1d") -> pd.DataFrame | None:
    """Historische OHLCV-Daten für einen Ticker. None falls nicht abrufbar. Standard: 2 Jahre für EMA200."""
    try:
        df = yf.Ticker(symbol).history(period="2y", interval=interval) # Geändert von 6mo auf 2y für EMA200
    except Exception:
        logger.exception("Konnte Historie für %s nicht laden", symbol)
        return None
    if df is None or df.empty:
        logger.warning("Keine Daten für %s erhalten", symbol)
        return None
    return df


def fetch_top_movers(screen_name: str, count: int = 10) -> list[dict]:
    """Nutzt Yahoo Finances vordefinierte Screener (day_gainers, day_losers, most_actives, ...)."""
    try:
        response = yf.screen(screen_name, count=count)
    except Exception:
        logger.exception("Screener '%s' fehlgeschlagen", screen_name)
        return []

    quotes = response.get("quotes", []) if isinstance(response, dict) else []
    results = []
    for q in quotes:
        results.append(
            {
                "symbol": q.get("symbol"),
                "name": q.get("shortName") or q.get("longName"),
                "percent_change": q.get("regularMarketChangePercent"),
                "price": q.get("regularMarketPrice"),
                "market_cap": q.get("marketCap"),
            }
        )
    return results
