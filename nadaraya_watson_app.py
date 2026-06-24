"""
╔══════════════════════════════════════════════════════════════════╗
║     Nadaraya-Watson Envelope — Python Trading App                ║
║     Features: Backtest | Live Scanner | Alerts | All Timeframes  ║
║     Converted from LuxAlgo Pine Script                           ║
╚══════════════════════════════════════════════════════════════════╝

Install dependencies:
    pip install yfinance pandas numpy plotly streamlit playsound requests

Run:
    streamlit run nadaraya_watson_app.py
"""

try:
    import streamlit as st
except ImportError:
    raise SystemExit("❌ Streamlit nahi mila! Terminal mein chalao:\n   streamlit run nadaraya_watson_app.py")

import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
import time
import threading
import json
import os
import math
import requests

# ─────────────────────────────────────────────────────────────────
# LOAD SECRETS (Streamlit Cloud) or .env (Local)
# ─────────────────────────────────────────────────────────────────
def get_secret(key, default=""):
    # 1. Try Streamlit secrets (Streamlit Cloud pe)
    try:
        return st.secrets[key]
    except:
        pass
    # 2. Try environment variable (local .env ke liye)
    try:
        import os
        from dotenv import load_dotenv
        load_dotenv()
        return os.getenv(key, default)
    except:
        pass
    return default

# Pre-load secrets
_PRESET_TOKEN   = get_secret("TG_TOKEN")
_PRESET_CHAT_ID = get_secret("TG_CHAT_ID")

