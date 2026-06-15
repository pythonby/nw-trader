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

# ─────────────────────────────────────────────────────────────────
# SIGNAL DETECTION
# ─────────────────────────────────────────────────────────────────

def detect_signals(df: pd.DataFrame):
    """
    Returns DataFrame with signal column:
      'BUY'  — price crosses UNDER lower band (bounce up expected)
      'SELL' — price crosses OVER  upper band (reversal down expected)
    """
    signals = []
    close  = df['Close'].values
    upper  = df['upper'].values
    lower  = df['lower'].values

    for i in range(1, len(df)):
        sig = ''
        # Touch/cross lower → BUY alert
        if close[i] <= lower[i] and close[i - 1] > lower[i - 1]:
            sig = 'SELL_CROSS_LOWER'   # crossunder lower = bearish breakout
        elif close[i] < lower[i] and close[i - 1] >= lower[i - 1]:
            sig = 'SELL_CROSS_LOWER'
        # bounce back above lower from below → BUY
        if close[i] > lower[i] and close[i - 1] <= lower[i - 1]:
            sig = 'BUY'
        # Touch/cross upper → SELL alert
        if close[i] >= upper[i] and close[i - 1] < upper[i - 1]:
            sig = 'SELL'
        elif close[i] > upper[i] and close[i - 1] <= upper[i - 1]:
            sig = 'SELL'
        signals.append(sig)

    signals.insert(0, '')
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

# ─────────────────────────────────────────────────────────────────
# CHART BUILDER
# ─────────────────────────────────────────────────────────────────

