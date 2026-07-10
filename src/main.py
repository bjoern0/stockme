"""Einstiegspunkt: Watchlist scannen, Top-Mover checken, Alerts deduplizieren & versenden,
Dashboard aktualisieren.

Lokal:      python -m src.main
GitHub Actions: siehe .github/workflows/scan.yml
"""
from __future__ import annotations

import logging
from datetime import date

from . import dashboard, data, notifier, reddit_scan, state
from .config import load_settings
from .signals import evaluate

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def fetch_all(symbols: list[str]) -> dict:
    return {symbol: data.fetch_history(symbol) for symbol in symbols}


def scan_symbols(dataframes: dict, settings) -> list[str]:
    messages = []
    for symbol, df in dataframes.items():
        if df is None:
            continue
        for sig in evaluate(symbol, df, settings.indicators):
            if state.already_sent(sig.symbol, sig.kind):
                continue
            text = f"[{sig.symbol}] {sig.message}"
            messages.append(text)
            state.mark_sent(sig.symbol, sig.kind, message=sig.message)
    return messages


def scan_top_movers(settings) -> list[str]:
    cfg = settings.top_movers
    if not cfg.get("enabled", False):
        return []
    messages = []
    min_pct = cfg.get("min_percent_change", 5.0)
    for screen_name in cfg.get("screens", []):
        for row in data.fetch_top_movers(screen_name, cfg.get("count", 10)):
            symbol = row.get("symbol")
            pct = row.get("percent_change")
            if not symbol or pct is None or abs(pct) < min_pct:
                continue
            kind = f"TOP_MOVER_{screen_name.upper()}"
            if state.already_sent(symbol, kind):
                continue
            text = f"{row.get('name')}: {pct:+.1f}% (Screen: {screen_name}, Kurs {row.get('price')})"
            messages.append(f"[{symbol}] {text}")
            state.mark_sent(symbol, kind, message=text)
    return messages


def scan_reddit(settings) -> list[str]:
    cfg = settings.reddit
    if not cfg.get("enabled", False):
        return []
    symbols = settings.watchlist + settings.crypto_watchlist
    counts = reddit_scan.count_mentions(
        settings.reddit_client_id,
        settings.reddit_client_secret,
        cfg.get("subreddits", []),
        symbols,
        lookback_hours=cfg.get("lookback_hours", 24),
    )
    messages = []
    min_mentions = cfg.get("min_mentions", 5)
    for symbol, count in counts.items():
        if count < min_mentions:
            continue
        kind = "REDDIT_MENTIONS"
        if state.already_sent(symbol, kind):
            continue
        text = f"{count}x in {', '.join(cfg.get('subreddits', []))} erwähnt (letzte {cfg.get('lookback_hours', 24)}h)"
        messages.append(f"[{symbol}] {text}")
        state.mark_sent(symbol, kind, message=text)
    return messages


def main() -> None:
    settings = load_settings()
    logger.info("Watchlist: %s", settings.watchlist)
    logger.info("Crypto-Watchlist: %s", settings.crypto_watchlist)

    dataframes = fetch_all(settings.watchlist + settings.crypto_watchlist)

    messages = scan_symbols(dataframes, settings) + scan_top_movers(settings) + scan_reddit(settings)

    dashboard.render(dataframes, state.get_recent_alerts(), settings.indicators)
    logger.info("Dashboard aktualisiert: %s", dashboard.OUTPUT_PATH)

    if not messages:
        logger.info("Keine neuen Signale.")
        return

    text = f"Stockme Alerts ({date.today().isoformat()}):\n\n" + "\n".join(messages)
    logger.info("Sende %d Alert(s)", len(messages))
    notifier.send_telegram(settings.telegram_bot_token, settings.telegram_chat_id, text)


if __name__ == "__main__":
    main()
