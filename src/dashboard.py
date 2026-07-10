"""Erzeugt eine statische docs/index.html (Chart.js via CDN) mit Kursverlauf, RSI und
den zuletzt gesendeten Alerts. Wird über GitHub Pages ausgeliefert (Settings -> Pages ->
Branch: main, Ordner: /docs).

Da bei jedem Lauf ohnehin frische Kursdaten geholt werden, braucht es keine eigene
Preis-Historie-Tabelle - die Charts basieren direkt auf den zuletzt gefetchten Daten.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from collections import defaultdict
import logging
from pathlib import Path

import yfinance as yf
import pandas as pd

from . import indicators as ind
from .signals import overall_bias

logger = logging.getLogger(__name__)

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
    "STRATEGY_BULLISH_REVERSAL": "Strategie",
    "REDDIT_MENTIONS": "Reddit",
}
PRIORITY_CATEGORIES = {"Breakout", "Top-Mover", "Reddit", "Strategie"}


def _categorize(kind: str) -> str:
    """Ordnet einem Signal-Typ eine Dashboard-Kategorie zu."""
    if kind.startswith("TOP_MOVER_"):
        return "Top-Mover"
    return CATEGORY_MAP.get(kind, "Sonstige")

TEMPLATE = """<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="utf-8">
<title>stockme Dashboard</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/tablesort/5.2.1/tablesort.min.js"></script>
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
  /* Tablesort.js styles */
  table.sortable th:not(.no-sort) {{ cursor: pointer; }}
  table.sortable th:not(.no-sort):after {{ content: " \\25bc"; opacity: 0.2; }}
  table.sortable th:not(.no-sort).tablesort-asc:after {{ content: " \\25b2"; opacity: 1; }}
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
    <option value="Strategie">Strategie</option>
    <option value="Top-Mover">Top-Mover</option>
    <option value="Reddit">Reddit</option>
    <option value="RSI">RSI</option>
    <option value="MACD">MACD</option>
    <option value="Bollinger">Bollinger</option>
    <option value="Volumen">Volumen</option>
    <option value="Trend">Trend</option>
    <option value="Sonstige">Sonstige</option>
  </select>
  <select id="stockCategoryFilter">
    <option value="">Alle Stock-Kategorien</option>
    <!-- STOCK_CATEGORY_OPTIONS -->
  </select>

  <button id="resetFilters">Filter zurücksetzen</button>
</div>

<div id="fred-data" style="margin-top: 1.5rem; font-size: 0.9rem; color: #999;">
  <!-- FRED data will be inserted here by JS -->
</div>
<script> 
  // Function to format FRED values
  function formatFredValue(seriesId, value) {{
    return parseFloat(value).toFixed(2) + '%'; // Default to percentage for common FRED series
  }}
