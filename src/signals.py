"""Kombiniert Indikatoren zu einfachen, nachvollziehbaren Signalen.

Bewusst simpel gehalten: lieber wenige robuste Regeln als viele überoptimierte Parameter
(Overfitting auf historische Daten ist das größte Risiko bei sowas)."""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
from . import strategies

from . import indicators as ind


@dataclass
class Signal:
    symbol: str
    kind: str       # z.B. "RSI_OVERSOLD", "SMA_CROSS_UP", "VOLUME_SPIKE"
    message: str


def evaluate(symbol: str, df: pd.DataFrame, cfg: dict) -> list[Signal]:
    """Berechnet Indikatoren und wertet sie auf Basis von Einzel- und Kombinationsregeln (Strategien) aus."""
    if len(df) < max(cfg.get("sma_long", 50), cfg.get("bollinger_period", 20), 26) + 2:
        return []  # zu wenig Historie für verlässliche Signale

    # 1. Alle Indikatoren einmalig berechnen
    close = df["Close"]
    volume = df["Volume"]

    rsi_series = ind.rsi(close, cfg.get("rsi_period", 14))
    sma_short = ind.sma(close, cfg.get("sma_short", 20))
    sma_long = ind.sma(close, cfg.get("sma_long", 50))
    macd_df = ind.macd(close)  # nutzt Standard-Parameter, die nicht in config sind
    bb_df = ind.bollinger_bands(close, cfg.get("bollinger_period", 20), cfg.get("bollinger_stddev", 2.0))
    vol_spike_series = ind.volume_spike(
        volume, cfg.get("volume_lookback", 20), cfg.get("volume_spike_multiplier", 2.0)
    )
    support, resistance = ind.support_resistance(df, cfg.get("support_resistance_window", 20))

    signals: list[Signal] = []
    last = -1
    prev = -2

    last_close = close.iloc[last]
    last_rsi = rsi_series.iloc[last]

    # 2. Einzelne, grundlegende Signale prüfen
    if last_rsi <= cfg.get("rsi_oversold", 30):
        signals.append(Signal(symbol, "RSI_OVERSOLD", f"RSI {last_rsi:.1f} <= {cfg.get('rsi_oversold', 30)} (überverkauft)"))
    elif last_rsi >= cfg.get("rsi_overbought", 70):
        signals.append(Signal(symbol, "RSI_OVERBOUGHT", f"RSI {last_rsi:.1f} >= {cfg.get('rsi_overbought', 70)} (überkauft)"))

    crossed_up = sma_short.iloc[prev] <= sma_long.iloc[prev] and sma_short.iloc[last] > sma_long.iloc[last]
    crossed_down = sma_short.iloc[prev] >= sma_long.iloc[prev] and sma_short.iloc[last] < sma_long.iloc[last]
    if crossed_up:
        signals.append(Signal(symbol, "SMA_CROSS_UP", f"SMA{cfg.get('sma_short', 20)} kreuzt SMA{cfg.get('sma_long', 50)} nach oben"))
    elif crossed_down:
        signals.append(Signal(symbol, "SMA_CROSS_DOWN", f"SMA{cfg.get('sma_short', 20)} kreuzt SMA{cfg.get('sma_long', 50)} nach unten"))

    macd_crossed_up = macd_df["macd"].iloc[prev] <= macd_df["signal"].iloc[prev] and macd_df["macd"].iloc[last] > macd_df["signal"].iloc[last]
    macd_crossed_down = macd_df["macd"].iloc[prev] >= macd_df["signal"].iloc[prev] and macd_df["macd"].iloc[last] < macd_df["signal"].iloc[last]
    if macd_crossed_up:
        signals.append(Signal(symbol, "MACD_BULLISH", "MACD kreuzt Signal-Linie nach oben"))
    elif macd_crossed_down:
        signals.append(Signal(symbol, "MACD_BEARISH", "MACD kreuzt Signal-Linie nach unten"))

    if last_close < bb_df["lower"].iloc[last]:
        signals.append(Signal(symbol, "BOLLINGER_LOWER", "Kurs unter unterem Bollinger-Band"))
    elif last_close > bb_df["upper"].iloc[last]:
        signals.append(Signal(symbol, "BOLLINGER_UPPER", "Kurs über oberem Bollinger-Band"))

    if bool(vol_spike_series.iloc[last]):
        signals.append(Signal(symbol, "VOLUME_SPIKE", "Ungewöhnlich hohes Handelsvolumen"))

    if last_close > resistance:
        signals.append(Signal(symbol, "RESISTANCE_BREAKOUT", f"Kurs {last_close:.2f} über {cfg.get('support_resistance_window', 20)}-Tage-Hoch ({resistance:.2f})"))
    elif last_close < support:
        signals.append(Signal(symbol, "SUPPORT_BREAKDOWN", f"Kurs {last_close:.2f} unter {cfg.get('support_resistance_window', 20)}-Tage-Tief ({support:.2f})"))

    # 3. Kombinierte Signale (Strategien) prüfen für klarere Ein-/Ausstiegs-Chancen
    indicator_data = strategies.IndicatorData(
        symbol=symbol, df=df, rsi=rsi_series, sma_short=sma_short, sma_long=sma_long,
        macd=macd_df, bollinger=bb_df, cfg=cfg
    )
    for strategy_func in strategies.ALL_STRATEGIES:
        signals.extend(strategy_func(indicator_data))

    return signals


def overall_bias(df: pd.DataFrame, cfg: dict) -> tuple[str, str]:
    """Fasst mehrere Indikatoren zu einer groben Einordnung zusammen (bullish/bearish/neutral)."""
    close = df["Close"]
    if len(df) < max(cfg.get("sma_long", 50), 26) + 2:
        return "neutral", "zu wenig Historie"

    sma_short = ind.sma(close, cfg.get("sma_short", 20)).iloc[-1]
    sma_long = ind.sma(close, cfg.get("sma_long", 50)).iloc[-1]
    macd_hist = ind.macd(close)["hist"].iloc[-1]
    last_rsi = ind.rsi(close, cfg.get("rsi_period", 14)).iloc[-1]
    last_close = close.iloc[-1]

    score = 0
    reasons = []

    if last_close > sma_short > sma_long:
        score += 1
        reasons.append("Aufwärtstrend (Kurs > SMA-kurz > SMA-lang)")
    elif last_close < sma_short < sma_long:
        score -= 1
        reasons.append("Abwärtstrend (Kurs < SMA-kurz < SMA-lang)")

    if macd_hist > 0:
        score += 1
        reasons.append("MACD-Histogramm positiv")
    elif macd_hist < 0:
        score -= 1
        reasons.append("MACD-Histogramm negativ")

    if 50 < last_rsi < cfg.get("rsi_overbought", 70):
        score += 1
        reasons.append(f"RSI {last_rsi:.0f} mit bullischem Momentum")
    elif cfg.get("rsi_oversold", 30) < last_rsi < 50:
        score -= 1
        reasons.append(f"RSI {last_rsi:.0f} mit bärischem Momentum")

    label = "bullish" if score >= 2 else "bearish" if score <= -2 else "neutral"
    return label, "; ".join(reasons) if reasons else "keine klare Tendenz"
