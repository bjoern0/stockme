"""Telegram-Benachrichtigungen. Bot via @BotFather anlegen, Token + Chat-ID in .env / Secrets."""
from __future__ import annotations

import logging

import requests

logger = logging.getLogger(__name__)


def send_telegram(bot_token: str | None, chat_id: str | None, text: str) -> bool:
    if not bot_token or not chat_id:
        logger.warning("Kein TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID gesetzt, Nachricht wird nur geloggt:\n%s", text)
        return False
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    try:
        resp = requests.post(url, json={"chat_id": chat_id, "text": text}, timeout=15)
        resp.raise_for_status()
        return True
    except Exception:
        logger.exception("Telegram-Nachricht konnte nicht gesendet werden")
        return False