</script>
<h2>Übersicht</h2> 
<table id="overviewTable" class="sortable">
  <thead><tr><th>Symbol</th><th>Name</th><th>Preis</th><th>Tag %</th><th>EMA50</th><th>EMA200</th><th>Potential*</th><th>KGV</th><th>Div. Rendite</th><th>Marktkap.</th><th>EPS</th>
    <th>RSI</th><th>MACD Hist</th><th>52W High</th><th>52W Low</th><th>Bias</th></tr></thead>
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
  card.className = 'card'; // Add data-categories for filtering
  card.id = 'card-' + symbol;
  card.dataset.symbol = symbol;
  card.dataset.stockCategory = data.stock_category; // Add stock category to card dataset
  card.dataset.alertCategories = data.alert_categories ? data.alert_categories.join(',') : '';
  card.innerHTML = `<h2>${{symbol}} - ${{data.company_name}} <span style="font-size:0.8rem; color:${{data.bias_color}}">&#9679; ${{data.bias}}</span></h2>` +
    `<div style="font-size:0.8rem; color:#999; margin-bottom:0.5rem">${{data.bias_reason}}<br>ATR(14): ${{data.atr}} &middot; Support: ${{data.support}} &middot; Resistance: ${{data.resistance}}<br>52W High: ${{data.fifty_two_week_high}} &middot; 52W Low: ${{data.fifty_two_week_low}}</div>` +
    `<canvas></canvas>`;
  grid.appendChild(card);
  const ctx = card.querySelector('canvas');
  new Chart(ctx, {{
    type: 'line',
    data: {{
      labels: data.dates,
      datasets: [
        {{ label: 'Close', data: data.close, borderColor: '#4ea1ff', yAxisID: 'y', tension: 0.1, pointRadius: 0, borderWidth: 2 }},
        {{ label: 'RSI', data: data.rsi, borderColor: '#ff9f4e', yAxisID: 'y1', tension: 0.1, pointRadius: 0, borderWidth: 1 }},
        {{ label: 'SMA Short', data: data.sma_short, borderColor: 'rgba(255, 204, 0, 0.7)', yAxisID: 'y', tension: 0.1, pointRadius: 0, borderDash: [5, 5], borderWidth: 1 }},
        {{ label: 'SMA Long', data: data.sma_long, borderColor: 'rgba(200, 200, 200, 0.7)', yAxisID: 'y', tension: 0.1, pointRadius: 0, borderDash: [5, 5], borderWidth: 1 }},
        {{ label: 'BB Upper', data: data.bb_upper, borderColor: 'rgba(150, 150, 150, 0.5)', yAxisID: 'y', tension: 0.1, pointRadius: 0, borderWidth: 1 }},
        {{ label: 'BB Lower', data: data.bb_lower, borderColor: 'rgba(150, 150, 150, 0.5)', yAxisID: 'y', tension: 0.1, pointRadius: 0, fill: '-1', backgroundColor: 'rgba(150, 150, 150, 0.05)', borderWidth: 1 }}
      ]
    }},
    options: {{
      scales: {{
        y: {{ position: 'left' }},
        y1: {{ position: 'right', min: 0, max: 100, grid: {{ drawOnChartArea: false }} }}
      }},
      plugins: {{
        legend: {{
          labels: {{ color: '#e6e6e6' }}
        }}
      }},
    }}
  }});

  // MACD Chart
  const macd_card = card.querySelector('canvas:last-of-type');
  new Chart(macd_card, {{
    type: 'bar', // MACD histogram is bar, MACD/Signal lines are line
    data: {{
      labels: data.dates,
      datasets: [
        {{
          label: 'MACD Hist',
          data: data.macd_hist,
          backgroundColor: data.macd_hist.map(val => val >= 0 ? 'rgba(62, 207, 107, 0.6)' : 'rgba(255, 92, 92, 0.6)'),
          yAxisID: 'y',
          barPercentage: 0.8,
          categoryPercentage: 0.8,
        }},
        {{
          type: 'line',
          label: 'MACD',
          data: data.macd_line,
          borderColor: '#4ea1ff',
          yAxisID: 'y',
          tension: 0.1,
          pointRadius: 0,
          borderWidth: 1,
        }},
        {{
          type: 'line',
          label: 'Signal',
          data: data.signal_line,
          borderColor: '#ff9f4e',
          yAxisID: 'y',
          tension: 0.1,
          pointRadius: 0,
          borderWidth: 1,
        }}
      ]
    }},
    options: {{
      scales: {{ y: {{ position: 'left' }} }},
      plugins: {{ legend: {{ labels: {{ color: '#e6e6e6' }} }} }}
    }}
  }});
}}

function scrollToChart(symbol) {{
  const card = document.getElementById('card-' + symbol);
  if (card) {{
    card.scrollIntoView({{ behavior: 'smooth', block: 'center' }}); // Korrektur: scrollOfView -> scrollIntoView
    card.style.outline = '2px solid #4ea1ff';
    setTimeout(() => card.style.outline = '', 1500);
  }}
}}

