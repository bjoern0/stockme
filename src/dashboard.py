"""Erzeugt eine statische docs/index.html (Chart.js via CDN) mit Kursverlauf, RSI und
den zuletzt gesendeten Alerts. Wird über GitHub Pages ausgeliefert (Settings -> Pages ->
Branch: main, Ordner: /docs).

Da bei jedem Lauf ohnehin frische Kursdaten geholt werden, braucht es keine eigene
Preis-Historie-Tabelle - die Charts basieren direkt auf den zuletzt gefetchten Daten.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from . import indicators as ind
from .signals import overall_bias

OUTPUT_PATH = Path(__file__).resolve().parent.parent / "docs" / "index.html"

BIAS_COLORS = {"bullish": "#3ecf6b", "bearish": "#ff5c5c", "neutral": "#999"}

TEMPLATE = """<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="utf-8">
<title>stockme Dashboard</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4"></script>
<style>
  body {{ font-family: system-ui, sans-serif; margin: 2rem; background: #0f1115; color: #e6e6e6; }}
  h1 {{ font-size: 1.4rem; }}
  .meta {{ color: #999; font-size: 0.85rem; margin-bottom: 2rem; }}
  .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(420px, 1fr)); gap: 1.5rem; }}
  .card {{ background: #1a1d24; border-radius: 8px; padding: 1rem; }}
  .card h2 {{ margin: 0 0 0.5rem 0; font-size: 1.1rem; }}
  table {{ width: 100%; border-collapse: collapse; margin-top: 2rem; font-size: 0.9rem; }}
  th, td {{ text-align: left; padding: 0.4rem 0.6rem; border-bottom: 1px solid #333; }}
  th {{ color: #999; }}
  .disclaimer {{ margin-top: 2rem; color: #777; font-size: 0.8rem; }}
</style>
</head>
<body>
<h1>stockme Dashboard</h1>
<div class="meta">Letztes Update: {generated_at} UTC &middot; kein automatisiertes Trading, reine Analyse</div>

<div class="grid" id="charts"></div>

<h2>Letzte Alerts</h2>
<table>
  <thead><tr><th>Zeitpunkt (UTC)</th><th>Symbol</th><th>Signal</th></tr></thead>
  <tbody>
    {alert_rows}
  </tbody>
</table>

<div class="disclaimer">Reine technische Analyse, keine Anlageberatung, no warranty.</div>

<script>
const chartData = {chart_data_json};
for (const [symbol, data] of Object.entries(chartData)) {{
  const grid = document.getElementById('charts');
  const card = document.createElement('div');
  card.className = 'card';
  card.innerHTML = `<h2>${{symbol}} <span style="font-size:0.8rem; color:${{data.bias_color}}">&#9679; ${{data.bias}}</span></h2>` +
    `<div style="font-size:0.8rem; color:#999; margin-bottom:0.5rem">${{data.bias_reason}}<br>` +
    `ATR(14): ${{data.atr}} &middot; Support: ${{data.support}} &middot; Resistance: ${{data.resistance}}</div>` +
    `<canvas></canvas>`;
  grid.appendChild(card);
  const ctx = card.querySelector('canvas');
  new Chart(ctx, {{
    type: 'line',
    data: {{
      labels: data.dates,
      datasets: [
        {{ label: 'Close', data: data.close, borderColor: '#4ea1ff', yAxisID: 'y', tension: 0.1, pointRadius: 0 }},
        {{ label: 'RSI', data: data.rsi, borderColor: '#ff9f4e', yAxisID: 'y1', tension: 0.1, pointRadius: 0 }}
      ]
    }},
    options: {{
      scales: {{
        y: {{ position: 'left' }},
        y1: {{ position: 'right', min: 0, max: 100, grid: {{ drawOnChartArea: false }} }}
      }}
    }}
  }});
}}
</script>
</body>
</html>
"""


def _series_for_symbol(df: pd.DataFrame, cfg: dict, days: int = 90) -> dict:
    close = df["Close"].tail(days)
    rsi = ind.rsi(df["Close"]).tail(days)

    bias, reason = overall_bias(df, cfg)
    atr_value = ind.atr(df, cfg.get("atr_period", 14)).iloc[-1]
    support, resistance = ind.support_resistance(df, cfg.get("support_resistance_window", 20))

    return {
        "dates": [d.strftime("%Y-%m-%d") for d in close.index],
        "close": [round(v, 2) for v in close.tolist()],
        "rsi": [round(v, 1) for v in rsi.tolist()],
        "bias": bias,
        "bias_color": BIAS_COLORS.get(bias, "#999"),
        "bias_reason": reason,
        "atr": round(float(atr_value), 2) if pd.notna(atr_value) else "n/a",
        "support": round(support, 2),
        "resistance": round(resistance, 2),
    }


def render(symbol_dataframes: dict[str, pd.DataFrame], recent_alerts: list, indicator_cfg: dict | None = None) -> None:
    cfg = indicator_cfg or {}
    chart_data = {
        symbol: _series_for_symbol(df, cfg) for symbol, df in symbol_dataframes.items() if df is not None
    }

    alert_rows = "\n".join(
        f"<tr><td>{row['sent_at'][:19].replace('T', ' ')}</td><td>{row['symbol']}</td>"
        f"<td>{row['message'] or row['kind']}</td></tr>"
        for row in recent_alerts
    ) or "<tr><td colspan=\"3\">Noch keine Alerts.</td></tr>"

    html = TEMPLATE.format(
        generated_at=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M"),
        alert_rows=alert_rows,
        chart_data_json=json.dumps(chart_data),
    )

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(html, encoding="utf-8")
