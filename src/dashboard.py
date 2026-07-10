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

# Kategorie je Alert-"kind" (siehe state.py/signals.py) - für Filter-Dropdown & Highlighting im Dashboard.
# PRIORITY_CATEGORIES werden in der Alert-Tabelle optisch hervorgehoben (Breakouts, Top-Mover, Reddit-Spikes:
# das sind typischerweise die Alerts mit dem größten "etwas Ungewöhnliches passiert"-Neuigkeitswert).
CATEGORY_MAP = {
    "RSI_OVERSOLD": "RSI", "RSI_OVERBOUGHT": "RSI",
    "SMA_CROSS_UP": "Trend", "SMA_CROSS_DOWN": "Trend",
    "MACD_BULLISH": "MACD", "MACD_BEARISH": "MACD",
    "BOLLINGER_LOWER": "Bollinger", "BOLLINGER_UPPER": "Bollinger",
    "VOLUME_SPIKE": "Volumen",
    "RESISTANCE_BREAKOUT": "Breakout", "SUPPORT_BREAKDOWN": "Breakout",
    "REDDIT_MENTIONS": "Reddit",
}
PRIORITY_CATEGORIES = {"Breakout", "Top-Mover", "Reddit"}


def _categorize(kind: str) -> str:
    if kind.startswith("TOP_MOVER_"):
        return "Top-Mover"
    return CATEGORY_MAP.get(kind, "Sonstige")

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
  .filter-bar {{ display: flex; gap: 0.75rem; align-items: center; margin-top: 0.75rem; flex-wrap: wrap; }}
  .filter-bar input, .filter-bar select {{
    background: #1a1d24; color: #e6e6e6; border: 1px solid #333; border-radius: 6px; padding: 0.4rem 0.6rem;
  }}
  tr.priority {{ box-shadow: inset 3px 0 0 #ff9f4e; background: rgba(255, 159, 78, 0.08); }}
  tr.hidden-row {{ display: none; }}
  .card.hidden-card {{ display: none; }}
  a.symlink {{ color: #4ea1ff; text-decoration: none; cursor: pointer; }}
  a.symlink:hover {{ text-decoration: underline; }}
</style>
</head>
<body>
<h1>stockme Dashboard</h1>
<div class="meta">Letztes Update: {generated_at} UTC &middot; kein automatisiertes Trading, reine Analyse</div>

<div class="filter-bar">
  <input type="text" id="symbolFilter" placeholder="Symbol filtern (z.B. NVDA)...">
  <select id="categoryFilter">
    <option value="">Alle Kategorien</option>
    <option value="Breakout">Breakout</option>
    <option value="Top-Mover">Top-Mover</option>
    <option value="Reddit">Reddit</option>
    <option value="RSI">RSI</option>
    <option value="MACD">MACD</option>
    <option value="Bollinger">Bollinger</option>
    <option value="Volumen">Volumen</option>
    <option value="Trend">Trend</option>
    <option value="Sonstige">Sonstige</option>
  </select>
  <button id="resetFilters">Filter zurücksetzen</button>
</div>

<h2>Übersicht</h2>
<table>
  <thead><tr><th>Symbol</th><th>Preis</th><th>Tag %</th><th>EMA50</th><th>EMA200</th>
    <th>Potential*</th><th>Bias</th></tr></thead>
  <tbody>
    {overview_rows}
  </tbody>
</table>
<div class="disclaimer">*Potential = Abstand zum EMA200 in % (Mean-Reversion-Maß: wie weit müsste der Kurs
zum langfristigen Durchschnitt aufholen/nachgeben). Keine Kursprognose oder Kursziel.</div>

<div class="grid" id="charts"></div>

<h2>Letzte Alerts</h2>
<table id="alertsTable">
  <thead><tr><th>Zeitpunkt (UTC)</th><th>Symbol</th><th>Kategorie</th><th>Signal</th></tr></thead>
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
  card.id = 'card-' + symbol;
  card.dataset.symbol = symbol;
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

function scrollToChart(symbol) {{
  const card = document.getElementById('card-' + symbol);
  if (card) {{
    card.scrollIntoView({{ behavior: 'smooth', block: 'center' }});
    card.style.outline = '2px solid #4ea1ff';
    setTimeout(() => card.style.outline = '', 1500);
  }}
}}

function applyFilters() {{
  const symbolQuery = document.getElementById('symbolFilter').value.trim().toUpperCase();
  const category = document.getElementById('categoryFilter').value;

  document.querySelectorAll('#alertsTable tbody tr').forEach(row => {{
    const rowSymbol = (row.dataset.symbol || '').toUpperCase();
    const rowCategory = row.dataset.category || '';
    const symbolMatch = !symbolQuery || rowSymbol.includes(symbolQuery);
    const categoryMatch = !category || rowCategory === category;
    row.classList.toggle('hidden-row', !(symbolMatch && categoryMatch));
  }});

  document.querySelectorAll('#charts .card').forEach(card => {{
    const cardSymbol = (card.dataset.symbol || '').toUpperCase();
    card.classList.toggle('hidden-card', !(!symbolQuery || cardSymbol.includes(symbolQuery)));
  }});
}}

// addEventListener statt inline onclick/onchange-Attribute: robuster, funktioniert auch wenn
// Browser/Erweiterungen/CSP-Regeln Inline-Event-Handler blockieren.
document.getElementById('symbolFilter').addEventListener('input', applyFilters);
document.getElementById('categoryFilter').addEventListener('change', applyFilters);
document.getElementById('resetFilters').addEventListener('click', () => {{
  document.getElementById('symbolFilter').value = '';
  document.getElementById('categoryFilter').value = '';
  applyFilters();
}});
document.getElementById('alertsTable').addEventListener('click', (event) => {{
  const link = event.target.closest('.symlink');
  if (link) {{
    const row = link.closest('tr');
    if (row) scrollToChart(row.dataset.symbol);
  }}
}});
</script>
</body>
</html>
"""


def _series_for_symbol(df: pd.DataFrame, cfg: dict, days: int = 90) -> dict:
    full_close = df["Close"]
    close = full_close.tail(days)
    rsi = ind.rsi(full_close).tail(days)

    bias, reason = overall_bias(df, cfg)
    atr_value = ind.atr(df, cfg.get("atr_period", 14)).iloc[-1]
    support, resistance = ind.support_resistance(df, cfg.get("support_resistance_window", 20))

    last_price = float(full_close.iloc[-1])
    prev_price = float(full_close.iloc[-2]) if len(full_close) > 1 else last_price
    day_change_pct = (last_price / prev_price - 1) * 100 if prev_price else 0.0

    ema50 = ind.ema(full_close, 50).iloc[-1]
    ema200 = ind.ema(full_close, 200).iloc[-1] if len(full_close) >= 200 else float("nan")
    # "Potential" = Abstand zum EMA200 in % (Mean-Reversion-Maß, KEINE Kursprognose/-ziel):
    # positiv = Kurs unter EMA200 (Aufholpotential zum langfristigen Schnitt),
    # negativ = Kurs über EMA200 (bereits darüber gelaufen)
    potential_pct = (ema200 / last_price - 1) * 100 if pd.notna(ema200) and last_price else float("nan")

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
        "price": round(last_price, 2),
        "day_change_pct": round(day_change_pct, 2),
        "ema50": round(float(ema50), 2) if pd.notna(ema50) else None,
        "ema200": round(float(ema200), 2) if pd.notna(ema200) else None,
        "potential_pct": round(float(potential_pct), 2) if pd.notna(potential_pct) else None,
    }


def _overview_rows(chart_data: dict) -> str:
    rows = []
    for symbol, d in chart_data.items():
        change_color = "#3ecf6b" if d["day_change_pct"] >= 0 else "#ff5c5c"
        ema50_txt = f"{d['ema50']:.2f}" if d["ema50"] is not None else "n/a"
        ema200_txt = f"{d['ema200']:.2f}" if d["ema200"] is not None else "n/a (zu wenig Historie)"
        potential_txt = f"{d['potential_pct']:+.1f}%" if d["potential_pct"] is not None else "n/a"
        rows.append(
            f"<tr><td>{symbol}</td><td>{d['price']:.2f}</td>"
            f"<td style=\"color:{change_color}\">{d['day_change_pct']:+.2f}%</td>"
            f"<td>{ema50_txt}</td><td>{ema200_txt}</td><td>{potential_txt}</td>"
            f"<td style=\"color:{d['bias_color']}\">{d['bias']}</td></tr>"
        )
    return "\n".join(rows) or "<tr><td colspan=\"7\">Keine Daten.</td></tr>"


def _alert_row(row) -> str:
    category = _categorize(row["kind"])
    row_class = "priority" if category in PRIORITY_CATEGORIES else ""
    return (
        f"<tr class=\"{row_class}\" data-symbol=\"{row['symbol']}\" data-category=\"{category}\">"
        f"<td>{row['sent_at'][:19].replace('T', ' ')}</td>"
        f"<td><a class=\"symlink\">{row['symbol']}</a></td>"
        f"<td>{category}</td>"
        f"<td>{row['message'] or row['kind']}</td></tr>"
    )


def render(symbol_dataframes: dict[str, pd.DataFrame], recent_alerts: list, indicator_cfg: dict | None = None) -> None:
    cfg = indicator_cfg or {}
    chart_data = {
        symbol: _series_for_symbol(df, cfg) for symbol, df in symbol_dataframes.items() if df is not None
    }

    alert_rows = "\n".join(_alert_row(row) for row in recent_alerts) or (
        "<tr><td colspan=\"4\">Noch keine Alerts.</td></tr>"
    )

    html = TEMPLATE.format(
        generated_at=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M"),
        alert_rows=alert_rows,
        overview_rows=_overview_rows(chart_data),
        chart_data_json=json.dumps(chart_data),
    )

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(html, encoding="utf-8")
