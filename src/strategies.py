from __future__ import annotations

from dataclasses import dataclass

import pandas as pd # pandas ist hier nicht direkt nötig, kann entfernt werden

from .types import Signal # Importiere Signal aus dem neuen Modul


@dataclass
class IndicatorData:
    """Bündelt alle berechneten Indikatoren für eine einfache Übergabe."""

    symbol: str
    df: pd.DataFrame
    rsi: pd.Series
    sma_short: pd.Series
    sma_long: pd.Series
    macd: pd.DataFrame
    bollinger: pd.DataFrame
    cfg: dict


def check_bullish_reversal(data: IndicatorData) -> list[Signal]:
    """Prüft auf ein potenzielles bullisches Umkehrsignal.
    Bedingungen: RSI überverkauft + MACD kreuzt nach oben.
    """
    signals = []
    last = -1
    prev = -2

    is_oversold = data.rsi.iloc[last] <= data.cfg.get("rsi_oversold", 30)
    macd_crossed_up = (
        data.macd["macd"].iloc[prev] <= data.macd["signal"].iloc[prev]
        and data.macd["macd"].iloc[last] > data.macd["signal"].iloc[last]
    )

    if is_oversold and macd_crossed_up:
        signals.append(
            Signal(
                symbol=data.symbol,
                kind="STRATEGY_BULLISH_REVERSAL",
                message=f"Mögliche bullische Umkehr: RSI überverkauft ({data.rsi.iloc[last]:.1f}) und MACD-Kreuzung.",
            )
        )
    return signals


# Hier können zukünftig weitere Strategien ergänzt werden, z.B. für bärische Signale
# oder Trendfolge-Setups.
# def check_bearish_reversal(data: IndicatorData) -> list[Signal]:
#     ...


# Liste aller zu prüfenden Strategien.
# Fügen Sie hier einfach neue Strategie-Funktionen hinzu, um sie zu aktivieren.
ALL_STRATEGIES = [
    check_bullish_reversal,
    # check_bearish_reversal,
]