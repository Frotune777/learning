"""
Machine Learning, Technical Analysis Dashboard, Sector Rotation, and Quantitative Analytics menu handlers.
"""

from __future__ import annotations

import glob
import os
from datetime import datetime

import pandas as pd
import structlog

from src.cli.formatters import (
    _ask,
    _confirm,
    _display_csv,
    _header,
    _pause,
    _subheader,
    bold,
    cyan,
    dim,
    err,
    green,
    ok,
    red,
    tip,
    warn,
    white,
    yellow,
)
from src.cli.renderers.screener_views import (
    render_backtest_table,
    render_consensus_leaderboard,
    render_strategy_inspector_card,
)
from src.cli.renderers.system_views import render_nse_live_quote_table, render_option_chain_table
from src.cli.reporter import ScreenerReporter
from src.cli.telegram import TelegramService
from src.cli.visual import VisualUI
from src.core.config import Config, UserPrefs
from src.core.symbol_utils import get_delivery_history_from_bhavcopy
from src.core.utils import get_nse_utils
from src.nse_bhavcopy.correlation import run_correlation_cli
from src.nse_bhavcopy.heatmap import run_heatmap_cli
from src.nse_bhavcopy.sector_rotation import run_sector_rotation_cli
from src.nse_bhavcopy.ta_indicators import add_ta_indicators, calculate_technical_score
from src.scanners.pair_scanner import run_pair_scanner_cli
from src.scrapers.mmi_scraper import run_mmi_cli

logger = structlog.get_logger("nse_pipeline.ml_analytics")
_UI = VisualUI()
_REPORTER = ScreenerReporter()


