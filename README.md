# stockme

Kleiner, kostenloser Scanner für technische Signale + marktweite Top-Mover, mit Alerts per Telegram.
**Kein automatisiertes Trading** – reine Analyse/Benachrichtigung, Ausführung bleibt manuell.

## Konzept

- `config.yaml` – Watchlist + Schwellwerte, kein Code-Change nötig zum Erweitern
- `src/data.py` – Kursdaten via `yfinance` (kostenlos, kein API-Key)
- `src/indicators.py` – RSI, SMA/EMA, MACD, Bollinger Bands, Volumen-Spike, ATR, Support/Resistance
  (bewusst simpel, keine Overfitting-Parameter)
- `src/signals.py` – kombiniert Indikatoren zu Alerts + "Overall Bias" (bullish/bearish/neutral) für's Dashboard
- `src/state.py` – SQLite-Dedup, damit derselbe Alert nicht bei jedem Lauf erneut kommt
- `src/notifier.py` – Telegram-Versand
- `src/reddit_scan.py` – zählt Ticker-Erwähnungen in konfigurierten Subreddits (optional, siehe unten)
- `src/dashboard.py` – generiert statisches `docs/index.html` (Chart.js) für GitHub Pages
- `.github/workflows/scan.yml` – läuft alle 30 Min während der US-Handelszeit auf GitHub-Runnern (kostenlos, kein eigener Server nötig)

## Lokal testen

```bash
cd stockme
python -m venv .venv
. .venv/Scripts/activate   # Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
cp .env.example .env       # Telegram-Werte eintragen (siehe unten), sonst wird nur geloggt
python -m src.main
```

## SSL in Firmennetzwerken (z.B. Corporate-Proxy mit TLS-Inspection)

Falls beim lokalen Testen `SSL: CERTIFICATE_VERIFY_FAILED` / `self signed certificate in certificate chain` auftritt:
Dein Firmen-Proxy (z.B. Netskope, Zscaler) inspiziert TLS-Verbindungen mit einem eigenen Root-Zertifikat, das
Windows vertraut, die Python-Bibliotheken (insb. `curl_cffi`, von yfinance genutzt) aber nicht automatisch nutzen.

Einmalig lokal beheben:

```powershell
# 1. Firmen-Root-CAs aus dem Windows-Zertifikatsspeicher exportieren (Muster ggf. anpassen)
.\export_corp_ca.ps1

# 2. Mit certifi's Standard-Bundle kombinieren
$certifiPath = .venv\Scripts\python -c "import certifi; print(certifi.where())"
Copy-Item $certifiPath combined_ca_bundle.pem
Get-Content corp_ca_bundle.pem | Add-Content combined_ca_bundle.pem
```

Danach `run_local.ps1` statt `python -m src.main` nutzen – das Skript setzt automatisch
`CURL_CA_BUNDLE` / `REQUESTS_CA_BUNDLE` / `SSL_CERT_FILE` auf das kombinierte Bundle, falls vorhanden.

Diese Dateien (`corp_ca_bundle.pem`, `combined_ca_bundle.pem`) sind maschinenspezifisch und bewusst
in `.gitignore` – auf GitHub Actions ist kein Corporate-Proxy im Weg, daher dort nicht nötig.

⚠️ **Bekanntes Folgeproblem:** Manche Firmennetzwerke teilen sich wenige öffentliche Egress-IPs
(viele Mitarbeiter hinter derselben Proxy-IP). Yahoo Finance rate-limitet den inoffiziellen
`getcrumb`-Endpoint IP-basiert – bei starker Auslastung der Firmen-IP kann es zu dauerhaften
`429 Too Many Requests` kommen, unabhängig vom SSL-Fix. Zum Isolieren: einmal über ein anderes
Netz (Mobile Hotspot, Heimnetz) testen. Der produktive Lauf über GitHub Actions ist davon nicht betroffen,
da GitHub-Runner eigene, nicht überlastete IPs nutzen.

## Telegram-Bot einrichten

