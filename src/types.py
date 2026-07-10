"""Gemeinsame Typdefinitionen für das Projekt."""
from __future__ import annotations

from dataclasses import dataclass

@dataclass
class Signal:
    symbol: str
    kind: str       # z.B. "RSI_OVERSOLD", "SMA_CROSS_UP", "VOLUME_SPIKE"
    message: str