def menu_ta_dashboard(hist_dir: str, symbol: str | None = None) -> None:
    """Display a console dashboard for a single stock's TA indicators."""
    _header("TA Dashboard — Single Stock", "RSI · MACD · Bollinger · ADX · ATR · CCI · Score")

    if not symbol:
        symbol = input(f"  {dim('NSE Symbol')} (e.g. TCS): ").strip().upper()
        if not symbol:
            return

    path = os.path.join(hist_dir, "1d", f"{symbol}.parquet")
    if not os.path.exists(path):
        print(err(f"Historical data for '{symbol}' not found at: {path}"))
        print(tip("Sync this symbol first using option [2] or [3]."))
        _pause()
        return

    try:
        df = pd.read_parquet(path)
        if df.empty:
            print(err(f"Data file for '{symbol}' is empty."))
            _pause()
            return

        if df.index.tz is not None:
            df.index = df.index.tz_convert(None)
        else:
            df.index = pd.to_datetime(df.index)

        df = df.sort_index()

        needs_ta = (
            "RSI_14" not in df.columns
            or "EMA_20" not in df.columns
            or pd.isna(df["RSI_14"].iloc[-1])
            or pd.isna(df["EMA_20"].iloc[-1])
        )
        if needs_ta:
            print(f"  {dim('Refining and computing TA indicators on full history…')}")
            base_cols = [c for c in ["Open", "High", "Low", "Close", "Volume"] if c in df.columns]
            df = add_ta_indicators(df[base_cols] if len(base_cols) >= 4 else df)

        last_date = df.index[-1].date()
        today = datetime.now().date()
        days_stale = (today - last_date).days
        if days_stale > 3:
            print(warn(f"Data is {days_stale} days old (latest bar: {last_date}). Run sync to update."))

        row = df.iloc[-1]
        date_str = df.index[-1].strftime("%Y-%m-%d")

        cmp_val = float(row.get("Close", 0.0))
        high = float(row.get("High", 0.0))
        low = float(row.get("Low", 0.0))
        volume = float(row.get("Volume", 0.0))

        score_data = calculate_technical_score(row)
        score = int(score_data.get("score", 0))
        bias = str(score_data.get("rating", "NEUTRAL"))
        breakdown = score_data.get("breakdown", {})

        score_color = green if score >= 70 else (yellow if score >= 50 else red)

        print(f"\n  {bold(white(symbol))}  ·  {date_str}  ·  CMP: {bold(f'₹{cmp_val:,.2f}')}")
        print(f"  Day Range: ₹{low:,.2f} – ₹{high:,.2f}  ·  Vol: {volume:,.0f}")
        print(f"  Composite Technical Score: {bold(score_color(f'{score}/100'))}  [{score_color(bias)}]\n")

        rsi = float(row.get("RSI_14", 50.0))
        rsi_signal = "Oversold" if rsi < 30 else ("Overbought" if rsi > 70 else "Neutral")
        rsi_color = green if rsi < 30 else (red if rsi > 70 else white)
        print(f"  {'RSI (14)':<24} {rsi_color(f'{rsi:.1f}'):<12} {dim(rsi_signal)}")

        macd = float(row.get("MACD", 0.0))
        macd_sig = float(row.get("MACD_signal", 0.0))
        macd_hist = float(row.get("MACD_hist", 0.0))
        macd_signal = "Bullish Cross" if macd > macd_sig else "Bearish Cross"
        macd_color = green if macd > macd_sig else red
        print(f"  {'MACD (12,26,9)':<24} {macd_color(f'{macd:.2f} / {macd_sig:.2f}'):<12} {dim(f'{macd_signal} (hist: {macd_hist:+.2f})')}")

        ema20 = float(row.get("EMA_20", cmp_val))
        ema50 = float(row.get("EMA_50", cmp_val))
        ema200 = float(row.get("EMA_200", cmp_val))
        print(f"  {'EMA 20 / 50 / 200':<24} {f'₹{ema20:.1f} / ₹{ema50:.1f} / ₹{ema200:.1f}':<24}")

        bb_up = float(row.get("BB_upper", cmp_val))
        bb_mid = float(row.get("BB_middle", cmp_val))
        bb_low = float(row.get("BB_lower", cmp_val))
        bb_pos = "Near Upper Band" if cmp_val > bb_mid else "Near Lower Band"
        print(f"  {'Bollinger Bands':<24} {f'₹{bb_low:.1f} – ₹{bb_up:.1f}':<24} {dim(bb_pos)}")

        adx = float(row.get("ADX", 20.0))
        adx_trend = "Strong Trend" if adx > 25 else "Weak/No Trend"
        print(f"  {'ADX (Trend Strength)':<24} {f'{adx:.1f}':<12} {dim(adx_trend)}")

        atr = float(row.get("ATR", 0.0))
        atr_pct = (atr / cmp_val * 100) if cmp_val > 0 else 0.0
        print(f"  {'ATR (Volatility)':<24} {f'₹{atr:.2f} ({atr_pct:.1f}%)':<24}")

        cci = float(row.get("CCI", 0.0))
        cci_sig = "Overbought" if cci > 100 else ("Oversold" if cci < -100 else "Neutral")
        print(f"  {'CCI':<24} {f'{cci:.1f}':<12} {dim(cci_sig)}")

        if breakdown:
            print(f"\n  {dim('Score breakdown:')}")
            for comp, pts in breakdown.items():
                pts_color = green if pts > 0 else (red if pts < 0 else dim)
                print(f"    {comp:<32} {pts_color(f'{pts:+d}')}")

    except Exception as exc:
        print(err(f"Error reading {symbol}: {exc}"))
        logger.error("ta_dashboard_failed", symbol=symbol, error=str(exc))

    _pause()


def menu_sector_rotation() -> None:
    """Run the JdK RS-Ratio Sector Rotation analysis."""
    _header("Sector Rotation Analysis (JdK RS-Ratio)")
    print("  Fetching 90 days of historical data for sectors and Nifty 50...")
    print("  Calculating RS-Ratio and Momentum...\n")

    df = run_sector_rotation_cli()
    if df.empty:
        print(warn("No sector data could be processed."))
        _pause()
        return

    out_dir = "data/screener_output"
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "sector_rotation.csv")
    df.to_csv(out_path, index=False)

    _display_csv(
        out_path,
        "Sector Rotation (JdK RS-Ratio)",
        "Quadrants: Leading (Top-Right), Improving (Top-Left), Weakening (Bottom-Right), Lagging (Bottom-Left)",
    )
    print(f"\n  {dim(f'Saved to {out_path}')}")
    _pause()