1. Mit [@BotFather](https://t.me/BotFather) auf Telegram chatten, `/newbot`, Token kopieren → `TELEGRAM_BOT_TOKEN`
2. Deinem neuen Bot eine Nachricht schreiben (einmalig, sonst kann er dir nicht antworten)
3. `https://api.telegram.org/bot<TOKEN>/getUpdates` aufrufen, `chat.id` aus der Antwort kopieren → `TELEGRAM_CHAT_ID`

## GitHub Actions einrichten

1. Repo auf GitHub erstellen, dieses Verzeichnis pushen
2. Unter Settings → Secrets and variables → Actions: `TELEGRAM_BOT_TOKEN` und `TELEGRAM_CHAT_ID` als Repo-Secrets anlegen
3. Workflow läuft automatisch nach Zeitplan, oder manuell über den "Run workflow"-Button (Tab *Actions*)

## Dashboard (GitHub Pages)

Jeder Lauf generiert `docs/index.html` (Chart.js, Kursverlauf + RSI je Symbol, Tabelle der letzten Alerts)
und committet sie zurück ins Repo. Einmalig aktivieren:

1. Repo-Settings → **Pages**
2. Source: "Deploy from a branch", Branch: `main`, Ordner: `/docs`
3. Speichern – URL erscheint dort (Format `https://<username>.github.io/<repo>/`), nach dem nächsten Lauf gefüllt

⚠️ GitHub deaktiviert Scheduled Workflows automatisch nach 60 Tagen Repo-Inaktivität – ab und zu reinschauen/pushen.

## Watchlist erweitern

Einfach in `config.yaml` unter `watchlist` weitere Symbole (Yahoo-Finance-Ticker) ergänzen:

```yaml
watchlist:
  - symbol: MU
  - symbol: NVDA
  - symbol: NFLX
  - symbol: MSFT
  - symbol: BKNG
```

Krypto läuft separat unter `crypto_watchlist` (Yahoo-Ticker-Format `XXX-USD`), Start-Set: BTC, ETH, XRP.
Läuft 24/7 mit denselben Indikator-Schwellwerten wie Aktien – ggf. später eigene, weniger empfindliche
Schwellwerte ergänzen, da Krypto deutlich volatiler ist.

## Reddit-Sentiment einrichten

Zählt Ticker-Erwähnungen in konfigurierten Subreddits (Standard: wallstreetbets, wallstreetbetsGer, Trumptrades)
der letzten `lookback_hours` und alertet, wenn `min_mentions` überschritten wird (`config.yaml` → `reddit`).
Bewusst nur *ein* Faktor unter mehreren – diese Communities sind stark verrauscht und teils gezielt manipuliert
(Pump-and-Dump), nicht als alleiniges Kaufsignal verwenden.

1. Reddit-Account anlegen: [reddit.com/register](https://www.reddit.com/register)
2. App anlegen unter [reddit.com/prefs/apps](https://www.reddit.com/prefs/apps) → "create another app" → Typ **script**
   (redirect uri kann `http://localhost:8080` sein, wird für den read-only Application-Only-Modus nicht genutzt)
3. `client_id` (unter dem App-Namen) und `secret` in `.env` (lokal) bzw. als Repo-Secrets
   `REDDIT_CLIENT_ID` / `REDDIT_CLIENT_SECRET` (GitHub Actions) eintragen
4. In `config.yaml`: `reddit.enabled: true` setzen

Kein Reddit-Passwort im Code nötig – PRAW nutzt den Application-Only-Modus (nur `client_id`/`client_secret`),
das reicht für öffentliches Lesen. Reddit-API ist für diesen Umfang (nicht-kommerziell, <100 Requests/Min) kostenlos.

## Yahoo Finance Top-Mover

Aktiv über `top_movers` in `config.yaml`, nutzt `yfinance.screen()` für `day_gainers` / `day_losers` /
`most_actives` – markiert Werte mit starker Kursbewegung unabhängig von der Watchlist.

## Technische Analyse im Detail

Neben RSI/SMA/MACD/Bollinger/Volumen-Spike:

- **ATR (Average True Range)**: reines Volatilitätsmaß (keine Richtung), im Dashboard je Symbol angezeigt –
  hilfreich zur Einordnung, wie "wild" ein Wert aktuell schwankt (z.B. für eigene Stop-Loss-Überlegungen)
- **Support/Resistance**: einfaches Swing-Hoch/-Tief über `support_resistance_window` Tage (Standard 20),
  löst `RESISTANCE_BREAKOUT`/`SUPPORT_BREAKDOWN`-Alerts aus
- **Overall Bias**: fasst Trend (SMA-Verhältnis) + Momentum (MACD-Histogramm, RSI-Zone) zu einer groben
  bullish/bearish/neutral-Einordnung zusammen, inkl. Begründung – nur im Dashboard sichtbar, kein eigener
  Telegram-Alert (würde sonst täglich unverändert feuern, ohne echten Neuigkeitswert)

Diese drei sind an die Analyse-Checkliste aus [tradesdontlie/tradingview-mcp](https://github.com/tradesdontlie/tradingview-mcp)
(Skill `chart-analysis`) angelehnt – dessen eigentliches Tool (KI-Steuerung der lokalen TradingView-Desktop-App
per Chrome DevTools Protocol) passt nicht zu unserem headless GitHub-Actions-Setup, aber die Analyse-Methodik
dahinter (Trend + Momentum + Support/Resistance + zusammenfassender Bias) ließ sich 1:1 mit unseren eigenen,
kostenlosen Daten umsetzen.

## Geplante Erweiterung: Backtest-Report

Noch nicht implementiert, aber als Vorlage vorgemerkt (angelehnt an den `strategy-report`-Skill desselben
Projekts): Sobald ein Backtesting-Modul (z.B. mit `vectorbt`/`backtrader`) dazukommt, folgendes Report-Format:

| Metrik | Bedeutung |
|---|---|
| Net Profit / Return % | Gesamtergebnis |
| Win Rate | Anteil profitabler Trades |
| Profit Factor | Ziel > 1.5 |
| Max Drawdown | größter Verlust vom Hoch, $ und % |
| Sharpe Ratio | risikoadjustierte Rendite |
| Max Consecutive Losses | Robustheit der Strategie |

Wichtig beim eigenen Backtesting: Out-of-Sample testen, nicht nur auf denselben Daten optimieren
(Overfitting ist der häufigste Fehler bei Hobby-Systemen).

## Nicht enthalten (bewusst)

- Keine automatisierte Order-Ausführung (Bitpanda/Trade Republic/Robinhood haben dafür keine robuste,
  ToS-konforme API für Aktien/ETFs – siehe Diskussion im Projekt-Chat)
- Keine Garantie/Anlageberatung – reine technische Analyse-Hilfe, no warranty
