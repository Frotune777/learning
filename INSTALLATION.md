# Installation & Configuration Guide

## Prerequisites

| Requirement | Version | Notes |
|---|---|---|
| Python | 3.12+ | 3.13 recommended |
| [uv](https://github.com/astral-sh/uv) | latest | Fast Python package manager |
| TA-Lib | system library | See below |
| Fyers account | — | For live data (optional) |

---

## 1. Install `uv`

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
source ~/.bashrc   # or restart your terminal
```

---

## 2. Install TA-Lib System Library

TA-Lib requires the native C library before the Python binding can be installed.

**Ubuntu / Debian / Pop!_OS:**
```bash
sudo apt-get install -y libta-lib-dev
```

**Arch Linux:**
```bash
sudo pacman -S ta-lib
```

**macOS:**
```bash
brew install ta-lib
```

---

## 3. Clone & Set Up the Project

```bash
git clone <your-repo-url>
cd learning

# Install all dependencies into an isolated virtual environment
uv sync
```

---

## 4. Configure Environment Variables

Copy the example env file and fill in your credentials:

```bash
cp ".env copy.example" .env
```

Open `.env` in your editor and set the required values:

### Fyers API (Required for live data sync)

1. Go to [https://myapi.fyers.in/](https://myapi.fyers.in/) → **API** tab → **Create App**
2. Set the redirect URI to `https://trade.fyers.in/api-login/redirect-uri/index.html` (or your own server)
3. Copy the **App ID** and **App Secret** to `.env`:

```env
BROKER_API_KEY=YOUR_APP_ID-100
BROKER_API_SECRET=YOUR_APP_SECRET
FYERS_REDIRECT_URI=https://trade.fyers.in/api-login/redirect-uri/index.html
```

4. **Generate daily access token** (required each morning):

```bash
uv run main.py fyers-login     # prints a URL — open it in browser
# After login, copy the auth code from the redirect URL
uv run main.py fyers-token --code <AUTH_CODE>
```

The access token is saved automatically and used for all data fetches.

### Telegram Alerts (Optional)

1. Message [@BotFather](https://t.me/BotFather) on Telegram → `/newbot` → copy the token
2. Get your Chat ID by messaging [@userinfobot](https://t.me/userinfobot)
3. Add to `.env`:

```env
TELEGRAM_BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz
TELEGRAM_CHAT_ID=-1001234567890
```

4. Test from the CLI — **Option 27: Configure Telegram Alerts**

---

## 5. First-Time Data Setup

Run these steps in order:

```bash
# Launch the interactive menu
uv run main.py menu
```

Then follow this sequence:

| Step | Menu Option | Action |
|---|---|---|
| 1 | **Option 1** | Build Equity Master (downloads all NSE index constituents) |
| 2 | **Option 21** | Bhavcopy Incremental Sync (download 30 days of history) |
| 3 | **Option 2** | Sync Historical — All Symbols (full OHLCV Parquet build) |
| 4 | **Option 4** | Run Technical Screener |

---

## 6. Running the Streamlit Dashboard

```bash
uv run streamlit run src/dashboard/app.py
```

Open [http://localhost:8501](http://localhost:8501) in your browser.

The dashboard has four pages:
- **Landing** — System status, data overview, live strategy signal bar chart
- **Daily Signals** — Today's screener results with strategy breakdown
- **Portfolio** — Simulated portfolio positions and P&L
- **Strategy Inspector** — Deep-dive into any stock across all 13 strategies

---

## 7. CLI Quick Reference

```bash
# Interactive menu (recommended)
uv run main.py menu

# Non-interactive subcommands
uv run main.py build-master
uv run main.py sync-history --cap-filter Large --limit 50
uv run main.py screen
uv run main.py backtest --symbol TCS
uv run main.py bhavcopy-sync --days 30
uv run main.py fo-ban
uv run main.py fyers-login
uv run main.py fyers-token --code <AUTH_CODE>
uv run main.py ml-anomaly --symbol RELIANCE
```

---

## 8. Development Tools

```bash
# Lint checks
uv run ruff check src/ main.py

# Auto-fix imports and formatting
uv run ruff check --select I --fix src/ main.py
uv run ruff format src/ main.py

# Type checking
uv run mypy --explicit-package-bases src/ main.py

# Run tests
uv run pytest tests/ -v

# Run tests with coverage
uv run pytest tests/ -v --cov=src --cov-report=term-missing
```

---

## 9. Troubleshooting

### `ModuleNotFoundError: No module named 'talib'`
TA-Lib C library not installed. Follow Step 2 above then re-run `uv sync`.

### Fyers token expired
Run `uv run main.py fyers-login` each morning before market open to refresh the token.

### `NSE 404 / CloudFlare block`
The NSE public API returns 403/404 outside IST hours or during maintenance. The pipeline has automatic fallbacks via local CSVs — try again after market hours.

### `No master table found`
Run **Option 1** (Build Equity Master) before any sync operation.

### `No Bhavcopy CSV found in data/processed`
Run **Option 21** (Bhavcopy Incremental Sync) first, then run the screener.