def menu_correlation() -> None:
    """Run the Correlation Matrix analysis."""
    _header("Cross-Asset Correlation Matrix")
    print("  Fetching 1-year of historical returns for benchmarks...")

    df = run_correlation_cli()
    if df.empty:
        print(warn("No correlation data could be generated."))
        _pause()
        return

    out_dir = "data/screener_output"
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "correlation_matrix.csv")
    df.to_csv(out_path, index=False)

    _display_csv(
        out_path,
        "Correlation Matrix (1 Year Returns)",
        "Close to 100% means strong positive correlation, negative means inverse.",
    )
    print(f"\n  {dim(f'Saved to {out_path}')}")
    _pause()


def menu_heatmap() -> None:
    """Run the Nifty Indices Heatmap analysis."""
    _header("Nifty Indices Heatmap")
    print(f"  {dim('Example Indices:')} NIFTY 50, NIFTY BANK, NIFTY IT, NIFTY PHARMA")
    index_name = input("  Enter Index Name (default: NIFTY 50): ").strip() or "NIFTY 50"

    print(f"\n  Fetching realtime constituent data for {index_name}...\n")
    df = run_heatmap_cli(index_name)
    if df.empty:
        print(warn(f"No data could be generated for {index_name}."))
        _pause()
        return

    out_dir = "data/screener_output"
    os.makedirs(out_dir, exist_ok=True)
    safe_name = index_name.replace(" ", "_").lower()
    out_path = os.path.join(out_dir, f"{safe_name}_heatmap.csv")
    df.to_csv(out_path, index=False)

    _display_csv(
        out_path,
        f"Heatmap - {index_name}",
        "Sorted by Market Cap (Largest first). Green = Advancing, Red = Declining.",
    )
    print(f"\n  {dim(f'Saved to {out_path}')}")
    _pause()


def menu_mmi() -> None:
    """Run the Market Mood Index (MMI) Scraper."""
    _header("Market Mood Index (MMI)")
    run_mmi_cli()
    _pause()


def menu_pair_scanner(hist_dir: str) -> None:
    """Run the Engle-Granger Cointegration Pair Scanner."""
    _header("Cointegration Pair Scanner")
    daily_dir = os.path.join(hist_dir, "1d")
    if not os.path.isdir(daily_dir):
        print(warn(f"Daily directory '{daily_dir}' does not exist."))
        _pause()
        return

    parquet_files = [f for f in os.listdir(daily_dir) if f.endswith(".parquet")]
    if not parquet_files:
        print(warn(f"No parquet files found in '{daily_dir}'."))
        _pause()
        return

    print(f"  Total symbols available: {len(parquet_files)}")
    print(f"  {dim('Engle-Granger Cointegration Test (N*(N-1)/2 checks)')}\n")

    defaults = Config.SYNC_DEFAULTS
    try:
        limit_in = input(f"  Symbol scan limit [10-250, default {defaults['default_symbol_limit']}]: ").strip()
        symbol_limit = int(limit_in) if limit_in else defaults["default_symbol_limit"]
        if symbol_limit < 2:
            symbol_limit = 2
    except ValueError:
        symbol_limit = defaults["default_symbol_limit"]

    try:
        pval_in = input(f"  Max p-value threshold [0.001-0.20, default {defaults['max_pval_threshold']}]: ").strip()
        max_pval = float(pval_in) if pval_in else defaults["max_pval_threshold"]
    except ValueError:
        max_pval = defaults["max_pval_threshold"]

    try:
        max_pairs_in = input(f"  Max pairs to return [1-100, default {defaults['max_pairs']}]: ").strip()
        max_pairs = int(max_pairs_in) if max_pairs_in else defaults["max_pairs"]
    except ValueError:
        max_pairs = defaults["max_pairs"]

    print(f"\n  Scanning top {symbol_limit} symbols for cointegrated pairs (p <= {max_pval})...\n")
    df = run_pair_scanner_cli(
        daily_dir=daily_dir,
        symbol_limit=symbol_limit,
        max_pval=max_pval,
        max_pairs=max_pairs,
    )

    if df.empty:
        print(warn(f"No cointegrated pairs found at p-value <= {max_pval}."))
        _pause()
        return

    out_dir = "data/screener_output"
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "cointegrated_pairs.csv")
    df.to_csv(out_path, index=False)

    _display_csv(
        out_path,
        "Cointegrated Pairs (Stat-Arb / Mean-Reversion Candidates)",
        "p-value < 0.05 indicates strong mean-reversion. Use for pairs-trading.",
    )
    print(f"\n  {dim(f'Saved to {out_path}')}")
    _pause()


