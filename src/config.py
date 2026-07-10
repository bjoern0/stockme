"""Lädt config.yaml und Umgebungsvariablen (.env lokal, Secrets in GitHub Actions)."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import yaml
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(ROOT_DIR / ".env")


@dataclass
class Settings:
    raw: dict

    @property
    def watchlist(self) -> list[dict[str, str]]:
        return self.raw.get("watchlist", [])

    @property
    def crypto_watchlist(self) -> list[dict[str, str]]:
        return self.raw.get("crypto_watchlist", [])

    @property
    def screening_watchlist(self) -> list[dict[str, str]]:
        return self.raw.get("screening_watchlist", [])

    @property
    def all_stock_configs(self) -> list[dict[str, str]]:
        """Kombiniert alle Watchlists zu einer Liste von Symbol-Konfigurationen."""
        return self.watchlist + self.crypto_watchlist + self.screening_watchlist

    @property
    def indicators(self) -> dict:
        return self.raw.get("indicators", {})

    @property
    def top_movers(self) -> dict:
        return self.raw.get("top_movers", {})

    @property
    def reddit(self) -> dict:
        return self.raw.get("reddit", {})

    @property
    def telegram_bot_token(self) -> str | None:
        return os.environ.get("TELEGRAM_BOT_TOKEN")

    @property
    def telegram_chat_id(self) -> str | None:
        return os.environ.get("TELEGRAM_CHAT_ID")

    @property
    def reddit_client_id(self) -> str | None:
        return os.environ.get("REDDIT_CLIENT_ID")

    @property
    def reddit_client_secret(self) -> str | None:
        return os.environ.get("REDDIT_CLIENT_SECRET")

    @property
    def fred(self) -> dict:
        return self.raw.get("fred", {})

    @property
    def fred_api_key(self) -> str | None:
        return os.environ.get("FRED_API_KEY")


def load_settings(config_path: Path | None = None) -> Settings:
    path = config_path or (ROOT_DIR / "config.yaml")
    with open(path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    return Settings(raw=raw)
