"""Kombiniert Indikatoren zu einfachen, nachvollziehbaren Signalen.

Bewusst simpel gehalten: lieber wenige robuste Regeln als viele überoptimierte Parameter
(Overfitting auf historische Daten ist das größte Risiko bei sowas)."""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from . import indicators as ind


@dataclass
class Signal:
    symbol: str
    kind: str       # z.B. "RSI_OVERSOLD", "SMA_CROSS_UP", "VOLUME_SPIKE"
    message: str


def evaluate(symbol: str, df: pd.DataFrame, cfg: dict) -> list[Signal]:
    close = df["Close"]
    volume = df["Volume"]

    rsi_series = ind.rsi(close, cfg.get("rsi_period", 14))
    sma_short = ind.sma(close, cfg.get("sma_short", 20))
    sma_long = ind.sma(close, cfg.get("sma_long", 50))
    macd_df = ind.macd(close)
    bb = ind.bollinger_bands(close, cfg.get("bollinger_period", 20), cfg.get("bollinger_stddev", 2.0))
    vol_spike = ind.volume_spike(
        volume, cfg.get("volume_lookback", 20), cfg.get("volume_spike_multiplier", 2.0)
    )

    signals: list[Signal] = []
    last = -1
    prev = -2
    if len(df) < max(cfg.get("sma_long", 50), cfg.get("bollinger_period", 20)) + 2:
        return signals  # zu wenig Historie für verlässliche Signale

    last_close = close.iloc[last]
    last_rsi = rsi_series.iloc[last]

    if last_rsi <= cfg.get("rsi_oversold", 30):
        signals.append(Signal(symbol, "RSI_OVERSOLD", f"RSI {last_rsi:.1f} <= {cfg.get('rsi_oversold', 30)} (überverkauft)"))
    elif last_rsi >= cfg.get("rsi_overbought", 70):
        signals.append(Signal(symbol, "RSI_OVERBOUGHT", f"RSI {last_rsi:.1f} >= {cfg.get('rsi_overbought', 70)} (überkauft)"))

    crossed_up = sma_short.iloc[prev] <= sma_long.iloc[prev] and sma_short.iloc[last] > sma_long.iloc[last]
    crossed_down = sma_short.iloc[prev] >= sma_long.iloc[prev] and sma_short.iloc[last] < sma_long.iloc[last]
    if crossed_up:
        signals.append(Signal(symbol, "SMA_CROSS_UP", f"SMA{cfg.get('sma_short',20)} kreuzt SMA{cfg.get('sma_long',50)} nach oben"))
    elif crossed_down:
        signals.append(Signal(symbol, "SMA_CROSS_DOWN", f"SMA{cfg.get('sma_short',20)} kreuzt SMA{cfg.get('sma_long',50)} nach unten"))

    macd_crossed_up = macd_df["macd"].iloc[prev] <= macd_df["signal"].iloc[prev] and macd_df["macd"].iloc[last] > macd_df["signal"].iloc[last]
    macd_crossed_down = macd_df["macd"].iloc[prev] >= macd_df["signal"].iloc[prev] and macd_df["macd"].iloc[last] < macd_df["signal"].iloc[last]
    if macd_crossed_up:
        signals.append(Signal(symbol, "MACD_BULLISH", "MACD kreuzt Signal-Linie nach oben"))
    elif macd_crossed_down:
        signals.append(Signal(symbol, "MACD_BEARISH", "MACD kreuzt Signal-Linie nach unten"))

    if last_close < bb["lower"].iloc[last]:
        signals.append(Signal(symbol, "BOLLINGER_LOWER", "Kurs unter unterem Bollinger-Band"))
    elif last_close > bb["upper"].iloc[last]:
        signals.append(Signal(symbol, "BOLLINGER_UPPER", "Kurs über oberem Bollinger-Band"))

    if bool(vol_spike.iloc[last]):
        signals.append(Signal(symbol, "VOLUME_SPIKE", "Ungewöhnlich hohes Handelsvolumen"))

    return signals