def build_chart(df: pd.DataFrame, symbol: str, tf: str) -> go.Figure:
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

    # NWE midline (dashed blue like TradingView)
    if 'nwe' in df.columns:
        fig.add_trace(go.Scatter(
            x=df.index, y=df['nwe'],
            line=dict(color='#74c0fc', width=1.5, dash='dash'),
            name='NW Estimate',
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

    SYMBOL_LIST = {
        "── Indian Indices ──":   None,
        "📊 Nifty 50":            "^NSEI",
        "📊 Nifty Bank":          "^NSEBANK",
        "📊 Nifty IT":            "^CNXIT",
        "📊 Nifty Midcap 100":    "^NSEMDCP100",
        "📊 Nifty Auto":          "^CNXAUTO",
        "📊 Nifty FMCG":          "^CNXFMCG",
        "📊 Nifty Pharma":        "^CNXPHARMA",
        "📊 Nifty Energy":        "^CNXENERGY",
        "📊 Nifty Metal":         "^CNXMETAL",
        "📊 Nifty Realty":        "^CNXREALTY",
        "📊 Sensex (BSE)":        "^BSESN",
        "📊 India VIX":           "^INDIAVIX",
        "── F&O Futures ──":      None,
        "📈 Nifty Futures":       "NIFTY50=F",
        "📈 BankNifty Futures":   "BANKNIFTY=F",
        "── Large Cap Stocks ──": None,
        "🏢 Reliance":            "RELIANCE.NS",
        "🏢 TCS":                 "TCS.NS",
        "🏢 Infosys":             "INFY.NS",
        "🏢 HDFC Bank":           "HDFCBANK.NS",
        "🏢 ICICI Bank":          "ICICIBANK.NS",
        "🏢 Axis Bank":           "AXISBANK.NS",
        "🏢 SBI":                 "SBIN.NS",
        "🏢 Wipro":               "WIPRO.NS",
        "🏢 HCL Tech":            "HCLTECH.NS",
        "🏢 Bajaj Finance":       "BAJFINANCE.NS",
        "🏢 Kotak Bank":          "KOTAKBANK.NS",
        "🏢 L&T":                 "LT.NS",
        "🏢 Asian Paints":        "ASIANPAINT.NS",
        "🏢 Maruti":              "MARUTI.NS",
        "🏢 Titan":               "TITAN.NS",
        "🏢 Sun Pharma":          "SUNPHARMA.NS",
        "🏢 Tata Motors":         "TATAMOTORS.NS",
        "🏢 Tata Steel":          "TATASTEEL.NS",
        "🏢 ITC":                 "ITC.NS",
        "🏢 HUL":                 "HINDUNILVR.NS",
        "🏢 ONGC":                "ONGC.NS",
        "🏢 Coal India":          "COALINDIA.NS",
        "🏢 NTPC":                "NTPC.NS",
        "🏢 Power Grid":          "POWERGRID.NS",
        "🏢 Adani Enterprises":   "ADANIENT.NS",
        "🏢 Adani Ports":         "ADANIPORTS.NS",
        "🏢 M&M":                 "M&M.NS",
        "🏢 Hero MotoCorp":       "HEROMOTOCO.NS",
        "🏢 Eicher Motors":       "EICHERMOT.NS",
        "🏢 IndusInd Bank":       "INDUSINDBK.NS",
        "🏢 Dr Reddy's":          "DRREDDY.NS",
        "🏢 Cipla":               "CIPLA.NS",
        "🏢 Nestle India":        "NESTLEIND.NS",
        "🏢 UltraTech Cement":    "ULTRACEMCO.NS",
        "── Crypto ──":           None,
        "₿ Bitcoin (BTC)":        "BTC-USD",
        "₿ Ethereum (ETH)":       "ETH-USD",
        "── Custom ──":           None,
        "✏️ Custom Symbol...":    "CUSTOM",
    }

    valid_labels = [k for k, v in SYMBOL_LIST.items() if v is not None]
    selected_label = st.selectbox(
        "📌 Symbol / Index",
        valid_labels,
        index=0,
        help="Nifty indices, stocks ya custom symbol choose karo"
    )
    selected_val = SYMBOL_LIST[selected_label]

    if selected_val == "CUSTOM":
        symbol = st.text_input("Custom Symbol likhein", value="RELIANCE.NS",
                               help="NSE: .NS | BSE: .BO | US: AAPL | Crypto: BTC-USD").upper()
    else:
        symbol = selected_val
        st.caption(f"Yahoo ticker: `{symbol}`")

    st.markdown("### NW Parameters")
    bandwidth = st.slider("Bandwidth (h)", 1.0, 20.0, 8.0, 0.5,
                          help="Controls smoothing — higher = smoother")
    mult      = st.slider("Multiplier (envelope width)", 0.5, 6.0, 3.0, 0.1)
    lookback  = st.slider("Lookback bars", 50, 499, 200, 10)

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
    <h1>📈 Nadaraya-Watson Envelope</h1>
    <p>LuxAlgo strategy | h={bandwidth} | mult={mult} | {tf_selected} | {symbol}</p>
  </div>
</div>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────
# TABS
# ─────────────────────────────────────────────────────────────────

tab_chart, tab_backtest, tab_scanner, tab_alerts, tab_watchlist, tab_help = st.tabs([
    "📊 Chart", "🧪 Backtest", "🔍 Live Scanner", "🔔 Alerts", "📋 Watchlist", "📖 Help"
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
        nwe_vals, upper_vals, lower_vals = compute_nwe_endpoint(prices, bandwidth, mult, lookback)
        df['nwe']   = nwe_vals
        df['upper'] = upper_vals
        df['lower'] = lower_vals
        df = detect_signals(df)

        fig = build_chart(df, symbol, tf_chart)
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

    # ── Period + Timeframe Selection ─────────────
    BACKTEST_PERIODS = {
        "1 Month":   30,
        "3 Months":  90,
        "6 Months":  180,
        "9 Months":  270,
        "1 Year":    365,
        "2 Years":   730,
        "3 Years":   1095,
        "5 Years":   1825,
        "Max Data":  0,   # 0 = use full data
    }

    bt_c1, bt_c2, bt_c3 = st.columns([2, 2, 1])
    with bt_c1:
        bt_tf = st.selectbox("⏱ Timeframe", list(TIMEFRAMES.keys()), index=6, key="bt_tf")
    with bt_c2:
        bt_period_label = st.selectbox(
            "📅 Backtest Period",
            list(BACKTEST_PERIODS.keys()),
            index=2,   # default: 6 Months
            key="bt_period"
        )
    with bt_c3:
        st.write("")
        st.write("")
        run_bt = st.button("▶ Run", use_container_width=True, type="primary")

    # Period info
    period_days = BACKTEST_PERIODS[bt_period_label]
    if period_days > 0:
        from datetime import timedelta
        end_date   = datetime.now()
        start_date = end_date - timedelta(days=period_days)
        st.caption(f"📅 Period: **{start_date.strftime('%d %b %Y')}** → **{end_date.strftime('%d %b %Y')}** ({bt_period_label})")
    else:
        st.caption("📅 Period: **Maximum available data**")

    if run_bt:
        iv_bt, period_bt = TIMEFRAMES[bt_tf]
        with st.spinner(f"Running backtest — {bt_period_label} — {symbol}..."):
            df_bt = fetch_data(symbol, iv_bt, period_bt)
            if df_bt.empty:
                st.error("❌ No data. Symbol ya timeframe check karo.")
            else:
                # ── Filter by selected period ──
                if period_days > 0:
                    cutoff = pd.Timestamp.now(tz=df_bt.index.tz) - pd.Timedelta(days=period_days)
                    df_bt = df_bt[df_bt.index >= cutoff]

                if len(df_bt) < 50:
                    st.warning(f"⚠️ Sirf {len(df_bt)} bars mile — is period ke liye data kam hai. Bada period ya alag timeframe try karo.")
                else:
                    prices_bt = df_bt['Close'].values.flatten().astype(float)
                    lb_bt = min(lookback, len(prices_bt)-1)
                    nwe_bt, up_bt, lo_bt = compute_nwe_endpoint(prices_bt, bandwidth, mult, lb_bt)
                    df_bt['nwe']   = nwe_bt
                    df_bt['upper'] = up_bt
                    df_bt['lower'] = lo_bt
                    df_bt = detect_signals(df_bt)
                    trades_df, stats, equity_curve = run_backtest(df_bt, float(capital))

                    # ── Period Summary Banner ──
                    st.markdown(f"""
                    <div style='background:#1c2128; border:1px solid #30363d; border-radius:8px;
                                padding:10px 18px; margin-bottom:12px; color:#8b949e; font-size:0.85rem;'>
                        📊 <b style='color:#e6edf3'>{symbol}</b> &nbsp;|&nbsp;
                        ⏱ <b style='color:#58a6ff'>{bt_tf}</b> &nbsp;|&nbsp;
                        📅 <b style='color:#3fb950'>{bt_period_label}</b> &nbsp;|&nbsp;
                        📈 <b style='color:#e6edf3'>{len(df_bt)} bars</b>
                    </div>
                    """, unsafe_allow_html=True)

                    if stats:
                        st.markdown("#### 📊 Performance Summary")
                        cols = st.columns(4)
                        stat_items = list(stats.items())
                        for idx, (k, v) in enumerate(stat_items):
                            color = ""
                            try:
                                num = float(str(v).replace('%','').replace('₹','').replace(',','').strip())
                                if ('PnL' in k or 'Profit' in k or 'Capital' in k or 'Rate' in k):
                                    color = "green" if num > 0 else "red"
                            except:
                                pass
                            cols[idx % 4].markdown(
                                f'<div class="metric-card"><div class="label">{k}</div><div class="value {color}">{v}</div></div>',
                                unsafe_allow_html=True
                            )

                        st.markdown("#### 📈 Equity Curve")
                        eq_fig = go.Figure()
                        eq_fig.add_trace(go.Scatter(
                            y=equity_curve, mode='lines',
                            line=dict(color='#58a6ff', width=2),
                            fill='tozeroy', fillcolor='rgba(88,166,255,0.08)',
                            name='Equity'
                        ))
                        eq_fig.add_hline(y=float(capital), line_dash='dash',
                                         line_color='#8b949e', opacity=0.5,
                                         annotation_text="Initial Capital",
                                         annotation_font_color="#8b949e")
                        # Profit zone green, loss zone red
                        final_eq = equity_curve[-1] if equity_curve else float(capital)
                        eq_color = '#3fb950' if final_eq >= float(capital) else '#f85149'
                        eq_fig.update_traces(line_color=eq_color, selector=dict(name='Equity'))
                        eq_fig.update_layout(
                            template='plotly_dark', paper_bgcolor='#0d1117',
                            plot_bgcolor='#0d1117', height=300,
                            margin=dict(l=10,r=10,t=20,b=10),
                            showlegend=False,
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
                                ),
                                use_container_width=True, height=300
                            )
                            csv = trades_df.to_csv(index=False)
                            st.download_button("⬇ Download Trade Log CSV", csv,
                                               f"{symbol}_{bt_period_label}_trades.csv", "text/csv")
                    else:
                        st.warning(f"⚠️ {bt_period_label} mein koi completed trade nahi mila. Alag period ya timeframe try karo.")

# ══════════════════════════════════════════════
# TAB 3: LIVE SCANNER
# ══════════════════════════════════════════════
with tab_scanner:
    st.markdown("### 🔍 Live Multi-Symbol Scanner")

    # ── Source Selection ─────────────────────────
    scan_source = st.radio(
        "📂 Scan Kahan Se Karna Hai?",
        ["📋 Meri Watchlist Se", "✏️ Custom Symbols", "📊 Default List"],
        horizontal=True,
        key="scan_source"
    )

    scan_symbols = []

    if scan_source == "📋 Meri Watchlist Se":
        # Watchlist init check
        if 'watchlists' not in st.session_state or not st.session_state.watchlists:
            st.warning("⚠️ Koi watchlist nahi hai! Pehle **Watchlist tab** mein banao.")
        else:
            wl_names = list(st.session_state.watchlists.keys())
            sel_wl_sc = st.selectbox(
                "📂 Watchlist Choose Karo",
                wl_names,
                key="scanner_wl_select"
            )
            wl_stocks = st.session_state.watchlists.get(sel_wl_sc, [])
            if wl_stocks:
                st.success(f"✅ **{sel_wl_sc}** — {len(wl_stocks)} stocks: {', '.join(wl_stocks[:6])}{'...' if len(wl_stocks)>6 else ''}")
                scan_symbols = wl_stocks.copy()
                # Option to add current selected symbol too
                if symbol not in scan_symbols:
                    if st.checkbox(f"➕ '{symbol}' bhi add karo", value=False):
                        scan_symbols = [symbol] + scan_symbols
            else:
                st.warning(f"'{sel_wl_sc}' watchlist mein koi stock nahi! Watchlist tab mein add karo.")

    elif scan_source == "✏️ Custom Symbols":
        st.markdown("**Symbols likhein** (comma ya newline se alag karo):")
        custom_input = st.text_area(
            "Custom symbols",
            value="RELIANCE.NS, TCS.NS, INFY.NS, HDFCBANK.NS, ICICIBANK.NS",
            height=100,
            label_visibility="collapsed",
            placeholder="RELIANCE.NS, TCS.NS, ^NSEI, BTC-USD"
        )
        raw_syms = [s.strip().upper() for s in custom_input.replace('\n', ',').split(',') if s.strip()]
        scan_symbols = list(dict.fromkeys(raw_syms))
        if scan_symbols:
            st.caption(f"📋 {len(scan_symbols)} symbols: {', '.join(scan_symbols[:8])}{'...' if len(scan_symbols)>8 else ''}")

    else:  # Default List
        default_syms = [s.strip().upper() for s in scan_symbols_raw.strip().split('\n') if s.strip()]
        if symbol not in default_syms:
            default_syms = [symbol] + default_syms
        scan_symbols = list(dict.fromkeys(default_syms))
        st.caption(f"📋 Default {len(scan_symbols)} symbols")

    st.divider()

    # ── Scan Controls ────────────────────────────
    sc_c1, sc_c2, sc_c3 = st.columns([2, 1, 1])
    with sc_c1:
        scan_tf_tab = st.selectbox("⏱ Timeframe", list(TIMEFRAMES.keys()), index=5, key='scan_tf_tab')
    with sc_c2:
        st.write("")
        st.write("")
        run_scan = st.button("🚀 Scan Now", use_container_width=True, type="primary")
    with sc_c3:
        st.write("")
        st.write("")
        st.caption(f"Total: **{len(scan_symbols)}** symbols")

    if run_scan:
        if not scan_symbols:
            st.error("❌ Koi symbol nahi! Watchlist banao ya custom symbols likhein.")
        else:
            iv_sc, per_sc = TIMEFRAMES[scan_tf_tab]
            results = []
            prog = st.progress(0)
            status_text = st.empty()

            for i, sym in enumerate(scan_symbols):
                status_text.text(f"⏳ Scanning {sym}... ({i+1}/{len(scan_symbols)})")
                df_sc = fetch_data(sym, iv_sc, per_sc)
                if not df_sc.empty and len(df_sc) > 50:
                    prices_sc = df_sc['Close'].values.flatten().astype(float)
                    lb_sc = min(lookback, len(prices_sc)-1)
                    _, up_sc, lo_sc = compute_nwe_endpoint(prices_sc, bandwidth, mult, lb_sc)
                    df_sc['upper'] = up_sc
                    df_sc['lower'] = lo_sc
                    df_sc = detect_signals(df_sc)
                    last_row   = df_sc.iloc[-1]
                    close_p    = float(last_row['Close'])
                    up_p       = float(last_row['upper']) if not np.isnan(last_row['upper']) else 0
                    lo_p       = float(last_row['lower']) if not np.isnan(last_row['lower']) else 0
                    sig        = last_row['signal'] if last_row['signal'] else 'NEUTRAL'
                    dist_upper = round((up_p - close_p) / close_p * 100, 2) if up_p else 0
                    dist_lower = round((close_p - lo_p) / close_p * 100, 2) if lo_p else 0
                    results.append({
                        'Symbol':       sym,
                        'Price':        f"₹{close_p:,.2f}",
                        'Upper Band':   f"₹{up_p:,.2f}",
                        'Lower Band':   f"₹{lo_p:,.2f}",
                        'Dist Upper %': f"{dist_upper}%",
                        'Dist Lower %': f"{dist_lower}%",
                        'Signal':       sig,
                        'Time':         str(df_sc.index[-1])[:16],
                    })
                prog.progress((i + 1) / len(scan_symbols))

            status_text.empty()
            prog.empty()

            if results:
                res_df = pd.DataFrame(results)

                # Summary boxes
                buy_count  = len(res_df[res_df['Signal']=='BUY'])
                sell_count = len(res_df[res_df['Signal']=='SELL'])
                neu_count  = len(res_df[res_df['Signal']=='NEUTRAL'])
                s1, s2, s3, s4 = st.columns(4)
                s1.markdown(f'<div class="metric-card"><div class="label">Total Scanned</div><div class="value">{len(results)}</div></div>', unsafe_allow_html=True)
                s2.markdown(f'<div class="metric-card"><div class="label">BUY Signals</div><div class="value green">{buy_count}</div></div>', unsafe_allow_html=True)
                s3.markdown(f'<div class="metric-card"><div class="label">SELL Signals</div><div class="value red">{sell_count}</div></div>', unsafe_allow_html=True)
                s4.markdown(f'<div class="metric-card"><div class="label">Neutral</div><div class="value">{neu_count}</div></div>', unsafe_allow_html=True)
                st.write("")

                def highlight_signal(val):
                    if val == 'BUY':    return 'background-color:#0d2818; color:#3fb950; font-weight:bold'
                    elif val == 'SELL': return 'background-color:#2d0f0f; color:#f85149; font-weight:bold'
                    return 'color:#8b949e'

                st.dataframe(
                    res_df.style.map(highlight_signal, subset=['Signal']),
                    use_container_width=True, height=400
                )

                # Alert banners
                buy_syms  = res_df[res_df['Signal']=='BUY']['Symbol'].tolist()
                sell_syms = res_df[res_df['Signal']=='SELL']['Symbol'].tolist()
                if buy_syms:
                    st.markdown(f'<div class="alert-buy">✅ BUY: {" | ".join(buy_syms)}</div>', unsafe_allow_html=True)
                if sell_syms:
                    st.markdown(f'<div class="alert-sell">🔴 SELL: {" | ".join(sell_syms)}</div>', unsafe_allow_html=True)

                st.download_button("⬇ Download CSV", res_df.to_csv(index=False), "scan_results.csv", "text/csv")
            else:
                st.warning("⚠️ Koi data nahi aaya. Symbols check karo.")

# ══════════════════════════════════════════════
# TAB 4: ALERTS
# ══════════════════════════════════════════════
with tab_alerts:
    st.markdown("### 🔔 Alert Monitor")
    st.markdown("""
    **Alert Logic (from Pine Script):**
    - 🟢 **BUY Alert** — Candle closes ABOVE lower band after touching/crossing it
    - 🔴 **SELL Alert** — Candle touches or crosses ABOVE upper band
    """)

    col_al, col_ar = st.columns([2, 1])
    with col_al:
        alert_tf = st.selectbox("Alert Timeframe", list(TIMEFRAMES.keys()), index=5, key='alert_tf')
    with col_ar:
        st.write("")
        st.write("")
        check_alerts = st.button("🔍 Check Alerts Now", use_container_width=True)

    # Session alert log
    if 'alert_log' not in st.session_state:
        st.session_state.alert_log = []

    if check_alerts:
        iv_al, per_al = TIMEFRAMES[alert_tf]
        df_al = fetch_data(symbol, iv_al, per_al)
        if not df_al.empty:
            prices_al = df_al['Close'].values.flatten().astype(float)
            _, up_al, lo_al = compute_nwe_endpoint(prices_al, bandwidth, mult, lookback)
            df_al['upper'] = up_al
            df_al['lower'] = lo_al
            df_al = detect_signals(df_al)

            # Last N signals
            recent = df_al[df_al['signal'].isin(['BUY','SELL','SELL_CROSS_LOWER'])].tail(10)
            if recent.empty:
                st.info("No recent signals found.")
            else:
                for idx, row in recent.iterrows():
                    ts    = str(idx)[:16]
                    price = round(float(row['Close']), 2)
                    sig   = row['signal']
                    if sig == 'BUY' and alert_lower:
                        msg = f"✅ BUY — {symbol} @ ₹{price:,}  [{ts}]  Candle bounced above Lower Band"
                        st.markdown(f'<div class="alert-buy">{msg}</div>', unsafe_allow_html=True)
                        st.session_state.alert_log.append({'type':'BUY','symbol':symbol,'price':price,'time':ts})
                    elif sig in ('SELL','SELL_CROSS_LOWER') and alert_upper:
                        msg = f"🔴 SELL — {symbol} @ ₹{price:,}  [{ts}]  Candle touched Upper Band"
                        st.markdown(f'<div class="alert-sell">{msg}</div>', unsafe_allow_html=True)
                        st.session_state.alert_log.append({'type':'SELL','symbol':symbol,'price':price,'time':ts})

                # Webhook / Telegram
                if webhook_url.strip():
                    for _, row in recent.iterrows():
                        msg_text = f"[NW Alert] {row['signal']} {symbol} @ {round(float(row['Close']),2)} [{str(row.name)[:16]}]"
                        try:
                            import requests
                            requests.post(webhook_url, json={"text": msg_text}, timeout=5)
                            st.success(f"📡 Sent to webhook: {msg_text}")
                        except Exception as e:
                            st.error(f"Webhook failed: {e}")

    # Alert history
    if st.session_state.alert_log:
        st.markdown("#### 📋 Alert History (this session)")
        log_df = pd.DataFrame(st.session_state.alert_log[::-1])
        st.dataframe(log_df, use_container_width=True, height=250)
        if st.button("🗑 Clear History"):
            st.session_state.alert_log = []
            st.rerun()

# ══════════════════════════════════════════════
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
                            _, up_wl, lo_wl = compute_nwe_endpoint(prices_wl, bandwidth, mult, lb_wl)
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
# TAB 6: HELP
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