function applyFilters() {{
  const symbolQuery = document.getElementById('symbolFilter').value.trim().toUpperCase();
  const alertCategory = document.getElementById('categoryFilter').value; // Renamed for clarity
  const stockCategory = document.getElementById('stockCategoryFilter').value; // New stock category filter

  // Filter alerts table
  document.querySelectorAll('#alertsTable tbody tr').forEach(row => {{
    const rowSymbol = (row.dataset.symbol || '').toUpperCase();
    const rowAlertCategory = row.dataset.category || '';
    const symbolMatch = !symbolQuery || rowSymbol.includes(symbolQuery);
    const alertCategoryMatch = !alertCategory || rowAlertCategory === alertCategory;
    row.classList.toggle('hidden-row', !(symbolMatch && alertCategoryMatch));
  }});

  // Filter charts
  document.querySelectorAll('#charts .card').forEach(card => {{
    const cardSymbol = (card.dataset.symbol || '').toUpperCase();
    const cardAlertCategories = (card.dataset.alertCategories || '').split(','); // Use renamed attribute
    const cardStockCategory = card.dataset.stockCategory || ''; // Get stock category from dataset

    const symbolMatch = !symbolQuery || cardSymbol.includes(symbolQuery);
    const alertCategoryMatch = !alertCategory || cardAlertCategories.includes(alertCategory);
    const stockCategoryMatch = !stockCategory || cardStockCategory === stockCategory;

    card.classList.toggle('hidden-card', !(symbolMatch && alertCategoryMatch && stockCategoryMatch));
  }});
}}

// addEventListener statt inline onclick/onchange-Attribute: robuster, funktioniert auch wenn
// Browser/Erweiterungen/CSP-Regeln Inline-Event-Handler blockieren.
document.getElementById('symbolFilter').addEventListener('input', applyFilters);
document.getElementById('categoryFilter').addEventListener('change', applyFilters);
document.getElementById('stockCategoryFilter').addEventListener('change', applyFilters); // New event listener for stock categories
document.getElementById('resetFilters').addEventListener('click', () => {{
  document.getElementById('symbolFilter').value = '';
  document.getElementById('categoryFilter').value = '';
  document.getElementById('stockCategoryFilter').value = ''; // Reset new filter
  applyFilters();
}});
document.getElementById('alertsTable').addEventListener('click', (event) => {{
  const link = event.target.closest('.symlink');
  if (link) {{
    const symbol = link.dataset.symbol; // Get symbol from data-symbol attribute
    if (symbol) scrollToChart(symbol);
  }}
}});

// Scroll to chart from overview table
document.querySelector('table:first-of-type').addEventListener('click', (event) => {{
  // Check if the clicked element or its parent is a td, and then if it's the symbol column
  if (event.target.tagName === 'TD' && event.target.cellIndex === 0) {{
    const symbol = event.target.textContent;
    if (symbol) scrollToChart(symbol);
  }}
}});

// Initialize Tablesort.js on the overview table
try {{
  new Tablesort(document.getElementById('overviewTable'));
  console.log('Tablesort initialized successfully.');
}} catch (e) {{
  console.error('Error initializing Tablesort:', e);
}}