def menu_nse_live() -> None:
    """Interactive NSE live market data query menu."""
    from rich.table import Table

    _header("Live NSE Market Data Hub", "Direct queries to live NSE endpoints")

    nse = get_nse_utils()
    options = [
        ("1", "Pre-Open Market Summary", "View advancing/declining counts and top pre-open stocks"),
        ("2", "Live Stock Quote", "Real-time LTP, bid/ask, day high/low for a single symbol"),
        ("3", "Live Option Chain", "Real-time option chain for Nifty / BankNifty / Stock"),
        ("0", "Back to Main Menu", "Return to the main REPL menu"),
    ]

    for num, title, desc in options:
        print(f"  [{cyan(num)}] {bold(title)} — {dim(desc)}")
    print()

    choice = input("  Select option: ").strip()

    if choice == "1":
        print("\n  Fetching live pre-open market summary...")
        data = nse.get_pre_open_market()
        if data:
            print(f"  {bold('Total Pre-Open Stocks:')} {len(data)}")
            adv = sum(1 for d in data if d.get("pChange", 0) > 0)
            dec = sum(1 for d in data if d.get("pChange", 0) < 0)
            print(f"  {green(f'Advances: {adv}')}  |  {red(f'Declines: {dec}')}\n")
            top5 = sorted(data, key=lambda x: x.get("pChange", 0), reverse=True)[:5]
            tbl = Table(title="Top 5 Pre-Open Gainers", header_style="bold cyan")
            tbl.add_column("Symbol", justify="left")
            tbl.add_column("Price (₹)", justify="right")
            tbl.add_column("Change (%)", justify="right")
            for item in top5:
                tbl.add_row(item.get("symbol", ""), f"{item.get('iep', 0):,.2f}", f"+{item.get('pChange', 0):.2f}%")
            _UI.console.print(tbl)
        else:
            print(warn("Could not retrieve pre-open data. Market might be closed."))
    elif choice == "2":
        sym = input("  Enter NSE Symbol (e.g., RELIANCE): ").strip().upper()
        if sym:
            print(f"\n  Fetching live quote for {sym}...")
            quote = nse.get_quote(sym)
            if quote and "priceInfo" in quote:
                pi = quote["priceInfo"]
                render_nse_live_quote_table({
                    "Symbol": sym,
                    "LTP": f"₹{pi.get('lastPrice', 0):,.2f}",
                    "Change": f"{pi.get('change', 0):+,.2f} ({pi.get('pChange', 0):+.2f}%)",
                    "Day High": f"₹{pi.get('intraDayHighLow', {}).get('max', 0):,.2f}",
                    "Day Low": f"₹{pi.get('intraDayHighLow', {}).get('min', 0):,.2f}",
                    "Previous Close": f"₹{pi.get('previousClose', 0):,.2f}",
                })
            else:
                print(warn(f"Could not retrieve quote for {sym}."))
    elif choice == "3":
        sym = input("  Enter Symbol/Index (e.g., NIFTY, BANKNIFTY, RELIANCE): ").strip().upper()
        if sym:
            print(f"\n  Fetching live option chain for {sym}...")
            chain = nse.get_option_chain(sym)
            if chain and "records" in chain:
                records = chain["records"].get("data", [])
                print(f"  {ok(f'Retrieved {len(records)} strikes for {sym}')}")
                underlying = chain["records"].get("underlyingValue", 0)
                print(f"  {bold('Underlying Price:')} ₹{underlying:,.2f}")
            else:
                print(warn(f"Could not retrieve option chain for {sym}."))
    _pause()


