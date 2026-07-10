"""Technische Indikatoren, bewusst ohne pandas-ta implementiert (weniger Dependency-Ärger,
z.B. bekannte Kompatibilitätsprobleme von pandas-ta mit neueren numpy-Versionen)."""
from __future__ import annotations

import pandas as pd


def sma(series: pd.Series, period: int) -> pd.Series:
    return series.rolling(window=period).mean()


def ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()


def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(window=period).mean()
    avg_loss = loss.rolling(window=period).mean()
    rs = avg_gain / avg_loss.replace(0, float("nan"))
    result = 100 - (100 / (1 + rs))
    return result.fillna(50)  # neutral, solange nicht genug Historie da ist


def macd(series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
    ema_fast = ema(series, fast)
    ema_slow = ema(series, slow)
    macd_line = ema_fast - ema_slow
    signal_line = ema(macd_line, signal)
    return pd.DataFrame({"macd": macd_line, "signal": signal_line, "hist": macd_line - signal_line})


def bollinger_bands(series: pd.Series, period: int = 20, stddev: float = 2.0) -> pd.DataFrame:
    mid = sma(series, period)
    std = series.rolling(window=period).std()
    return pd.DataFrame({"mid": mid, "upper": mid + stddev * std, "lower": mid - stddev * std})


def volume_spike(volume: pd.Series, lookback: int = 20, multiplier: float = 2.0) -> pd.Series:
    avg_volume = volume.rolling(window=lookback).mean()
    return volume > (avg_volume * multiplier)