# ─────────────────────────────────────────────────────────────────
# PAGE CONFIG
# ─────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="NW Envelope Trader",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ─────────────────────────────────────────────────────────────────
# CUSTOM CSS  (dark trading terminal feel)
# ─────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    /* Base */
    html, body, [class*="css"] { font-family: 'JetBrains Mono', 'Courier New', monospace; }
    .main { background-color: #0d1117; }
    section[data-testid="stSidebar"] { background-color: #161b22; border-right: 1px solid #30363d; }
    /* Sidebar all text white */
    section[data-testid="stSidebar"] label { color: #ffffff !important; }
    section[data-testid="stSidebar"] p { color: #ffffff !important; }
    section[data-testid="stSidebar"] span { color: #ffffff !important; }
    section[data-testid="stSidebar"] h1,
    section[data-testid="stSidebar"] h2,
    section[data-testid="stSidebar"] h3 { color: #ffffff !important; }
    section[data-testid="stSidebar"] .stMarkdown * { color: #ffffff !important; }
    section[data-testid="stSidebar"] input { color: #ffffff !important; background-color: #21262d !important; }
    section[data-testid="stSidebar"] textarea { color: #ffffff !important; background-color: #21262d !important; }
    /* Selectbox selected value */
    section[data-testid="stSidebar"] [data-baseweb="select"] div { color: #ffffff !important; background-color: #21262d !important; }
    section[data-testid="stSidebar"] [data-baseweb="select"] span { color: #ffffff !important; }
    /* Dropdown popup options - dark text on light bg */
    [data-baseweb="popover"] li { color: #111111 !important; }
    [data-baseweb="menu"] li { color: #111111 !important; }
    [data-baseweb="menu"] ul li { color: #111111 !important; background-color: #ffffff !important; }
    [data-baseweb="menu"] [role="option"] { color: #111111 !important; }
    [data-baseweb="menu"] [role="option"]:hover { background-color: #e8f4ff !important; color: #000000 !important; }
    /* Caption text */
    section[data-testid="stSidebar"] small { color: #adbac7 !important; }
    section[data-testid="stSidebar"] code { color: #79c0ff !important; background: #21262d !important; }

    /* Header */
    .app-header {
        background: linear-gradient(135deg, #1f2937 0%, #111827 100%);
        border: 1px solid #30363d;
        border-radius: 10px;
        padding: 18px 24px;
        margin-bottom: 20px;
        display: flex; align-items: center; gap: 14px;
    }
    .app-header h1 { color: #58a6ff; margin: 0; font-size: 1.5rem; }
    .app-header p  { color: #8b949e; margin: 0; font-size: 0.85rem; }

    /* Metric cards */
    .metric-card {
        background: #161b22;
        border: 1px solid #30363d;
        border-radius: 8px;
        padding: 16px;
        text-align: center;
    }
    .metric-card .label { color: #8b949e; font-size: 0.75rem; text-transform: uppercase; letter-spacing: 1px; }
    .metric-card .value { color: #f0f6fc; font-size: 1.6rem; font-weight: 700; margin-top: 4px; }
    .metric-card .value.green { color: #3fb950; }
    .metric-card .value.red   { color: #f85149; }

    /* Alert box */
    .alert-buy  { background:#0d2818; border-left:4px solid #3fb950; padding:10px 14px; border-radius:6px; margin:4px 0; color:#3fb950; font-size:0.85rem; }
    .alert-sell { background:#2d0f0f; border-left:4px solid #f85149; padding:10px 14px; border-radius:6px; margin:4px 0; color:#f85149; font-size:0.85rem; }

    /* Scanner table */
    .scanner-row { display:flex; align-items:center; padding:8px 12px; border-bottom:1px solid #21262d; }
    .signal-buy  { background:#0d2818; color:#3fb950; padding:3px 10px; border-radius:12px; font-size:0.75rem; font-weight:700; }
    .signal-sell { background:#2d0f0f; color:#f85149; padding:3px 10px; border-radius:12px; font-size:0.75rem; font-weight:700; }
    .signal-neutral { background:#1c2128; color:#8b949e; padding:3px 10px; border-radius:12px; font-size:0.75rem; }

    /* Tab styling */
    .stTabs [data-baseweb="tab"] { color: #8b949e; font-size: 0.9rem; }
    .stTabs [aria-selected="true"] { color: #58a6ff !important; border-bottom-color: #58a6ff !important; }

    /* Buttons */
    .stButton > button {
        background: #21262d; border: 1px solid #30363d; color: #c9d1d9;
        border-radius: 6px; font-family: monospace;
    }
    .stButton > button:hover { background: #30363d; border-color: #58a6ff; color: #58a6ff; }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────
# NADARAYA-WATSON CORE FUNCTIONS
# ─────────────────────────────────────────────────────────────────

def gauss(x: float, h: float) -> float:
    """Gaussian kernel — same as Pine Script gauss()"""
    return math.exp(-(x ** 2) / (h * h * 2))

def compute_nwe(prices: np.ndarray, h: float = 8.0, mult: float = 3.0, lookback: int = 499):
    """
    Compute Nadaraya-Watson Envelope (repainting=True style — full smoothing).
    Returns: nwe, upper, lower arrays same length as prices.
    """
    n = len(prices)
    lb = min(lookback, n)
    nwe_vals = np.full(n, np.nan)

    for i in range(lb):
        s = 0.0
        sw = 0.0
        for j in range(lb):
            w = gauss(i - j, h)
            s  += prices[n - 1 - j] * w
            sw += w
        nwe_vals[n - 1 - i] = s / sw if sw != 0 else prices[n - 1 - i]

    # SAE (mean absolute error * mult) → envelope width
    valid = ~np.isnan(nwe_vals)
    sae = np.nanmean(np.abs(prices[valid] - nwe_vals[valid])) * mult

    upper = nwe_vals + sae
    lower = nwe_vals - sae
    return nwe_vals, upper, lower

def compute_nwe_endpoint(prices: np.ndarray, h: float = 8.0, mult: float = 3.0, lookback: int = 499):
    """
    Non-repainting endpoint method — faster, good for live/backtest.
    """
    n = len(prices)
    lb = min(lookback, n)

    coefs = np.array([gauss(i, h) for i in range(lb)])
    den   = coefs.sum()

    nwe_vals = np.full(n, np.nan)
    for idx in range(lb - 1, n):
        window = prices[idx - lb + 1: idx + 1][::-1]  # most-recent first
        nwe_vals[idx] = np.dot(window, coefs[:len(window)]) / den

    mae_arr = np.full(n, np.nan)
    for idx in range(lb - 1, n):
        window_src = prices[idx - lb + 1: idx + 1][::-1]
        window_nwe = nwe_vals[idx - lb + 1: idx + 1][::-1]
        mae_arr[idx] = np.nanmean(np.abs(window_src - window_nwe)) * mult

    upper = nwe_vals + mae_arr
    lower = nwe_vals - mae_arr
    return nwe_vals, upper, lower


def compute_bollinger_bands(prices: np.ndarray, length: int = 20, mult: float = 2.0):
    """
    Bollinger Bands — classic mean + std-dev envelope.
    Returns: middle (SMA), upper, lower — same shape as compute_nwe_endpoint output
    so it can be used as a drop-in replacement.
    """
    n = len(prices)
    lb = min(length, n)

    middle = np.full(n, np.nan)
    upper  = np.full(n, np.nan)
    lower  = np.full(n, np.nan)

    s = pd.Series(prices)
    sma = s.rolling(window=lb, min_periods=lb).mean().values
    std = s.rolling(window=lb, min_periods=lb).std(ddof=0).values

    middle = sma
    upper  = sma + mult * std
    lower  = sma - mult * std

    return middle, upper, lower

# ─────────────────────────────────────────────────────────────────
# INDICATOR DISPATCHER — switch between NW Envelope and Bollinger
# ─────────────────────────────────────────────────────────────────

def compute_indicator(prices: np.ndarray, indicator: str, bandwidth: float, mult: float, lookback: int):
    """
    Unified entry point used by Chart, Backtest, Live Scanner, and Alerts.
    indicator: "NW Envelope" or "Bollinger Bands"
    For NW: bandwidth = h, lookback = NW lookback bars
    For BB: bandwidth ignored, lookback = BB period length
    """
    if indicator == "Bollinger Bands":
        return compute_bollinger_bands(prices, length=lookback, mult=mult)
    else:
        return compute_nwe_endpoint(prices, h=bandwidth, mult=mult, lookback=lookback)

# ─────────────────────────────────────────────────────────────────
# SIGNAL DETECTION
# ─────────────────────────────────────────────────────────────────

def detect_signals(df: pd.DataFrame):
    """
    Returns DataFrame with signal column:
      'BUY'  — price touches/crosses lower band (mean-reversion buy zone)
      'SELL' — price touches/crosses upper band (mean-reversion sell zone)

    Logic (clean, non-overlapping):
      - If close <= lower band  -> BUY  (price is at/below lower band)
      - If close >= upper band  -> SELL (price is at/above upper band)
      - Only fires on the bar where this FIRST becomes true (transition),
        not on every bar while price stays beyond the band.
    """
    signals = []
    close  = df['Close'].values
    upper  = df['upper'].values
    lower  = df['lower'].values

    n = len(df)
    for i in range(n):
        sig = ''
        if i == 0 or np.isnan(upper[i]) or np.isnan(lower[i]):
            signals.append(sig)
            continue

        was_below_lower = close[i-1] <= lower[i-1] if not np.isnan(lower[i-1]) else False
        was_above_upper = close[i-1] >= upper[i-1] if not np.isnan(upper[i-1]) else False

        now_below_lower = close[i] <= lower[i]
        now_above_upper = close[i] >= upper[i]

        # Fire BUY only on the transition INTO the lower-band zone
        if now_below_lower and not was_below_lower:
            sig = 'BUY'
        # Fire SELL only on the transition INTO the upper-band zone
        elif now_above_upper and not was_above_upper:
            sig = 'SELL'

        signals.append(sig)

    df = df.copy()
    df['signal'] = signals
    return df

# ─────────────────────────────────────────────────────────────────
# DATA FETCH
# ─────────────────────────────────────────────────────────────────

TIMEFRAMES = {
    "1m":  ("1m",  "7d"),
    "2m":  ("2m",  "60d"),
    "5m":  ("5m",  "60d"),
    "15m": ("15m", "60d"),
    "30m": ("30m", "60d"),
    "1H":  ("1h",  "180d"),
    "4H":  ("4h",  "730d"),
    "1D":  ("1d",  "5y"),
    "1W":  ("1wk", "10y"),
    "1Mo": ("1mo", "10y"),
}

@st.cache_data(ttl=60)
def fetch_data(symbol: str, interval: str, period: str) -> pd.DataFrame:
    try:
        df = yf.download(symbol, interval=interval, period=period, progress=False, auto_adjust=True)
        if df.empty:
            return pd.DataFrame()
        df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]
        df = df[['Open','High','Low','Close','Volume']].dropna()
        return df
    except Exception as e:
        st.error(f"Data fetch error: {e}")
        return pd.DataFrame()

# ─────────────────────────────────────────────────────────────────
# BACKTEST ENGINE
# ─────────────────────────────────────────────────────────────────

def run_backtest(df: pd.DataFrame, initial_capital: float = 100000.0):
    """
    Simple signal-based backtest.
    BUY  signal → enter long
    SELL signal → exit long / enter short (if enabled)
    """
    trades    = []
    equity    = [initial_capital]
    capital   = initial_capital
    position  = None   # {'entry_price', 'entry_time', 'type'}

    for i, row in df.iterrows():
        sig = row.get('signal', '')
        price = row['Close']
        ts    = str(i)

        if sig == 'BUY' and position is None:
            position = {'entry_price': price, 'entry_time': ts, 'type': 'LONG'}

        elif sig == 'SELL' and position is not None:
            pnl = (price - position['entry_price']) / position['entry_price'] * 100
            pnl_abs = (price - position['entry_price']) * (capital / position['entry_price'])
            capital += pnl_abs
            trades.append({
                'Entry Time':  position['entry_time'],
                'Exit Time':   ts,
                'Type':        position['type'],
                'Entry Price': round(position['entry_price'], 4),
                'Exit Price':  round(price, 4),
                'PnL %':       round(pnl, 2),
                'PnL ₹':       round(pnl_abs, 2),
                'Result':      '✅ Win' if pnl > 0 else '❌ Loss'
            })
            position = None
        equity.append(capital)

    # Close open position at last price
    if position is not None:
        price = df['Close'].iloc[-1]
        pnl_abs = (price - position['entry_price']) * (capital / position['entry_price'])
        capital += pnl_abs

    trades_df = pd.DataFrame(trades)
    stats = {}
    if not trades_df.empty:
        wins  = trades_df[trades_df['PnL %'] > 0]
        stats = {
            'Total Trades':    len(trades_df),
            'Win Rate':        f"{round(len(wins)/len(trades_df)*100,1)}%",
            'Total PnL %':     f"{round(trades_df['PnL %'].sum(),2)}%",
            'Avg PnL %':       f"{round(trades_df['PnL %'].mean(),2)}%",
            'Best Trade':      f"{trades_df['PnL %'].max()}%",
            'Worst Trade':     f"{trades_df['PnL %'].min()}%",
            'Final Capital':   f"₹{round(capital,2):,}",
            'Net Profit':      f"₹{round(capital - initial_capital,2):,}",
        }
    return trades_df, stats, equity


def run_backtest_signal_only(df: pd.DataFrame, signal_type: str, holding_bars: int = 10,
                              sl_target_mode: str = "none", sl_pct: float = 1.0, tgt_pct: float = 2.0,
                              initial_capital: float = 100000.0):
    """
    Pure signal backtest with proper SL/Target — analyzes EVERY occurrence of a
    signal independently using real risk management rules.

    signal_type: 'BUY' (lower band touches) or 'SELL' (upper band touches)
    holding_bars: max bars to hold if SL/Target not hit (timeout exit)

    sl_target_mode:
        "none"    — no SL/Target, just measure price after holding_bars (old behavior)
        "percent" — SL/Target as % of entry price
        "band"    — SL = entry band itself broken further, Target = opposite band touched

    sl_pct / tgt_pct: used only when sl_target_mode == "percent"
    """
    trades = []
    target_signals = ['BUY'] if signal_type == 'BUY' else ['SELL', 'SELL_CROSS_LOWER']

    n = len(df)
    close_arr = df['Close'].values
    high_arr  = df['High'].values if 'High' in df.columns else close_arr
    low_arr   = df['Low'].values  if 'Low'  in df.columns else close_arr
    upper_arr = df['upper'].values if 'upper' in df.columns else None
    lower_arr = df['lower'].values if 'lower' in df.columns else None

    for i in range(n):
        sig = df['signal'].iloc[i] if 'signal' in df.columns else ''
        if sig in target_signals:
            entry_price = float(close_arr[i])
            entry_time  = str(df.index[i])
            max_exit_idx = min(i + holding_bars, n - 1)
            if max_exit_idx <= i:
                continue

            # ── Determine SL / Target price levels ──
            if sl_target_mode == "percent":
                if signal_type == 'BUY':
                    sl_price  = entry_price * (1 - sl_pct/100)
                    tgt_price = entry_price * (1 + tgt_pct/100)
                else:
                    sl_price  = entry_price * (1 + sl_pct/100)
                    tgt_price = entry_price * (1 - tgt_pct/100)
            elif sl_target_mode == "band":
                # Target = opposite band at entry bar; SL = small buffer beyond entry band
                if signal_type == 'BUY':
                    tgt_price = float(upper_arr[i]) if upper_arr is not None and not np.isnan(upper_arr[i]) else entry_price*1.02
                    sl_price  = float(lower_arr[i]) * 0.995 if lower_arr is not None and not np.isnan(lower_arr[i]) else entry_price*0.99
                else:
                    tgt_price = float(lower_arr[i]) if lower_arr is not None and not np.isnan(lower_arr[i]) else entry_price*0.98
                    sl_price  = float(upper_arr[i]) * 1.005 if upper_arr is not None and not np.isnan(upper_arr[i]) else entry_price*1.01
            else:
                sl_price = tgt_price = None  # no SL/Target

            # ── Walk forward bar by bar to find first SL or Target hit ──
            exit_idx   = max_exit_idx
            exit_price = float(close_arr[max_exit_idx])
            exit_reason = "⏱ Timeout"

            if sl_target_mode in ("percent", "band"):
                for j in range(i+1, max_exit_idx+1):
                    hi = float(high_arr[j])
                    lo = float(low_arr[j])
                    if signal_type == 'BUY':
                        if lo <= sl_price:
                            exit_idx, exit_price, exit_reason = j, sl_price, "🛑 SL Hit"
                            break
                        if hi >= tgt_price:
                            exit_idx, exit_price, exit_reason = j, tgt_price, "🎯 Target Hit"
                            break
                    else:
                        if hi >= sl_price:
                            exit_idx, exit_price, exit_reason = j, sl_price, "🛑 SL Hit"
                            break
                        if lo <= tgt_price:
                            exit_idx, exit_price, exit_reason = j, tgt_price, "🎯 Target Hit"
                            break

            exit_time = str(df.index[exit_idx])

            if signal_type == 'BUY':
                pnl_pct = (exit_price - entry_price) / entry_price * 100
            else:
                pnl_pct = (entry_price - exit_price) / entry_price * 100

            # Best favorable move within the holding window (informational)
            future_slice = close_arr[i:max_exit_idx+1]
            if signal_type == 'BUY':
                best_pct = (future_slice.max() - entry_price) / entry_price * 100
            else:
                best_pct = (entry_price - future_slice.min()) / entry_price * 100

            row = {
                'Signal Time':  entry_time,
                'Signal Price': round(entry_price, 4),
                'Exit Price':   round(float(exit_price), 4),
                'Exit Time':    exit_time,
                'Exit Reason':  exit_reason,
                'PnL %':        round(pnl_pct, 2),
                'PnL ₹':        round(initial_capital * pnl_pct / 100, 2),
                'Best Move %':  round(best_pct, 2),
                'Result':       '✅ Win' if pnl_pct > 0 else '❌ Loss'
            }
            if sl_target_mode in ("percent", "band"):
                row['SL Price']  = round(sl_price, 4)
                row['Target Price'] = round(tgt_price, 4)
            trades.append(row)

    trades_df = pd.DataFrame(trades)
    stats = {}
    if not trades_df.empty:
        wins = trades_df[trades_df['PnL %'] > 0]

        # ── Compounded capital simulation (each signal trades full capital) ──
        running_capital = initial_capital
        for pnl_p in trades_df['PnL %']:
            running_capital += running_capital * (pnl_p / 100)
        net_profit = running_capital - initial_capital

        stats = {
            'Total Signals':   len(trades_df),
            'Win Rate':        f"{round(len(wins)/len(trades_df)*100,1)}%",
            'Avg PnL %':       f"{round(trades_df['PnL %'].mean(),2)}%",
            'Avg Best Move %': f"{round(trades_df['Best Move %'].mean(),2)}%",
            'Best Signal':     f"{trades_df['PnL %'].max()}%",
            'Worst Signal':    f"{trades_df['PnL %'].min()}%",
            'Total Return %':  f"{round(trades_df['PnL %'].sum(),2)}%",
            'Final Capital':   f"₹{round(running_capital,2):,}",
            'Net Profit':      f"₹{round(net_profit,2):,}",
        }
        if sl_target_mode in ("percent", "band") and 'Exit Reason' in trades_df.columns:
            sl_hits  = len(trades_df[trades_df['Exit Reason']=='🛑 SL Hit'])
            tgt_hits = len(trades_df[trades_df['Exit Reason']=='🎯 Target Hit'])
            timeouts = len(trades_df[trades_df['Exit Reason']=='⏱ Timeout'])
            stats['🎯 Target Hits'] = f"{tgt_hits} ({round(tgt_hits/len(trades_df)*100,1)}%)"
            stats['🛑 SL Hits']     = f"{sl_hits} ({round(sl_hits/len(trades_df)*100,1)}%)"
            stats['⏱ Timeouts']    = f"{timeouts} ({round(timeouts/len(trades_df)*100,1)}%)"
    return trades_df, stats

# ─────────────────────────────────────────────────────────────────
# CHART BUILDER
# ─────────────────────────────────────────────────────────────────

def build_chart(df: pd.DataFrame, symbol: str, tf: str, indicator_name: str = "NW Envelope (Nadaraya-Watson)") -> go.Figure:
    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        row_heights=[0.75, 0.25],
        vertical_spacing=0.03,
        subplot_titles=[f"{symbol} — {tf}", "Volume"]
    )

    # Smart candle rendering based on bar count
    bar_count = len(df)
    if bar_count > 300:
        # Too many bars — use OHLC for clarity
        fig.add_trace(go.Ohlc(
            x=df.index,
            open=df['Open'], high=df['High'],
            low=df['Low'],   close=df['Close'],
            increasing=dict(line=dict(color='#26a69a', width=1)),
            decreasing=dict(line=dict(color='#ef5350', width=1)),
            name='Price'
        ), row=1, col=1)
    else:
        # Few bars — proper candlesticks
        fig.add_trace(go.Candlestick(
            x=df.index,
            open=df['Open'], high=df['High'],
            low=df['Low'],   close=df['Close'],
            increasing=dict(line=dict(color='#26a69a', width=2), fillcolor='#26a69a'),
            decreasing=dict(line=dict(color='#ef5350', width=2), fillcolor='#ef5350'),
            name='Price'
        ), row=1, col=1)

    # NWE Upper band first (for fill reference)
    if 'upper' in df.columns:
        fig.add_trace(go.Scatter(
            x=df.index, y=df['upper'],
            line=dict(color='#ff6b6b', width=2),
            name='Upper Band',
            opacity=1.0
        ), row=1, col=1)

    # Lower band with fill between upper and lower
    if 'lower' in df.columns:
        fig.add_trace(go.Scatter(
            x=df.index, y=df['lower'],
            line=dict(color='#51cf66', width=2),
            fill='tonexty',
            fillcolor='rgba(120,120,180,0.10)',
            name='Lower Band',
            opacity=1.0
        ), row=1, col=1)

    # Midline — NW Estimate or Bollinger Middle (SMA), dashed
    if 'nwe' in df.columns:
        mid_label = "Middle (SMA)" if indicator_name == "Bollinger Bands" else "NW Estimate"
        fig.add_trace(go.Scatter(
            x=df.index, y=df['nwe'],
            line=dict(color='#74c0fc', width=1.5, dash='dash'),
            name=mid_label,
            opacity=0.85
        ), row=1, col=1)

    # BUY/SELL signals - big visible arrows
    if 'signal' in df.columns:
        buy_df  = df[df['signal'] == 'BUY']
        sell_df = df[df['signal'] == 'SELL']
        if not buy_df.empty:
            fig.add_trace(go.Scatter(
                x=buy_df.index,
                y=buy_df['Low'] * 0.9985,
                mode='markers',
                marker=dict(
                    symbol='triangle-up',
                    size=14,
                    color='#00e676',
                    line=dict(color='#00e676', width=1)
                ),
                name='BUY Signal',
            ), row=1, col=1)
        if not sell_df.empty:
            fig.add_trace(go.Scatter(
                x=sell_df.index,
                y=sell_df['High'] * 1.0015,
                mode='markers',
                marker=dict(
                    symbol='triangle-down',
                    size=14,
                    color='#ff1744',
                    line=dict(color='#ff1744', width=1)
                ),
                name='SELL Signal',
            ), row=1, col=1)

    # Volume
    colors = ['#3fb950' if c >= o else '#f85149'
              for c, o in zip(df['Close'], df['Open'])]
    fig.add_trace(go.Bar(
        x=df.index, y=df['Volume'],
        marker_color=colors, name='Volume', opacity=0.6
    ), row=2, col=1)

    fig.update_layout(
        template='plotly_dark',
        paper_bgcolor='#0d1117',
        plot_bgcolor='#0d1117',
        height=650,
        showlegend=True,
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1,
                    font=dict(size=10, color='#8b949e')),
        margin=dict(l=10, r=10, t=40, b=10),
        font=dict(color='#c9d1d9', family='monospace'),
        xaxis=dict(
            rangeslider=dict(visible=False),
            showgrid=True,
            gridcolor='#1e2530',
            zeroline=False,
            tickangle=-45,
        ),
        xaxis2=dict(
            rangeslider=dict(visible=False),
            showgrid=True,
            gridcolor='#1e2530',
            zeroline=False,
        ),
    )
    fig.update_yaxes(gridcolor='#1e2530', showgrid=True, zeroline=False)
    return fig

# ─────────────────────────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("## ⚙️ Settings")

    # ═══════════════════════════════════════════════
    # MASTER INDEX & STOCK DATABASE
    # ═══════════════════════════════════════════════
    INDEX_DATABASE = {
        # ══════════════════════════════════════════
        "🏆 NIFTY INDICES": {
            "Nifty 50":              "^NSEI",
            "Nifty Next 50":         "^NSMIDCP",
            "Nifty 100":             "^CNX100",
            "Nifty 200":             "^CNX200",
            "Nifty 500":             "^CNX500",
            "Nifty Midcap 50":       "^NSEMDCP50",
            "Nifty Midcap 100":      "^NSEMDCP100",
            "Nifty Smallcap 50":     "^CNXSC",
            "Nifty Smallcap 100":    "NIFTY_SMLCAP100.NS",
            "Nifty Smallcap 250":    "NIFTY_SMLCAP250.NS",
            "Nifty LargeMidcap 250": "NIFTY_LARGEMID250.NS",
            "Nifty MicroCap 250":    "NIFTY_MICROCAP250.NS",
            "Nifty Total Market":    "NIFTY_TOTAL_MKT.NS",
            "Sensex":                "^BSESN",
            "BSE 100":               "BSE-100.BO",
            "BSE 200":               "BSE-200.BO",
            "BSE 500":               "BSE-500.BO",
            "BSE Midcap":            "BSE-MID.BO",
            "BSE Smallcap":          "BSE-SMLCAP.BO",
            "India VIX":             "^INDIAVIX",
        },
        # ══════════════════════════════════════════
        "🏭 NIFTY SECTORS": {
            "Bank Nifty":            "^NSEBANK",
            "Nifty IT":              "^CNXIT",
            "Nifty Auto":            "^CNXAUTO",
            "Nifty Pharma":          "^CNXPHARMA",
            "Nifty FMCG":            "^CNXFMCG",
            "Nifty Metal":           "^CNXMETAL",
            "Nifty Energy":          "^CNXENERGY",
            "Nifty Realty":          "^CNXREALTY",
            "Nifty Media":           "^CNXMEDIA",
            "Nifty Infra":           "^CNXINFRA",
            "Nifty PSU Bank":        "^CNXPSUBANK",
            "Nifty Private Bank":    "NIFTY_PVT_BANK.NS",
            "Nifty Financial Serv":  "^CNXFINANCE",
            "Nifty Healthcare":      "NIFTY_HEALTH.NS",
            "Nifty Consumer Dur":    "NIFTY_CONSR_DURBL.NS",
            "Nifty Oil & Gas":       "NIFTY_OIL_AND_GAS.NS",
            "Nifty Chemicals":       "NIFTY_INDIA_CHEMICAL.NS",
            "Nifty Defence":         "NIFTY_INDIA_DEFENCE.NS",
            "Nifty MNC":             "^CNXMNC",
            "Nifty Services":        "^CNXSERVICE",
            "Nifty Commodities":     "^CNXCMDT",
            "Nifty Div Opps 50":     "^CNXDIVOP",
            "Nifty Alpha 50":        "NIFTY_ALPHA_50.NS",
            "Nifty100 Quality 30":   "NIFTY100_QUALITY30.NS",
        },
        # ══════════════════════════════════════════
        "📈 F&O FUTURES": {
            "Nifty 50 Futures":      "NIFTY50=F",
            "BankNifty Futures":     "BANKNIFTY=F",
            "FinNifty Futures":      "FINNIFTY=F",
            "MidcapNifty Futures":   "MIDCPNIFTY=F",
            "Sensex Futures":        "SENSEX=F",
        },
        # ══════════════════════════════════════════
        "🏢 NIFTY 50 STOCKS": {
            "Reliance":              "RELIANCE.NS",
            "TCS":                   "TCS.NS",
            "HDFC Bank":             "HDFCBANK.NS",
            "Infosys":               "INFY.NS",
            "ICICI Bank":            "ICICIBANK.NS",
            "Bajaj Finance":         "BAJFINANCE.NS",
            "Wipro":                 "WIPRO.NS",
            "HCL Tech":              "HCLTECH.NS",
            "L&T":                   "LT.NS",
            "Kotak Bank":            "KOTAKBANK.NS",
            "Axis Bank":             "AXISBANK.NS",
            "SBI":                   "SBIN.NS",
            "Asian Paints":          "ASIANPAINT.NS",
            "Maruti":                "MARUTI.NS",
            "Titan":                 "TITAN.NS",
            "Sun Pharma":            "SUNPHARMA.NS",
            "ITC":                   "ITC.NS",
            "HUL":                   "HINDUNILVR.NS",
            "Power Grid":            "POWERGRID.NS",
            "NTPC":                  "NTPC.NS",
            "Tata Motors":           "TATAMOTORS.NS",
            "Tata Steel":            "TATASTEEL.NS",
            "JSW Steel":             "JSWSTEEL.NS",
            "Hindalco":              "HINDALCO.NS",
            "UltraTech Cement":      "ULTRACEMCO.NS",
            "Nestle India":          "NESTLEIND.NS",
            "Adani Ports":           "ADANIPORTS.NS",
            "Adani Ent.":            "ADANIENT.NS",
            "Coal India":            "COALINDIA.NS",
            "ONGC":                  "ONGC.NS",
            "BPCL":                  "BPCL.NS",
            "Dr Reddys":             "DRREDDY.NS",
            "Cipla":                 "CIPLA.NS",
            "Eicher Motors":         "EICHERMOT.NS",
            "Hero MotoCorp":         "HEROMOTOCO.NS",
            "M&M":                   "M&M.NS",
            "IndusInd Bank":         "INDUSINDBK.NS",
            "Shriram Finance":       "SHRIRAMFIN.NS",
            "Bajaj Auto":            "BAJAJ-AUTO.NS",
            "Bajaj Finserv":         "BAJAJFINSV.NS",
            "BEL":                   "BEL.NS",
            "Trent":                 "TRENT.NS",
            "Grasim":                "GRASIM.NS",
            "Britannia":             "BRITANNIA.NS",
            "Divis Lab":             "DIVISLAB.NS",
            "Apollo Hospitals":      "APOLLOHOSP.NS",
            "Tata Consumer":         "TATACONSUM.NS",
            "IOC":                   "IOC.NS",
            "Zomato":                "ZOMATO.NS",
            "Jio Financial":         "JIOFIN.NS",
        },
        # ══════════════════════════════════════════
        "🥈 NIFTY NEXT 50": {
            "ABB India":             "ABB.NS",
            "ACC":                   "ACC.NS",
            "Ambuja Cement":         "AMBUJACEM.NS",
            "Astral":                "ASTRAL.NS",
            "Avenue Supermarts":     "DMART.NS",
            "Berger Paints":         "BERGEPAINT.NS",
            "Bosch":                 "BOSCHLTD.NS",
            "Cholamandalam":         "CHOLAFIN.NS",
            "Colgate":               "COLPAL.NS",
            "Cummins India":         "CUMMINSIND.NS",
            "DLF":                   "DLF.NS",
            "Godrej Consumer":       "GODREJCP.NS",
            "Havells":               "HAVELLS.NS",
            "HDFC Life":             "HDFCLIFE.NS",
            "ICICI Lombard":         "ICICIGI.NS",
            "ICICI Pru Life":        "ICICIPRULI.NS",
            "Info Edge (Naukri)":    "NAUKRI.NS",
            "Indigo":                "INDIGO.NS",
            "LTIMindtree":           "LTIM.NS",
            "Lupin":                 "LUPIN.NS",
            "Mankind Pharma":        "MANKIND.NS",
            "Marico":                "MARICO.NS",
            "MRF":                   "MRF.NS",
            "Muthoot Finance":       "MUTHOOTFIN.NS",
            "Nykaa":                 "NYKAA.NS",
            "PFC":                   "PFC.NS",
            "PI Industries":         "PIIND.NS",
            "Pidilite":              "PIDILITIND.NS",
            "REC":                   "RECLTD.NS",
            "SBI Cards":             "SBICARD.NS",
            "SBI Life":              "SBILIFE.NS",
            "Siemens":               "SIEMENS.NS",
            "Tata Power":            "TATAPOWER.NS",
            "Torrent Pharma":        "TORNTPHARM.NS",
            "TVS Motor":             "TVSMOTOR.NS",
            "Vedanta":               "VEDL.NS",
            "Voltas":                "VOLTAS.NS",
            "Zydus Life":            "ZYDUSLIFE.NS",
            "Adani Green":           "ADANIGREEN.NS",
            "Adani Total Gas":       "ATGL.NS",
            "Adani Trans.":          "ADANITRANS.NS",
            "Godrej Properties":     "GODREJPROP.NS",
            "Hindustan Aeronaut":    "HAL.NS",
            "Indian Oil":            "IOC.NS",
            "Kalyan Jewellers":      "KALYANKJIL.NS",
            "Macrotech Dev":         "LODHA.NS",
            "Max Healthcare":        "MAXHEALTH.NS",
            "Motherson Sumi":        "MOTHERSON.NS",
            "Oberoi Realty":         "OBEROIRLTY.NS",
            "Paytm":                 "PAYTM.NS",
        },
        # ══════════════════════════════════════════
        "🏦 BANKING": {
            "HDFC Bank":             "HDFCBANK.NS",
            "ICICI Bank":            "ICICIBANK.NS",
            "SBI":                   "SBIN.NS",
            "Axis Bank":             "AXISBANK.NS",
            "Kotak Bank":            "KOTAKBANK.NS",
            "IndusInd Bank":         "INDUSINDBK.NS",
            "Bank of Baroda":        "BANKBARODA.NS",
            "PNB":                   "PNB.NS",
            "Federal Bank":          "FEDERALBNK.NS",
            "IDFC First Bank":       "IDFCFIRSTB.NS",
            "Yes Bank":              "YESBANK.NS",
            "AU Small Finance":      "AUBANK.NS",
            "Canara Bank":           "CANBK.NS",
            "Union Bank":            "UNIONBANK.NS",
            "Indian Bank":           "INDIANB.NS",
            "Bank of India":         "BANKINDIA.NS",
            "Central Bank":          "CENTRALBK.NS",
            "UCO Bank":              "UCOBANK.NS",
            "IOB":                   "IOB.NS",
            "Karnataka Bank":        "KTKBANK.NS",
            "City Union Bank":       "CUB.NS",
            "DCB Bank":              "DCBBANK.NS",
            "South Indian Bank":     "SOUTHBANK.NS",
            "Ujjivan Small Fin":     "UJJIVANSFB.NS",
            "Equitas Small Fin":     "EQUITASBNK.NS",
            "RBL Bank":              "RBLBANK.NS",
            "Bandhan Bank":          "BANDHANBNK.NS",
            "Shriram Finance":       "SHRIRAMFIN.NS",
            "Bajaj Finance":         "BAJFINANCE.NS",
            "Bajaj Finserv":         "BAJAJFINSV.NS",
            "Muthoot Finance":       "MUTHOOTFIN.NS",
            "Cholamandalam":         "CHOLAFIN.NS",
            "HDFC Life":             "HDFCLIFE.NS",
            "SBI Life":              "SBILIFE.NS",
            "ICICI Lombard":         "ICICIGI.NS",
            "ICICI Pru Life":        "ICICIPRULI.NS",
            "SBI Cards":             "SBICARD.NS",
            "PFC":                   "PFC.NS",
            "REC":                   "RECLTD.NS",
            "Jio Financial":         "JIOFIN.NS",
        },
        # ══════════════════════════════════════════
        "💻 IT / TECH": {
            "TCS":                   "TCS.NS",
            "Infosys":               "INFY.NS",
            "Wipro":                 "WIPRO.NS",
            "HCL Tech":              "HCLTECH.NS",
            "Tech Mahindra":         "TECHM.NS",
            "LTIMindtree":           "LTIM.NS",
            "Mphasis":               "MPHASIS.NS",
            "Persistent Sys":        "PERSISTENT.NS",
            "Coforge":               "COFORGE.NS",
            "KPIT Tech":             "KPITTECH.NS",
            "Tata Elxsi":            "TATAELXSI.NS",
            "Info Edge (Naukri)":    "NAUKRI.NS",
            "Zensar Tech":           "ZENSARTECH.NS",
            "Cyient":                "CYIENT.NS",
            "Birlasoft":             "BSOFT.NS",
            "Mastek":                "MASTEK.NS",
            "Happiest Minds":        "HAPPSTMNDS.NS",
            "NIIT Tech":             "NIITTECH.NS",
            "Oracle Fin Serv":       "OFSS.NS",
            "Sonata Software":       "SONATSOFTW.NS",
            "Rategain Travel":       "RATEGAIN.NS",
            "Netweb Tech":           "NETWEB.NS",
            "Newgen Software":       "NEWGEN.NS",
            "Tanla Platforms":       "TANLA.NS",
            "Intellect Design":      "INTELLECT.NS",
            "Firstsource Sol":       "FSL.NS",
            "Subex":                 "SUBEXLTD.NS",
            "Hexaware":              "HEXAWARE.NS",
            "MapmyIndia":            "MAPMYINDIA.NS",
            "Zaggle Prepaid":        "ZAGGLE.NS",
        },
        # ══════════════════════════════════════════
        "💊 PHARMA / HEALTHCARE": {
            "Sun Pharma":            "SUNPHARMA.NS",
            "Dr Reddys":             "DRREDDY.NS",
            "Cipla":                 "CIPLA.NS",
            "Divis Lab":             "DIVISLAB.NS",
            "Lupin":                 "LUPIN.NS",
            "Torrent Pharma":        "TORNTPHARM.NS",
            "Mankind Pharma":        "MANKIND.NS",
            "Apollo Hospitals":      "APOLLOHOSP.NS",
            "Zydus Life":            "ZYDUSLIFE.NS",
            "Aurobindo":             "AUROPHARMA.NS",
            "Alkem Lab":             "ALKEM.NS",
            "Glenmark":              "GLENMARK.NS",
            "Ipca Lab":              "IPCALAB.NS",
            "Abbott India":          "ABBOTINDIA.NS",
            "Pfizer India":          "PFIZER.NS",
            "GSK Pharma":            "GLAXO.NS",
            "Sanofi India":          "SANOFI.NS",
            "Natco Pharma":          "NATCOPHARM.NS",
            "Laurus Labs":           "LAURUSLABS.NS",
            "Divi Lab":              "DIVISLAB.NS",
            "Granules India":        "GRANULES.NS",
            "JB Chemicals":          "JBCHEPHARM.NS",
            "Eris Lifesciences":     "ERIS.NS",
            "Ajanta Pharma":         "AJANTPHARM.NS",
            "Solara Active":         "SOLARA.NS",
            "Suven Pharma":          "SUVENPHAR.NS",
            "Strides Pharma":        "STAR.NS",
            "Sequent Scientific":    "SEQUENT.NS",
            "Max Healthcare":        "MAXHEALTH.NS",
            "Fortis Healthcare":     "FORTIS.NS",
            "Narayana Health":       "NH.NS",
            "Krishna Institute":     "KIMS.NS",
            "Rainbow Children":      "RAINBOW.NS",
            "Thyrocare Tech":        "THYROCARE.NS",
            "Metropolis Health":     "METROPOLIS.NS",
        },
        # ══════════════════════════════════════════
        "🚗 AUTO / EV": {
            "Maruti":                "MARUTI.NS",
            "Tata Motors":           "TATAMOTORS.NS",
            "M&M":                   "M&M.NS",
            "Hero MotoCorp":         "HEROMOTOCO.NS",
            "Bajaj Auto":            "BAJAJ-AUTO.NS",
            "Eicher Motors":         "EICHERMOT.NS",
            "TVS Motor":             "TVSMOTOR.NS",
            "Ashok Leyland":         "ASHOKLEY.NS",
            "Bosch":                 "BOSCHLTD.NS",
            "Motherson Sumi":        "MOTHERSON.NS",
            "MRF":                   "MRF.NS",
            "Apollo Tyres":          "APOLLOTYRE.NS",
            "Exide":                 "EXIDEIND.NS",
            "Amara Raja":            "AMARAJABAT.NS",
            "Endurance Tech":        "ENDURANCE.NS",
            "Minda Corp":            "MINDACORP.NS",
            "Minda Industries":      "MINDAIND.NS",
            "Suprajit Engg":         "SUPRAJIT.NS",
            "Balkrishna Ind":        "BALKRISIND.NS",
            "CEAT":                  "CEATLTD.NS",
            "JK Tyre":               "JKTYRE.NS",
            "Force Motors":          "FORCEMOT.NS",
            "SML Isuzu":             "SMLISUZU.NS",
            "Escorts Kubota":        "ESCORTS.NS",
            "VST Tillers":           "VSTTILLERS.NS",
            "Olectra Greentech":     "OLECTRA.NS",
            "Greaves Cotton":        "GREAVESCOT.NS",
            "Ola Electric":          "OLAELEC.NS",
            "EKI Energy":            "EKINOROG.NS",
            "KPIT Tech":             "KPITTECH.NS",
        },
        # ══════════════════════════════════════════
        "⚡ ENERGY / POWER": {
            "Reliance":              "RELIANCE.NS",
            "ONGC":                  "ONGC.NS",
            "BPCL":                  "BPCL.NS",
            "IOC":                   "IOC.NS",
            "NTPC":                  "NTPC.NS",
            "Power Grid":            "POWERGRID.NS",
            "Tata Power":            "TATAPOWER.NS",
            "Adani Green":           "ADANIGREEN.NS",
            "Adani Power":           "ADANIPOWER.NS",
            "Coal India":            "COALINDIA.NS",
            "NHPC":                  "NHPC.NS",
            "GAIL":                  "GAIL.NS",
            "Petronet LNG":          "PETRONET.NS",
            "HPCL":                  "HINDPETRO.NS",
            "Adani Total Gas":       "ATGL.NS",
            "Gujarat Gas":           "GUJARATGAS.NS",
            "Indraprastha Gas":      "IGL.NS",
            "Mahanagar Gas":         "MGL.NS",
            "SJVN":                  "SJVN.NS",
            "CESC":                  "CESC.NS",
            "Torrent Power":         "TORNTPOWER.NS",
            "JSW Energy":            "JSWENERGY.NS",
            "Renewable Energy":      "RELI.NS",
            "KPI Green Energy":      "KPIGREEN.NS",
            "Websol Energy":         "WESOLINV.NS",
            "Waaree Energies":       "WAAREEENER.NS",
            "Premier Energies":      "PREMIERENE.NS",
            "Inox Wind":             "INOXWIND.NS",
            "Suzlon Energy":         "SUZLON.NS",
            "Sterling Wilson":       "SWSOLAR.NS",
        },
        # ══════════════════════════════════════════
        "🏗️ INFRA / CONSTRUCTION": {
            "L&T":                   "LT.NS",
            "Adani Ports":           "ADANIPORTS.NS",
            "DLF":                   "DLF.NS",
            "Godrej Properties":     "GODREJPROP.NS",
            "Macrotech (Lodha)":     "LODHA.NS",
            "Oberoi Realty":         "OBEROIRLTY.NS",
            "Prestige Estates":      "PRESTIGE.NS",
            "Brigade Ent.":          "BRIGADE.NS",
            "Sobha":                 "SOBHA.NS",
            "Phoenix Mills":         "PHOENIXLTD.NS",
            "NCC":                   "NCC.NS",
            "KNR Constructions":     "KNRCON.NS",
            "PNC Infratech":         "PNCINFRA.NS",
            "Dilip Buildcon":        "DBL.NS",
            "IRB Infra":             "IRB.NS",
            "HAL":                   "HAL.NS",
            "BEL":                   "BEL.NS",
            "BEML":                  "BEML.NS",
            "RVNL":                  "RVNL.NS",
            "IRCON":                 "IRCON.NS",
            "NBCC":                  "NBCC.NS",
            "Ahluwalia Contracts":   "AHLUCONT.NS",
            "HG Infra":              "HGINFRA.NS",
            "G R Infraprojects":     "GRINFRA.NS",
            "Capacite Infra":        "CAPACITE.NS",
            "Welspun Corp":          "WELCORP.NS",
            "Man Infra":             "MANINFRA.NS",
            "Ashoka Buildcon":       "ASHOKA.NS",
            "J Kumar Infra":         "JKIL.NS",
            "PSP Projects":          "PSPPROJECT.NS",
        },
        # ══════════════════════════════════════════
        "🔩 METAL / MINING": {
            "Tata Steel":            "TATASTEEL.NS",
            "JSW Steel":             "JSWSTEEL.NS",
            "Hindalco":              "HINDALCO.NS",
            "Vedanta":               "VEDL.NS",
            "Coal India":            "COALINDIA.NS",
            "NMDC":                  "NMDC.NS",
            "SAIL":                  "SAIL.NS",
            "Jindal Steel":          "JINDALSTEL.NS",
            "Jindal Stainless":      "JSL.NS",
            "APL Apollo Tubes":      "APLAPOLLO.NS",
            "Ratnamani Metals":      "RATNAMANI.NS",
            "NALCO":                 "NATIONALUM.NS",
            "Hindustan Zinc":        "HINDZINC.NS",
            "Hindustan Copper":      "HINDCOPPER.NS",
            "MOIL":                  "MOIL.NS",
            "Shyam Metalics":        "SHYAMMETL.NS",
            "Welspun Corp":          "WELCORP.NS",
            "Mishra Dhatu":          "MIDHANI.NS",
            "MSTC":                  "MSTCLTD.NS",
            "Gravita India":         "GRAVITA.NS",
            "Lloyds Metals":         "LLOYDMETAL.NS",
            "Adani Ent.":            "ADANIENT.NS",
            "Steel Authority":       "SAIL.NS",
            "Ispat Industries":      "JSWSTEEL.NS",
            "Graphite India":        "GRAPHITE.NS",
            "HEG":                   "HEG.NS",
            "Maharashtra Seamless":  "MAHSEAMLES.NS",
            "Gallantt Metal":        "GALLANTT.NS",
            "Godawari Power":        "GPIL.NS",
            "Welspun Special":       "WSSL.NS",
        },
        # ══════════════════════════════════════════
        "🛒 FMCG / CONSUMER": {
            "HUL":                   "HINDUNILVR.NS",
            "ITC":                   "ITC.NS",
            "Nestle India":          "NESTLEIND.NS",
            "Britannia":             "BRITANNIA.NS",
            "Marico":                "MARICO.NS",
            "Dabur":                 "DABUR.NS",
            "Godrej Consumer":       "GODREJCP.NS",
            "Emami":                 "EMAMILTD.NS",
            "Colgate":               "COLPAL.NS",
            "Asian Paints":          "ASIANPAINT.NS",
            "Berger Paints":         "BERGEPAINT.NS",
            "Pidilite":              "PIDILITIND.NS",
            "United Spirits":        "UNITDSPR.NS",
            "United Breweries":      "UBL.NS",
            "Radico Khaitan":        "RADICO.NS",
            "Tata Consumer":         "TATACONSUM.NS",
            "Patanjali Foods":       "PATANJALI.NS",
            "Varun Beverages":       "VBL.NS",
            "CCL Products":          "CCL.NS",
            "Zydus Wellness":        "ZYDUSWELL.NS",
            "Bajaj Consumer":        "BAJAJCON.NS",
            "Jyothy Labs":           "JYOTHYLAB.NS",
            "Kama Holdings":         "KAMAHOLD.NS",
            "Hatsun Agro":           "HATSUN.NS",
            "Heritage Foods":        "HERITGFOOD.NS",
            "Mrs Bectors Food":      "BECTORFOOD.NS",
            "Bikaji Foods":          "BIKAJI.NS",
            "Prataap Snacks":        "DIAMONDYD.NS",
            "DFM Foods":             "DFMFOODS.NS",
            "Westlife Foodworld":    "WESTLIFE.NS",
        },
        # ══════════════════════════════════════════
        "🏭 CAPITAL GOODS / MFG": {
            "Siemens":               "SIEMENS.NS",
            "ABB India":             "ABB.NS",
            "Havells":               "HAVELLS.NS",
            "Cummins India":         "CUMMINSIND.NS",
            "Bharat Forge":          "BHARATFORG.NS",
            "Thermax":               "THERMAX.NS",
            "Voltas":                "VOLTAS.NS",
            "Crompton Consumer":     "CROMPTON.NS",
            "Orient Electric":       "ORIENTELEC.NS",
            "Polycab India":         "POLYCAB.NS",
            "KEI Industries":        "KEI.NS",
            "Finolex Cables":        "FINCABLES.NS",
            "V-Guard":               "VGUARD.NS",
            "Dixon Tech":            "DIXON.NS",
            "Kaynes Tech":           "KAYNES.NS",
            "Amber Enterprises":     "AMBER.NS",
            "Bharat Electronics":    "BEL.NS",
            "Data Patterns":         "DATAPATTNS.NS",
            "MTAR Tech":             "MTARTECH.NS",
            "Paras Defence":         "PARAS.NS",
            "Solar Industries":      "SOLARINDS.NS",
            "Bharat Dynamics":       "BDL.NS",
            "Cochin Shipyard":       "COCHINSHIP.NS",
            "Mazagon Dock":          "MAZDOCK.NS",
            "Garden Reach":          "GRSE.NS",
            "GRSE":                  "GRSE.NS",
            "Texmaco Rail":          "TEXRAIL.NS",
            "Titagarh Rail":         "TITAGARH.NS",
            "RVNL":                  "RVNL.NS",
            "Jupiter Wagons":        "JWL.NS",
        },
        # ══════════════════════════════════════════
        "🌾 AGRI / CHEMICALS": {
            "UPL":                   "UPL.NS",
            "PI Industries":         "PIIND.NS",
            "Coromandel Intl":       "COROMANDEL.NS",
            "Bayer CropScience":     "BAYERCROP.NS",
            "Rallis India":          "RALLIS.NS",
            "Dhanuka Agritech":      "DHANUKA.NS",
            "Astec Lifesciences":    "ASTEC.NS",
            "Insecticides India":    "INSECTICID.NS",
            "Gujarat Fluorochem":    "FLUOROCHEM.NS",
            "SRF":                   "SRF.NS",
            "Navin Fluorine":        "NAVINFLUOR.NS",
            "Clean Science":         "CLEAN.NS",
            "Aarti Industries":      "AARTIIND.NS",
            "Aarti Drugs":           "AARTIDRUGS.NS",
            "Fine Organics":         "FINEORG.NS",
            "Galaxy Surfactants":    "GALAXYSURF.NS",
            "Vinati Organics":       "VINATIORGA.NS",
            "Deepak Nitrite":        "DEEPAKNTR.NS",
            "Tata Chemicals":        "TATACHEM.NS",
            "Chambal Fert":          "CHAMBLFERT.NS",
            "Deepak Fert":           "DEEPAKFERT.NS",
            "GNFC":                  "GNFC.NS",
            "GSFC":                  "GSFC.NS",
            "National Fert":         "NFL.NS",
            "IFFCO Tokio":           "IFFCOTOKIO.NS",
            "Godrej Agrovet":        "GODREJAGRO.NS",
            "Kaveri Seed":           "KANSAINER.NS",
            "Avanti Feeds":          "AVANTIFEED.NS",
            "Waterbase":             "WATERBASE.NS",
            "Satia Industries":      "SATIA.NS",
        },
        # ══════════════════════════════════════════
        "✈️ TRAVEL / HOSPITALITY": {
            "Indigo":                "INDIGO.NS",
            "SpiceJet":              "SPICEJET.NS",
            "Air India (Tata)":      "AIRINDIA.NS",
            "Indian Hotels":         "INDHOTEL.NS",
            "EIH (Oberoi)":          "EIHOTEL.NS",
            "Lemon Tree Hotels":     "LEMONTREE.NS",
            "Chalet Hotels":         "CHALET.NS",
            "Mahindra Holidays":     "MHRIL.NS",
            "Thomas Cook":           "THOMASCOOK.NS",
            "Cox & Kings":           "COXANDKNG.NS",
            "IRCTC":                 "IRCTC.NS",
            "Easy Trip Planner":     "EASEMYTRIP.NS",
            "Yatra Online":          "YATRA.NS",
            "Devyani Intl":          "DEVYANI.NS",
            "Jubilant FoodWorks":    "JUBLFOOD.NS",
            "Westlife Foodworld":    "WESTLIFE.NS",
            "Restaurant Brands":     "RBA.NS",
            "Sapphire Foods":        "SAPPHIRE.NS",
            "Barbeque Nation":       "BARBEQUE.NS",
            "Burger King India":     "BURGERKING.NS",
        },
        # ══════════════════════════════════════════
        "📺 MEDIA / TELECOM": {
            "Bharti Airtel":         "BHARTIARTL.NS",
            "Vodafone Idea":         "IDEA.NS",
            "Jio Financial":         "JIOFIN.NS",
            "Tata Comm":             "TATACOMM.NS",
            "MTNL":                  "MTNL.NS",
            "BSNL":                  "BSNL.NS",
            "Zee Entertainment":     "ZEEL.NS",
            "Sun TV":                "SUNTV.NS",
            "Network18":             "NETWORK18.NS",
            "TV18 Broadcast":        "TV18BRDCST.NS",
            "PVR Inox":              "PVRINOX.NS",
            "Inox Leisure":          "INOXLEISUR.NS",
            "Tips Music":            "TIPSINDLTD.NS",
            "Saregama India":        "SAREGAMA.NS",
            "Nazara Tech":           "NAZARA.NS",
            "Hathway Cable":         "HATHWAY.NS",
            "Den Networks":          "DEN.NS",
            "Dish TV":               "DISHTV.NS",
            "Tata Sky":              "TATASKY.NS",
            "One97 (Paytm)":         "PAYTM.NS",
        },
        # ══════════════════════════════════════════
        "💎 JEWELLERY / RETAIL": {
            "Titan":                 "TITAN.NS",
            "Kalyan Jewellers":      "KALYANKJIL.NS",
            "Senco Gold":            "SENCO.NS",
            "Thangamayil Jewel":     "THANGAMAYL.NS",
            "PC Jeweller":           "PCJEWELLER.NS",
            "Rajesh Exports":        "RAJESHEXPO.NS",
            "Trent":                 "TRENT.NS",
            "Avenue Supermarts":     "DMART.NS",
            "V-Mart Retail":         "VMART.NS",
            "Shoppers Stop":         "SHOPERSTOP.NS",
            "Aditya Birla Fashion":  "ABFRL.NS",
            "Page Industries":       "PAGEIND.NS",
            "Vedant Fashions":       "MANYAVAR.NS",
            "Bata India":            "BATAINDIA.NS",
            "Metro Brands":          "METROBRAND.NS",
            "Campus Activewear":     "CAMPUS.NS",
            "Relaxo Footwear":       "RELAXO.NS",
            "Nykaa":                 "NYKAA.NS",
            "Mamaearth":             "HONASA.NS",
            "Beauty & Personal":     "VLCC.NS",
        },
        # ══════════════════════════════════════════
        "₿ CRYPTO": {
            "Bitcoin":               "BTC-USD",
            "Ethereum":              "ETH-USD",
            "BNB":                   "BNB-USD",
            "XRP":                   "XRP-USD",
            "Solana":                "SOL-USD",
            "Dogecoin":              "DOGE-USD",
            "Cardano":               "ADA-USD",
            "Polkadot":              "DOT-USD",
            "Avalanche":             "AVAX-USD",
            "Chainlink":             "LINK-USD",
        },
        # ══════════════════════════════════════════
        "✏️ CUSTOM": {
            "Custom Symbol...":      "CUSTOM",
        },
    }

    # Helper: get all stocks from a category
    def get_category_stocks(category_name):
        if category_name == "ALL CATEGORIES":
            all_stocks = []
            for cat, stocks in INDEX_DATABASE.items():
                for name, ticker in stocks.items():
                    if ticker != "CUSTOM":
                        all_stocks.append(ticker)
            return list(dict.fromkeys(all_stocks))
        if category_name in INDEX_DATABASE:
            return [v for v in INDEX_DATABASE[category_name].values() if v != "CUSTOM"]
        return []

    # Flatten for dropdown
    all_categories = list(INDEX_DATABASE.keys())
    sel_category = st.selectbox(
        "📂 Category / Sector",
        all_categories,
        index=0,
        help="Index, Sector, ya Stock category choose karo"
    )

    sym_options = INDEX_DATABASE[sel_category]
    sel_sym_label = st.selectbox(
        "📌 Symbol / Index",
        list(sym_options.keys()),
        help="Symbol choose karo"
    )
    selected_val = sym_options[sel_sym_label]

    if selected_val == "CUSTOM":
        symbol = st.text_input("Custom Symbol likhein", value="RELIANCE.NS",
                               help="NSE: .NS | BSE: .BO | US: AAPL | Crypto: BTC-USD").upper()
    else:
        symbol = selected_val
        st.caption(f"Yahoo ticker: `{symbol}`")

    # (symbol selection handled by INDEX_DATABASE above)

    st.markdown("### 📐 Indicator")
    indicator_choice = st.selectbox(
        "Indicator Type",
        ["NW Envelope (Nadaraya-Watson)", "Bollinger Bands"],
        index=0,
        help="Dono indicators Chart, Backtest, Live Scanner, aur Alerts mein use honge",
        key="indicator_type_select"
    )

    if indicator_choice == "Bollinger Bands":
        st.markdown("### Bollinger Parameters")
        bandwidth = 8.0  # unused for BB, kept for compatibility
        mult      = st.slider("Std Dev Multiplier", 0.5, 4.0, 2.0, 0.1,
                              help="Bollinger Bands standard — 2.0 is classic",
                              key="bb_mult_slider")
        lookback  = st.slider("BB Period (length)", 5, 100, 20, 1,
                              help="Bollinger Bands standard — 20 is classic",
                              key="bb_length_slider")
    else:
        st.markdown("### NW Parameters")
        bandwidth = st.slider("Bandwidth (h)", 1.0, 20.0, 8.0, 0.5,
                              help="Controls smoothing — higher = smoother",
                              key="nw_bandwidth_slider")
        mult      = st.slider("Multiplier (envelope width)", 0.5, 6.0, 3.5, 0.1,
                              key="nw_mult_slider")
        lookback  = st.slider("Lookback bars", 50, 499, 200, 10,
                              key="nw_lookback_slider")

    st.markdown("### Timeframe")
    tf_selected = st.selectbox("Timeframe", list(TIMEFRAMES.keys()), index=6)

    st.markdown("### Alerts")
    alert_sound    = st.checkbox("🔔 Browser notification (auto)", value=True)
    alert_lower    = st.checkbox("✅ Alert: Lower band touch (BUY)", value=True)
    alert_upper    = st.checkbox("🔴 Alert: Upper band touch (SELL)", value=True)
    webhook_url    = st.text_input("📡 Telegram/Webhook URL (optional)", value="")

    st.markdown("### Backtest")
    capital = st.number_input("Initial Capital (₹)", value=100000, step=10000)

    st.markdown("### Live Scanner")
    scan_symbols_raw = st.text_area(
        "Scan Symbols (one per line)",
        value="RELIANCE.NS\nINFY.NS\nTCS.NS\nHDFCBANK.NS\nNIFTY50=F",
        height=120
    )
    scan_tf = st.selectbox("Scanner Timeframe", list(TIMEFRAMES.keys()), index=5, key='scan_tf')
    auto_refresh = st.checkbox("🔄 Auto-refresh (60s)", value=False)

# ─────────────────────────────────────────────────────────────────
# HEADER
# ─────────────────────────────────────────────────────────────────

st.markdown(f"""
<div class="app-header">
  <div>
    <h1>📈 {indicator_choice}</h1>
    <p>{'h='+str(bandwidth)+' | ' if indicator_choice != 'Bollinger Bands' else 'Period='+str(lookback)+' | '}mult={mult} | {tf_selected} | {symbol}</p>
  </div>
</div>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────
# TABS
# ─────────────────────────────────────────────────────────────────

tab_chart, tab_backtest, tab_scanner, tab_alerts, tab_watchlist, tab_screener, tab_help = st.tabs([
    "📊 Chart", "🧪 Backtest", "🔍 Live Scanner", "🔔 Alerts", "📋 Watchlist", "📡 Technical Screener", "📖 Help"
])

# ══════════════════════════════════════════════
# TAB 1: CHART
# ══════════════════════════════════════════════
with tab_chart:
    col1, col2 = st.columns([3, 1])
    with col1:
        tf_chart = st.selectbox("Chart Timeframe", list(TIMEFRAMES.keys()),
                                index=list(TIMEFRAMES.keys()).index(tf_selected), key='chart_tf')
    with col2:
        st.write("")
        st.write("")
        refresh_chart = st.button("🔄 Refresh Chart")

    iv, period = TIMEFRAMES[tf_chart]
    with st.spinner(f"Loading {symbol} {tf_chart} data..."):
        df = fetch_data(symbol, iv, period)

    if df.empty:
        st.error("❌ No data. Check symbol or try again.")
    else:
        prices = df['Close'].values.flatten().astype(float)
        nwe_vals, upper_vals, lower_vals = compute_indicator(prices, indicator_choice, bandwidth, mult, lookback)
        df['nwe']   = nwe_vals
        df['upper'] = upper_vals
        df['lower'] = lower_vals
        df = detect_signals(df)

        fig = build_chart(df, symbol, tf_chart, indicator_name=indicator_choice)
        st.plotly_chart(fig, use_container_width=True)

        # Last bar info
        last = df.iloc[-1]
        c1, c2, c3, c4 = st.columns(4)
        def mcard(label, val, color=""):
            return f'<div class="metric-card"><div class="label">{label}</div><div class="value {color}">{val}</div></div>'

        c1.markdown(mcard("Last Price", f"₹{round(float(last['Close']),2):,}"), unsafe_allow_html=True)
        c2.markdown(mcard("Upper Band", f"₹{round(float(last['upper']),2):,}", "red"), unsafe_allow_html=True)
        c3.markdown(mcard("Lower Band", f"₹{round(float(last['lower']),2):,}", "green"), unsafe_allow_html=True)
        sig_color = "green" if last['signal'] == 'BUY' else ("red" if last['signal'] == 'SELL' else "")
        sig_label = last['signal'] if last['signal'] else "NEUTRAL"
        c4.markdown(mcard("Signal", sig_label, sig_color), unsafe_allow_html=True)

# ══════════════════════════════════════════════
# TAB 2: BACKTEST
# ══════════════════════════════════════════════
with tab_backtest:
    st.markdown("### 🧪 Backtest Engine")

    # ── Backtest Mode ─────────────────────────
    bt_mode = st.radio(
        "🎯 Backtest Mode",
        ["🔁 Full Strategy (BUY→SELL pairs)", "✅ BUY Signal Only (Lower Band)", "🔴 SELL Signal Only (Upper Band)"],
        horizontal=False, key="bt_mode_sel",
        help="Full Strategy = BUY pe entry, SELL pe exit. Signal Only = har lower/upper band touch ka standalone result."
    )

    if bt_mode != "🔁 Full Strategy (BUY→SELL pairs)":
        st.caption("📊 Har signal occurrence ko alag analyze karega — SL/Target ya N bars ke hisaab se result dikhayega")

        sl_mode_label = st.radio(
            "🛡️ SL / Target Type",
            ["⏱ No SL/Target (sirf N bars baad price check)", "📐 % Based SL/Target", "📊 NW Band Based SL/Target"],
            key="sl_mode_sel"
        )

        sl_c1, sl_c2, sl_c3 = st.columns(3)
        with sl_c1:
            holding_bars = st.slider("📏 Max Holding Bars (timeout)", 3, 100, 10, 1,
                                      help="Agar SL/Target na lage to itne bars baad force exit")

        if sl_mode_label == "📐 % Based SL/Target":
            sl_target_mode = "percent"
            with sl_c2:
                sl_pct_input = st.number_input("🛑 Stop Loss %", min_value=0.1, max_value=20.0, value=1.0, step=0.1)
            with sl_c3:
                tgt_pct_input = st.number_input("🎯 Target %", min_value=0.1, max_value=50.0, value=2.0, step=0.1)
            st.caption(f"Risk:Reward = 1 : {round(tgt_pct_input/sl_pct_input,2)}")
        elif sl_mode_label == "📊 NW Band Based SL/Target":
            sl_target_mode = "band"
            sl_pct_input, tgt_pct_input = 1.0, 2.0
            st.caption("🎯 Target = Opposite band touch | 🛑 SL = Entry band thoda aur toot jaye (0.5% buffer)")
        else:
            sl_target_mode = "none"
            sl_pct_input, tgt_pct_input = 1.0, 2.0
    else:
        holding_bars = 10
        sl_target_mode = "none"
        sl_pct_input, tgt_pct_input = 1.0, 2.0

    st.divider()

    # ── Symbol Source ─────────────────────────
    bt_src_c1, bt_src_c2 = st.columns([1,1])
    with bt_src_c1:
        bt_source = st.radio("📂 Symbol Source", ["✅ Selected Symbol", "🏆 Pick from Category"],
                              horizontal=True, key="bt_source_sel")
    with bt_src_c2:
        if bt_source == "🏆 Pick from Category":
            bt_cat = st.selectbox("Category", list(INDEX_DATABASE.keys()), key="bt_cat_sel")
            bt_sym_options = INDEX_DATABASE.get(bt_cat, {})
            bt_sym_label = st.selectbox("Symbol", [k for k,v in bt_sym_options.items() if v!="CUSTOM"], key="bt_sym_sel")
            bt_symbol = bt_sym_options.get(bt_sym_label, symbol)
        else:
            bt_symbol = symbol
            st.caption(f"Using sidebar symbol: `{bt_symbol}`")

    # ── Period + Timeframe Selection ─────────────
    BACKTEST_PERIODS = {
        "7 Days":    7,
        "1 Month":   30,
        "3 Months":  90,
        "6 Months":  180,
        "9 Months":  270,
        "1 Year":    365,
        "2 Years":   730,
        "3 Years":   1095,
        "5 Years":   1825,
        "Max Data":  0,
    }

    bt_c1, bt_c2, bt_c3 = st.columns([2, 2, 1])
    with bt_c1:
        bt_tf = st.selectbox("⏱ Timeframe", list(TIMEFRAMES.keys()), index=0, key="bt_tf")
    with bt_c2:
        # Smart default period based on timeframe (1m only has 7 days of data on Yahoo)
        tf_max_period = {
            "1m": "7 Days", "2m": "1 Month", "5m": "1 Month", "15m": "1 Month",
            "30m": "1 Month", "1H": "6 Months", "4H": "1 Year", "1D": "1 Year",
            "1W": "2 Years", "1Mo": "5 Years"
        }
        default_period = tf_max_period.get(bt_tf, "6 Months")
        bt_period_label = st.selectbox(
            "📅 Backtest Period",
            list(BACKTEST_PERIODS.keys()),
            index=list(BACKTEST_PERIODS.keys()).index(default_period),
            key="bt_period"
        )
    with bt_c3:
        st.write("")
        st.write("")
        run_bt = st.button("▶ Run", use_container_width=True, type="primary")

    # ── Data availability warning ─────────────
    YAHOO_LIMITS = {
        "1m": 7, "2m": 60, "5m": 60, "15m": 60, "30m": 60,
        "1H": 730, "4H": 730, "1D": 999999, "1W": 999999, "1Mo": 999999
    }
    period_days = BACKTEST_PERIODS[bt_period_label]
    yahoo_limit = YAHOO_LIMITS.get(bt_tf, 60)

    if period_days > 0 and period_days > yahoo_limit:
        st.warning(f"⚠️ **{bt_tf}** timeframe ke liye Yahoo Finance sirf **{yahoo_limit} din** ka data deta hai. "
                   f"Aapne {bt_period_label} select kiya hai — sirf available data use hoga (~{yahoo_limit} din).")

    if period_days > 0:
        from datetime import timedelta
        end_date   = datetime.now()
        start_date = end_date - timedelta(days=min(period_days, yahoo_limit) if yahoo_limit < 999999 else period_days)
        st.caption(f"📅 Effective Period: **{start_date.strftime('%d %b %Y')}** → **{end_date.strftime('%d %b %Y')}**")
    else:
        st.caption(f"📅 Period: **Maximum available** (~{yahoo_limit if yahoo_limit < 999999 else 'all'} days for {bt_tf})")

    if run_bt:
        iv_bt, period_bt = TIMEFRAMES[bt_tf]
        with st.spinner(f"Running backtest — {bt_period_label} — {bt_symbol}..."):
            df_bt = fetch_data(bt_symbol, iv_bt, period_bt)
            if df_bt.empty:
                st.error("❌ No data. Symbol ya timeframe check karo.")
            else:
                if period_days > 0:
                    cutoff = pd.Timestamp.now(tz=df_bt.index.tz) - pd.Timedelta(days=period_days)
                    df_bt = df_bt[df_bt.index >= cutoff]

                if len(df_bt) < 30:
                    st.warning(f"⚠️ Sirf {len(df_bt)} bars mile — kam hai. Bada period ya alag timeframe try karo.")
                else:
                    prices_bt = df_bt['Close'].values.flatten().astype(float)
                    lb_bt = min(lookback, len(prices_bt)-1)
                    nwe_bt, up_bt, lo_bt = compute_indicator(prices_bt, indicator_choice, bandwidth, mult, lb_bt)
                    df_bt['nwe']   = nwe_bt
                    df_bt['upper'] = up_bt
                    df_bt['lower'] = lo_bt
                    df_bt = detect_signals(df_bt)

                    # ── Period Summary Banner ──
                    st.markdown(f"""
                    <div style='background:#1c2128; border:1px solid #30363d; border-radius:8px;
                                padding:10px 18px; margin-bottom:12px; color:#8b949e; font-size:0.85rem;'>
                        📊 <b style='color:#e6edf3'>{bt_symbol}</b> &nbsp;|&nbsp;
                        ⏱ <b style='color:#58a6ff'>{bt_tf}</b> &nbsp;|&nbsp;
                        📅 <b style='color:#3fb950'>{bt_period_label}</b> &nbsp;|&nbsp;
                        📈 <b style='color:#e6edf3'>{len(df_bt)} bars</b> &nbsp;|&nbsp;
                        🎯 <b style='color:#ffa657'>{bt_mode.split('(')[0].strip()}</b>
                    </div>
                    """, unsafe_allow_html=True)

                    # ══════════════════════════════════════
                    # MODE 1: FULL STRATEGY (BUY→SELL pairs)
                    # ══════════════════════════════════════
                    if bt_mode == "🔁 Full Strategy (BUY→SELL pairs)":
                        trades_df, stats, equity_curve = run_backtest(df_bt, float(capital))

                        if stats:
                            st.markdown("#### 📊 Performance Summary")
                            cols = st.columns(4)
                            for idx, (k, v) in enumerate(stats.items()):
                                color = ""
                                try:
                                    num = float(str(v).replace('%','').replace('₹','').replace(',','').strip())
                                    if ('PnL' in k or 'Profit' in k or 'Capital' in k or 'Rate' in k):
                                        color = "green" if num > 0 else "red"
                                except: pass
                                cols[idx % 4].markdown(
                                    f'<div class="metric-card"><div class="label">{k}</div><div class="value {color}">{v}</div></div>',
                                    unsafe_allow_html=True
                                )

                            st.markdown("#### 📈 Equity Curve")
                            eq_fig = go.Figure()
                            eq_fig.add_trace(go.Scatter(
                                y=equity_curve, mode='lines',
                                line=dict(color='#58a6ff', width=2),
                                fill='tozeroy', fillcolor='rgba(88,166,255,0.08)', name='Equity'
                            ))
                            eq_fig.add_hline(y=float(capital), line_dash='dash', line_color='#8b949e', opacity=0.5)
                            eq_fig.update_layout(
                                template='plotly_dark', paper_bgcolor='#0d1117', plot_bgcolor='#0d1117',
                                height=280, margin=dict(l=10,r=10,t=20,b=10), showlegend=False,
                                font=dict(color='#c9d1d9', family='monospace')
                            )
                            eq_fig.update_xaxes(gridcolor='#21262d')
                            eq_fig.update_yaxes(gridcolor='#21262d')
                            st.plotly_chart(eq_fig, use_container_width=True)

                            st.markdown("#### 📋 Trade Log")
                            if not trades_df.empty:
                                st.dataframe(
                                    trades_df.style.map(
                                        lambda v: 'color: #3fb950' if '✅' in str(v) else ('color: #f85149' if '❌' in str(v) else ''),
                                        subset=['Result']
                                    ), use_container_width=True, height=300
                                )
                                st.download_button("⬇ Download Trade Log CSV", trades_df.to_csv(index=False),
                                                   f"{bt_symbol}_{bt_period_label}_trades.csv", "text/csv")
                        else:
                            st.warning(f"⚠️ {bt_period_label} mein koi completed BUY→SELL pair nahi mila.")

                    # ══════════════════════════════════════
                    # MODE 2 & 3: SIGNAL-ONLY (BUY or SELL)
                    # ══════════════════════════════════════
                    else:
                        sig_type = "BUY" if "BUY" in bt_mode else "SELL"
                        band_name = "Lower Band" if sig_type == "BUY" else "Upper Band"

                        trades_df, stats = run_backtest_signal_only(
                            df_bt, sig_type, holding_bars,
                            sl_target_mode=sl_target_mode,
                            sl_pct=sl_pct_input, tgt_pct=tgt_pct_input,
                            initial_capital=float(capital)
                        )

                        if stats:
                            icon = "✅" if sig_type == "BUY" else "🔴"
                            st.markdown(f"#### {icon} {band_name} Touch — Performance ({holding_bars} bars forward)")
                            cols = st.columns(4)
                            for idx, (k, v) in enumerate(stats.items()):
                                color = ""
                                try:
                                    num = float(str(v).replace('%','').replace('₹','').replace(',','').strip())
                                    if 'PnL' in k or 'Return' in k or 'Move' in k or 'Profit' in k or 'Capital' in k:
                                        color = "green" if num > 0 else "red"
                                except: pass
                                cols[idx % 4].markdown(
                                    f'<div class="metric-card"><div class="label">{k}</div><div class="value {color}">{v}</div></div>',
                                    unsafe_allow_html=True
                                )

                            st.markdown(f"#### 📋 {band_name} Signal Log")
                            style_subset = ['Result']
                            if 'Exit Reason' in trades_df.columns:
                                style_subset.append('Exit Reason')

                            def color_result(v):
                                if '✅' in str(v) or '🎯' in str(v): return 'color: #3fb950'
                                if '❌' in str(v) or '🛑' in str(v): return 'color: #f85149'
                                if '⏱' in str(v): return 'color: #8b949e'
                                return ''

                            st.dataframe(
                                trades_df.style.map(color_result, subset=style_subset),
                                use_container_width=True, height=350
                            )
                            st.download_button(
                                f"⬇ Download {sig_type} Signal Log",
                                trades_df.to_csv(index=False),
                                f"{bt_symbol}_{sig_type}_{bt_period_label}_signals.csv", "text/csv"
                            )

                            # Distribution chart
                            st.markdown("#### 📊 PnL Distribution")
                            dist_fig = go.Figure()
                            dist_fig.add_trace(go.Histogram(
                                x=trades_df['PnL %'], nbinsx=20,
                                marker_color='#3fb950' if sig_type=='BUY' else '#f85149',
                                opacity=0.7
                            ))
                            dist_fig.update_layout(
                                template='plotly_dark', paper_bgcolor='#0d1117', plot_bgcolor='#0d1117',
                                height=250, margin=dict(l=10,r=10,t=20,b=10), showlegend=False,
                                font=dict(color='#c9d1d9', family='monospace'),
                                xaxis_title="PnL %", yaxis_title="Frequency"
                            )
                            dist_fig.update_xaxes(gridcolor='#21262d')
                            dist_fig.update_yaxes(gridcolor='#21262d')
                            st.plotly_chart(dist_fig, use_container_width=True)
                        else:
                            st.warning(f"⚠️ {bt_period_label} mein koi {band_name} touch signal nahi mila. Bandwidth/Multiplier ya period change karo.")

# TAB 3: LIVE SCANNER
# ══════════════════════════════════════════════
with tab_scanner:
    st.markdown("### 🔍 Live Multi-Symbol Scanner")

    # ── Signal Filter ─────────────────────────
    sc_filter_c1, sc_filter_c2 = st.columns([2,2])
    with sc_filter_c1:
        signal_filter = st.radio(
            "🎯 Signal Filter",
            ["🔔 BUY + SELL Only", "✅ BUY Only (Lower Band)", "🔴 SELL Only (Upper Band)", "📊 ALL (including Neutral)"],
            horizontal=False, key="sc_signal_filter"
        )
    with sc_filter_c2:
        band_info = st.empty()

    # Show band filter info
    if signal_filter == "✅ BUY Only (Lower Band)":
        band_info.markdown("""
        <div class="alert-buy">
        ✅ Sirf wo stocks dikhenge jahan candle <b>Lower Band</b> touch/cross kare
        </div>""", unsafe_allow_html=True)
    elif signal_filter == "🔴 SELL Only (Upper Band)":
        band_info.markdown("""
        <div class="alert-sell">
        🔴 Sirf wo stocks dikhenge jahan candle <b>Upper Band</b> touch/cross kare
        </div>""", unsafe_allow_html=True)

    st.divider()

    # ── Scan Source ───────────────────────────
    scan_source = st.radio(
        "📂 Kahan Se Scan Karna Hai?",
        ["📋 Meri Watchlist", "🏆 Index/Sector Category", "✏️ Custom Symbols"],
        horizontal=True, key="scan_source2"
    )

    scan_symbols = []

    # ─── SOURCE 1: WATCHLIST ──────────────────
    if scan_source == "📋 Meri Watchlist":
        if 'watchlists' not in st.session_state or not st.session_state.watchlists:
            st.warning("⚠️ Koi watchlist nahi! Pehle Watchlist tab mein banao.")
        else:
            wl_names = list(st.session_state.watchlists.keys())
            sel_wl_sc = st.selectbox("📂 Watchlist Choose Karo", wl_names, key="scanner_wl2")
            wl_stocks = st.session_state.watchlists.get(sel_wl_sc, [])
            if wl_stocks:
                st.success(f"✅ {sel_wl_sc} — {len(wl_stocks)} stocks")
                scan_symbols = wl_stocks.copy()
            else:
                st.warning("Watchlist mein koi stock nahi!")

    # ─── SOURCE 2: INDEX/SECTOR ───────────────
    elif scan_source == "🏆 Index/Sector Category":
        cat_c1, cat_c2 = st.columns([1,1])
        with cat_c1:
            # Add "Scan All" option
            all_cats = ["⭐ SCAN ALL CATEGORIES"] + list(INDEX_DATABASE.keys())
            sel_scan_cat = st.selectbox("📂 Category Select Karo", all_cats, key="scan_cat")
        with cat_c2:
            if sel_scan_cat == "⭐ SCAN ALL CATEGORIES":
                all_tickers = []
                for cat, stocks in INDEX_DATABASE.items():
                    for ticker in stocks.values():
                        if ticker != "CUSTOM":
                            all_tickers.append(ticker)
                scan_symbols = list(dict.fromkeys(all_tickers))
                st.info(f"📊 Total: {len(scan_symbols)} symbols across all categories")
            else:
                cat_stocks = INDEX_DATABASE.get(sel_scan_cat, {})
                scan_symbols = [v for v in cat_stocks.values() if v != "CUSTOM"]
                st.success(f"✅ {sel_scan_cat}: {len(scan_symbols)} symbols")

        # Show symbols preview
        if scan_symbols:
            with st.expander(f"📋 Symbols preview ({len(scan_symbols)})", expanded=False):
                preview_cols = st.columns(4)
                for i, sym in enumerate(scan_symbols):
                    preview_cols[i%4].caption(sym)

    # ─── SOURCE 3: CUSTOM ────────────────────
    else:
        custom_input = st.text_area(
            "Symbols likhein (comma ya newline se alag karo)",
            value="RELIANCE.NS, TCS.NS, INFY.NS, HDFCBANK.NS",
            height=80, label_visibility="collapsed"
        )
        raw = [s.strip().upper() for s in custom_input.replace("\n",",").split(",") if s.strip()]
        scan_symbols = list(dict.fromkeys(raw))
        st.caption(f"📋 {len(scan_symbols)} symbols")

    st.divider()

    # ── Auto-save to Telegram Toggle ─────────
    auto_tg_save = st.checkbox(
        "📱 Har Scan Telegram Pe Auto-Save Karo (Permanent History)",
        value=False, key="auto_tg_scan_save",
        help="ON karne se har scan ka result automatically Telegram pe bhej diya jayega — wahan permanent history rahegi"
    )
    if auto_tg_save:
        if 'tg_token' in st.session_state and st.session_state.tg_token:
            st.caption("✅ Auto-save ON — Telegram connected")
        else:
            st.warning("⚠️ Pehle Alerts tab mein Telegram Token/Chat ID save karo!")

    st.write("")

    # ── Scan Controls ─────────────────────────
    sc_c1, sc_c2, sc_c3 = st.columns([2,1,1])
    with sc_c1:
        scan_tf_tab = st.selectbox("⏱ Timeframe", list(TIMEFRAMES.keys()), index=5, key="scan_tf_final")
    with sc_c2:
        st.write("")
        run_scan = st.button("🚀 Scan Now", use_container_width=True, type="primary", key="run_scan_final")
    with sc_c3:
        st.write("")
        st.metric("Symbols", len(scan_symbols))

    if run_scan:
        if not scan_symbols:
            st.error("❌ Koi symbol nahi!")
        else:
            iv_sc, per_sc = TIMEFRAMES[scan_tf_tab]
            results = []
            prog = st.progress(0)
            status_text = st.empty()

            for i, sym in enumerate(scan_symbols):
                status_text.text(f"⏳ Scanning {sym}... ({i+1}/{len(scan_symbols)})")
                df_sc = fetch_data(sym, iv_sc, per_sc)
                if not df_sc.empty and len(df_sc) > 50:
                    prices_sc = df_sc["Close"].values.flatten().astype(float)
                    lb_sc = min(lookback, len(prices_sc)-1)
                    _, up_sc, lo_sc = compute_indicator(prices_sc, indicator_choice, bandwidth, mult, lb_sc)
                    df_sc["upper"] = up_sc
                    df_sc["lower"] = lo_sc
                    df_sc = detect_signals(df_sc)
                    last_row   = df_sc.iloc[-1]
                    close_p    = float(last_row["Close"])
                    up_p       = float(last_row["upper"]) if not np.isnan(last_row["upper"]) else 0
                    lo_p       = float(last_row["lower"]) if not np.isnan(last_row["lower"]) else 0
                    sig        = last_row["signal"] if last_row["signal"] else "NEUTRAL"
                    dist_upper = round((up_p - close_p) / close_p * 100, 2) if up_p else 0
                    dist_lower = round((close_p - lo_p) / close_p * 100, 2) if lo_p else 0

                    # Band touch indicators — Near Upper/Lower also counts as signal
                    near_upper = dist_upper <= 0.5   # within 0.5% of upper band
                    near_lower = dist_lower <= 0.5   # within 0.5% of lower band
                    above_upper = close_p >= up_p    # price crossed above upper

                    # Override signal if near band
                    if above_upper or near_upper:
                        final_sig = "SELL"
                        band_status = "🔴 Upper Band Touch"
                    elif near_lower:
                        final_sig = "BUY"
                        band_status = "✅ Lower Band Touch"
                    elif sig in ("BUY",):
                        final_sig = "BUY"
                        band_status = "✅ Lower Band Touch"
                    elif sig in ("SELL", "SELL_CROSS_LOWER"):
                        final_sig = "SELL"
                        band_status = "🔴 Upper Band Touch"
                    else:
                        final_sig = "NEUTRAL"
                        band_status = "—"

                    results.append({
                        "Symbol":       sym,
                        "Price":        f"₹{close_p:,.2f}",
                        "Upper Band":   f"₹{up_p:,.2f}",
                        "Lower Band":   f"₹{lo_p:,.2f}",
                        "Dist Upper%":  f"{dist_upper}%",
                        "Dist Lower%":  f"{dist_lower}%",
                        "Band Status":  band_status,
                        "Signal":       final_sig,
                        "Time":         str(df_sc.index[-1])[:16],
                    })
                prog.progress((i+1)/len(scan_symbols))

            status_text.empty()
            prog.empty()

            if results:
                res_df = pd.DataFrame(results)

                # ── AUTO-SAVE TO TELEGRAM (Permanent History) ─────
                if auto_tg_save and 'tg_token' in st.session_state and st.session_state.tg_token:
                    buy_auto  = res_df[res_df["Signal"]=="BUY"]["Symbol"].tolist()
                    sell_auto = res_df[res_df["Signal"]=="SELL"]["Symbol"].tolist()
                    scan_time = pd.Timestamp.now().strftime("%d-%b-%Y %H:%M")

                    auto_msg = f"📊 <b>NW SCAN HISTORY</b>\n━━━━━━━━━━━━━\n"
                    auto_msg += f"🕐 {scan_time}\n"
                    auto_msg += f"⏱ TF: {scan_tf_tab} | Source: {scan_source}\n"
                    auto_msg += f"📈 Scanned: {len(results)} stocks\n\n"

                    if buy_auto:
                        auto_msg += f"✅ <b>BUY ({len(buy_auto)})</b>:\n"
                        auto_msg += "\n".join([f"• {s}" for s in buy_auto[:20]])
                        auto_msg += "\n\n"
                    if sell_auto:
                        auto_msg += f"🔴 <b>SELL ({len(sell_auto)})</b>:\n"
                        auto_msg += "\n".join([f"• {s}" for s in sell_auto[:20]])
                        auto_msg += "\n\n"
                    if not buy_auto and not sell_auto:
                        auto_msg += "⚪ Koi active signal nahi mila"
                    auto_msg += "━━━━━━━━━━━━━"

                    try:
                        r_auto = requests.post(
                            f"https://api.telegram.org/bot{st.session_state.tg_token}/sendMessage",
                            json={"chat_id": st.session_state.tg_chat_id,
                                  "text": auto_msg, "parse_mode": "HTML"},
                            timeout=15
                        )
                        if r_auto.status_code == 200:
                            st.toast("📱 History Telegram pe save ho gayi!", icon="✅")
                        else:
                            st.warning(f"⚠️ Auto-save failed: {r_auto.text[:100]}")
                    except Exception as e_auto:
                        st.warning(f"⚠️ Auto-save error: {e_auto}")

                # ── Apply Signal Filter ───────────
                if signal_filter == "✅ BUY Only (Lower Band)":
                    filtered_df = res_df[res_df["Signal"] == "BUY"]
                    st.markdown(f"#### ✅ Lower Band Touch — {len(filtered_df)} stocks found")
                elif signal_filter == "🔴 SELL Only (Upper Band)":
                    filtered_df = res_df[res_df["Signal"] == "SELL"]
                    st.markdown(f"#### 🔴 Upper Band Touch — {len(filtered_df)} stocks found")
                elif signal_filter == "📊 ALL (including Neutral)":
                    filtered_df = res_df
                    st.markdown(f"#### 📊 All Signals — {len(filtered_df)} stocks scanned")
                else:  # Default: BUY + SELL Only
                    filtered_df = res_df[res_df["Signal"].isin(["BUY", "SELL"])]
                    st.markdown(f"#### 🔔 Active Signals — ✅ {len(res_df[res_df['Signal']=='BUY'])} BUY | 🔴 {len(res_df[res_df['Signal']=='SELL'])} SELL")

                # ── Summary Cards ─────────────────
                buy_c  = len(res_df[res_df["Signal"]=="BUY"])
                sell_c = len(res_df[res_df["Signal"] == "SELL"])
                neu_c  = len(res_df[res_df["Signal"]=="NEUTRAL"])
                s1,s2,s3,s4 = st.columns(4)
                s1.markdown(f'<div class="metric-card"><div class="label">Total Scanned</div><div class="value">{len(results)}</div></div>', unsafe_allow_html=True)
                s2.markdown(f'<div class="metric-card"><div class="label">✅ BUY (Lower)</div><div class="value green">{buy_c}</div></div>', unsafe_allow_html=True)
                s3.markdown(f'<div class="metric-card"><div class="label">🔴 SELL (Upper)</div><div class="value red">{sell_c}</div></div>', unsafe_allow_html=True)
                s4.markdown(f'<div class="metric-card"><div class="label">⚪ Neutral</div><div class="value">{neu_c}</div></div>', unsafe_allow_html=True)
                st.write("")

                if filtered_df.empty:
                    st.info(f"⚪ Selected filter mein koi result nahi.")
                else:
                    def highlight_signal(val):
                        if val == "BUY":    return "background-color:#0d2818;color:#3fb950;font-weight:bold"
                        if val in ("SELL","SELL_CROSS_LOWER"): return "background-color:#2d0f0f;color:#f85149;font-weight:bold"
                        return "color:#8b949e"
                    def highlight_band(val):
                        if "Lower" in str(val): return "color:#3fb950;font-weight:bold"
                        if "Upper" in str(val): return "color:#f85149;font-weight:bold"
                        return ""

                    st.dataframe(
                        filtered_df.style
                            .map(highlight_signal, subset=["Signal"])
                            .map(highlight_band, subset=["Band Status"]),
                        use_container_width=True, height=min(500, len(filtered_df)*45+50)
                    )

                    # Alert banners
                    buy_syms  = res_df[res_df["Signal"]=="BUY"]["Symbol"].tolist()
                    sell_syms = res_df[res_df["Signal"] == "SELL"]["Symbol"].tolist()
                    if buy_syms:
                        st.markdown(f'<div class="alert-buy">✅ LOWER BAND TOUCH: {" | ".join(buy_syms[:10])}{"..." if len(buy_syms)>10 else ""}</div>', unsafe_allow_html=True)
                    if sell_syms:
                        st.markdown(f'<div class="alert-sell">🔴 UPPER BAND TOUCH: {" | ".join(sell_syms[:10])}{"..." if len(sell_syms)>10 else ""}</div>', unsafe_allow_html=True)

                    # ── Save Results ─────────────────
                    sv1, sv2, sv3 = st.columns(3)
                    with sv1:
                        st.download_button(
                            "⬇ CSV Download",
                            filtered_df.to_csv(index=False),
                            f"scan_{scan_tf_tab}_{pd.Timestamp.now().strftime('%Y%m%d_%H%M')}.csv",
                            "text/csv", use_container_width=True
                        )
                    with sv2:
                        # Save to session history
                        if st.button("💾 History Mein Save", use_container_width=True):
                            if 'scan_history' not in st.session_state:
                                st.session_state.scan_history = []
                            save_entry = {
                                'time':      pd.Timestamp.now().strftime('%d-%b %H:%M'),
                                'tf':        scan_tf_tab,
                                'total':     len(results),
                                'buy':       len(res_df[res_df["Signal"]=="BUY"]),
                                'sell':      len(res_df[res_df["Signal"]=="SELL"]),
                                'buy_syms':  ",".join(res_df[res_df["Signal"]=="BUY"]["Symbol"].tolist()[:10]),
                                'sell_syms': ",".join(res_df[res_df["Signal"]=="SELL"]["Symbol"].tolist()[:10]),
                            }
                            st.session_state.scan_history.insert(0, save_entry)
                            st.success("✅ Saved!")
                    with sv3:
                        # Send to Telegram
                        if st.button("📱 Telegram Bhejo", use_container_width=True):
                            if 'tg_token' in st.session_state and st.session_state.tg_token:
                                buy_list  = res_df[res_df["Signal"]=="BUY"]["Symbol"].tolist()
                                sell_list = res_df[res_df["Signal"]=="SELL"]["Symbol"].tolist()
                                tg_msg = f"📊 <b>NW Band Scanner</b>\n━━━━━━━━━━━━━\n"
                                tg_msg += f"⏱ TF: {scan_tf_tab} | Scanned: {len(results)}\n\n"
                                if buy_list:
                                    tg_msg += f"✅ BUY ({len(buy_list)}):\n" + "\n".join([f"• {s}" for s in buy_list[:15]]) + "\n\n"
                                if sell_list:
                                    tg_msg += f"🔴 SELL ({len(sell_list)}):\n" + "\n".join([f"• {s}" for s in sell_list[:15]])
                                if not buy_list and not sell_list:
                                    tg_msg += "⚪ Koi signal nahi mila"
                                try:
                                    r = requests.post(
                                        f"https://api.telegram.org/bot{st.session_state.tg_token}/sendMessage",
                                        json={"chat_id": st.session_state.tg_chat_id,
                                              "text": tg_msg, "parse_mode": "HTML"}, timeout=10)
                                    if r.status_code == 200: st.success("📱 Telegram pe bheja!")
                                    else: st.error("❌ Telegram error!")
                                except: st.error("❌ Failed!")
                            else:
                                st.warning("Alert tab mein Telegram setup karo!")

            else:
                st.warning("⚠️ Koi data nahi aaya.")



# ── Scan History ─────────────────────────────────────────────────
    if 'scan_history' in st.session_state and st.session_state.scan_history:
        st.divider()
        st.markdown(f"#### 📚 Scan History ({len(st.session_state.scan_history)} saved)")
        hist_df = pd.DataFrame(st.session_state.scan_history)
        def hl_hist(val):
            try:
                if int(val) > 0: return 'color:#3fb950;font-weight:bold'
            except: pass
            return ''
        st.dataframe(hist_df.style.map(hl_hist, subset=['buy','sell']),
                     use_container_width=True, height=200)
        hc1, hc2 = st.columns([1,3])
        with hc1:
            if st.button("🗑 History Clear", key="clr_sc_hist"):
                st.session_state.scan_history = []
                st.rerun()
        with hc2:
            st.download_button("⬇ History CSV",
                pd.DataFrame(st.session_state.scan_history).to_csv(index=False),
                "scan_history.csv", "text/csv")


# TAB 4: ALERTS
# ══════════════════════════════════════════════
with tab_alerts:
    st.markdown("### 🔔 NW Band Scanner — Alert System")

    # ── Telegram Setup ───────────────────────────
    with st.expander("📱 Telegram Setup Guide (Click here)", expanded=False):
        st.markdown("""
        **Step 1** — Telegram mein **@BotFather** search karo → `/newbot` → Token copy karo
        **Step 2** — **@userinfobot** search karo → `/start` → Chat ID copy karo
        **Step 3** — Neeche Token + Chat ID paste karo → Save karo
        **Step 4** — Test Alert bhejo → Phone pe message aayega! 🎉
        """)

    # ── Telegram Config ──────────────────────────
    st.markdown("#### 📱 Telegram Configuration")
    if 'tg_token'   not in st.session_state:
        st.session_state.tg_token   = _PRESET_TOKEN
    if 'tg_chat_id' not in st.session_state:
        st.session_state.tg_chat_id = _PRESET_CHAT_ID

    tg_c1, tg_c2 = st.columns(2)
    with tg_c1:
        tg_token_input = st.text_input("🤖 Bot Token",
            value=st.session_state.tg_token,
            placeholder="7123456789:AAGxxxxx", type="password")
    with tg_c2:
        tg_chat_input = st.text_input("💬 Chat ID",
            value=st.session_state.tg_chat_id, placeholder="987654321")

    btn1, btn2, _ = st.columns([1,1,2])
    with btn1:
        if st.button("💾 Save", use_container_width=True, type="primary"):
            st.session_state.tg_token   = tg_token_input.strip()
            st.session_state.tg_chat_id = tg_chat_input.strip()
            st.success("✅ Saved!")
    with btn2:
        if st.button("📨 Test", use_container_width=True):
            tok  = st.session_state.tg_token.strip()
            cid  = st.session_state.tg_chat_id.strip()
            if not tok:
                st.error("❌ Bot Token missing! Pehle save karo.")
            elif not cid:
                st.error("❌ Chat ID missing! Pehle save karo.")
            else:
                try:
                    url = f"https://api.telegram.org/bot{tok}/sendMessage"
                    payload = {
                        "chat_id":    cid,
                        "text":       "✅ NW Band Scanner\nBot connected! Alerts milne shuru honge",
                        "parse_mode": "HTML"
                    }
                    r = requests.post(url, json=payload, timeout=15)
                    if r.status_code == 200:
                        st.success("✅ Message Telegram pe gaya! Phone check karo.")
                    elif r.status_code == 401:
                        st.error("❌ Token galat hai! BotFather se dobara copy karo.")
                    elif r.status_code == 400:
                        resp_json = r.json()
                        err_desc = resp_json.get("description","")
                        if "chat not found" in err_desc.lower():
                            st.error("❌ Chat ID galat hai! @userinfobot se dobara check karo.")
                        else:
                            st.error(f"❌ Error: {err_desc}")
                    else:
                        st.error(f"❌ HTTP {r.status_code}: {r.text[:200]}")
                except requests.exceptions.Timeout:
                    st.error("❌ Timeout — Internet connection check karo.")
                except requests.exceptions.ConnectionError:
                    st.error("❌ Connection failed — Streamlit Cloud network issue.")
                except Exception as e_tg:
                    st.error(f"❌ Unknown error: {str(e_tg)}")

    tg_ok = bool(st.session_state.tg_token and st.session_state.tg_chat_id)
    if _PRESET_TOKEN:
        st.caption("🔐 Token Streamlit Secrets se load hua — secure!")
    if tg_ok:
        st.markdown('<div class="alert-buy">✅ Telegram Connected — Alerts phone pe milenge!</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="alert-sell">⚠️ Telegram setup nahi hua!</div>', unsafe_allow_html=True)

    st.divider()

    # ══════════════════════════════════════════════
    # ALERT SOURCE SELECTION
    # ══════════════════════════════════════════════
    st.markdown("#### 🎯 Alert Kahan Lagani Hai?")

    alert_mode = st.radio(
        "Alert Mode",
        ["📌 Particular Stock", "🏭 Sector / Category", "📋 Meri Watchlist"],
        horizontal=True, key="alert_mode_sel"
    )

    alert_symbols = []

    # ── MODE 1: PARTICULAR STOCK ─────────────────
    if alert_mode == "📌 Particular Stock":
        st.markdown("##### 📌 Stock Select Karo")
        ps_c1, ps_c2 = st.columns([1,1])
        with ps_c1:
            ps_cat = st.selectbox("Category",
                list(INDEX_DATABASE.keys()), key="ps_cat")
        with ps_c2:
            ps_syms = INDEX_DATABASE.get(ps_cat, {})
            ps_sym_label = st.selectbox("Stock / Index",
                [k for k,v in ps_syms.items() if v != "CUSTOM"],
                key="ps_sym_label")
        ps_ticker = ps_syms.get(ps_sym_label, symbol)
        if ps_ticker == "CUSTOM":
            ps_ticker = symbol

        # Multiple stocks add karne ka option
        st.markdown("**Ya multiple stocks add karo:**")
        if 'alert_custom_stocks' not in st.session_state:
            st.session_state.alert_custom_stocks = []

        add_c1, add_c2 = st.columns([3,1])
        with add_c1:
            new_alert_stock = st.text_input("Symbol add karo",
                placeholder="e.g. ZOMATO.NS, AAPL",
                key="new_alert_stock", label_visibility="collapsed")
        with add_c2:
            if st.button("➕ Add", key="btn_add_alert_stock"):
                sym_add = new_alert_stock.strip().upper()
                if sym_add and sym_add not in st.session_state.alert_custom_stocks:
                    st.session_state.alert_custom_stocks.append(sym_add)
                    st.rerun()

        # Show added stocks with remove option
        if st.session_state.alert_custom_stocks:
            st.markdown("**Added stocks:**")
            for i_as, stk_as in enumerate(list(st.session_state.alert_custom_stocks)):
                col_as1, col_as2 = st.columns([4,1])
                with col_as1:
                    st.markdown(f"`{stk_as}`")
                with col_as2:
                    if st.button("❌", key=f"rem_as_{stk_as}_{i_as}"):
                        st.session_state.alert_custom_stocks.remove(stk_as)
                        st.rerun()

        # Final symbols list
        alert_symbols = [ps_ticker] + st.session_state.alert_custom_stocks
        alert_symbols = list(dict.fromkeys(alert_symbols))
        st.success(f"✅ Alert stocks: **{', '.join(alert_symbols[:5])}**{'...' if len(alert_symbols)>5 else ''}")

    # ── MODE 2: SECTOR / CATEGORY ────────────────
    elif alert_mode == "🏭 Sector / Category":
        st.markdown("##### 🏭 Sector Select Karo")
        sec_c1, sec_c2 = st.columns([2,1])
        with sec_c1:
            all_sec_opts = ["⭐ ALL SECTORS"] + list(INDEX_DATABASE.keys())
            sel_alert_sector = st.selectbox("Sector / Category",
                all_sec_opts, key="alert_sector_sel")
        with sec_c2:
            if sel_alert_sector == "⭐ ALL SECTORS":
                all_sec_tickers = []
                for cat_s, stks_s in INDEX_DATABASE.items():
                    all_sec_tickers += [v for v in stks_s.values() if v != "CUSTOM"]
                alert_symbols = list(dict.fromkeys(all_sec_tickers))
                st.metric("Total Stocks", len(alert_symbols))
            else:
                cat_data = INDEX_DATABASE.get(sel_alert_sector, {})
                alert_symbols = [v for v in cat_data.values() if v != "CUSTOM"]
                st.metric(sel_alert_sector, f"{len(alert_symbols)} stocks")

        if alert_symbols:
            with st.expander(f"📋 Stocks preview ({len(alert_symbols)})", expanded=False):
                prev_cols = st.columns(4)
                for i_p, s_p in enumerate(alert_symbols[:40]):
                    prev_cols[i_p%4].caption(s_p)
                if len(alert_symbols) > 40:
                    st.caption(f"...aur {len(alert_symbols)-40} stocks")

    # ── MODE 3: WATCHLIST ────────────────────────
    else:
        if 'watchlists' not in st.session_state or not st.session_state.watchlists:
            st.warning("⚠️ Koi watchlist nahi! Pehle Watchlist tab mein banao.")
        else:
            alert_wl_sel = st.selectbox("Watchlist",
                list(st.session_state.watchlists.keys()), key="alert_wl_sel3")
            alert_symbols = st.session_state.watchlists.get(alert_wl_sel, [])
            st.success(f"✅ {alert_wl_sel}: {len(alert_symbols)} stocks")

    st.divider()

    # ══════════════════════════════════════════════
    # MULTI-TIMEFRAME ALERT RULES
    # ══════════════════════════════════════════════
    st.markdown("#### ⚙️ Timeframe-wise Alert Rules")
    st.caption("Har timeframe ke liye alag BUY/SELL alert set karo — sab ek saath check honge")

    if 'alert_rules' not in st.session_state:
        st.session_state.alert_rules = [
            {"tf": "5m",  "buy": True,  "sell": True,  "active": True},
            {"tf": "15m", "buy": True,  "sell": True,  "active": True},
            {"tf": "1H",  "buy": True,  "sell": True,  "active": True},
            {"tf": "4H",  "buy": False, "sell": False,  "active": False},
            {"tf": "1D",  "buy": False, "sell": False,  "active": False},
        ]

    h1,h2,h3,h4 = st.columns([1.5,1,1,1])
    h1.markdown("**⏱ Timeframe**")
    h2.markdown("**✅ BUY (Lower)**")
    h3.markdown("**🔴 SELL (Upper)**")
    h4.markdown("**🔘 Active**")

    # IMPORTANT: Use rule's own unique id (not index) as widget key so toggles persist correctly
    for i_r, rule in enumerate(st.session_state.alert_rules):
        rc = st.columns([1.5,1,1,1])
        rule_id = rule.get("_id", i_r)  # stable id

        with rc[0]:
            tf_s = st.selectbox("", list(TIMEFRAMES.keys()),
                index=list(TIMEFRAMES.keys()).index(rule["tf"]) if rule["tf"] in TIMEFRAMES else 0,
                key=f"rtf_{rule_id}", label_visibility="collapsed")
            st.session_state.alert_rules[i_r]["tf"] = tf_s

        with rc[1]:
            buy_s = st.checkbox("BUY", value=rule["buy"],
                key=f"rbuy_{rule_id}", label_visibility="collapsed")
            st.session_state.alert_rules[i_r]["buy"] = buy_s

        with rc[2]:
            sell_s = st.checkbox("SELL", value=rule["sell"],
                key=f"rsell_{rule_id}", label_visibility="collapsed")
            st.session_state.alert_rules[i_r]["sell"] = sell_s

        with rc[3]:
            act_s = st.checkbox("ON", value=rule["active"],
                key=f"ract_{rule_id}", label_visibility="collapsed")
            st.session_state.alert_rules[i_r]["active"] = act_s

        if "_id" not in rule:
            st.session_state.alert_rules[i_r]["_id"] = i_r

    ra1, ra2, _ = st.columns([1,1,2])
    with ra1:
        if st.button("➕ Row Add") and len(st.session_state.alert_rules) < 8:
            new_id = max([r.get("_id", 0) for r in st.session_state.alert_rules], default=0) + 1
            st.session_state.alert_rules.append({"tf":"1D","buy":True,"sell":True,"active":True,"_id":new_id})
            st.rerun()
    with ra2:
        if st.button("➖ Row Hatao") and len(st.session_state.alert_rules) > 1:
            st.session_state.alert_rules.pop()
            st.rerun()

    active_rules = [r for r in st.session_state.alert_rules if r["active"]]
    if active_rules:
        summary = " | ".join([
            f"{'✅' if r['buy'] else ''}{'🔴' if r['sell'] else ''} {r['tf']}"
            for r in active_rules])
        st.caption(f"Active: {summary}")

    st.divider()

    # ── Run Alert Check ──────────────────────────
    al_run_c1, al_run_c2 = st.columns([3,1])
    with al_run_c1:
        st.markdown(f"**Checking:** {len(alert_symbols)} stocks × {len(active_rules)} timeframes = **{len(alert_symbols)*len(active_rules)} checks**")
    with al_run_c2:
        check_alerts = st.button("🔍 Check Now", use_container_width=True, type="primary")

    if 'alert_log' not in st.session_state:
        st.session_state.alert_log = []

    def send_tg(token, chat_id, text):
        """Send Telegram message — returns (success, error_msg)"""
        try:
            # Split long messages
            max_len = 4096
            if len(text) > max_len:
                text = text[:max_len-100] + "\n...aur bhi results hain."
            r = requests.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"},
                timeout=15
            )
            if r.status_code == 200:
                return True, "OK"
            else:
                return False, r.json().get("description", r.text[:100])
        except requests.exceptions.Timeout:
            return False, "Timeout"
        except Exception as ex:
            return False, str(ex)

    if check_alerts:
        if not alert_symbols:
            st.error("❌ Koi symbol nahi! Upar stock/sector/watchlist select karo.")
        elif not active_rules:
            st.warning("⚠️ Koi active rule nahi! Timeframe rules mein ON karo.")
        else:
            all_alerts = []
            total = len(active_rules) * len(alert_symbols)
            prog = st.progress(0)
            status = st.empty()
            count = 0

            for rule in active_rules:
                tf_r = rule["tf"]
                iv_r, per_r = TIMEFRAMES[tf_r]

                for sym_al in alert_symbols:
                    status.text(f"⏳ {sym_al} | {tf_r} ({count+1}/{total})")
                    df_al = fetch_data(sym_al, iv_r, per_r)

                    if not df_al.empty and len(df_al) > 50:
                        prices_al = df_al['Close'].values.flatten().astype(float)
                        lb_al = min(lookback, len(prices_al)-1)
                        _, up_al, lo_al = compute_indicator(prices_al, indicator_choice, bandwidth, mult, lb_al)
                        df_al['upper'] = up_al
                        df_al['lower'] = lo_al

                        last_al   = df_al.iloc[-1]
                        price_al  = round(float(last_al['Close']), 2)
                        up_v_al   = float(last_al['upper']) if not np.isnan(last_al['upper']) else 0
                        lo_v_al   = float(last_al['lower']) if not np.isnan(last_al['lower']) else 0
                        ts_al     = str(df_al.index[-1])[:16]

                        dist_up_al = round((up_v_al - price_al) / price_al * 100, 2) if up_v_al else 999
                        dist_lo_al = round((price_al - lo_v_al) / price_al * 100, 2) if lo_v_al else 999

                        near_upper_al = dist_up_al <= 0.5 or price_al >= up_v_al
                        near_lower_al = dist_lo_al <= 0.5 or price_al <= lo_v_al

                        if near_upper_al and rule["sell"]:
                            all_alerts.append({
                                'type': 'SELL', 'symbol': sym_al,
                                'price': price_al, 'time': ts_al, 'tf': tf_r,
                                'dist': f"{dist_up_al}% from upper",
                                'msg': f"📉 <b>NW Band Scanner</b>\n━━━━━━━━━━━━━\n🔴 <b>SELL SIGNAL</b>\n📌 {sym_al}\n⏱ TF: {tf_r}\n💰 ₹{price_al:,}\n📊 Upper Band Touch ({dist_up_al}%)\n🕐 {ts_al}\n━━━━━━━━━━━━━"
                            })
                        elif near_lower_al and rule["buy"]:
                            all_alerts.append({
                                'type': 'BUY', 'symbol': sym_al,
                                'price': price_al, 'time': ts_al, 'tf': tf_r,
                                'dist': f"{dist_lo_al}% from lower",
                                'msg': f"📈 <b>NW Band Scanner</b>\n━━━━━━━━━━━━━\n✅ <b>BUY SIGNAL</b>\n📌 {sym_al}\n⏱ TF: {tf_r}\n💰 ₹{price_al:,}\n📊 Lower Band Touch ({dist_lo_al}%)\n🕐 {ts_al}\n━━━━━━━━━━━━━"
                            })
                    count += 1
                    prog.progress(count/total)

            status.empty()
            prog.empty()

            if all_alerts:
                st.markdown(f"#### 🔔 {len(all_alerts)} Alert(s) Found!")
                for al in all_alerts:
                    if al['type'] == 'BUY':
                        st.markdown(
                            f'<div class="alert-buy">✅ <b>BUY</b> — {al["symbol"]} | ⏱ {al["tf"]} | 💰 ₹{al["price"]:,} | 📊 {al["dist"]} | 🕐 {al["time"]}</div>',
                            unsafe_allow_html=True)
                    else:
                        st.markdown(
                            f'<div class="alert-sell">🔴 <b>SELL</b> — {al["symbol"]} | ⏱ {al["tf"]} | 💰 ₹{al["price"]:,} | 📊 {al["dist"]} | 🕐 {al["time"]}</div>',
                            unsafe_allow_html=True)
                    if tg_ok:
                        ok, err = send_tg(st.session_state.tg_token, st.session_state.tg_chat_id, al['msg'])
                        if ok:
                            st.caption(f"  📱 Sent: {al['symbol']} {al['tf']}")
                        else:
                            st.warning(f"  ⚠️ Telegram failed ({al['symbol']}): {err}")
                    st.session_state.alert_log.append(al)
            else:
                st.info(f"⚪ {len(alert_symbols)} stocks × {len(active_rules)} TF checked — Koi signal nahi mila.")
                if tg_ok:
                    ok2, err2 = send_tg(st.session_state.tg_token, st.session_state.tg_chat_id,
                        f"📊 <b>NW Band Scanner</b>\n⚪ Scan Complete\n{len(alert_symbols)} stocks checked\nKoi signal nahi mila.")
                    if not ok2:
                        st.warning(f"⚠️ Telegram: {err2}")

    # ── Alert Log ────────────────────────────────
    if st.session_state.alert_log:
        st.divider()
        st.markdown(f"#### 📋 Alert History ({len(st.session_state.alert_log)})")
        log_df = pd.DataFrame([{
            'Time':   a['time'],
            'Type':   a['type'],
            'Symbol': a['symbol'],
            'TF':     a.get('tf',''),
            'Price':  f"₹{a['price']:,}",
            'Band':   a.get('dist',''),
        } for a in st.session_state.alert_log[::-1]])

        def hl_log(val):
            if val == 'BUY':  return 'background-color:#0d2818;color:#3fb950;font-weight:bold'
            if val == 'SELL': return 'background-color:#2d0f0f;color:#f85149;font-weight:bold'
            return ''
        st.dataframe(log_df.style.map(hl_log, subset=['Type']),
                     use_container_width=True, height=250)
        c_cl1, _ = st.columns([1,3])
        with c_cl1:
            if st.button("🗑 Clear History"):
                st.session_state.alert_log = []
                st.rerun()


# TAB 5: WATCHLIST MANAGER
# ══════════════════════════════════════════════
with tab_watchlist:

    # ── Session State Init ───────────────────────────────────────
    if 'watchlists' not in st.session_state:
        st.session_state.watchlists = {
            "My Picks": ["RELIANCE.NS", "TCS.NS", "INFY.NS", "HDFCBANK.NS"],
            "Bank Stocks": ["HDFCBANK.NS", "ICICIBANK.NS", "SBIN.NS", "AXISBANK.NS"],
        }
    if 'active_wl' not in st.session_state:
        st.session_state.active_wl = list(st.session_state.watchlists.keys())[0]

    # ── MASTER SYMBOL LIST for quick add ────────────────────────
    ALL_SYMBOLS = {
        "-- Select --": "",
        "📊 Nifty 50": "^NSEI", "📊 Bank Nifty": "^NSEBANK",
        "📊 Nifty IT": "^CNXIT", "📊 Nifty Pharma": "^CNXPHARMA",
        "📊 Nifty Auto": "^CNXAUTO", "📊 Nifty Metal": "^CNXMETAL",
        "📊 Sensex": "^BSESN", "📈 Nifty Futures": "NIFTY50=F",
        "🏢 Reliance": "RELIANCE.NS", "🏢 TCS": "TCS.NS",
        "🏢 Infosys": "INFY.NS", "🏢 HDFC Bank": "HDFCBANK.NS",
        "🏢 ICICI Bank": "ICICIBANK.NS", "🏢 SBI": "SBIN.NS",
        "🏢 Axis Bank": "AXISBANK.NS", "🏢 Kotak Bank": "KOTAKBANK.NS",
        "🏢 Wipro": "WIPRO.NS", "🏢 HCL Tech": "HCLTECH.NS",
        "🏢 L&T": "LT.NS", "🏢 Bajaj Finance": "BAJFINANCE.NS",
        "🏢 Titan": "TITAN.NS", "🏢 Maruti": "MARUTI.NS",
        "🏢 Asian Paints": "ASIANPAINT.NS", "🏢 Sun Pharma": "SUNPHARMA.NS",
        "🏢 ITC": "ITC.NS", "🏢 HUL": "HINDUNILVR.NS",
        "🏢 Tata Motors": "TATAMOTORS.NS", "🏢 Tata Steel": "TATASTEEL.NS",
        "🏢 ONGC": "ONGC.NS", "🏢 NTPC": "NTPC.NS",
        "🏢 Coal India": "COALINDIA.NS", "🏢 Power Grid": "POWERGRID.NS",
        "🏢 Adani Ent.": "ADANIENT.NS", "🏢 Adani Ports": "ADANIPORTS.NS",
        "🏢 M&M": "M&M.NS", "🏢 Hero MotoCorp": "HEROMOTOCO.NS",
        "🏢 Zomato": "ZOMATO.NS", "🏢 Paytm": "PAYTM.NS",
        "🏢 Nykaa": "NYKAA.NS", "🏢 IndusInd Bank": "INDUSINDBK.NS",
        "🏢 Dr Reddy": "DRREDDY.NS", "🏢 Cipla": "CIPLA.NS",
        "🏢 JSW Steel": "JSWSTEEL.NS", "🏢 Hindalco": "HINDALCO.NS",
        "🏢 UltraTech": "ULTRACEMCO.NS", "🏢 Nestle": "NESTLEIND.NS",
        "₿ Bitcoin": "BTC-USD", "₿ Ethereum": "ETH-USD",
    }

    st.markdown("### 📋 My Watchlists")

    # ════════════════════════════════════════════
    # LEFT: Watchlist names | RIGHT: Stocks
    # ════════════════════════════════════════════
    left_col, right_col = st.columns([1, 2])

    with left_col:
        st.markdown("#### 📂 Watchlists")

        # Show all watchlists as buttons
        for wl_name in list(st.session_state.watchlists.keys()):
            is_active = (wl_name == st.session_state.active_wl)
            btn_style = "background:#1f6feb; color:white;" if is_active else "background:#21262d; color:#c9d1d9;"
            col_wlb, col_wld = st.columns([3, 1])
            with col_wlb:
                if st.button(
                    f"{'▶ ' if is_active else ''}{wl_name} ({len(st.session_state.watchlists[wl_name])})",
                    key=f"wl_btn_{wl_name}",
                    use_container_width=True,
                    type="primary" if is_active else "secondary"
                ):
                    st.session_state.active_wl = wl_name
                    st.rerun()
            with col_wld:
                if st.button("🗑", key=f"del_wl_{wl_name}", help=f"Delete {wl_name}"):
                    del st.session_state.watchlists[wl_name]
                    remaining = list(st.session_state.watchlists.keys())
                    st.session_state.active_wl = remaining[0] if remaining else ""
                    st.success(f"'{wl_name}' deleted!")
                    st.rerun()

        st.divider()

        # Create new watchlist
        st.markdown("**➕ Nayi Watchlist**")
        new_wl_name = st.text_input("Naam likhein", placeholder="e.g. Swing Trades", key="new_wl_name", label_visibility="collapsed")
        if st.button("✅ Create Watchlist", use_container_width=True):
            name = new_wl_name.strip()
            if name:
                if name not in st.session_state.watchlists:
                    st.session_state.watchlists[name] = []
                    st.session_state.active_wl = name
                    st.success(f"✅ '{name}' bana di!")
                    st.rerun()
                else:
                    st.warning("Ye naam pehle se hai!")
            else:
                st.error("Naam likhein!")

    with right_col:
        active = st.session_state.active_wl
        if not active or active not in st.session_state.watchlists:
            st.info("Koi watchlist select karo ya banao.")
        else:
            stocks = st.session_state.watchlists[active]
            st.markdown(f"#### 📋 {active}  `{len(stocks)} stocks`")

            # ── ADD STOCK SECTION ────────────────
            st.markdown("---")
            st.markdown("**➕ Stock Add Karo**")
            add_c1, add_c2 = st.columns([1, 1])
            with add_c1:
                manual_sym = st.text_input(
                    "Custom symbol likhein",
                    placeholder="e.g. ZOMATO.NS, AAPL, BTC-USD",
                    key="manual_sym"
                )
            with add_c2:
                quick_sym_label = st.selectbox(
                    "Ya list se choose karo",
                    list(ALL_SYMBOLS.keys()),
                    key="quick_sym"
                )

            if st.button("➕ ADD SYMBOL", use_container_width=True, type="primary"):
                # Manual input has priority
                sym = manual_sym.strip().upper() if manual_sym.strip() else ALL_SYMBOLS.get(quick_sym_label, "")
                if sym and sym != "":
                    if sym not in st.session_state.watchlists[active]:
                        st.session_state.watchlists[active].append(sym)
                        st.success(f"✅ {sym} add ho gaya!")
                        st.rerun()
                    else:
                        st.warning(f"⚠️ {sym} pehle se hai!")
                else:
                    st.error("❌ Symbol likhein ya list se choose karo!")

            # ── STOCK LIST WITH DELETE ───────────
            st.markdown("---")
            st.markdown("**📃 Stock List**")

            if not stocks:
                st.info("Koi stock nahi hai. Upar se add karo! ⬆️")
            else:
                # Delete All button
                col_da, col_sp = st.columns([1, 3])
                with col_da:
                    if st.button("🗑️ Sab Delete", key="del_all"):
                        st.session_state.watchlists[active] = []
                        st.success("Sab stocks delete ho gaye!")
                        st.rerun()

                st.write("")

                # Show each stock with delete button — clean rows
                for idx_s, stk in enumerate(list(stocks)):
                    c1, c2, c3 = st.columns([3, 1, 1])
                    with c1:
                        st.markdown(
                            f"<div style='background:#161b22; border:1px solid #30363d; "
                            f"border-radius:6px; padding:8px 14px; color:#e6edf3; "
                            f"font-family:monospace; font-size:0.9rem;'>"
                            f"<b>{idx_s+1}.</b> {stk}</div>",
                            unsafe_allow_html=True
                        )
                    with c2:
                        # View chart button
                        if st.button("📊", key=f"chart_{stk}_{idx_s}", help=f"Chart dekhein: {stk}"):
                            st.session_state['jump_symbol'] = stk
                            st.info(f"Chart tab mein jaake {stk} select karo!")
                    with c3:
                        if st.button("🗑️", key=f"del_stk_{stk}_{idx_s}", help=f"Remove {stk}"):
                            st.session_state.watchlists[active].remove(stk)
                            st.success(f"✅ {stk} remove ho gaya!")
                            st.rerun()
                    st.write("")

            # ── SCAN WATCHLIST ───────────────────
            st.markdown("---")
            st.markdown("**🚀 Watchlist Scan Karo**")
            scan_c1, scan_c2 = st.columns([2, 1])
            with scan_c1:
                scan_tf_wl = st.selectbox("Timeframe", list(TIMEFRAMES.keys()), index=5, key='wl_scan_tf')
            with scan_c2:
                st.write("")
                run_wl_scan = st.button("🚀 Scan Now", use_container_width=True, type="primary", key="run_wl_scan")

            if run_wl_scan:
                if not stocks:
                    st.warning("Pehle stocks add karo!")
                else:
                    iv_wl, per_wl = TIMEFRAMES[scan_tf_wl]
                    wl_results = []
                    prog_wl = st.progress(0)
                    status_wl = st.empty()
                    for i_wl, sym_wl in enumerate(stocks):
                        status_wl.text(f"Scanning {sym_wl}... ({i_wl+1}/{len(stocks)})")
                        df_wl = fetch_data(sym_wl, iv_wl, per_wl)
                        if not df_wl.empty and len(df_wl) > 50:
                            prices_wl = df_wl['Close'].values.flatten().astype(float)
                            lb_wl = min(lookback, len(prices_wl)-1)
                            _, up_wl, lo_wl = compute_indicator(prices_wl, indicator_choice, bandwidth, mult, lb_wl)
                            df_wl['upper'] = up_wl
                            df_wl['lower'] = lo_wl
                            df_wl = detect_signals(df_wl)
                            last_wl  = df_wl.iloc[-1]
                            close_wl = float(last_wl['Close'])
                            up_v     = float(last_wl['upper']) if not np.isnan(last_wl['upper']) else 0
                            lo_v     = float(last_wl['lower']) if not np.isnan(last_wl['lower']) else 0
                            sig_wl   = last_wl['signal'] if last_wl['signal'] else 'NEUTRAL'
                            dist_up  = round((up_v - close_wl) / close_wl * 100, 2) if up_v else 0
                            dist_lo  = round((close_wl - lo_v) / close_wl * 100, 2) if lo_v else 0
                            wl_results.append({
                                'Symbol':      sym_wl,
                                'Price':       f"₹{close_wl:,.2f}",
                                'Upper Band':  f"₹{up_v:,.2f}",
                                'Lower Band':  f"₹{lo_v:,.2f}",
                                'Dist Upper%': f"{dist_up}%",
                                'Dist Lower%': f"{dist_lo}%",
                                'Signal':      sig_wl,
                                'Time':        str(df_wl.index[-1])[:16],
                            })
                        prog_wl.progress((i_wl+1)/len(stocks))
                    status_wl.empty()
                    prog_wl.empty()

                    if wl_results:
                        res_wl = pd.DataFrame(wl_results)

                        def hl_sig_wl(val):
                            if val == 'BUY':     return 'background-color:#0d2818;color:#3fb950;font-weight:bold'
                            if val == 'SELL':    return 'background-color:#2d0f0f;color:#f85149;font-weight:bold'
                            return 'color:#8b949e'

                        st.dataframe(res_wl.style.map(hl_sig_wl, subset=['Signal']),
                                     use_container_width=True, height=min(400, len(wl_results)*60+50))

                        # Alert summary
                        buys  = res_wl[res_wl['Signal']=='BUY']['Symbol'].tolist()
                        sells = res_wl[res_wl['Signal']=='SELL']['Symbol'].tolist()
                        if buys:
                            st.markdown(f'<div class="alert-buy">✅ BUY Signals: {" | ".join(buys)}</div>', unsafe_allow_html=True)
                        if sells:
                            st.markdown(f'<div class="alert-sell">🔴 SELL Signals: {" | ".join(sells)}</div>', unsafe_allow_html=True)
                        if not buys and not sells:
                            st.info("⚪ Koi active signal nahi — sabhi NEUTRAL hain.")

                        st.download_button("⬇ CSV Download", res_wl.to_csv(index=False),
                                           f"{active}_scan.csv", "text/csv")


# ══════════════════════════════════════════════
# ══════════════════════════════════════════════
# TAB 6: TECHNICAL SCREENER (Chartink-style)
# ══════════════════════════════════════════════
with tab_screener:
    st.markdown("### 📡 Technical Screener")
    st.markdown("Chartink jaise filters lagao — RSI, Supertrend, CCI, MFI, Stochastic, Ichimoku, High/Low patterns")

    # ── Technical Indicator Functions ────────────
    def compute_rsi(prices, period=14):
        s = pd.Series(prices)
        delta = s.diff()
        gain = delta.where(delta>0, 0.0)
        loss = -delta.where(delta<0, 0.0)
        avg_gain = gain.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
        rs = avg_gain / avg_loss.replace(0, np.nan)
        rsi = 100 - (100/(1+rs))
        return rsi.values

    def compute_stoch_rsi(prices, period=14, smooth_k=3, smooth_d=3):
        rsi = pd.Series(compute_rsi(prices, period))
        rsi_min = rsi.rolling(period).min()
        rsi_max = rsi.rolling(period).max()
        stoch_rsi = (rsi - rsi_min) / (rsi_max - rsi_min + 1e-10) * 100
        k = stoch_rsi.rolling(smooth_k).mean()
        d = k.rolling(smooth_d).mean()
        return k.values, d.values

    def compute_cci(high, low, close, period=20):
        tp = (high + low + close) / 3
        s = pd.Series(tp)
        ma = s.rolling(period).mean()
        mad = s.rolling(period).apply(lambda x: np.mean(np.abs(x - x.mean())), raw=True)
        cci = (s - ma) / (0.015 * mad)
        return cci.values

    def compute_mfi(high, low, close, volume, period=14):
        tp   = (high + low + close) / 3
        rmf  = tp * volume
        df_  = pd.DataFrame({'tp': tp, 'rmf': rmf})
        pos  = df_['rmf'].where(df_['tp'] > df_['tp'].shift(1), 0)
        neg  = df_['rmf'].where(df_['tp'] < df_['tp'].shift(1), 0)
        pmf  = pos.rolling(period).sum()
        nmf  = neg.rolling(period).sum()
        mfr  = pmf / nmf.replace(0, np.nan)
        mfi  = 100 - (100/(1+mfr))
        return mfi.values

    def compute_supertrend(high, low, close, period=7, multiplier=2.0):
        hl2   = (high + low) / 2
        s_h   = pd.Series(high); s_l = pd.Series(low); s_c = pd.Series(close)
        atr_s = (s_h - s_l).rolling(period).mean()
        upper = hl2 + multiplier * atr_s
        lower = hl2 - multiplier * atr_s
        n = len(close)
        supertrend = np.full(n, np.nan)
        direction  = np.full(n, 1)  # 1=bullish, -1=bearish
        for i in range(1, n):
            if np.isnan(upper.iloc[i]) or np.isnan(lower.iloc[i]):
                continue
            # Upper band
            if upper.iloc[i] < upper.iloc[i-1] or close[i-1] > upper.iloc[i-1]:
                up = upper.iloc[i]
            else:
                up = upper.iloc[i-1]
            # Lower band
            if lower.iloc[i] > lower.iloc[i-1] or close[i-1] < lower.iloc[i-1]:
                lo = lower.iloc[i]
            else:
                lo = lower.iloc[i-1]
            upper.iloc[i] = up
            lower.iloc[i] = lo
            if direction[i-1] == -1 and close[i] > up:
                direction[i] = 1
            elif direction[i-1] == 1 and close[i] < lo:
                direction[i] = -1
            else:
                direction[i] = direction[i-1]
            supertrend[i] = lo if direction[i] == 1 else up
        return supertrend, direction

    def compute_ichimoku(high, low, close):
        h = pd.Series(high); l = pd.Series(low)
        tenkan  = (h.rolling(9).max()  + l.rolling(9).min())  / 2
        kijun   = (h.rolling(26).max() + l.rolling(26).min()) / 2
        senkou_a = ((tenkan + kijun) / 2).shift(26)
        senkou_b = ((h.rolling(52).max() + l.rolling(52).min()) / 2).shift(26)
        chikou   = pd.Series(close).shift(-26)
        return tenkan.values, kijun.values, senkou_a.values, senkou_b.values, chikou.values

    def compute_fast_slow_stoch(high, low, close, k_period=14, d_period=3, slowing=3):
        h = pd.Series(high); l = pd.Series(low); c = pd.Series(close)
        lowest_low   = l.rolling(k_period).min()
        highest_high = h.rolling(k_period).max()
        fast_k = (c - lowest_low) / (highest_high - lowest_low + 1e-10) * 100
        slow_k = fast_k.rolling(slowing).mean()
        slow_d = slow_k.rolling(d_period).mean()
        fast_d = fast_k.rolling(d_period).mean()
        return fast_k.values, fast_d.values, slow_k.values, slow_d.values

    def compute_sma(prices, period):
        return pd.Series(prices).rolling(period).mean().values

    def compute_ema(prices, period):
        return pd.Series(prices).ewm(span=period, adjust=False).mean().values

    # ─────────────────────────────────────────────
    # SCREEN BUILDER UI
    # ─────────────────────────────────────────────

    # Source selection
    scr_src_c1, scr_src_c2 = st.columns([1,1])
    with scr_src_c1:
        scr_source = st.radio("📂 Stocks",
            ["📋 Watchlist", "🏆 Category/Index", "✏️ Custom"],
            horizontal=True, key="scr_source")
    with scr_src_c2:
        scr_tf = st.selectbox("⏱ Timeframe", list(TIMEFRAMES.keys()), index=7, key="scr_tf")

    scr_symbols = []
    if scr_source == "📋 Watchlist":
        if 'watchlists' in st.session_state and st.session_state.watchlists:
            scr_wl = st.selectbox("Watchlist", list(st.session_state.watchlists.keys()), key="scr_wl")
            scr_symbols = st.session_state.watchlists.get(scr_wl, [])
            st.caption(f"✅ {len(scr_symbols)} stocks")
        else:
            st.warning("Koi watchlist nahi — Watchlist tab mein banao")
    elif scr_source == "🏆 Category/Index":
        scr_cat_opts = ["⭐ ALL"] + list(INDEX_DATABASE.keys())
        scr_cat = st.selectbox("Category", scr_cat_opts, key="scr_cat")
        if scr_cat == "⭐ ALL":
            for cat_v in INDEX_DATABASE.values():
                scr_symbols += [v for v in cat_v.values() if v != "CUSTOM"]
        else:
            scr_symbols = [v for v in INDEX_DATABASE.get(scr_cat,{}).values() if v != "CUSTOM"]
        scr_symbols = list(dict.fromkeys(scr_symbols))
        st.caption(f"✅ {len(scr_symbols)} stocks")
    else:
        scr_custom = st.text_area("Symbols (comma separated)",
            value="RELIANCE.NS, TCS.NS, INFY.NS, HDFCBANK.NS",
            height=60, label_visibility="collapsed", key="scr_custom")
        scr_symbols = list(dict.fromkeys([s.strip().upper() for s in scr_custom.replace('\n',',').split(',') if s.strip()]))
        st.caption(f"✅ {len(scr_symbols)} symbols")

    st.divider()

    # ─────────────────────────────────────────────
    # FILTER BUILDER
    # ─────────────────────────────────────────────
    st.markdown("#### 🔧 Filters (AND Conditions — sab sahi hone chahiye)")

    # Initialize filters in session state
    if 'scr_filters' not in st.session_state:
        st.session_state.scr_filters = [
            {"enabled": True,  "indicator": "⭐ RSI-EMA System (RSI crossed above EMA9+21+50, all <40)", "condition": "True", "value": 0.0, "period": 14},
            {"enabled": False, "indicator": "RSI",         "condition": "Greater Than", "value": 50.0,  "period": 14},
            {"enabled": False, "indicator": "Supertrend",  "condition": "Bullish",      "value": 0.0,   "period": 7},
            {"enabled": False, "indicator": "CCI",         "condition": "Greater Than", "value": 200.0, "period": 20},
        ]

    FILTER_INDICATORS = [
        "⭐ RSI-EMA System (RSI crossed above EMA9+21+50, all <40)",
        "RSI", "StochRSI %K", "StochRSI %D",
        "CCI", "MFI",
        "Supertrend",
        "Ichimoku Cloud (Close above Cloud)", "Ichimoku Cloud (Close below Cloud)",
        "Fast Stoch %K > Slow Stoch %K", "Fast Stoch %D > Slow Stoch %D",
        "SMA Cross (Fast > Slow)", "EMA Cross (Fast > Slow)",
        "Daily High > N-day High", "Daily Low > N-day Low",
        "Daily Close > N-day Open",
        "RSI Divergence (Oversold)", "RSI Divergence (Overbought)",
        "Price > Upper BB", "Price < Lower BB",
        "Volume > Avg Volume",
        "RSI Crossing Above EMA(9)",
        "RSI Crossing Above EMA(21)",
        "RSI Crossing Above EMA(50)",
        "RSI Above All EMAs (9,21,50)",
        "All EMAs Below 40",
        "RSI Above 40",
        "⭐ RSI-EMA System BEARISH (RSI crossed below EMA9+21+50, all >60)",
        "RSI Crossing Below EMA(9)",
        "RSI Crossing Below EMA(21)",
        "RSI Crossing Below EMA(50)",
        "RSI Below All EMAs (9,21,50)",
        "All EMAs Above 60",
        "RSI Below 60",
    ]

    CONDITION_MAP = {
        "RSI":                                ["Greater Than", "Less Than", "Crossing Above", "Crossing Below"],
        "StochRSI %K":                        ["Greater Than", "Less Than", "Crossing Above", "Crossing Below"],
        "StochRSI %D":                        ["Greater Than", "Less Than"],
        "CCI":                                ["Greater Than", "Less Than"],
        "MFI":                                ["Greater Than", "Less Than"],
        "Supertrend":                         ["Bullish", "Bearish"],
        "Ichimoku Cloud (Close above Cloud)": ["True"],
        "Ichimoku Cloud (Close below Cloud)": ["True"],
        "Fast Stoch %K > Slow Stoch %K":     ["True", "False"],
        "Fast Stoch %D > Slow Stoch %D":     ["True", "False"],
        "SMA Cross (Fast > Slow)":            ["True", "False"],
        "EMA Cross (Fast > Slow)":            ["True", "False"],
        "Daily High > N-day High":            ["True"],
        "Daily Low > N-day Low":              ["True"],
        "Daily Close > N-day Open":           ["True"],
        "RSI Divergence (Oversold)":          ["True"],
        "RSI Divergence (Overbought)":        ["True"],
        "Price > Upper BB":                   ["True"],
        "Price < Lower BB":                   ["True"],
        "Volume > Avg Volume":                ["True"],
        "⭐ RSI-EMA System (RSI crossed above EMA9+21+50, all <40)": ["True"],
        "RSI Crossing Above EMA(9)":          ["True"],
        "RSI Crossing Above EMA(21)":         ["True"],
        "RSI Crossing Above EMA(50)":         ["True"],
        "RSI Above All EMAs (9,21,50)":       ["True"],
        "All EMAs Below 40":                  ["True"],
        "RSI Above 40":                       ["True"],
        "⭐ RSI-EMA System BEARISH (RSI crossed below EMA9+21+50, all >60)": ["True"],
        "RSI Crossing Below EMA(9)":          ["True"],
        "RSI Crossing Below EMA(21)":         ["True"],
        "RSI Crossing Below EMA(50)":         ["True"],
        "RSI Below All EMAs (9,21,50)":       ["True"],
        "All EMAs Above 60":                  ["True"],
        "RSI Below 60":                       ["True"],
    }

    # Render filter rows
    for i, flt in enumerate(st.session_state.scr_filters):
        fc = st.columns([0.5, 2, 2, 1.5, 1, 0.5])
        with fc[0]:
            en = st.checkbox("", value=flt["enabled"], key=f"scr_en_{i}_{flt['indicator']}")
            st.session_state.scr_filters[i]["enabled"] = en
        with fc[1]:
            ind = st.selectbox("Indicator", FILTER_INDICATORS,
                index=FILTER_INDICATORS.index(flt["indicator"]) if flt["indicator"] in FILTER_INDICATORS else 0,
                key=f"scr_ind_{i}", label_visibility="collapsed")
            st.session_state.scr_filters[i]["indicator"] = ind
        with fc[2]:
            cond_opts = CONDITION_MAP.get(ind, ["Greater Than", "Less Than"])
            cond_idx  = cond_opts.index(flt["condition"]) if flt["condition"] in cond_opts else 0
            cond = st.selectbox("Condition", cond_opts, index=cond_idx,
                key=f"scr_cond_{i}", label_visibility="collapsed")
            st.session_state.scr_filters[i]["condition"] = cond
        with fc[3]:
            if cond not in ["True", "False", "Bullish", "Bearish"]:
                val = st.number_input("Value", value=float(flt["value"]),
                    key=f"scr_val_{i}", label_visibility="collapsed")
                st.session_state.scr_filters[i]["value"] = val
            else:
                st.empty()
                val = flt["value"]
        with fc[4]:
            prd = st.number_input("Period", value=int(flt["period"]), min_value=1, max_value=200,
                key=f"scr_prd_{i}", label_visibility="collapsed")
            st.session_state.scr_filters[i]["period"] = prd
        with fc[5]:
            if st.button("❌", key=f"scr_del_{i}") and len(st.session_state.scr_filters) > 1:
                st.session_state.scr_filters.pop(i)
                st.rerun()

    # Add filter button
    af1, af2, _ = st.columns([1,1,3])
    with af1:
        if st.button("➕ Filter Add Karo") and len(st.session_state.scr_filters) < 10:
            st.session_state.scr_filters.append(
                {"enabled": True, "indicator": "RSI", "condition": "Greater Than", "value": 50.0, "period": 14})
            st.rerun()
    with af2:
        active_filters = [f for f in st.session_state.scr_filters if f["enabled"]]
        st.caption(f"{len(active_filters)} active filters")

    st.divider()

    # ─────────────────────────────────────────────
    # RUN SCREENER
    # ─────────────────────────────────────────────
    scr_c1, scr_c2 = st.columns([3,1])
    with scr_c1:
        st.markdown(f"**Screening:** {len(scr_symbols)} stocks × {len(active_filters)} filters")
    with scr_c2:
        run_screener = st.button("🚀 Run Screener", type="primary", use_container_width=True)

    if run_screener:
        if not scr_symbols:
            st.error("❌ Koi symbol nahi!")
        elif not active_filters:
            st.error("❌ Koi active filter nahi!")
        else:
            iv_scr, per_scr = TIMEFRAMES[scr_tf]
            matched = []
            prog_scr = st.progress(0)
            status_scr = st.empty()

            for i_scr, sym_scr in enumerate(scr_symbols):
                status_scr.text(f"⏳ Screening {sym_scr}... ({i_scr+1}/{len(scr_symbols)})")
                df_scr = fetch_data(sym_scr, iv_scr, per_scr)

                if df_scr.empty or len(df_scr) < 60:
                    prog_scr.progress((i_scr+1)/len(scr_symbols))
                    continue

                try:
                    close_a = df_scr['Close'].values.flatten().astype(float)
                    high_a  = df_scr['High'].values.flatten().astype(float)  if 'High' in df_scr.columns else close_a
                    low_a   = df_scr['Low'].values.flatten().astype(float)   if 'Low'  in df_scr.columns else close_a
                    vol_a   = df_scr['Volume'].values.flatten().astype(float) if 'Volume' in df_scr.columns else np.ones(len(close_a))

                    # Pre-compute all indicators once per stock
                    cached = {}
                    def get_ind(name, period):
                        key = f"{name}_{period}"
                        if key in cached: return cached[key]
                        if name == "RSI":
                            cached[key] = compute_rsi(close_a, period); return cached[key]
                        if name in ("StochRSI %K","StochRSI %D"):
                            k,d = compute_stoch_rsi(close_a, period)
                            cached[f"StochRSI %K_{period}"] = k
                            cached[f"StochRSI %D_{period}"] = d
                            return cached[key]
                        if name == "CCI":
                            cached[key] = compute_cci(high_a, low_a, close_a, period); return cached[key]
                        if name == "MFI":
                            cached[key] = compute_mfi(high_a, low_a, close_a, vol_a, period); return cached[key]
                        return np.full(len(close_a), np.nan)

                    # Evaluate all active filters
                    all_pass = True
                    filter_vals = {}

                    for flt in active_filters:
                        ind  = flt["indicator"]
                        cond = flt["condition"]
                        val  = float(flt["value"])
                        prd  = int(flt["period"])
                        passed = False

                        # ── RSI ──────────────────────────────
                        if ind == "RSI":
                            rsi = get_ind("RSI", prd)
                            curr = rsi[-1]; prev = rsi[-2] if len(rsi)>1 else curr
                            filter_vals["RSI"] = round(float(curr),2)
                            if cond == "Greater Than":       passed = curr > val
                            elif cond == "Less Than":        passed = curr < val
                            elif cond == "Crossing Above":   passed = curr > val and prev <= val
                            elif cond == "Crossing Below":   passed = curr < val and prev >= val

                        # ── StochRSI ─────────────────────────
                        elif ind in ("StochRSI %K","StochRSI %D"):
                            arr = get_ind(ind, prd)
                            curr = arr[-1]; prev = arr[-2] if len(arr)>1 else curr
                            filter_vals[ind] = round(float(curr),2)
                            if cond == "Greater Than":     passed = curr > val
                            elif cond == "Less Than":      passed = curr < val
                            elif cond == "Crossing Above": passed = curr > val and prev <= val
                            elif cond == "Crossing Below": passed = curr < val and prev >= val

                        # ── CCI ──────────────────────────────
                        elif ind == "CCI":
                            cci = get_ind("CCI", prd)
                            curr = cci[-1]
                            filter_vals["CCI"] = round(float(curr),2)
                            if cond == "Greater Than": passed = curr > val
                            elif cond == "Less Than":  passed = curr < val

                        # ── MFI ──────────────────────────────
                        elif ind == "MFI":
                            mfi = get_ind("MFI", prd)
                            curr = mfi[-1]
                            filter_vals["MFI"] = round(float(curr),2)
                            if cond == "Greater Than": passed = curr > val
                            elif cond == "Less Than":  passed = curr < val

                        # ── Supertrend ───────────────────────
                        elif ind == "Supertrend":
                            _, direction = compute_supertrend(high_a, low_a, close_a, prd, 2.0)
                            d = direction[-1]
                            filter_vals["Supertrend"] = "Bullish 📈" if d==1 else "Bearish 📉"
                            if cond == "Bullish": passed = d == 1
                            elif cond == "Bearish": passed = d == -1

                        # ── Ichimoku ─────────────────────────
                        elif "Ichimoku" in ind:
                            ten, kij, sen_a, sen_b, _ = compute_ichimoku(high_a, low_a, close_a)
                            cl = close_a[-1]
                            cloud_top = max(sen_a[-1] if not np.isnan(sen_a[-1]) else 0,
                                           sen_b[-1] if not np.isnan(sen_b[-1]) else 0)
                            cloud_bot = min(sen_a[-1] if not np.isnan(sen_a[-1]) else 0,
                                           sen_b[-1] if not np.isnan(sen_b[-1]) else 0)
                            filter_vals["Ichimoku Cloud Top"] = round(cloud_top,2)
                            if "above" in ind: passed = cl > cloud_top
                            else:              passed = cl < cloud_bot

                        # ── Fast/Slow Stochastic ─────────────
                        elif "Stoch" in ind and "RSI" not in ind:
                            fk, fd, sk, sd = compute_fast_slow_stoch(high_a, low_a, close_a, prd)
                            filter_vals["Fast Stoch %K"] = round(float(fk[-1]),2)
                            filter_vals["Slow Stoch %K"] = round(float(sk[-1]),2)
                            if "Fast Stoch %K" in ind: passed = fk[-1] > sk[-1]
                            else:                      passed = fd[-1] > sd[-1]

                        # ── SMA Cross ────────────────────────
                        elif "SMA Cross" in ind:
                            fast_p = max(1, prd//2)
                            sma_f = compute_sma(close_a, fast_p)
                            sma_s = compute_sma(close_a, prd)
                            filter_vals[f"SMA{fast_p}"] = round(float(sma_f[-1]),2)
                            filter_vals[f"SMA{prd}"] = round(float(sma_s[-1]),2)
                            passed = sma_f[-1] > sma_s[-1]

                        # ── EMA Cross ────────────────────────
                        elif "EMA Cross" in ind:
                            fast_p = max(1, prd//2)
                            ema_f = compute_ema(close_a, fast_p)
                            ema_s = compute_ema(close_a, prd)
                            filter_vals[f"EMA{fast_p}"] = round(float(ema_f[-1]),2)
                            filter_vals[f"EMA{prd}"] = round(float(ema_s[-1]),2)
                            passed = ema_f[-1] > ema_s[-1]

                        # ── Daily High > N-day High ───────────
                        elif "Daily High" in ind:
                            hi_s = pd.Series(high_a)
                            passed = high_a[-1] > hi_s.iloc[-prd-1:-1].max() if len(high_a) > prd else False
                            filter_vals["N-day High"] = round(float(hi_s.iloc[-prd-1:-1].max()),2) if len(high_a)>prd else 0

                        # ── Daily Low > N-day Low ─────────────
                        elif "Daily Low" in ind:
                            lo_s = pd.Series(low_a)
                            passed = low_a[-1] > lo_s.iloc[-prd-1:-1].min() if len(low_a) > prd else False
                            filter_vals["N-day Low"] = round(float(lo_s.iloc[-prd-1:-1].min()),2) if len(low_a)>prd else 0

                        # ── Daily Close > N-day Open ──────────
                        elif "Daily Close" in ind and "Open" in ind:
                            open_a = df_scr['Open'].values.flatten().astype(float) if 'Open' in df_scr.columns else close_a
                            passed = close_a[-1] > open_a[-prd] if len(open_a) > prd else False

                        # ── Bollinger ─────────────────────────
                        elif "BB" in ind:
                            _, bb_u, bb_l = compute_bollinger_bands(close_a, prd, 2.0)
                            filter_vals["BB Upper"] = round(float(bb_u[-1]),2)
                            filter_vals["BB Lower"] = round(float(bb_l[-1]),2)
                            if "Upper" in ind: passed = close_a[-1] > bb_u[-1]
                            else:              passed = close_a[-1] < bb_l[-1]

                        # ── Volume > Avg Volume ───────────────
                        elif "Volume" in ind:
                            avg_vol = np.nanmean(vol_a[-prd:])
                            filter_vals["Volume"] = int(vol_a[-1])
                            filter_vals["Avg Vol"] = int(avg_vol)
                            passed = vol_a[-1] > avg_vol

                        # ── RSI Divergence ────────────────────
                        elif "RSI Divergence" in ind:
                            rsi = compute_rsi(close_a, prd)
                            if "Oversold" in ind:   passed = rsi[-1] < 30
                            else:                   passed = rsi[-1] > 70
                            filter_vals["RSI (Div)"] = round(float(rsi[-1]),2)

                        # ── RSI-EMA System (Full) ─────────────
                        elif "RSI-EMA System" in ind:
                            rsi    = compute_rsi(close_a, prd)
                            ema9   = compute_ema(rsi, 9)
                            ema21  = compute_ema(rsi, 21)
                            ema50  = compute_ema(rsi, 50)
                            rsi_curr  = rsi[-1];  rsi_prev  = rsi[-2]
                            e9_curr   = ema9[-1]; e9_prev   = ema9[-2]
                            e21_curr  = ema21[-1];e21_prev  = ema21[-2]
                            e50_curr  = ema50[-1];e50_prev  = ema50[-2]
                            # All 3 crossings happened recently (within last 5 bars)
                            cross9  = any(rsi[j] > ema9[j]  and rsi[j-1] <= ema9[j-1]  for j in range(max(1,len(rsi)-5), len(rsi)))
                            cross21 = any(rsi[j] > ema21[j] and rsi[j-1] <= ema21[j-1] for j in range(max(1,len(rsi)-5), len(rsi)))
                            cross50 = any(rsi[j] > ema50[j] and rsi[j-1] <= ema50[j-1] for j in range(max(1,len(rsi)-5), len(rsi)))
                            all_ema_below40 = e9_curr < 40 and e21_curr < 40 and e50_curr < 40
                            rsi_above40     = rsi_curr > 40
                            passed = cross9 and cross21 and cross50 and all_ema_below40 and rsi_above40
                            filter_vals["RSI(14)"]  = round(float(rsi_curr),2)
                            filter_vals["EMA9"]     = round(float(e9_curr),2)
                            filter_vals["EMA21"]    = round(float(e21_curr),2)
                            filter_vals["EMA50"]    = round(float(e50_curr),2)
                            filter_vals["All EMAs<40"] = "✅" if all_ema_below40 else "❌"
                            filter_vals["RSI>40"]   = "✅" if rsi_above40 else "❌"

                        # ── RSI Crossing Above EMA(9) ──────────
                        elif ind == "RSI Crossing Above EMA(9)":
                            rsi  = compute_rsi(close_a, prd)
                            ema9 = compute_ema(rsi, 9)
                            passed = any(rsi[j] > ema9[j] and rsi[j-1] <= ema9[j-1]
                                         for j in range(max(1,len(rsi)-5), len(rsi)))
                            filter_vals["RSI"]  = round(float(rsi[-1]),2)
                            filter_vals["EMA9"] = round(float(ema9[-1]),2)

                        # ── RSI Crossing Above EMA(21) ─────────
                        elif ind == "RSI Crossing Above EMA(21)":
                            rsi   = compute_rsi(close_a, prd)
                            ema21 = compute_ema(rsi, 21)
                            passed = any(rsi[j] > ema21[j] and rsi[j-1] <= ema21[j-1]
                                         for j in range(max(1,len(rsi)-5), len(rsi)))
                            filter_vals["RSI"]   = round(float(rsi[-1]),2)
                            filter_vals["EMA21"] = round(float(ema21[-1]),2)

                        # ── RSI Crossing Above EMA(50) ─────────
                        elif ind == "RSI Crossing Above EMA(50)":
                            rsi   = compute_rsi(close_a, prd)
                            ema50 = compute_ema(rsi, 50)
                            passed = any(rsi[j] > ema50[j] and rsi[j-1] <= ema50[j-1]
                                         for j in range(max(1,len(rsi)-5), len(rsi)))
                            filter_vals["RSI"]   = round(float(rsi[-1]),2)
                            filter_vals["EMA50"] = round(float(ema50[-1]),2)

                        # ── RSI Above All EMAs ─────────────────
                        elif ind == "RSI Above All EMAs (9,21,50)":
                            rsi   = compute_rsi(close_a, prd)
                            ema9  = compute_ema(rsi, 9)
                            ema21 = compute_ema(rsi, 21)
                            ema50 = compute_ema(rsi, 50)
                            passed = rsi[-1] > ema9[-1] and rsi[-1] > ema21[-1] and rsi[-1] > ema50[-1]
                            filter_vals["RSI"]   = round(float(rsi[-1]),2)
                            filter_vals["EMA9"]  = round(float(ema9[-1]),2)
                            filter_vals["EMA21"] = round(float(ema21[-1]),2)
                            filter_vals["EMA50"] = round(float(ema50[-1]),2)

                        # ── All EMAs Below 40 ─────────────────
                        elif ind == "All EMAs Below 40":
                            rsi   = compute_rsi(close_a, prd)
                            ema9  = compute_ema(rsi, 9)
                            ema21 = compute_ema(rsi, 21)
                            ema50 = compute_ema(rsi, 50)
                            passed = ema9[-1] < 40 and ema21[-1] < 40 and ema50[-1] < 40
                            filter_vals["EMA9"]  = round(float(ema9[-1]),2)
                            filter_vals["EMA21"] = round(float(ema21[-1]),2)
                            filter_vals["EMA50"] = round(float(ema50[-1]),2)

                        # ── RSI Above 40 ──────────────────────
                        elif ind == "RSI Above 40":
                            rsi = compute_rsi(close_a, prd)
                            passed = rsi[-1] > 40
                            filter_vals["RSI"] = round(float(rsi[-1]),2)

                        # ══════════════════════════════════════
                        # BEARISH RSI-EMA SYSTEM (mirror of bullish)
                        # ══════════════════════════════════════

                        # ── RSI-EMA Bearish System (Full) ─────
                        elif "RSI-EMA System BEARISH" in ind:
                            rsi   = compute_rsi(close_a, prd)
                            ema9  = compute_ema(rsi, 9)
                            ema21 = compute_ema(rsi, 21)
                            ema50 = compute_ema(rsi, 50)
                            rsi_curr = rsi[-1]
                            e9_curr  = ema9[-1]
                            e21_curr = ema21[-1]
                            e50_curr = ema50[-1]
                            # All 3 crossings happened recently (within last 5 bars) — RSI crossed BELOW EMAs
                            cross9  = any(rsi[j] < ema9[j]  and rsi[j-1] >= ema9[j-1]  for j in range(max(1,len(rsi)-5), len(rsi)))
                            cross21 = any(rsi[j] < ema21[j] and rsi[j-1] >= ema21[j-1] for j in range(max(1,len(rsi)-5), len(rsi)))
                            cross50 = any(rsi[j] < ema50[j] and rsi[j-1] >= ema50[j-1] for j in range(max(1,len(rsi)-5), len(rsi)))
                            all_ema_above60 = e9_curr > 60 and e21_curr > 60 and e50_curr > 60
                            rsi_below60     = rsi_curr < 60
                            passed = cross9 and cross21 and cross50 and all_ema_above60 and rsi_below60
                            filter_vals["RSI(14)"]     = round(float(rsi_curr),2)
                            filter_vals["EMA9"]        = round(float(e9_curr),2)
                            filter_vals["EMA21"]       = round(float(e21_curr),2)
                            filter_vals["EMA50"]       = round(float(e50_curr),2)
                            filter_vals["All EMAs>60"] = "✅" if all_ema_above60 else "❌"
                            filter_vals["RSI<60"]      = "✅" if rsi_below60 else "❌"

                        # ── RSI Crossing Below EMA(9) ──────────
                        elif ind == "RSI Crossing Below EMA(9)":
                            rsi  = compute_rsi(close_a, prd)
                            ema9 = compute_ema(rsi, 9)
                            passed = any(rsi[j] < ema9[j] and rsi[j-1] >= ema9[j-1]
                                         for j in range(max(1,len(rsi)-5), len(rsi)))
                            filter_vals["RSI"]  = round(float(rsi[-1]),2)
                            filter_vals["EMA9"] = round(float(ema9[-1]),2)

                        # ── RSI Crossing Below EMA(21) ─────────
                        elif ind == "RSI Crossing Below EMA(21)":
                            rsi   = compute_rsi(close_a, prd)
                            ema21 = compute_ema(rsi, 21)
                            passed = any(rsi[j] < ema21[j] and rsi[j-1] >= ema21[j-1]
                                         for j in range(max(1,len(rsi)-5), len(rsi)))
                            filter_vals["RSI"]   = round(float(rsi[-1]),2)
                            filter_vals["EMA21"] = round(float(ema21[-1]),2)

                        # ── RSI Crossing Below EMA(50) ─────────
                        elif ind == "RSI Crossing Below EMA(50)":
                            rsi   = compute_rsi(close_a, prd)
                            ema50 = compute_ema(rsi, 50)
                            passed = any(rsi[j] < ema50[j] and rsi[j-1] >= ema50[j-1]
                                         for j in range(max(1,len(rsi)-5), len(rsi)))
                            filter_vals["RSI"]   = round(float(rsi[-1]),2)
                            filter_vals["EMA50"] = round(float(ema50[-1]),2)

                        # ── RSI Below All EMAs ─────────────────
                        elif ind == "RSI Below All EMAs (9,21,50)":
                            rsi   = compute_rsi(close_a, prd)
                            ema9  = compute_ema(rsi, 9)
                            ema21 = compute_ema(rsi, 21)
                            ema50 = compute_ema(rsi, 50)
                            passed = rsi[-1] < ema9[-1] and rsi[-1] < ema21[-1] and rsi[-1] < ema50[-1]
                            filter_vals["RSI"]   = round(float(rsi[-1]),2)
                            filter_vals["EMA9"]  = round(float(ema9[-1]),2)
                            filter_vals["EMA21"] = round(float(ema21[-1]),2)
                            filter_vals["EMA50"] = round(float(ema50[-1]),2)

                        # ── All EMAs Above 60 ──────────────────
                        elif ind == "All EMAs Above 60":
                            rsi   = compute_rsi(close_a, prd)
                            ema9  = compute_ema(rsi, 9)
                            ema21 = compute_ema(rsi, 21)
                            ema50 = compute_ema(rsi, 50)
                            passed = ema9[-1] > 60 and ema21[-1] > 60 and ema50[-1] > 60
                            filter_vals["EMA9"]  = round(float(ema9[-1]),2)
                            filter_vals["EMA21"] = round(float(ema21[-1]),2)
                            filter_vals["EMA50"] = round(float(ema50[-1]),2)

                        # ── RSI Below 60 ──────────────────────
                        elif ind == "RSI Below 60":
                            rsi = compute_rsi(close_a, prd)
                            passed = rsi[-1] < 60
                            filter_vals["RSI"] = round(float(rsi[-1]),2)

                        if not passed:
                            all_pass = False
                            break

                    if all_pass:
                        row = {"Symbol": sym_scr, "Price": f"₹{close_a[-1]:,.2f}"}
                        row.update({k: v for k, v in filter_vals.items()})
                        row["Time"] = str(df_scr.index[-1])[:16]
                        matched.append(row)

                except Exception as e_scr:
                    pass  # Skip stocks that fail

                prog_scr.progress((i_scr+1)/len(scr_symbols))

            status_scr.empty()
            prog_scr.empty()

            # ── Results ──────────────────────────
            st.markdown(f"#### 🎯 {len(matched)} stocks matched all filters (out of {len(scr_symbols)} scanned)")

            if matched:
                # Summary cards
                m1, m2, m3 = st.columns(3)
                m1.markdown(f'<div class="metric-card"><div class="label">Total Scanned</div><div class="value">{len(scr_symbols)}</div></div>', unsafe_allow_html=True)
                m2.markdown(f'<div class="metric-card"><div class="label">✅ Matched</div><div class="value green">{len(matched)}</div></div>', unsafe_allow_html=True)
                m3.markdown(f'<div class="metric-card"><div class="label">❌ Filtered Out</div><div class="value red">{len(scr_symbols)-len(matched)}</div></div>', unsafe_allow_html=True)
                st.write("")

                res_scr = pd.DataFrame(matched)
                st.dataframe(res_scr, use_container_width=True, height=min(500, len(matched)*50+60))

                # Action buttons
                btn1, btn2, _ = st.columns([1,1,2])
                with btn1:
                    st.download_button("⬇ CSV Download", res_scr.to_csv(index=False),
                        f"screener_{scr_tf}_{pd.Timestamp.now().strftime('%Y%m%d_%H%M')}.csv", "text/csv")
                with btn2:
                    if st.button("📱 Telegram Bhejo", key="scr_tg_btn"):
                        if 'tg_token' in st.session_state and st.session_state.tg_token:
                            syms = [r["Symbol"] for r in matched]
                            msg = f"📡 <b>Technical Screener</b>\n━━━━━━━━━━━━━\n"
                            msg += f"⏱ TF: {scr_tf} | Matched: {len(matched)}/{len(scr_symbols)}\n\n"
                            msg += "✅ <b>Stocks:</b>\n" + "\n".join([f"• {s}" for s in syms[:30]])
                            try:
                                r = requests.post(
                                    f"https://api.telegram.org/bot{st.session_state.tg_token}/sendMessage",
                                    json={"chat_id": st.session_state.tg_chat_id,
                                          "text": msg, "parse_mode": "HTML"}, timeout=10)
                                if r.status_code == 200: st.success("📱 Telegram pe bheja!")
                                else: st.error(f"❌ {r.text[:100]}")
                            except Exception as e_tg: st.error(f"❌ {e_tg}")
                        else:
                            st.warning("Alert tab mein Telegram setup karo!")

                # Add to watchlist option
                st.markdown("---")
                if st.session_state.get('watchlists'):
                    wl_add_c1, wl_add_c2 = st.columns([2,1])
                    with wl_add_c1:
                        target_wl = st.selectbox("📋 Watchlist mein add karo",
                            list(st.session_state.watchlists.keys()), key="scr_add_wl")
                    with wl_add_c2:
                        st.write("")
                        if st.button("➕ Add to Watchlist"):
                            added = 0
                            for r in matched:
                                s = r["Symbol"]
                                if s not in st.session_state.watchlists[target_wl]:
                                    st.session_state.watchlists[target_wl].append(s)
                                    added += 1
                            st.success(f"✅ {added} stocks added to '{target_wl}'!")
            else:
                st.info("⚪ Koi stock sab filters pass nahi kar paya. Filters loosens karo ya alag timeframe try karo.")

# ══════════════════════════════════════════════
# TAB 7: HELP
# ══════════════════════════════════════════════
# ══════════════════════════════════════════════
with tab_help:
    st.markdown("""
    ### 📖 How to Use

    #### Installation
    ```bash
    pip install streamlit yfinance pandas numpy plotly requests
    streamlit run nadaraya_watson_app.py
    ```

    #### Symbol Format
    | Market | Example |
    |--------|---------|
    | NSE India | `RELIANCE.NS`, `NIFTY50=F` |
    | BSE India | `RELIANCE.BO` |
    | US Stocks | `AAPL`, `TSLA` |
    | Crypto | `BTC-USD`, `ETH-USD` |
    | Forex | `USDINR=X` |

    #### NW Parameters
    - **Bandwidth (h)** — smoothing level. 8 = default (same as Pine Script)
    - **Multiplier** — envelope width. 3.0 = default
    - **Lookback** — how many bars back (max 499, same as Pine Script)

    #### Alert Logic
    | Signal | Condition |
    |--------|-----------|
    | ✅ BUY | Candle bounces back above Lower Band (crossover lower) |
    | 🔴 SELL | Candle touches or crosses Upper Band (crossover upper) |

    #### Timeframes
    `1m, 3m, 5m, 15m, 30m, 1H, 2H, 4H, 1D, 1W` — all supported

    #### Telegram Alerts
    1. Create a Telegram bot via @BotFather
    2. Get your chat ID
    3. Paste this as webhook URL:
       `https://api.telegram.org/bot<TOKEN>/sendMessage?chat_id=<CHAT_ID>&text=`

    ---
    *Converted from LuxAlgo Pine Script © — NW Envelope by LuxAlgo (CC BY-NC-SA 4.0)*
    """)

# ─────────────────────────────────────────────────────────────────
# AUTO-REFRESH (if enabled)
# ─────────────────────────────────────────────────────────────────
if auto_refresh:
    time.sleep(60)
    st.rerun()