def menu_backtest(hist_dir: str, data_dir: str) -> None:
    """Interactive ML Classifier Backtester menu handler."""
    _header("ML Classifier Backtester")
    symbol = _ask("Enter Stock Symbol (e.g. TCS)", "TCS").strip().upper()

    defaults = Config.SYNC_DEFAULTS
    try:
        n_est_in = input(f"  Number of estimators [default {defaults.get('n_estimators', 100)}]: ").strip()
        n_estimators = int(n_est_in) if n_est_in else defaults.get("n_estimators", 100)
    except ValueError:
        n_estimators = defaults.get("n_estimators", 100)

    try:
        max_depth_in = input(f"  Max depth [default {defaults.get('max_depth', 5)}]: ").strip()
        max_depth = int(max_depth_in) if max_depth_in else defaults.get("max_depth", 5)
    except ValueError:
        max_depth = defaults.get("max_depth", 5)

    price_path = os.path.join(hist_dir, "1d", f"{symbol}.parquet")
    if not os.path.exists(price_path):
        print(err(f"Historical Parquet file not found at: {price_path}"))
        _pause()
        return

    try:
        print(f"\n  Loading price data for {symbol}...")
        df_prices = pd.read_parquet(price_path)
        if df_prices.empty or len(df_prices) < 20:
            print(err(f"Insufficient history for {symbol} ({len(df_prices)} bars)."))
            _pause()
            return

        print(f"  Scanning for delivery percentage data in {data_dir}/processed...")
        df_delivery = get_delivery_history_from_bhavcopy(os.path.join(data_dir, "processed"), symbol)
        if df_delivery is not None and not df_delivery.empty:
            print(ok(f"Aggregated {len(df_delivery)} records of delivery percentage data."))
        else:
            print(warn("No delivery percentage data found. Defaulting to 0.0."))

        print(f"  Training Random Forest (n_estimators={n_estimators}, max_depth={max_depth})...")
        from src.ml.ml_classifier import MLClassifier
        from src.nse_bhavcopy.backtester import NSEEventBacktester

        clf = MLClassifier(n_estimators=n_estimators, max_depth=max_depth)
        X, y = clf.prepare_features(df_prices, df_delivery)
        if len(X) < 10:
            print(err("Not enough feature rows generated to train/test."))
            _pause()
            return

        split_idx = int(len(X) * 0.8)
        X_train, X_test = X.iloc[:split_idx], X.iloc[split_idx:]
        y_train, y_test = y.iloc[:split_idx], y.iloc[split_idx:]

        clf.train(X_train, y_train)
        preds = clf.predict(X_test)

        from sklearn.metrics import accuracy_score, precision_score, recall_score

        acc = float(accuracy_score(y_test, preds))
        prec = float(precision_score(y_test, preds, zero_division=0))
        rec = float(recall_score(y_test, preds, zero_division=0))

        signals_test = pd.Series(preds, index=X_test.index)
        test_prices = df_prices.loc[X_test.index]
        ev_bt = NSEEventBacktester(init_cash=100000.0)
        bt_res = ev_bt.run(test_prices, signals_test)

        render_backtest_table({
            "Classifier Accuracy": f"{acc * 100:.2f}%",
            "Classifier Precision": f"{prec * 100:.2f}%",
            "Classifier Recall": f"{rec * 100:.2f}%",
            "Initial Portfolio Cash": "INR 100,000.00",
            "Final Portfolio Value": f"INR {bt_res['final_value']:,.2f}",
            "Simulated Strategy Return": f"{bt_res['total_return_pct']:.2f}%",
            "Max Drawdown": f"{bt_res['max_drawdown_pct']:.2f}%",
            "Total Executed Trades": str(bt_res["total_trades"]),
        }, title=f"ML Backtest Results: {symbol}")

        logger.info("backtest_completed", symbol=symbol, accuracy=acc)

    except Exception as exc:
        print(err(f"Backtest execution failed: {exc}"))
        logger.error("backtest_failed", symbol=symbol, error=str(exc))

    _pause()


def menu_fo_ban(data_dir: str) -> None:
    """Interactive F&O Ban list query."""
    _header("NSE F&O Ban Securities")
    try:
        from src.scrapers.fo_ban import FOBanManager

        manager = FOBanManager(cache_dir=data_dir)
        ban_list = manager.fetch_fo_ban_list()
        if ban_list:
            print(ok(f"Found {len(ban_list)} securities in F&O ban:"))
            for sym in sorted(ban_list):
                print(f"  {dim('·')} {bold(sym)}")
        else:
            print(ok("No securities are currently in the F&O ban period."))
    except Exception as exc:
        print(err(f"Failed to query F&O ban list: {exc}"))
        logger.error("fo_ban_failed", error=str(exc))
    _pause()