</script>
</body>
</html>
""" # End of TEMPLATE


def _format_fred_data_for_js(fred_data: dict) -> str:
    """Formats FRED data into a string for JavaScript display."""
    if not fred_data:
        return ""
    
    items = []
    for series_id, data in fred_data.items():
        # Use JS function to format values
        items.append(f"<span>{data['display_name']}: <span id='fred-{series_id}'></span> ({data['date']})</span>")
    
    return " &middot; ".join(items)


def _series_for_symbol(symbol: str, df: pd.DataFrame, cfg: dict, stock_category: str = "Uncategorized", days: int = 90) -> dict:
    full_close = df["Close"]
    # Sicherstellen, dass wir nicht mehr Daten anfordern als vorhanden
    if len(full_close) < days:
        days = len(full_close)

    close = full_close.tail(days)

    # MACD muss über den gesamten DataFrame berechnet werden, um korrekte Werte zu erhalten
    macd_df_full = ind.macd(full_close)

    rsi = ind.rsi(full_close, cfg.get("rsi_period", 14)).tail(days)
    sma_short = ind.sma(full_close, cfg.get("sma_short", 20)).tail(days)
    sma_long = ind.sma(full_close, cfg.get("sma_long", 50)).tail(days)
    bb = ind.bollinger_bands(full_close, cfg.get("bollinger_period", 20), cfg.get("bollinger_stddev", 2.0)).tail(days)

    bias, reason = overall_bias(df, cfg)
    atr_value = ind.atr(df, cfg.get("atr_period", 14)).iloc[-1] if len(df) > cfg.get("atr_period", 14) else float("nan")

    # 52-Wochen-Hoch/-Tief über den gesamten verfügbaren DataFrame
    fifty_two_week_high = float(df["High"].max())
    fifty_two_week_low = float(df["Low"].min())

    support, resistance = ind.support_resistance(df, cfg.get("support_resistance_window", 20))

    last_price = float(full_close.iloc[-1])
    prev_price = float(full_close.iloc[-2]) if len(full_close) > 1 else last_price
    day_change_pct = (last_price / prev_price - 1) * 100 if prev_price else 0.0

    ema50 = ind.ema(full_close, 50).iloc[-1]
    ema200 = ind.ema(full_close, 200).iloc[-1] if len(full_close) >= 200 else float("nan")
    # "Potential" = Abstand zum EMA200 in % (Mean-Reversion-Maß, KEINE Kursprognose/-ziel):
    # positiv = Kurs unter EMA200 (Aufholpotential zum langfristigen Schnitt),
    # negativ = Kurs über EMA200 (bereits darüber gelaufen)
    potential_pct = float("nan")
    if pd.notna(ema200) and last_price and last_price != 0: # Zusätzliche Prüfung auf last_price != 0
        potential_pct = (ema200 / last_price - 1) * 100

    # --- Fundamentaldaten abrufen ---
    pe_ratio: float | None = None
    dividend_yield: float | None = None
    market_cap: float | None = None
    company_name: str | None = None
    eps: float | None = None
    try:
        ticker_info = yf.Ticker(symbol).info
        pe_ratio = ticker_info.get("trailingPE")
        dividend_yield = ticker_info.get("dividendYield")
        market_cap = ticker_info.get("marketCap")
        eps = ticker_info.get("trailingEps")
        company_name = ticker_info.get("longName") or ticker_info.get("shortName")
    except Exception as e:
        logger.warning(f"Konnte Fundamentaldaten für {symbol} nicht abrufen: {e}")
    # --- ENDE Fundamentaldaten ---

    return {
        "dates": [d.strftime("%Y-%m-%d") for d in close.index],
        "close": [round(v, 2) for v in close.tolist()],
        "rsi": [round(v, 1) for v in rsi.tolist()],
        "sma_short": [round(v, 2) if pd.notna(v) else None for v in sma_short.tolist()],
        "sma_long": [round(v, 2) if pd.notna(v) else None for v in sma_long.tolist()],
        "bb_upper": [round(v, 2) if pd.notna(v) else None for v in bb["upper"].tolist()],
        "bb_lower": [round(v, 2) if pd.notna(v) else None for v in bb["lower"].tolist()],
        "macd_line": [round(v, 2) if pd.notna(v) else None for v in macd_df_full["macd"].tail(days).tolist()],
        "signal_line": [round(v, 2) if pd.notna(v) else None for v in macd_df_full["signal"].tail(days).tolist()],
        "macd_hist": [round(v, 2) if pd.notna(v) else None for v in macd_df_full["hist"].tail(days).tolist()],
        "bias": bias,
        "bias_color": BIAS_COLORS.get(bias, "#999"),
        "bias_reason": reason,
        "atr": round(float(atr_value), 2) if pd.notna(atr_value) else "n/a",
        "support": round(support, 2),
        "resistance": round(resistance, 2),
        "fifty_two_week_high": round(fifty_two_week_high, 2),
        "fifty_two_week_low": round(fifty_two_week_low, 2),
        "price": round(last_price, 2),
        "day_change_pct": round(day_change_pct, 2),
        "ema50": round(float(ema50), 2) if pd.notna(ema50) else None,
        "ema200": round(float(ema200), 2) if pd.notna(ema200) else None,
        "potential_pct": round(float(potential_pct), 2) if pd.notna(potential_pct) else None,
        "last_rsi": round(float(rsi.iloc[-1]), 1),
        "last_macd_hist": round(float(macd_df_full["hist"].iloc[-1]), 2) if pd.notna(macd_df_full["hist"].iloc[-1]) else None,
        # --- Fundamentaldaten formatieren und hinzufügen ---
        "pe_ratio": round(pe_ratio, 2) if isinstance(pe_ratio, (int, float)) and pd.notna(pe_ratio) else "n/a", 
        "dividend_yield": (
            f"{dividend_yield:.2f}%" if isinstance(dividend_yield, (int, float)) and pd.notna(dividend_yield) and dividend_yield > 1.0 # If already scaled (e.g., 1.85 for 1.85%)
            else f"{dividend_yield * 100:.2f}%" if isinstance(dividend_yield, (int, float)) and pd.notna(dividend_yield) # If decimal (e.g., 0.0185 for 1.85%)
            else "n/a"
        ),
        "market_cap": f"{market_cap / 1_000_000_000:.2f}B" if isinstance(market_cap, (int, float)) and pd.notna(market_cap) else "n/a", # Format in Billions
        "stock_category": stock_category,
        "company_name": company_name if company_name else "n/a",
        "eps": round(eps, 2) if isinstance(eps, (int, float)) and pd.notna(eps) else "n/a",
    }


def _overview_rows(chart_data: dict) -> str: # This function was already correct, no changes needed here.
    rows = []
    for symbol, d in chart_data.items():
        # Proximity to 52W High/Low
        high_proximity_pct = (d['price'] / d['fifty_two_week_high'] - 1) * 100 if d['fifty_two_week_high'] else float('nan')
        low_proximity_pct = (d['price'] / d['fifty_two_week_low'] - 1) * 100 if d['fifty_two_week_low'] else float('nan')

        high_prox_txt = f"{high_proximity_pct:+.1f}%" if pd.notna(high_proximity_pct) else "n/a"
        low_prox_txt = f"{low_proximity_pct:+.1f}%" if pd.notna(low_proximity_pct) else "n/a"

        # Format MACD Hist
        macd_hist_txt = f"{d['last_macd_hist']:+.2f}" if d['last_macd_hist'] is not None else "n/a"
        macd_hist_color = "#3ecf6b" if d['last_macd_hist'] is not None and d['last_macd_hist'] >= 0 else "#ff5c5c"
        # Fallback for None, though it should be handled by the check above
        if d['last_macd_hist'] is None:
            macd_hist_color = "#999"


        change_color = "#3ecf6b" if d["day_change_pct"] >= 0 else "#ff5c5c"
        ema50_txt = f"{d['ema50']:.2f}" if d["ema50"] is not None else "n/a"
        ema200_txt = f"{d['ema200']:.2f}" if d["ema200"] is not None else "n/a (zu wenig Historie)"
        potential_txt = f"{d['potential_pct']:+.1f}%" if pd.notna(d.get('potential_pct')) else "n/a" # Robustere Prüfung auf NaN
        pe_ratio_val = d.get('pe_ratio')
        pe_ratio_txt = f"{pe_ratio_val:.2f}" if isinstance(pe_ratio_val, (int, float)) else "n/a"

        dividend_yield_val = d.get('dividend_yield')
        dividend_yield_txt = dividend_yield_val if isinstance(dividend_yield_val, str) else "n/a"

        market_cap_val = d.get('market_cap')
        market_cap_txt = market_cap_val if isinstance(market_cap_val, str) else "n/a"

        eps_val = d.get('eps')
        eps_txt = f"{eps_val:.2f}" if isinstance(eps_val, (int, float)) else "n/a"

        rows.append(
            f"<tr data-stock-category=\"{d['stock_category']}\"><td>{symbol}</td><td>{d['company_name']}</td><td>{d['price']:.2f}</td>"
            f"<td style=\"color:{change_color}\">{d['day_change_pct']:+.2f}%</td>"
            f"<td>{ema50_txt}</td><td>{ema200_txt}</td><td>{potential_txt}</td>" # Potential
            f"<td>{pe_ratio_txt}</td>" # KGV
            f"<td>{dividend_yield_txt}</td>" # Dividendenrendite
            f"<td>{market_cap_txt}</td>" # Marktkapitalisierung
            f"<td>{eps_txt}</td>" # EPS
            f"<td>{d['last_rsi']:.1f}</td>" # RSI
            f"<td style=\"color:{macd_hist_color}\">{macd_hist_txt}</td>" # MACD Hist
            f"<td>{high_prox_txt}</td>" # 52W High Proximity
            f"<td>{low_prox_txt}</td>" # 52W Low Proximity
            f"<td style=\"color:{d['bias_color']}\">{d['bias']}</td></tr>"
        )
    return "\n".join(rows) or "<tr><td colspan=\"17\">Keine Daten.</td></tr>"


def _alert_row(row) -> str:
    category = _categorize(row["kind"])
    row_class = "priority" if category in PRIORITY_CATEGORIES else ""
    return (
        f"<tr class=\"{row_class}\" data-symbol=\"{row['symbol']}\" data-category=\"{category}\">"
        f"<td>{row['sent_at'][:19].replace('T', ' ')}</td>"
        f"<td><a class=\"symlink\" data-symbol=\"{row['symbol']}\">{row['symbol']}</a></td>"
        f"<td>{category}</td>"
        f"<td>{row['message'] or row['kind']}</td></tr>"
    )


def render(symbol_dataframes: dict[str, pd.DataFrame], recent_alerts: list, indicator_cfg: dict | None = None, fred_economic_data: dict | None = None, stock_configs: list[dict[str, str]] | None = None) -> None:
    cfg = indicator_cfg or {}
    stock_configs = stock_configs or []
    # Create a mapping from symbol to its stock category for easy lookup
    symbol_to_stock_category = {item['symbol']: item.get('category', 'Uncategorized') for item in stock_configs}

    # Sammle alle Kategorien pro Symbol aus den Alerts
    symbol_to_alert_categories = defaultdict(set)
    for row in recent_alerts:
        symbol_to_alert_categories[row['symbol']].add(_categorize(row['kind']))
    
    # Get all unique stock categories for the filter dropdown
    all_stock_categories = sorted(list(set(symbol_to_stock_category.values())))
    stock_category_options = "".join([f"<option value=\"{cat}\">{cat}</option>" for cat in all_stock_categories])

    chart_data = {}
    for symbol, df in symbol_dataframes.items():
        if df is not None:
            stock_category = symbol_to_stock_category.get(symbol, "Uncategorized")
            data = _series_for_symbol(symbol, df, cfg, stock_category=stock_category) # Pass stock_category
            data['alert_categories'] = list(symbol_to_alert_categories[symbol]) # Füge Kategorien zu den Chart-Daten hinzu
            chart_data[symbol] = data

    alert_rows = "\n".join(_alert_row(row) for row in recent_alerts) or (
        "<tr><td colspan=\"4\">Noch keine Alerts.</td></tr>"
    )

    fred_data_html = _format_fred_data_for_js(fred_economic_data or {})

    html = TEMPLATE.format(
        generated_at=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M"),
        fred_data_html=fred_data_html,
        alert_rows=alert_rows,
        overview_rows=_overview_rows(chart_data),
        chart_data_json=json.dumps(chart_data),
    )
    html = html.replace("<!-- STOCK_CATEGORY_OPTIONS -->", stock_category_options)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(html, encoding="utf-8")

    # Inject FRED data values into the HTML after rendering
    if fred_economic_data:
        fred_script = "<script>\n"
        for series_id, data in fred_economic_data.items():
            fred_script += f"  document.getElementById('fred-{series_id}').textContent = formatFredValue('{series_id}', {data['value']});\n"
        fred_script += "</script>"
        with open(OUTPUT_PATH, "a", encoding="utf-8") as f:
            f.write(fred_script)