def menu_ml_anomaly(hist_dir: str, data_dir: str) -> None:
    """Interactive prompt for ML Data Anomaly Detector."""
    import argparse
    from src.cli.actions import cmd_ml_anomaly

    _header("ML Data Anomaly Detector", "Identify bad ticks, volume shocks, or smart money footprints")
    sym = input(f"  {dim('Stock Symbol (e.g. RELIANCE, TCS)')}: ").strip().upper()
    if not sym:
        print(warn("No symbol entered."))
        _pause()
        return

    algo = input(f"  {dim('Algorithm [isolation_forest / robust_covariance]')} [isolation_forest]: ").strip().lower()
    if not algo:
        algo = "isolation_forest"

    cont_str = input(f"  {dim('Contamination rate (0.01 - 0.15)')} [0.03]: ").strip()
    try:
        cont = float(cont_str) if cont_str else 0.03
    except ValueError:
        cont = 0.03

    args = argparse.Namespace(
        hist_dir=hist_dir,
        symbol=sym,
        contamination=cont,
        algo=algo,
    )
    cmd_ml_anomaly(args)
    _pause()


def menu_strategy_inspector(hist_dir: str) -> None:
    """Show all 13 strategy signals for a single stock using the ScreenerReporter."""
    _UI.render_header("STRATEGY INSPECTOR", "All 13 strategy signals for a single stock · color-coded · with narrative")

    analyzed_files = sorted(glob.glob(os.path.join(hist_dir, "top_250_analyzed_*.csv")), reverse=True)
    if not analyzed_files:
        print(err("No analyzed CSV found. Run the Technical Screener (option 4) first."))
        _pause()
        return

    latest = analyzed_files[0]
    df = pd.read_csv(latest)
    df = _REPORTER._ensure_consensus(df)
    print(f"\n  {dim('Dataset:')} {os.path.basename(latest)}  {dim(f'({len(df)} stocks)')}\n")

    symbol = input(f"  {dim('Enter NSE Symbol')} (e.g. TCS): ").strip().upper()
    if not symbol:
        print(warn("No symbol entered."))
        _pause()
        return

    render_strategy_inspector_card(symbol, df)

    row_match = df[df.get("SYMBOL", pd.Series()).astype(str).str.upper() == symbol]
    if not row_match.empty:
        row = row_match.iloc[0]
        narrative = _REPORTER.generate_narrative(row)
        print()
        print(f"  {cyan('▸')} {bold('AI Narrative:')}")
        print(f"  {dim(narrative)}")

    _pause()


def menu_consensus_leaderboard(hist_dir: str) -> None:
    """Display stocks ranked by CONSENSUS_SCORE from the latest analyzed CSV."""
    _UI.render_header("CONSENSUS LEADERBOARD", "Top stocks ranked by multi-strategy agreement score")

    analyzed_files = sorted(glob.glob(os.path.join(hist_dir, "top_250_analyzed_*.csv")), reverse=True)
    if not analyzed_files:
        print(err("No analyzed CSV found. Run the Technical Screener (option 4) first."))
        _pause()
        return

    latest = analyzed_files[0]
    df = pd.read_csv(latest)
    print(f"\n  {dim('Dataset:')} {os.path.basename(latest)}  {dim(f'({len(df)} stocks)')}")

    top_str = input(f"  {dim('How many top stocks to show')} [20]: ").strip()
    top_n = int(top_str) if top_str.isdigit() else 20

    render_consensus_leaderboard(df, top_n=top_n)
    _pause()


def menu_configure_alerts() -> None:
    """Configure Telegram Bot credentials interactively."""
    _header("Configure Telegram Alerts", "Set bot token and chat ID for automated delivery")
    prefs = UserPrefs()
    existing_token = prefs.get("telegram_bot_token")
    existing_chat = prefs.get("telegram_chat_id")

    if existing_token:
        masked = existing_token[:6] + "..." + existing_token[-4:]
        print(f"  Current Bot Token : {cyan(masked)}")
    else:
        print(f"  Current Bot Token : {dim('Not configured')}")

    if existing_chat:
        print(f"  Current Chat ID   : {cyan(existing_chat)}")
    else:
        print(f"  Current Chat ID   : {dim('Not configured')}")

    print()
    token = input(f"  {dim('Bot Token (Enter to keep current)')}: ").strip()
    chat_id = input(f"  {dim('Chat ID   (Enter to keep current)')}: ").strip()

    if token:
        prefs.set("telegram_bot_token", token)
    if chat_id:
        prefs.set("telegram_chat_id", chat_id)

    if not token and not existing_token:
        print(warn("No bot token set."))
        _pause()
        return

    tg = TelegramService(
        bot_token=token or existing_token,
        chat_id=chat_id or existing_chat,
    )
    if not tg.is_configured():
        print(warn("Telegram is not fully configured."))
        _pause()
        return

    if _confirm("Send a test message now?"):
        success = tg.send_message("<b>Fortune ADSS</b>: Telegram alert integration active.")
        if success:
            print(ok("Test message sent successfully!"))
        else:
            print(err("Failed to send test message. Check token and chat ID."))

    _pause()


def menu_send_alerts(hist_dir: str) -> None:
    """Send latest screener results to Telegram."""
    _header("Send Screener Results via Telegram")
    tg = TelegramService()
    if not tg.is_configured():
        print(warn("Telegram is not configured. (Missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID)"))
        if _confirm("Would you like to configure Telegram credentials now?"):
            menu_configure_alerts()
            return
        _pause()
        return

    today_str = datetime.now().strftime("%Y%m%d")
    final_csv = os.path.join(hist_dir, f"final_list_{today_str}.csv")
    swing_csv = os.path.join(hist_dir, f"swing_list_{today_str}.csv")
    analyzed_csv = os.path.join(hist_dir, f"top_250_analyzed_{today_str}.csv")

    files_to_send = [p for p in [final_csv, swing_csv, analyzed_csv] if os.path.exists(p)]
    if not files_to_send:
        all_csvs = sorted(glob.glob(os.path.join(hist_dir, "*_list_*.csv")), reverse=True)
        if all_csvs:
            files_to_send = all_csvs[:2]

    if not files_to_send:
        print(err("No screener CSV files found to send."))
        _pause()
        return

    print(f"\n  Files to send ({len(files_to_send)}):")
    for f in files_to_send:
        print(f"    {dim('·')} {bold(os.path.basename(f))}")

    if not _confirm(f"Send {len(files_to_send)} file(s) to Telegram?"):
        print(warn("Cancelled."))
        _pause()
        return

    results = tg.send_screener_bundle(files_to_send)
    sent_count = sum(1 for v in results.values() if v)
    print(ok(f"Sent {sent_count}/{len(files_to_send)} files successfully."))
    _pause()


def menu_train_ml(hist_dir: str, data_dir: str) -> None:
    """Train machine learning models across local historical datasets."""
    _header("Train Machine Learning Models")
    try:
        from src.engine.orchestrator import train_ml_models

        train_ml_models()
    except Exception as e:
        print(err(f"ML training failed: {e}"))
    _pause()


def menu_run_optimizer(hist_dir: str, data_dir: str) -> None:
    """Run Strategy Parameter Optimizer using Optuna."""
    _header("Run Strategy Optimizer (Optuna)")
    try:
        from src.analysis.strategy_optimizer import run_optimizer_cli

        run_optimizer_cli()
    except Exception as e:
        print(err(f"Optimizer failed: {e}"))
    _pause()


def menu_llm_dossier(hist_dir: str) -> None:
    """Export Symbol Quantitative Dossier (Markdown for AI)."""
    _header("Export Symbol Quantitative Dossier (Markdown for AI)")
    symbol = input(f"  {dim('Enter Stock Symbol')} (e.g. RELIANCE, TCS): ").strip().upper()
    if not symbol:
        print(warn("No symbol entered."))
        _pause()
        return

    from src.engine.llm_report import generate_llm_report

    hist_1d = os.path.join(hist_dir, "1d") if os.path.isdir(os.path.join(hist_dir, "1d")) else hist_dir
    report = generate_llm_report(symbol, hist_1d)
    if report:
        out_dir = "data/llm_reports"
        os.makedirs(out_dir, exist_ok=True)
        out_path = os.path.join(out_dir, f"{symbol}_dossier.md")
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(report)
        print(ok(f"\n  Quantitative Dossier written to: {out_path}"))
        print(tip("  Share this markdown file with Claude/ChatGPT/Gemini for deep fundamental & technical thesis."))
    else:
        print(err(f"Could not generate report for {symbol} (missing parquet or insufficient history)."))
    _pause()
