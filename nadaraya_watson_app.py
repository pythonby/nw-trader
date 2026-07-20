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
    """Load from Streamlit secrets → .env → default"""
    try:
        val = st.secrets[key]
        if val: return val
    except: pass
    try:
        import os
        from dotenv import load_dotenv
        load_dotenv()
        val = os.getenv(key, default)
        if val: return val
    except: pass
    return default

# Pre-load secrets
_PRESET_TOKEN   = get_secret("TG_TOKEN")
_PRESET_CHAT_ID = get_secret("TG_CHAT_ID")

# ─────────────────────────────────────────────────────────────────
# PERSISTENT STORAGE — Token aur Alerts hamesha save rahenge
# Streamlit Cloud pe JSON file use nahi hoti — sirf session state
# Token: Streamlit Secrets se load hota hai (permanent)
# Alerts: session mein hain, lekin auto-restore karte hain secrets se
# ─────────────────────────────────────────────────────────────────

def save_alerts_to_secrets_hint():
    """Show user how to make alerts permanent"""
    pass

import json as _json
import os as _os

# ─────────────────────────────────────────────────────────────────
# PERSISTENT STORAGE — GitHub repo file based (SURVIVES app sleep/restart)
# /tmp ki jagah ab GitHub repo me data/nw_scanner_data.json me save hoga.
# Local /tmp ko sirf FAST CACHE ki tarah use karte hain (same session ke liye),
# GitHub hi source-of-truth hai jo restarts ke baad bhi bacha rahega.
# ─────────────────────────────────────────────────────────────────

import base64

STORAGE_FILE = "/tmp/nw_scanner_data.json"

GITHUB_TOKEN      = get_secret("GITHUB_PAT")
GITHUB_REPO_OWNER = "pythonby"
GITHUB_REPO_NAME  = "nw-trader"
GITHUB_DATA_PATH  = "data/nw_scanner_data.json"
_GH_API           = f"https://api.github.com/repos/{GITHUB_REPO_OWNER}/{GITHUB_REPO_NAME}/contents/{GITHUB_DATA_PATH}"


def _gh_headers():
    return {"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd.github+json"}


def _load_storage():
    """Load persistent data — pehle GitHub se try karo, fail ho to local /tmp fallback."""
    if GITHUB_TOKEN:
        try:
            r = requests.get(_GH_API, headers=_gh_headers(), timeout=10)
            if r.status_code == 200:
                content = r.json()
                decoded = json.loads(base64.b64decode(content["content"]).decode("utf-8"))
                st.session_state["_gh_sha"] = content["sha"]
                # local /tmp me bhi cache kar lo (fast repeated reads ke liye)
                try:
                    with open(STORAGE_FILE, "w") as f:
                        json.dump(decoded, f, default=str)
                except: pass
                return decoded
            elif r.status_code == 404:
                st.session_state["_gh_sha"] = None
                return {}
        except Exception:
            pass  # network issue -> neeche /tmp fallback try hoga

    # Fallback: local /tmp (agar GITHUB_PAT set nahi hai ya GitHub unreachable hai)
    try:
        if os.path.exists(STORAGE_FILE):
            with open(STORAGE_FILE, "r") as f:
                return json.load(f)
    except: pass
    return {}


def _save_storage(data: dict):
    """Save persistent data — GitHub repo file me commit karo (permanent), + local /tmp cache."""
    ok = False

    # 1) Local /tmp me turant save karo (fast, current session ke liye)
    try:
        with open(STORAGE_FILE, "w") as f:
            json.dump(data, f, indent=2, default=str)
        ok = True
    except: pass

    # 2) GitHub repo file me bhi commit karo (permanent — restart ke baad bhi rahega)
    if GITHUB_TOKEN:
        try:
            content_str = json.dumps(data, indent=2, default=str)
            encoded = base64.b64encode(content_str.encode("utf-8")).decode("utf-8")

            sha = st.session_state.get("_gh_sha")
            if sha is None:
                r_get = requests.get(_GH_API, headers=_gh_headers(), timeout=10)
                if r_get.status_code == 200:
                    sha = r_get.json().get("sha")

            payload = {"message": "Auto-update nw_scanner_data.json", "content": encoded}
            if sha:
                payload["sha"] = sha

            r_put = requests.put(_GH_API, headers=_gh_headers(), json=payload, timeout=15)
            if r_put.status_code in (200, 201):
                st.session_state["_gh_sha"] = r_put.json()["content"]["sha"]
                ok = True
        except Exception:
            pass  # GitHub save fail hua to bhi local /tmp save to ho hi chuka hai

    return ok

def init_persistent_state():
    """
    Initialize state on every page load.
    Loads from JSON file (persistent across restarts).
    Token always comes from Streamlit Secrets (most secure).
    """
    # ── Token: Secrets > File > Empty ────────────
    if _PRESET_TOKEN:
        # Secrets token always wins (most secure)
        st.session_state.tg_token   = _PRESET_TOKEN
        st.session_state.tg_chat_id = _PRESET_CHAT_ID
    elif "tg_token" not in st.session_state:
        # Try loading from file
        st.session_state.tg_token   = load_persistent("tg_token", "")
        st.session_state.tg_chat_id = load_persistent("tg_chat_id", "")

    # ── Saved Alerts: Load from file ─────────────
    if "saved_alerts" not in st.session_state:
        saved = load_persistent("saved_alerts", {})
        st.session_state.saved_alerts = saved

    # ── Watchlists: Load from file ────────────────
    if "watchlists" not in st.session_state:
        wl = load_persistent("watchlists", {
            "My Picks":    ["RELIANCE.NS","TCS.NS","INFY.NS","HDFCBANK.NS"],
            "Bank Stocks": ["HDFCBANK.NS","ICICIBANK.NS","SBIN.NS","AXISBANK.NS"],
        })
        st.session_state.watchlists = wl

    # ── Other state defaults ──────────────────────
    if "alert_log"    not in st.session_state: st.session_state.alert_log    = []
    if "scan_history" not in st.session_state: st.session_state.scan_history = []
    if "alert_rules"  not in st.session_state:
        st.session_state.alert_rules = [
            {"tf":"5m",  "buy":True,  "sell":True,  "active":True,  "_id":0},
            {"tf":"15m", "buy":True,  "sell":True,  "active":True,  "_id":1},
            {"tf":"1H",  "buy":True,  "sell":True,  "active":True,  "_id":2},
            {"tf":"4H",  "buy":False, "sell":False, "active":False, "_id":3},
            {"tf":"1D",  "buy":False, "sell":False, "active":False, "_id":4},
        ]

# Run init on every page load
init_persistent_state()

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
# BACKGROUND AUTO-SCANNER (triggered by UptimeRobot pings)
# Jab bhi koi (ya UptimeRobot bot) is URL ko kholta hai,
# saved active alerts automatically check ho jaate hain
# aur Telegram pe bhej diye jaate hain — bina manually
# "Check Now" dabaye.
# ─────────────────────────────────────────────────────────────────

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

def check_indicator_condition(df_c, al_cfg_c):
    """Check if technical indicator condition is met for last bar"""
    ind_c    = al_cfg_c.get("indicator_used","NW Envelope / Bollinger Bands (Band Touch)")
    params_c = al_cfg_c.get("ind_params",{})
    buy_c    = al_cfg_c.get("buy", True)
    sell_c   = al_cfg_c.get("sell", False)
    prices_c = df_c["Close"].values.flatten().astype(float)
    high_c   = df_c["High"].values.flatten().astype(float) if "High" in df_c.columns else prices_c
    low_c    = df_c["Low"].values.flatten().astype(float)  if "Low"  in df_c.columns else prices_c
    vol_c    = df_c["Volume"].values.flatten().astype(float) if "Volume" in df_c.columns else np.ones(len(prices_c))
    n_c      = len(prices_c)
    if n_c < 10: return False, "BUY", "Not enough data", {}

    result_vals = {}

    if "NW Envelope" in ind_c or "Bollinger" in ind_c:
        _, up_c, lo_c = compute_indicator(prices_c, indicator_choice, bandwidth, mult, min(lookback, n_c-1))
        price_last = prices_c[-1]
        up_last    = up_c[-1] if not np.isnan(up_c[-1]) else 0
        lo_last    = lo_c[-1] if not np.isnan(lo_c[-1]) else 0
        dist_up = round((up_last-price_last)/price_last*100,2) if up_last else 999
        dist_lo = round((price_last-lo_last)/price_last*100,2) if lo_last else 999
        near_up = dist_up<=0.5 or price_last>=up_last
        near_lo = dist_lo<=0.5 or price_last<=lo_last
        result_vals = {"Price": round(price_last,2), "Upper": round(up_last,2), "Lower": round(lo_last,2)}
        if near_up and sell_c: return True, "SELL", f"Upper Band Touch ({dist_up}%)", result_vals
        if near_lo and buy_c:  return True, "BUY",  f"Lower Band Touch ({dist_lo}%)", result_vals
        return False, "", "", result_vals

    elif ind_c == "RSI":
        p   = int(params_c.get("rsi_period",14))
        cnd = params_c.get("rsi_condition","RSI > Value (Above)")
        val = float(params_c.get("rsi_value",60))
        rsi_arr = compute_rsi(prices_c, p)
        curr = rsi_arr[-1]; prev = rsi_arr[-2] if n_c>1 else curr
        result_vals = {f"RSI({p})": round(float(curr),2), "Value": val}
        triggered = False
        if "Above" in cnd and "Crosses" not in cnd: triggered = curr > val
        elif "Below" in cnd and "Crosses" not in cnd: triggered = curr < val
        elif "Crosses Above" in cnd: triggered = curr>val and prev<=val
        elif "Crosses Below" in cnd: triggered = curr<val and prev>=val
        sig = "BUY" if "Above" in cnd else "SELL"
        return triggered, sig, f"RSI({p})={round(float(curr),2)} {cnd.replace('Value',str(val))}", result_vals

    elif ind_c == "RSI + EMA Cross":
        p    = int(params_c.get("rsi_period",14))
        ema_type = params_c.get("ema_type","RSI crossed above EMA(9)")
        rsi_arr = compute_rsi(prices_c, p)
        if "ALL" in ema_type:
            ema9  = compute_ema(rsi_arr, 9)
            ema21 = compute_ema(rsi_arr, 21)
            ema50 = compute_ema(rsi_arr, 50)
            is_above = "above" in ema_type
            cross9  = any(rsi_arr[j]>ema9[j]  and rsi_arr[j-1]<=ema9[j-1]  for j in range(max(1,n_c-5),n_c))
            cross21 = any(rsi_arr[j]>ema21[j] and rsi_arr[j-1]<=ema21[j-1] for j in range(max(1,n_c-5),n_c))
            cross50 = any(rsi_arr[j]>ema50[j] and rsi_arr[j-1]<=ema50[j-1] for j in range(max(1,n_c-5),n_c))
            if is_above:
                triggered = cross9 and cross21 and cross50 and ema9[-1]<40 and ema21[-1]<40 and ema50[-1]<40 and rsi_arr[-1]>40
            else:
                cross9b  = any(rsi_arr[j]<ema9[j]  and rsi_arr[j-1]>=ema9[j-1]  for j in range(max(1,n_c-5),n_c))
                cross21b = any(rsi_arr[j]<ema21[j] and rsi_arr[j-1]>=ema21[j-1] for j in range(max(1,n_c-5),n_c))
                cross50b = any(rsi_arr[j]<ema50[j] and rsi_arr[j-1]>=ema50[j-1] for j in range(max(1,n_c-5),n_c))
                triggered = cross9b and cross21b and cross50b and ema9[-1]>60 and ema21[-1]>60 and ema50[-1]>60 and rsi_arr[-1]<60
            sig = "BUY" if is_above else "SELL"
            result_vals = {f"RSI({p})":round(float(rsi_arr[-1]),2),"EMA9":round(float(ema9[-1]),2),"EMA21":round(float(ema21[-1]),2),"EMA50":round(float(ema50[-1]),2)}
        else:
            ema_n = 9 if "(9)" in ema_type else 21 if "(21)" in ema_type else 50
            ema_arr = compute_ema(rsi_arr, ema_n)
            is_above = "above" in ema_type
            triggered = any((rsi_arr[j]>ema_arr[j] if is_above else rsi_arr[j]<ema_arr[j]) and
                             (rsi_arr[j-1]<=ema_arr[j-1] if is_above else rsi_arr[j-1]>=ema_arr[j-1])
                             for j in range(max(1,n_c-5),n_c))
            sig = "BUY" if is_above else "SELL"
            result_vals = {f"RSI({p})":round(float(rsi_arr[-1]),2),f"EMA({ema_n})":round(float(ema_arr[-1]),2)}
        return triggered, sig, f"RSI({p}) {ema_type}", result_vals

    elif ind_c == "EMA Cross":
        ef = int(params_c.get("ema_fast",9)); es = int(params_c.get("ema_slow",21))
        ef_arr = compute_ema(prices_c, ef); es_arr = compute_ema(prices_c, es)
        is_above = buy_c
        triggered = (ef_arr[-1]>es_arr[-1] and ef_arr[-2]<=es_arr[-2]) if is_above else (ef_arr[-1]<es_arr[-1] and ef_arr[-2]>=es_arr[-2])
        result_vals = {f"EMA({ef})":round(float(ef_arr[-1]),2),f"EMA({es})":round(float(es_arr[-1]),2)}
        return triggered, "BUY" if is_above else "SELL", f"EMA({ef}) crossed {'above' if is_above else 'below'} EMA({es})", result_vals

    elif ind_c == "SMA Cross":
        sf = int(params_c.get("sma_fast",20)); ss = int(params_c.get("sma_slow",50))
        sf_arr = compute_sma(prices_c, sf); ss_arr = compute_sma(prices_c, ss)
        is_above = buy_c
        triggered = (sf_arr[-1]>ss_arr[-1] and sf_arr[-2]<=ss_arr[-2]) if is_above else (sf_arr[-1]<ss_arr[-1] and sf_arr[-2]>=ss_arr[-2])
        result_vals = {f"SMA({sf})":round(float(sf_arr[-1]),2),f"SMA({ss})":round(float(ss_arr[-1]),2)}
        return triggered, "BUY" if is_above else "SELL", f"SMA({sf}) crossed {'above' if is_above else 'below'} SMA({ss})", result_vals

    elif ind_c == "Supertrend":
        p = int(params_c.get("st_period",7)); m = float(params_c.get("st_mult",2.0))
        _, direction = compute_supertrend(high_c, low_c, prices_c, p, m)
        is_bull = buy_c
        triggered = (direction[-1]==1 and direction[-2]==-1) if is_bull else (direction[-1]==-1 and direction[-2]==1)
        result_vals = {"Supertrend":"Bullish 📈" if direction[-1]==1 else "Bearish 📉"}
        return triggered, "BUY" if is_bull else "SELL", f"Supertrend({p},{m}) turned {'Bullish' if is_bull else 'Bearish'}", result_vals

    elif ind_c == "MACD":
        mf = int(params_c.get("macd_fast",12)); ms = int(params_c.get("macd_slow",26)); msig = int(params_c.get("macd_signal",9))
        mcond = params_c.get("macd_cond","MACD crosses ABOVE Signal (BUY)")
        ema_f = compute_ema(prices_c, mf); ema_s = compute_ema(prices_c, ms)
        macd_line = ema_f - ema_s
        sig_line  = compute_ema(macd_line, msig)
        hist      = macd_line - sig_line
        triggered = False
        if "ABOVE" in mcond: triggered = macd_line[-1]>sig_line[-1] and macd_line[-2]<=sig_line[-2]
        elif "BELOW" in mcond: triggered = macd_line[-1]<sig_line[-1] and macd_line[-2]>=sig_line[-2]
        elif "> 0" in mcond: triggered = macd_line[-1]>0
        elif "< 0" in mcond: triggered = macd_line[-1]<0
        result_vals = {"MACD":round(float(macd_line[-1]),4),"Signal":round(float(sig_line[-1]),4),"Hist":round(float(hist[-1]),4)}
        sig_type = "BUY" if "ABOVE" in mcond or "> 0" in mcond else "SELL"
        return triggered, sig_type, f"MACD({mf},{ms},{msig}) {mcond.split('(')[0].strip()}", result_vals

    elif ind_c == "CCI":
        p = int(params_c.get("cci_period",20)); cnd = params_c.get("cci_condition","CCI > Value"); val = float(params_c.get("cci_value",200))
        cci_arr = compute_cci(high_c, low_c, prices_c, p)
        curr = cci_arr[-1]; prev = cci_arr[-2] if n_c>1 else curr
        result_vals = {f"CCI({p})":round(float(curr),2)}
        if ">" in cnd and "Crosses" not in cnd: triggered = curr>val
        elif "<" in cnd and "Crosses" not in cnd: triggered = curr<val
        elif "Above" in cnd: triggered = curr>val and prev<=val
        elif "Below" in cnd: triggered = curr<val and prev>=val
        else: triggered = False
        return triggered, "BUY" if ">" in cnd or "Above" in cnd else "SELL", f"CCI({p})={round(float(curr),2)} {cnd.replace('Value',str(val))}", result_vals

    elif ind_c == "MFI":
        p = int(params_c.get("mfi_period",14)); cnd = params_c.get("mfi_condition","MFI > Value (Above)"); val = float(params_c.get("mfi_value",50))
        mfi_arr = compute_mfi(high_c, low_c, prices_c, vol_c, p)
        curr = mfi_arr[-1]; prev = mfi_arr[-2] if n_c>1 else curr
        result_vals = {f"MFI({p})":round(float(curr),2)}
        if "Above" in cnd and "Crosses" not in cnd: triggered = curr>val
        elif "Below" in cnd and "Crosses" not in cnd: triggered = curr<val
        elif "Crosses Above" in cnd: triggered = curr>val and prev<=val
        elif "Crosses Below" in cnd: triggered = curr<val and prev>=val
        else: triggered = False
        return triggered, "BUY" if ">" in cnd or "Above" in cnd else "SELL", f"MFI({p})={round(float(curr),2)} {cnd.replace('Value',str(val))}", result_vals

    elif ind_c == "Stochastic":
        p = int(params_c.get("stoch_period",14)); cnd = params_c.get("stoch_cond","%K > Value"); val = float(params_c.get("stoch_value",50))
        fk,fd,sk,sd = compute_fast_slow_stoch(high_c, low_c, prices_c, p)
        curr = fk[-1]; prev = fk[-2] if n_c>1 else curr
        result_vals = {f"Stoch %K":round(float(curr),2),f"Stoch %D":round(float(fd[-1]),2)}
        if "%K > Value" in cnd: triggered = curr>val
        elif "%K < Value" in cnd: triggered = curr<val
        elif "Above %D" in cnd: triggered = fk[-1]>fd[-1] and fk[-2]<=fd[-2]
        elif "Below %D" in cnd: triggered = fk[-1]<fd[-1] and fk[-2]>=fd[-2]
        elif "Crosses Above Value" in cnd: triggered = curr>val and prev<=val
        elif "Crosses Below Value" in cnd: triggered = curr<val and prev>=val
        else: triggered = False
        return triggered, "BUY" if ">" in cnd or "Above" in cnd else "SELL", f"Stoch({p}) {cnd.replace('Value',str(val))}", result_vals

    return False, "", "", {}


def run_background_auto_scan():
    """
    Background auto-scanner — completely independent of session state.
    Loads everything from persistent file storage directly.
    Called on every page load (throttled to 4 min intervals).
    """
    import time as _time

    # ── Step 1: Throttle check ────────────────────
    last_run = load_persistent("last_auto_scan_time", 0)
    now_ts   = _time.time()
    if now_ts - float(last_run) < 240:  # 4 min cooldown
        return
    save_persistent("last_auto_scan_time", now_ts)

    # ── Step 2: Load Telegram credentials from file/secrets ──
    tok = str(_PRESET_TOKEN or load_persistent("tg_token", "")).strip()
    cid = str(_PRESET_CHAT_ID or load_persistent("tg_chat_id", "")).strip()
    if not tok or not cid or len(tok) < 10:
        return  # No telegram configured

    # ── Step 3: Load saved alerts from persistent file ────────
    saved_alerts = load_persistent("saved_alerts", {})
    if not saved_alerts:
        # Also try session state as fallback
        saved_alerts = st.session_state.get("saved_alerts", {})
    if not saved_alerts:
        return

    active_alerts = {k: v for k, v in saved_alerts.items()
                     if v.get("active", True)}
    if not active_alerts:
        return

    # ── Step 4: Default NW params (fallback if sidebar not loaded) ──
    _bandwidth = 8.0
    _mult      = 3.5
    _lookback  = 200
    _indicator = "NW Envelope (Nadaraya-Watson)"

    # ── Step 5: Scan each alert ───────────────────
    for al_name, al_cfg in active_alerts.items():
        syms = al_cfg.get("symbols", [])
        tfs  = al_cfg.get("tf_list", [])
        ind  = al_cfg.get("indicator_used", _indicator)
        if not syms or not tfs:
            continue

        for tf_bg in tfs:
            if tf_bg not in TIMEFRAMES:
                continue
            iv_bg, per_bg = TIMEFRAMES[tf_bg]

            for sym_bg in syms[:30]:  # safety cap
                try:
                    df_bg = fetch_data(sym_bg, iv_bg, per_bg)
                    if df_bg.empty or len(df_bg) < 50:
                        continue

                    prices_bg = df_bg["Close"].values.flatten().astype(float)
                    high_bg   = df_bg["High"].values.flatten().astype(float) if "High" in df_bg.columns else prices_bg
                    low_bg    = df_bg["Low"].values.flatten().astype(float)  if "Low"  in df_bg.columns else prices_bg
                    vol_bg    = df_bg["Volume"].values.flatten().astype(float) if "Volume" in df_bg.columns else np.ones(len(prices_bg))
                    n_bg      = len(prices_bg)
                    if n_bg < 10:
                        continue

                    buy_bg  = al_cfg.get("buy",  True)
                    sell_bg = al_cfg.get("sell", False)
                    params  = al_cfg.get("ind_params", {})
                    triggered_bg = False
                    sig_bg       = ""
                    cond_str_bg  = al_cfg.get("condition_desc", "Band Touch")
                    vals_str_bg  = ""

                    # ── Evaluate condition ────────────────
                    if "NW" in ind or "Bollinger" in ind or "Band" in ind:
                        # NW Envelope / Bollinger Bands
                        lb_bg = min(_lookback, n_bg - 1)
                        _, up_bg, lo_bg = compute_indicator(prices_bg, _indicator, _bandwidth, _mult, lb_bg)
                        price_last = prices_bg[-1]
                        up_last    = float(up_bg[-1]) if not np.isnan(up_bg[-1]) else 0
                        lo_last    = float(lo_bg[-1]) if not np.isnan(lo_bg[-1]) else 0
                        dist_up = round((up_last - price_last) / price_last * 100, 2) if up_last else 999
                        dist_lo = round((price_last - lo_last) / price_last * 100, 2) if lo_last else 999
                        near_up = dist_up <= 0.5 or price_last >= up_last
                        near_lo = dist_lo <= 0.5 or price_last <= lo_last
                        vals_str_bg = f"Upper={round(up_last,2)} Lower={round(lo_last,2)} Price={round(price_last,2)}"
                        if near_up and sell_bg:
                            triggered_bg = True; sig_bg = "SELL"
                            cond_str_bg  = f"Upper Band Touch ({dist_up}%)"
                        elif near_lo and buy_bg:
                            triggered_bg = True; sig_bg = "BUY"
                            cond_str_bg  = f"Lower Band Touch ({dist_lo}%)"

                    elif ind == "RSI":
                        p   = int(params.get("rsi_period", 14))
                        cnd = params.get("rsi_condition", "RSI > Value (Above)")
                        val = float(params.get("rsi_value", 60))
                        rsi_arr = compute_rsi(prices_bg, p)
                        curr = float(rsi_arr[-1]); prev = float(rsi_arr[-2]) if n_bg > 1 else curr
                        vals_str_bg = f"RSI({p})={round(curr,2)}"
                        if   "Above" in cnd and "Crosses" not in cnd: triggered_bg = curr > val
                        elif "Below" in cnd and "Crosses" not in cnd: triggered_bg = curr < val
                        elif "Crosses Above" in cnd: triggered_bg = curr > val and prev <= val
                        elif "Crosses Below" in cnd: triggered_bg = curr < val and prev >= val
                        sig_bg = "BUY" if buy_bg else "SELL"

                    elif "RSI + EMA" in ind or "RSI-EMA" in ind:
                        p  = int(params.get("rsi_period", 14))
                        et = params.get("ema_type", "RSI crossed above EMA(9)")
                        rsi_arr = compute_rsi(prices_bg, p)
                        ema_n   = 9 if "(9)" in et else 21 if "(21)" in et else 50
                        ema_arr = compute_ema(rsi_arr, ema_n)
                        is_above = "above" in et.lower()
                        triggered_bg = any(
                            (rsi_arr[j] > ema_arr[j] if is_above else rsi_arr[j] < ema_arr[j]) and
                            (rsi_arr[j-1] <= ema_arr[j-1] if is_above else rsi_arr[j-1] >= ema_arr[j-1])
                            for j in range(max(1, n_bg-5), n_bg)
                        )
                        vals_str_bg = f"RSI({p})={round(float(rsi_arr[-1]),2)} EMA({ema_n})={round(float(ema_arr[-1]),2)}"
                        sig_bg = "BUY" if is_above else "SELL"

                    elif "EMA Cross" in ind:
                        ef = int(params.get("ema_fast", 9)); es = int(params.get("ema_slow", 21))
                        ef_arr = compute_ema(prices_bg, ef); es_arr = compute_ema(prices_bg, es)
                        triggered_bg = (ef_arr[-1] > es_arr[-1] and ef_arr[-2] <= es_arr[-2]) if buy_bg \
                                   else (ef_arr[-1] < es_arr[-1] and ef_arr[-2] >= es_arr[-2])
                        vals_str_bg = f"EMA({ef})={round(float(ef_arr[-1]),2)} EMA({es})={round(float(es_arr[-1]),2)}"
                        sig_bg = "BUY" if buy_bg else "SELL"

                    elif "SMA Cross" in ind:
                        sf = int(params.get("sma_fast", 20)); ss = int(params.get("sma_slow", 50))
                        sf_arr = compute_sma(prices_bg, sf); ss_arr = compute_sma(prices_bg, ss)
                        triggered_bg = (sf_arr[-1] > ss_arr[-1] and sf_arr[-2] <= ss_arr[-2]) if buy_bg \
                                   else (sf_arr[-1] < ss_arr[-1] and sf_arr[-2] >= ss_arr[-2])
                        vals_str_bg = f"SMA({sf})={round(float(sf_arr[-1]),2)} SMA({ss})={round(float(ss_arr[-1]),2)}"
                        sig_bg = "BUY" if buy_bg else "SELL"

                    elif "Supertrend" in ind:
                        p = int(params.get("st_period", 7)); m = float(params.get("st_mult", 2.0))
                        _, direction = compute_supertrend(high_bg, low_bg, prices_bg, p, m)
                        triggered_bg = (direction[-1]==1 and direction[-2]==-1) if buy_bg \
                                   else (direction[-1]==-1 and direction[-2]==1)
                        vals_str_bg = f"Supertrend={'Bullish' if direction[-1]==1 else 'Bearish'}"
                        sig_bg = "BUY" if buy_bg else "SELL"

                    elif "MACD" in ind:
                        mf = int(params.get("macd_fast",12)); ms = int(params.get("macd_slow",26))
                        msig = int(params.get("macd_signal",9))
                        mcnd = params.get("macd_cond","MACD crosses ABOVE Signal (BUY)")
                        macd_line = compute_ema(prices_bg,mf) - compute_ema(prices_bg,ms)
                        sig_line  = compute_ema(macd_line, msig)
                        if   "ABOVE" in mcnd: triggered_bg = macd_line[-1]>sig_line[-1] and macd_line[-2]<=sig_line[-2]
                        elif "BELOW" in mcnd: triggered_bg = macd_line[-1]<sig_line[-1] and macd_line[-2]>=sig_line[-2]
                        elif "> 0"  in mcnd:  triggered_bg = macd_line[-1]>0
                        elif "< 0"  in mcnd:  triggered_bg = macd_line[-1]<0
                        vals_str_bg = f"MACD={round(float(macd_line[-1]),4)} Signal={round(float(sig_line[-1]),4)}"
                        sig_bg = "BUY" if "ABOVE" in mcnd or "> 0" in mcnd else "SELL"

                    elif "CCI" in ind:
                        p   = int(params.get("cci_period",20))
                        cnd = params.get("cci_condition","CCI > Value")
                        val = float(params.get("cci_value",200))
                        cci_arr = compute_cci(high_bg, low_bg, prices_bg, p)
                        curr = float(cci_arr[-1]); prev = float(cci_arr[-2]) if n_bg>1 else curr
                        if   ">" in cnd and "Crosses" not in cnd: triggered_bg = curr > val
                        elif "<" in cnd and "Crosses" not in cnd: triggered_bg = curr < val
                        elif "Above" in cnd: triggered_bg = curr>val and prev<=val
                        elif "Below" in cnd: triggered_bg = curr<val and prev>=val
                        vals_str_bg = f"CCI({p})={round(curr,2)}"
                        sig_bg = "BUY" if ">" in cnd or "Above" in cnd else "SELL"

                    elif "MFI" in ind:
                        p   = int(params.get("mfi_period",14))
                        cnd = params.get("mfi_condition","MFI > Value (Above)")
                        val = float(params.get("mfi_value",50))
                        mfi_arr = compute_mfi(high_bg, low_bg, prices_bg, vol_bg, p)
                        curr = float(mfi_arr[-1]); prev = float(mfi_arr[-2]) if n_bg>1 else curr
                        if   "Above" in cnd and "Crosses" not in cnd: triggered_bg = curr > val
                        elif "Below" in cnd and "Crosses" not in cnd: triggered_bg = curr < val
                        elif "Crosses Above" in cnd: triggered_bg = curr>val and prev<=val
                        elif "Crosses Below" in cnd: triggered_bg = curr<val and prev>=val
                        vals_str_bg = f"MFI({p})={round(curr,2)}"
                        sig_bg = "BUY" if ">" in cnd or "Above" in cnd else "SELL"

                    # ── Send Telegram if triggered ────────
                    if triggered_bg and sig_bg:
                        price_bg  = round(float(df_bg["Close"].iloc[-1]), 2)
                        ts_bg     = str(df_bg.index[-1])[:16]
                        icon_bg   = "📈" if sig_bg == "BUY" else "📉"
                        s_icon_bg = "✅" if sig_bg == "BUY" else "🔴"
                        msg_bg = (
                            f"{icon_bg} <b>NW Band Scanner</b>\n"
                            f"━━━━━━━━━━━━━\n"
                            f"{s_icon_bg} <b>{sig_bg} SIGNAL</b>\n"
                            f"🏷 Alert: {al_name}\n"
                            f"📌 Symbol: {sym_bg}\n"
                            f"⏱ Timeframe: {tf_bg}\n"
                            f"🎯 Condition: {cond_str_bg}\n"
                            f"📊 Values: {vals_str_bg}\n"
                            f"💰 Price: ₹{price_bg:,}\n"
                            f"🕐 {ts_bg}\n"
                            f"━━━━━━━━━━━━━"
                        )
                        try:
                            requests.post(
                                f"https://api.telegram.org/bot{tok}/sendMessage",
                                json={"chat_id": cid, "text": msg_bg, "parse_mode": "HTML"},
                                timeout=10
                            )
                        except Exception:
                            pass

                except Exception:
                    continue

# (trigger moved below fetch_data definition)

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

# ─────────────────────────────────────────────────────────────────
# ANGEL ONE API INTEGRATION
# ─────────────────────────────────────────────────────────────────

# Angel One interval mapping
ANGEL_INTERVAL_MAP = {
    "1m":  "ONE_MINUTE",
    "2m":  "TWO_MINUTE",
    "5m":  "FIVE_MINUTE",
    "15m": "FIFTEEN_MINUTE",
    "30m": "THIRTY_MINUTE",
    "1h":  "ONE_HOUR",
    "1H":  "ONE_HOUR",
    "4h":  "FOUR_HOUR",
    "4H":  "FOUR_HOUR",
    "1d":  "ONE_DAY",
    "1D":  "ONE_DAY",
    "1wk": "ONE_DAY",  # Angel doesn't have weekly — use daily
    "1W":  "ONE_DAY",
    "1mo": "ONE_DAY",
    "1Mo": "ONE_DAY",
}

def get_angel_session():
    """Create Angel One SmartAPI session"""
    try:
        from SmartApi import SmartConnect
        import pyotp
        api_key  = st.secrets.get("ANGEL_API_KEY",  load_persistent("angel_api_key",  ""))
        client_id= st.secrets.get("ANGEL_CLIENT_ID",load_persistent("angel_client_id",""))
        password = st.secrets.get("ANGEL_PASSWORD",  load_persistent("angel_password",  ""))
        totp_key = st.secrets.get("ANGEL_TOTP_KEY",  load_persistent("angel_totp_key",  ""))

        if not all([api_key, client_id, password]):
            return None, "Angel One credentials missing"

        obj = SmartConnect(api_key=api_key)
        totp = pyotp.TOTP(totp_key).now() if totp_key else ""
        data = obj.generateSession(client_id, password, totp)
        if data.get("status"):
            return obj, "OK"
        return None, data.get("message","Login failed")
    except ImportError:
        return None, "SmartApi not installed"
    except Exception as e:
        return None, str(e)

def angel_symbol_lookup(symbol_ns: str) -> tuple:
    """
    Convert NSE symbol (e.g. RELIANCE.NS) to Angel One token.
    Returns (token, exchange, trading_symbol)
    """
    # Common index tokens
    INDEX_TOKENS = {
        "^NSEI":     ("99926000", "NSE", "Nifty 50"),
        "^NSEBANK":  ("99926009", "NSE", "Nifty Bank"),
        "^BSESN":    ("99919000", "BSE", "SENSEX"),
        "NIFTY50=F": ("26000",    "NFO", "NIFTY"),
        "BANKNIFTY=F":("26009",   "NFO", "BANKNIFTY"),
    }
    if symbol_ns in INDEX_TOKENS:
        return INDEX_TOKENS[symbol_ns]

    # Strip .NS / .BO
    clean = symbol_ns.replace(".NS","").replace(".BO","")
    exch  = "BSE" if ".BO" in symbol_ns else "NSE"
    # For equity, token lookup needs scrip master — return None to fallback to yfinance
    return None, exch, clean

def fetch_angel_data(symbol: str, interval: str, days: int) -> pd.DataFrame:
    """Fetch OHLCV data from Angel One SmartAPI"""
    try:
        obj, status = get_angel_session()
        if obj is None:
            return pd.DataFrame()

        token, exchange, trading_sym = angel_symbol_lookup(symbol)
        if token is None:
            return pd.DataFrame()

        angel_interval = ANGEL_INTERVAL_MAP.get(interval, "ONE_DAY")
        from datetime import datetime, timedelta
        to_dt   = datetime.now()
        from_dt = to_dt - timedelta(days=days)

        params = {
            "exchange":    exchange,
            "symboltoken": token,
            "interval":    angel_interval,
            "fromdate":    from_dt.strftime("%Y-%m-%d %H:%M"),
            "todate":      to_dt.strftime("%Y-%m-%d %H:%M"),
        }
        hist = obj.getCandleData(params)
        if not hist.get("status") or not hist.get("data"):
            return pd.DataFrame()

        df = pd.DataFrame(hist["data"],
            columns=["Datetime","Open","High","Low","Close","Volume"])
        df["Datetime"] = pd.to_datetime(df["Datetime"])
        df.set_index("Datetime", inplace=True)
        df = df.astype(float)
        return df.dropna()
    except Exception as e:
        return pd.DataFrame()

# Period string → days mapping
PERIOD_TO_DAYS = {
    "1d": 1, "2d": 2, "5d": 5, "7d": 7,
    "14d": 14, "30d": 30, "60d": 60,
    "90d": 90, "180d": 180, "365d": 365,
    "730d": 730, "1825d": 1825,
    "2y": 730, "5y": 1825, "10y": 3650,
}

@st.cache_data(ttl=60)
def fetch_data(symbol: str, interval: str, period: str) -> pd.DataFrame:
    """
    Unified data fetch — tries Angel One first (if configured),
    falls back to yfinance automatically.
    """
    use_angel = load_persistent("use_angel_api", False)

    # Try Angel One if enabled
    if use_angel:
        days = PERIOD_TO_DAYS.get(period, 30)
        df_angel = fetch_angel_data(symbol, interval, days)
        if not df_angel.empty:
            return df_angel
        # If Angel fails — silently fallback to yfinance

    # yfinance fallback
    try:
        df = yf.download(symbol, interval=interval, period=period,
                         progress=False, auto_adjust=True)
        if df.empty:
            return pd.DataFrame()
        df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]
        df = df[["Open","High","Low","Close","Volume"]].dropna()
        return df
    except Exception as e:
        return pd.DataFrame()

# (background scan trigger moved to after sidebar — needs bandwidth/mult/lookback/indicator_choice)

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

    # ── Angel One API Settings ───────────────
    st.divider()
    st.markdown("### 📡 Data Source")

    use_angel = load_persistent("use_angel_api", False)
    angel_enabled = st.toggle(
        "Angel One API (Real-time)",
        value=use_angel,
        help="ON = Angel One real-time data | OFF = yfinance (delayed)",
        key="angel_toggle"
    )
    if angel_enabled != use_angel:
        save_persistent("use_angel_api", angel_enabled)

    if angel_enabled:
        st.markdown('<div class="alert-buy">✅ Angel One API Active</div>',
                    unsafe_allow_html=True)
        with st.expander("⚙️ Angel One Credentials", expanded=False):
            ang_key  = st.text_input("API Key",      value=load_persistent("angel_api_key",""),  type="password", key="ang_key")
            ang_cid  = st.text_input("Client ID",    value=load_persistent("angel_client_id",""), key="ang_cid")
            ang_pwd  = st.text_input("Password",     value=load_persistent("angel_password",""),  type="password", key="ang_pwd")
            ang_totp = st.text_input("TOTP Secret",  value=load_persistent("angel_totp_key",""),  type="password", key="ang_totp",
                                     help="TOTP secret key from Angel One 2FA setup")
            if st.button("💾 Save Credentials", key="ang_save"):
                save_persistent("angel_api_key",   ang_key.strip())
                save_persistent("angel_client_id", ang_cid.strip())
                save_persistent("angel_password",  ang_pwd.strip())
                save_persistent("angel_totp_key",  ang_totp.strip())
                st.success("✅ Credentials saved!")
            if st.button("🔌 Test Connection", key="ang_test"):
                with st.spinner("Connecting..."):
                    obj, msg = get_angel_session()
                    if obj: st.success("✅ Angel One connected!")
                    else:   st.error(f"❌ {msg}")
            st.caption("""
            **Streamlit Secrets mein permanently save karo:**
            ```toml
            ANGEL_API_KEY   = "your_api_key"
            ANGEL_CLIENT_ID = "your_client_id"
            ANGEL_PASSWORD  = "your_password"
            ANGEL_TOTP_KEY  = "your_totp_secret"
            ```
            """)
    else:
        st.caption("📊 yfinance (free, delayed data)")

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
        value="RELIANCE.NS\nINFY.NS\nTCS.NS\nHDFCBANK.NS\n^NSEI",
        height=120
    )
    scan_tf = st.selectbox("Scanner Timeframe", list(TIMEFRAMES.keys()), index=5, key='scan_tf')
    auto_refresh = st.checkbox("🔄 Auto-refresh (60s)", value=False)

    # ── Background Scan Debug ─────────────────
    st.divider()
    st.markdown("### 🔍 Auto-Scan Debug")
    if '_bg_debug' in dir():
        for _d in _bg_debug:
            st.caption(_d)
    else:
        st.caption("Debug info loading...")
    if st.button("🔄 Force Scan Now", key="force_bg_scan"):
        save_persistent("last_auto_scan_time", 0)
        st.success("✅ Cooldown reset! Refresh karo.")
        st.rerun()

# ─────────────────────────────────────────────────────────────────
# TRIGGER BACKGROUND AUTO-SCAN
# All dependencies (bandwidth, mult, lookback, indicator_choice,
# compute_indicator, fetch_data, TIMEFRAMES) are now defined.
# Throttled internally to once per 4 minutes per app instance.
# Triggered every time someone (or UptimeRobot) loads this page.
# ─────────────────────────────────────────────────────────────────
# Run background scan + show debug in sidebar
_bg_debug = []
try:
    import time as _t
    _last = load_persistent("last_auto_scan_time", 0)
    _now  = _t.time()
    _diff = int(_now - float(_last))
    _bg_debug.append(f"Last scan: {_diff}s ago (cooldown=240s)")

    _bg_tok = str(_PRESET_TOKEN or load_persistent("tg_token","")).strip()
    _bg_cid = str(_PRESET_CHAT_ID or load_persistent("tg_chat_id","")).strip()
    _bg_debug.append(f"Token: {'✅ found' if len(_bg_tok)>10 else '❌ missing'}")
    _bg_debug.append(f"Chat ID: {'✅ found' if _bg_cid else '❌ missing'}")

    _bg_alerts = load_persistent("saved_alerts", {})
    _bg_debug.append(f"Saved alerts (file): {len(_bg_alerts)}")
    _bg_ss_alerts = st.session_state.get("saved_alerts", {})
    _bg_debug.append(f"Saved alerts (session): {len(_bg_ss_alerts)}")

    if _diff >= 240:
        run_background_auto_scan()
        _bg_debug.append("✅ Scan ran!")
    else:
        _bg_debug.append(f"⏳ Cooldown: {240-_diff}s remaining")
except Exception as _bg_err:
    _bg_debug.append(f"❌ Error: {_bg_err}")

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
            all_cats = [
                "⭐ ALL SECTORS",
                "⭐ Nifty 50 Only",
                "⭐ Nifty Next 50",
                "⭐ Indices Only",
                "⭐ F&O Futures Only",
                "── Sectors ──",
            ] + list(INDEX_DATABASE.keys())
            sel_scan_cat = st.selectbox("📂 Category Select Karo", all_cats, key="scan_cat")
        with cat_c2:
            if sel_scan_cat in ("⭐ ALL SECTORS", "⭐ SCAN ALL CATEGORIES"):
                all_tickers = []
                for cat, stocks in INDEX_DATABASE.items():
                    for ticker in stocks.values():
                        if ticker != "CUSTOM": all_tickers.append(ticker)
                scan_symbols = list(dict.fromkeys(all_tickers))
                st.info(f"📊 ALL SECTORS: {len(scan_symbols)} total symbols")
            elif sel_scan_cat == "⭐ Nifty 50 Only":
                scan_symbols = [v for v in INDEX_DATABASE.get("🏢 NIFTY 50 STOCKS",{}).values() if v!="CUSTOM"]
                st.success(f"✅ Nifty 50: {len(scan_symbols)} stocks")
            elif sel_scan_cat == "⭐ Nifty Next 50":
                scan_symbols = [v for v in INDEX_DATABASE.get("🥈 NIFTY NEXT 50",{}).values() if v!="CUSTOM"]
                st.success(f"✅ Nifty Next 50: {len(scan_symbols)} stocks")
            elif sel_scan_cat == "⭐ Indices Only":
                scan_symbols  = [v for v in INDEX_DATABASE.get("🏆 NIFTY INDICES",{}).values() if v!="CUSTOM"]
                scan_symbols += [v for v in INDEX_DATABASE.get("🏭 NIFTY SECTORS",{}).values() if v!="CUSTOM"]
                scan_symbols  = list(dict.fromkeys(scan_symbols))
                st.success(f"✅ All Indices: {len(scan_symbols)} symbols")
            elif sel_scan_cat == "⭐ F&O Futures Only":
                scan_symbols = [v for v in INDEX_DATABASE.get("📈 F&O FUTURES",{}).values() if v!="CUSTOM"]
                st.success(f"✅ F&O Futures: {len(scan_symbols)} symbols")
            elif sel_scan_cat == "── Sectors ──":
                scan_symbols = []
                st.caption("Neeche se koi sector select karo")
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
        "📱 Scan result automatically Telegram pe bhejo",
        value=True,
        key="auto_tg_scan_save",
        help="ON hone par scan complete hote hi BUY/SELL signals Telegram pe chale jayenge"
    )
    # Show telegram status clearly
    _tok_check = str(st.session_state.get("tg_token","")).strip()
    _cid_check = str(st.session_state.get("tg_chat_id","")).strip()
    if _tok_check and _cid_check and len(_tok_check) > 10:
        st.caption(f"✅ Telegram ready — Token: ...{_tok_check[-6:]} | Chat: {_cid_check}")
    else:
        st.warning("⚠️ Telegram token nahi mila! Alerts tab → Telegram Config mein Token + Chat ID save karo, phir scan karo.")

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

                # ── AUTO-SEND TO TELEGRAM ────────────────────
                buy_auto  = res_df[res_df["Signal"]=="BUY"]["Symbol"].tolist()
                sell_auto = res_df[res_df["Signal"]=="SELL"]["Symbol"].tolist()

                _tok = str(st.session_state.get("tg_token","")).strip()
                _cid = str(st.session_state.get("tg_chat_id","")).strip()

                if _tok and _cid and len(_tok) > 10:
                    scan_time = pd.Timestamp.now().strftime("%d-%b-%Y %H:%M")
                    msg  = f"📊 <b>NW Band Scanner</b>\n━━━━━━━━━━━━━\n"
                    msg += f"🕐 {scan_time}\n"
                    msg += f"⏱ TF: {scan_tf_tab}\n"
                    msg += f"📈 Scanned: {len(results)} stocks\n\n"
                    if buy_auto:
                        msg += f"✅ <b>BUY ({len(buy_auto)})</b>:\n"
                        msg += "\n".join([f"• {s}" for s in buy_auto[:25]]) + "\n\n"
                    if sell_auto:
                        msg += f"🔴 <b>SELL ({len(sell_auto)})</b>:\n"
                        msg += "\n".join([f"• {s}" for s in sell_auto[:25]]) + "\n\n"
                    if not buy_auto and not sell_auto:
                        msg += "⚪ Koi signal nahi mila\n\n"
                    msg += "━━━━━━━━━━━━━"
                    try:
                        r_tg = requests.post(
                            f"https://api.telegram.org/bot{_tok}/sendMessage",
                            json={"chat_id":_cid,"text":msg,"parse_mode":"HTML"},
                            timeout=15
                        )
                        if r_tg.status_code == 200:
                            st.success(f"✅ Telegram sent! BUY={len(buy_auto)} SELL={len(sell_auto)}")
                        else:
                            st.error(f"❌ Telegram Error {r_tg.status_code}: {r_tg.text[:150]}")
                    except Exception as e_tg2:
                        st.error(f"❌ Telegram: {e_tg2}")
                else:
                    st.warning("⚠️ Telegram token nahi — Alerts tab mein save karo!")


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
    st.markdown("### 🔔 Alert System")

    # ── Telegram Config ──────────────────────────
    with st.expander("📱 Telegram Setup & Config", expanded=False):
        st.markdown("""
        ### 🔐 Token Permanently Save Karne Ka Tarika

        **Streamlit Cloud pe (Permanent — ek baar karो, hamesha rahega):**
        1. 👉 https://share.streamlit.io → Apni app ke **⋮** → **Settings** → **Secrets**
        2. Ye paste karo:
        ```toml
        TG_TOKEN = "aapka_bot_token"
        TG_CHAT_ID = "aapka_chat_id"
        ```
        3. **Save** karo → App restart hoga → Token hamesha load hoga!

        **Token kahan se milega:**
        - Token: Telegram mein **@BotFather** → `/mybots` → Apna bot → API Token
        - Chat ID: **@userinfobot** → `/start` → Id copy karo
        """)

        # Show current token status
        if _PRESET_TOKEN:
            st.success(f"✅ Token Streamlit Secrets se load hua — Permanent! (ID: ...{_PRESET_TOKEN[-6:]})")
            st.caption("Token change karne ke liye Streamlit Cloud → Settings → Secrets update karo")
        else:
            st.warning("⚠️ Token Secrets mein nahi hai — manually save karo (sirf is session ke liye)")

        tc1, tc2 = st.columns(2)
        with tc1:
            tg_tok = st.text_input("🤖 Bot Token",
                value=st.session_state.tg_token,
                type="password",
                placeholder="7123456789:AAGxxxxx",
                key="tg_tok_inp2",
                help="Streamlit Secrets use karo permanent save ke liye")
        with tc2:
            tg_cid = st.text_input("💬 Chat ID",
                value=st.session_state.tg_chat_id,
                placeholder="987654321",
                key="tg_cid_inp2")

        tb1, tb2, _ = st.columns([1,1,2])
        with tb1:
            if st.button("💾 Save Token", key="tg_save2",
                help="Token file mein save hoga — app restart hone par bhi rahega"):
                st.session_state.tg_token   = tg_tok.strip()
                st.session_state.tg_chat_id = tg_cid.strip()
                # Save to persistent file
                save_persistent("tg_token",   tg_tok.strip())
                save_persistent("tg_chat_id", tg_cid.strip())
                st.success("✅ Token saved! App restart ke baad bhi rahega.")
        with tb2:
            if st.button("📨 Test", key="tg_test2"):
                tok = st.session_state.tg_token.strip()
                cid = st.session_state.tg_chat_id.strip()
                if tok and cid:
                    try:
                        r = requests.post(f"https://api.telegram.org/bot{tok}/sendMessage",
                            json={"chat_id":cid,"text":"✅ <b>NW Band Scanner</b>\nBot connected! 🎉","parse_mode":"HTML"}, timeout=15)
                        if r.status_code==200: st.success("✅ Message gaya!")
                        elif r.status_code==401: st.error("❌ Token galat hai! @BotFather se check karo")
                        elif r.status_code==400:
                            err = r.json().get("description","")
                            if "chat not found" in err.lower(): st.error("❌ Chat ID galat hai!")
                            else: st.error(f"❌ {err}")
                        else: st.error(f"❌ HTTP {r.status_code}")
                    except requests.exceptions.Timeout: st.error("❌ Timeout!")
                    except Exception as e_t: st.error(f"❌ {e_t}")
                else: st.warning("Token + Chat ID save karo!")

    tg_ok = bool(st.session_state.get("tg_token","") and st.session_state.get("tg_chat_id",""))
    if tg_ok:
        st.markdown('<div class="alert-buy">✅ Telegram Connected</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="alert-sell">⚠️ Telegram setup nahi hua</div>', unsafe_allow_html=True)

    st.divider()

    # ══════════════════════════════════════════════
    # EXPORT / IMPORT ALERTS (Permanent Save)
    # ══════════════════════════════════════════════
    with st.expander("💾 Alerts Export/Import (Permanent Save karo)", expanded=False):
        st.markdown("""
        **Alerts session band hone par delete ho jaate hain.**
        Unhe permanently save karne ke liye **Export** karo aur dobara **Import** karo!
        """)
        exp_c1, exp_c2 = st.columns(2)
        with exp_c1:
            st.markdown("**⬇ Export — Alerts download karo**")
            if st.session_state.saved_alerts:
                import json as _json
                alerts_json = _json.dumps(st.session_state.saved_alerts, indent=2, default=str)
                st.download_button(
                    "⬇ Download Alerts JSON",
                    alerts_json,
                    "my_alerts.json",
                    "application/json",
                    use_container_width=True
                )
                st.caption(f"📋 {len(st.session_state.saved_alerts)} alerts export honge")
            else:
                st.info("Koi saved alert nahi")

        with exp_c2:
            st.markdown("**⬆ Import — Pehle wale alerts restore karo**")
            uploaded_alerts = st.file_uploader("JSON file upload karo",
                type=["json"], key="al_import_file")
            if uploaded_alerts:
                try:
                    import json as _json
                    imported = _json.loads(uploaded_alerts.read())
                    if st.button("✅ Import Karo", use_container_width=True, key="al_import_btn"):
                        st.session_state.saved_alerts.update(imported)
                        st.success(f"✅ {len(imported)} alerts imported!")
                        st.rerun()
                    st.caption(f"📋 {len(imported)} alerts milenge")
                except Exception as e_imp:
                    st.error(f"❌ Invalid file: {e_imp}")

    st.divider()

    # ══════════════════════════════════════════════
    # SAVED ALERTS DASHBOARD
    # ══════════════════════════════════════════════
    st.markdown("#### 📋 Saved Alerts Dashboard")

    if "saved_alerts" not in st.session_state:
        st.session_state.saved_alerts = {}

    if st.session_state.saved_alerts:
        for al_name, al_cfg in list(st.session_state.saved_alerts.items()):
            is_on  = al_cfg.get("active", True)
            bg     = "#0d1f12" if is_on else "#1c2128"
            border = "#3fb950" if is_on else "#30363d"
            cond_text = al_cfg.get("condition_desc", "—")
            tfs_text  = " | ".join(al_cfg.get("tf_list", []))
            syms_text = al_cfg.get("symbols_desc","—")
            ind_text  = al_cfg.get("indicator_used","NW Envelope")

            st.markdown(f"""
            <div style="background:{bg};border:1px solid {border};border-radius:10px;padding:14px 18px;margin:8px 0;">
                <div style="display:flex;justify-content:space-between;align-items:center;">
                    <b style="color:#e6edf3;font-size:1rem">{al_name}</b>
                    <span style="color:{"#3fb950" if is_on else "#8b949e"};font-weight:bold">{"🟢 ACTIVE" if is_on else "⚫ PAUSED"}</span>
                </div>
                <div style="margin-top:8px;color:#8b949e;font-size:0.82rem;line-height:1.8">
                    📌 <b style="color:#e6edf3">Symbol:</b> {syms_text}<br>
                    ⏱ <b style="color:#e6edf3">Timeframe:</b> {tfs_text}<br>
                    📐 <b style="color:#e6edf3">Indicator:</b> {ind_text}<br>
                    🎯 <b style="color:#e6edf3">Condition:</b> <span style="color:{"#3fb950" if "BUY" in cond_text or "Lower" in cond_text or "above" in cond_text.lower() or ">" in cond_text else "#f85149" if "SELL" in cond_text or "Upper" in cond_text or "below" in cond_text.lower() or "<" in cond_text else "#58a6ff"}">{cond_text}</span>
                </div>
            </div>
            """, unsafe_allow_html=True)

            ac1, ac2, ac3 = st.columns([1,1,1])
            with ac1:
                if st.button("⏸ Pause" if is_on else "▶ Activate", key=f"tog_{al_name}", use_container_width=True):
                    st.session_state.saved_alerts[al_name]["active"] = not is_on
                    save_persistent("saved_alerts", st.session_state.saved_alerts)
                    st.rerun()
            with ac2:
                if st.button("🔍 Check Now", key=f"chk_{al_name}", use_container_width=True):
                    st.session_state["run_alert_now"] = al_name
            with ac3:
                if st.button("🗑 Delete", key=f"del_{al_name}", use_container_width=True):
                    del st.session_state.saved_alerts[al_name]
                    save_persistent("saved_alerts", st.session_state.saved_alerts)
                    st.rerun()
    else:
        st.info("Koi saved alert nahi — neeche banao ⬇️")

    st.divider()

    # ══════════════════════════════════════════════
    # CREATE NEW ALERT
    # ══════════════════════════════════════════════
    st.markdown("#### ➕ Nayi Alert Banao")

    # Alert Name
    al_name_inp = st.text_input("🏷️ Alert naam", placeholder="e.g. Nifty RSI 60 BUY 1H", key="al_name_inp3")

    # ── STEP 1: Symbol ────────────────────────────
    st.markdown("##### 📌 Step 1 — Symbol / Index")
    s1c1, s1c2 = st.columns(2)
    with s1c1:
        al_cat_opts3 = ["⭐ ALL SECTORS (sab stocks)"] + list(INDEX_DATABASE.keys())
        al_cat3 = st.selectbox("Category", al_cat_opts3, key="al_cat3")
    with s1c2:
        if al_cat3 == "⭐ ALL SECTORS (sab stocks)":
            al_sym_lbl3 = "All Sectors"
            al_sym3 = "__ALL__"
            st.info(f"📊 Total: {sum(len([v for v in cat.values() if v!='CUSTOM']) for cat in INDEX_DATABASE.values())} stocks")
        else:
            al_sym_opts3 = {k:v for k,v in INDEX_DATABASE[al_cat3].items() if v!="CUSTOM"}
            al_sym_lbl3  = st.selectbox("Symbol", list(al_sym_opts3.keys()), key="al_sym3")
            al_sym3 = al_sym_opts3[al_sym_lbl3]

    # Extra stocks
    if "al_extra3" not in st.session_state: st.session_state.al_extra3 = []
    with st.expander("➕ Aur symbols (optional)"):
        exc1, exc2 = st.columns([3,1])
        with exc1: extra3_inp = st.text_input("", placeholder="ZOMATO.NS", key="al_extra3_inp", label_visibility="collapsed")
        with exc2:
            if st.button("Add", key="al_extra3_add"):
                s3 = extra3_inp.strip().upper()
                if s3 and s3 not in st.session_state.al_extra3: st.session_state.al_extra3.append(s3); st.rerun()
        for i3, se3 in enumerate(list(st.session_state.al_extra3)):
            e3c1,e3c2 = st.columns([4,1]); e3c1.caption(f"`{se3}`")
            if e3c2.button("❌", key=f"rem3_{i3}"): st.session_state.al_extra3.remove(se3); st.rerun()
    if al_sym3 == "__ALL__":
        all_tickers3 = []
        for _cat3 in INDEX_DATABASE.values():
            all_tickers3 += [v for v in _cat3.values() if v!="CUSTOM"]
        final_syms3 = list(dict.fromkeys(all_tickers3 + st.session_state.al_extra3))
    else:
        final_syms3 = list(dict.fromkeys([al_sym3]+st.session_state.al_extra3))
    st.caption(f"✅ {len(final_syms3)} symbol(s): {', '.join(final_syms3[:5])}{'...' if len(final_syms3)>5 else ''}")

    # ── STEP 2: Timeframe ─────────────────────────
    st.markdown("##### ⏱ Step 2 — Timeframe")
    tf_keys3 = list(TIMEFRAMES.keys())
    tf_cols3 = st.columns(len(tf_keys3))
    sel_tfs3 = []
    for i3, tf3 in enumerate(tf_keys3):
        with tf_cols3[i3]:
            if st.checkbox(tf3, value=(tf3 in ["15m","1H"]), key=f"al_tf3_{tf3}"): sel_tfs3.append(tf3)
    if sel_tfs3: st.caption(f"✅ {' | '.join(sel_tfs3)}")
    else: st.warning("⚠️ Timeframe select karo!")

    # ── STEP 3: Indicator ─────────────────────────
    st.markdown("##### 📐 Step 3 — Indicator")
    al_indicator = st.selectbox("Indicator", [
        "NW Envelope / Bollinger Bands (Band Touch)",
        "RSI", "RSI + EMA Cross",
        "EMA Cross", "SMA Cross",
        "Supertrend",
        "MACD", "CCI", "MFI", "Stochastic",
    ], key="al_ind3")

    # ── STEP 4: Condition (dynamic based on indicator) ──
    st.markdown("##### 🎯 Step 4 — Condition")

    condition_desc3 = ""
    buy_cond3 = False
    sell_cond3 = False
    al_ind_params = {}

    if al_indicator == "NW Envelope / Bollinger Bands (Band Touch)":
        band_cond = st.radio("Band Condition", [
            "✅ BUY — Lower Band Touch (price neeche band ko touch kare)",
            "🔴 SELL — Upper Band Touch (price upar band ko touch kare)",
            "🔔 DONO — Lower Band BUY + Upper Band SELL",
        ], key="al_band_cond3")
        if "BUY" in band_cond and "SELL" not in band_cond: buy_cond3=True; sell_cond3=False
        elif "SELL" in band_cond and "BUY" not in band_cond: buy_cond3=False; sell_cond3=True
        else: buy_cond3=True; sell_cond3=True
        condition_desc3 = band_cond.split("(")[0].strip()

    elif al_indicator == "RSI":
        rsi_p3 = st.slider("RSI Period", 5, 30, 14, 1, key="al_rsi_p3")
        rsi_cond3 = st.selectbox("RSI Condition", [
            "RSI > Value (Above)",
            "RSI < Value (Below)",
            "RSI Crosses Above Value",
            "RSI Crosses Below Value",
        ], key="al_rsi_cond3")
        rsi_val3 = st.slider("RSI Value", 10.0, 90.0, 60.0, 1.0, key="al_rsi_val3")

        # Visual RSI zone indicator
        zone = "🔴 Overbought Zone" if rsi_val3 > 70 else "🟡 Middle Zone" if rsi_val3 > 30 else "🟢 Oversold Zone"
        st.caption(f"RSI({rsi_p3}) {rsi_cond3} {rsi_val3} — {zone}")
        buy_cond3  = "Above" in rsi_cond3 or ("Crosses" in rsi_cond3 and "Above" in rsi_cond3)
        sell_cond3 = "Below" in rsi_cond3 or ("Crosses" in rsi_cond3 and "Below" in rsi_cond3)
        condition_desc3 = f"RSI({rsi_p3}) {rsi_cond3.replace('Value',str(int(rsi_val3)))}"
        al_ind_params = {"rsi_period": rsi_p3, "rsi_condition": rsi_cond3, "rsi_value": rsi_val3}

    elif al_indicator == "RSI + EMA Cross":
        rsi_p3 = st.slider("RSI Period", 5, 30, 14, 1, key="al_rsie_p3")
        ema_type3 = st.selectbox("RSI crossed which EMA?", [
            "RSI crossed above EMA(9)",
            "RSI crossed above EMA(21)",
            "RSI crossed above EMA(50)",
            "RSI crossed above ALL EMAs (9,21,50) + all EMAs <40 + RSI>40",
            "RSI crossed below EMA(9)",
            "RSI crossed below EMA(21)",
            "RSI crossed below EMA(50)",
            "RSI crossed below ALL EMAs (9,21,50) + all EMAs >60 + RSI<60",
        ], key="al_rsie_cond3")
        buy_cond3  = "above" in ema_type3
        sell_cond3 = "below" in ema_type3
        condition_desc3 = f"RSI({rsi_p3}) — {ema_type3}"
        al_ind_params = {"rsi_period": rsi_p3, "ema_type": ema_type3}

    elif al_indicator == "EMA Cross":
        ema_f3 = st.slider("Fast EMA", 3, 50, 9, 1, key="al_emaf3")
        ema_s3 = st.slider("Slow EMA", 5, 200, 21, 1, key="al_emas3")
        ema_cond3 = st.radio("", ["Fast EMA crosses ABOVE Slow (BUY)", "Fast EMA crosses BELOW Slow (SELL)"], key="al_ema_cond3")
        buy_cond3  = "ABOVE" in ema_cond3
        sell_cond3 = "BELOW" in ema_cond3
        condition_desc3 = f"EMA({ema_f3}) {ema_cond3.split('(')[0].strip()}"
        al_ind_params = {"ema_fast": ema_f3, "ema_slow": ema_s3}

    elif al_indicator == "SMA Cross":
        sma_f3 = st.slider("Fast SMA", 3, 50, 20, 1, key="al_smaf3")
        sma_s3 = st.slider("Slow SMA", 5, 200, 50, 1, key="al_smas3")
        sma_cond3 = st.radio("", ["Fast SMA crosses ABOVE Slow (BUY)", "Fast SMA crosses BELOW Slow (SELL)"], key="al_sma_cond3")
        buy_cond3  = "ABOVE" in sma_cond3
        sell_cond3 = "BELOW" in sma_cond3
        condition_desc3 = f"SMA({sma_f3}) {sma_cond3.split('(')[0].strip()}"
        al_ind_params = {"sma_fast": sma_f3, "sma_slow": sma_s3}

    elif al_indicator == "Supertrend":
        st_p3 = st.slider("Supertrend Period", 5, 20, 7, 1, key="al_stp3")
        st_m3 = st.slider("Supertrend Multiplier", 1.0, 5.0, 2.0, 0.5, key="al_stm3")
        st_cond3 = st.radio("", ["Supertrend turns BULLISH (BUY signal)", "Supertrend turns BEARISH (SELL signal)"], key="al_st_cond3")
        buy_cond3  = "BULLISH" in st_cond3
        sell_cond3 = "BEARISH" in st_cond3
        condition_desc3 = f"Supertrend({st_p3},{st_m3}) {st_cond3.split('(')[0].strip()}"
        al_ind_params = {"st_period": st_p3, "st_mult": st_m3}

    elif al_indicator == "MACD":
        macd_f3 = st.slider("MACD Fast", 3, 20, 12, 1, key="al_macdf3")
        macd_s3 = st.slider("MACD Slow", 10, 50, 26, 1, key="al_macds3")
        macd_sig3 = st.slider("Signal Line", 3, 15, 9, 1, key="al_macdsig3")
        macd_cond3 = st.radio("", ["MACD crosses ABOVE Signal (BUY)", "MACD crosses BELOW Signal (SELL)", "MACD > 0 (Positive)", "MACD < 0 (Negative)"], key="al_macd_cond3")
        buy_cond3  = "ABOVE" in macd_cond3 or "> 0" in macd_cond3
        sell_cond3 = "BELOW" in macd_cond3 or "< 0" in macd_cond3
        condition_desc3 = f"MACD({macd_f3},{macd_s3},{macd_sig3}) {macd_cond3.split('(')[0].strip()}"
        al_ind_params = {"macd_fast": macd_f3, "macd_slow": macd_s3, "macd_signal": macd_sig3, "macd_cond": macd_cond3}

    elif al_indicator == "CCI":
        cci_p3  = st.slider("CCI Period", 5, 50, 20, 1, key="al_ccip3")
        cci_cond3 = st.selectbox("CCI Condition", ["CCI > Value", "CCI < Value", "CCI Crosses Above Value", "CCI Crosses Below Value"], key="al_ccicond3")
        cci_val3  = st.slider("CCI Value", -300.0, 300.0, 200.0, 10.0, key="al_ccival3")
        zone3 = "🔴 Overbought" if cci_val3>100 else "🟢 Oversold" if cci_val3<-100 else "⚪ Neutral"
        st.caption(f"CCI({cci_p3}) {cci_cond3} {cci_val3} — {zone3}")
        buy_cond3  = ">" in cci_cond3 or "Above" in cci_cond3
        sell_cond3 = "<" in cci_cond3 or "Below" in cci_cond3
        condition_desc3 = f"CCI({cci_p3}) {cci_cond3.replace('Value',str(int(cci_val3)))}"
        al_ind_params = {"cci_period": cci_p3, "cci_condition": cci_cond3, "cci_value": cci_val3}

    elif al_indicator == "MFI":
        mfi_p3   = st.slider("MFI Period", 5, 30, 14, 1, key="al_mfip3")
        mfi_cond3 = st.selectbox("MFI Condition", ["MFI > Value (Above)", "MFI < Value (Below)", "MFI Crosses Above Value", "MFI Crosses Below Value"], key="al_mficond3")
        mfi_val3  = st.slider("MFI Value", 10.0, 90.0, 50.0, 5.0, key="al_mfival3")
        zone3 = "🔴 Overbought" if mfi_val3>80 else "🟢 Oversold" if mfi_val3<20 else "⚪ Middle"
        st.caption(f"MFI({mfi_p3}) {mfi_cond3} {mfi_val3} — {zone3}")
        buy_cond3  = ">" in mfi_cond3 or "Above" in mfi_cond3
        sell_cond3 = "<" in mfi_cond3 or "Below" in mfi_cond3
        condition_desc3 = f"MFI({mfi_p3}) {mfi_cond3.replace('Value',str(int(mfi_val3)))}"
        al_ind_params = {"mfi_period": mfi_p3, "mfi_condition": mfi_cond3, "mfi_value": mfi_val3}

    elif al_indicator == "Stochastic":
        stoch_k3   = st.slider("Stoch %K Period", 5, 30, 14, 1, key="al_stochk3")
        stoch_cond3 = st.selectbox("Condition", ["%K > Value", "%K < Value", "%K Crosses Above %D (BUY)", "%K Crosses Below %D (SELL)", "%K Crosses Above Value", "%K Crosses Below Value"], key="al_stochcond3")
        stoch_val3  = st.slider("Value", 10.0, 90.0, 50.0, 5.0, key="al_stochval3") if "Value" in stoch_cond3 else 50.0
        zone3 = "🔴 Overbought" if stoch_val3>80 else "🟢 Oversold" if stoch_val3<20 else "⚪ Middle"
        if "Value" in stoch_cond3: st.caption(f"Stoch({stoch_k3}) {stoch_cond3} {stoch_val3} — {zone3}")
        buy_cond3  = ">" in stoch_cond3 or "Above" in stoch_cond3
        sell_cond3 = "<" in stoch_cond3 or "Below" in stoch_cond3
        condition_desc3 = f"Stoch({stoch_k3}) {stoch_cond3.replace('Value',str(int(stoch_val3)) if 'Value' in stoch_cond3 else '')}"
        al_ind_params = {"stoch_period": stoch_k3, "stoch_cond": stoch_cond3, "stoch_value": stoch_val3}

    # ── Condition Preview Box ─────────────────────
    if condition_desc3:
        cond_color = "#3fb950" if buy_cond3 and not sell_cond3 else "#f85149" if sell_cond3 and not buy_cond3 else "#58a6ff"
        st.markdown(f"""
        <div style="background:#1c2128;border:2px solid {cond_color};border-radius:10px;padding:16px 20px;margin:12px 0;">
            <b style="color:#e6edf3;font-size:1rem">📋 Alert Preview</b>
            <div style="margin-top:10px;color:#8b949e;font-size:0.85rem;line-height:2">
                🏷 <b style="color:#e6edf3">Name:</b> {al_name_inp or "(naam likhein)"}<br>
                📌 <b style="color:#e6edf3">Symbol:</b> {", ".join(final_syms3[:3])}{"..." if len(final_syms3)>3 else ""}<br>
                ⏱ <b style="color:#e6edf3">Timeframe:</b> {" | ".join(sel_tfs3) if sel_tfs3 else "—"}<br>
                📐 <b style="color:#e6edf3">Indicator:</b> {al_indicator}<br>
                🎯 <b style="color:#e6edf3">Condition:</b> <b style="color:{cond_color}">{condition_desc3}</b><br>
                📱 <b style="color:#e6edf3">Telegram Message:</b>
                <span style="color:#74c0fc;font-size:0.8rem">
                "NW Band Scanner | {al_name_inp or "Alert"} | {al_sym_lbl3} | {" | ".join(sel_tfs3[:2]) if sel_tfs3 else "—"} | {condition_desc3}"
                </span>
            </div>
        </div>
        """, unsafe_allow_html=True)

    # ── Save Button ───────────────────────────────
    if st.button("💾 Alert Save Karo", type="primary", use_container_width=True, key="al_save3"):
        if not al_name_inp.strip(): st.error("❌ Alert naam likhein!")
        elif not sel_tfs3: st.error("❌ Timeframe select karo!")
        elif not condition_desc3: st.error("❌ Condition select karo!")
        else:
            rules3 = [{"tf":tf3,"buy":buy_cond3,"sell":sell_cond3,"active":True,"_id":i3}
                      for i3,tf3 in enumerate(sel_tfs3)]
            st.session_state.saved_alerts[al_name_inp.strip()] = {
                "active":         True,
                "symbols":        final_syms3,
                "symbols_desc":   f"{al_sym_lbl3}" + (f" +{len(st.session_state.al_extra3)}" if st.session_state.al_extra3 else ""),
                "tf_list":        sel_tfs3,
                "indicator_used": al_indicator,
                "condition_desc": condition_desc3,
                "buy":            buy_cond3,
                "sell":           sell_cond3,
                "rules":          rules3,
                "ind_params":     al_ind_params,
            }
            # Auto-save permanently to file
            save_persistent("saved_alerts", st.session_state.saved_alerts)
            st.session_state.al_extra3 = []
            st.success(f"✅ Alert '{al_name_inp}' permanently saved! App restart ke baad bhi rahega.")
            st.rerun()

    st.divider()

    # ══════════════════════════════════════════════
    # RUN ALERTS
    # ══════════════════════════════════════════════
    st.markdown("#### 🚀 Alerts Check Karo")

    run_mode3 = st.radio("", ["✅ Sab Active Alerts", "📌 Ek specific alert"],
        horizontal=True, key="al_run_mode3")

    sel_alert3 = None
    if run_mode3 == "📌 Ek specific alert" and st.session_state.saved_alerts:
        sel_alert3 = st.selectbox("Alert select karo", list(st.session_state.saved_alerts.keys()), key="al_sel3")

    check_alerts3 = st.button("🔍 Check Now", type="primary", key="al_check3")
    if "run_alert_now" in st.session_state:
        sel_alert3 = st.session_state.pop("run_alert_now")
        check_alerts3 = True

    if "alert_log" not in st.session_state: st.session_state.alert_log = []

    def send_tg3(token, chat_id, text):
        try:
            if len(text)>4096: text=text[:4000]+"\n..."
            r = requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
                json={"chat_id":chat_id,"text":text,"parse_mode":"HTML"}, timeout=15)
            return r.status_code==200, r.json().get("description","") if r.status_code!=200 else "OK"
        except Exception as ex: return False, str(ex)

    # check_indicator_condition is now defined globally (see top of file)
    def run_saved_alert(al_name_r, al_cfg_r):
        found_r = []
        syms_r  = al_cfg_r.get("symbols",[])
        tfs_r   = al_cfg_r.get("tf_list",[])
        if not syms_r or not tfs_r: return found_r
        total_r = len(syms_r)*len(tfs_r)
        prog_r  = st.progress(0); stat_r = st.empty(); count_r = 0
        for tf_r in tfs_r:
            iv_r, per_r = TIMEFRAMES[tf_r]
            for sym_r in syms_r:
                stat_r.text(f"⏳ [{al_name_r}] {sym_r} | {tf_r} ({count_r+1}/{total_r})")
                df_r = fetch_data(sym_r, iv_r, per_r)
                if not df_r.empty and len(df_r)>50:
                    triggered_r, sig_r, cond_str_r, vals_r = check_indicator_condition(df_r, al_cfg_r)
                    if triggered_r:
                        price_r = round(float(df_r["Close"].iloc[-1]),2)
                        ts_r    = str(df_r.index[-1])[:16]
                        vals_str = " | ".join([f"{k}={v}" for k,v in vals_r.items()])
                        msg_r = (f"{"📈" if sig_r=="BUY" else "📉"} <b>NW Band Scanner</b>\n"
                                 f"━━━━━━━━━━━━━\n"
                                 f"{"✅" if sig_r=="BUY" else "🔴"} <b>{sig_r} SIGNAL</b>\n"
                                 f"🏷 Alert: {al_name_r}\n"
                                 f"📌 Symbol: {sym_r}\n"
                                 f"⏱ Timeframe: {tf_r}\n"
                                 f"📐 Indicator: {al_cfg_r.get('indicator_used','—')}\n"
                                 f"🎯 Condition: {cond_str_r}\n"
                                 f"📊 Values: {vals_str}\n"
                                 f"💰 Price: ₹{price_r:,}\n"
                                 f"🕐 Time: {ts_r}\n"
                                 f"━━━━━━━━━━━━━")
                        found_r.append({"type":sig_r,"symbol":sym_r,"price":price_r,
                            "time":ts_r,"tf":tf_r,"cond":cond_str_r,"vals":vals_str,
                            "alert":al_name_r,"msg":msg_r})
                count_r+=1; prog_r.progress(count_r/total_r)
        stat_r.empty(); prog_r.empty()
        return found_r

    if check_alerts3:
        all_found3 = []
        if run_mode3 == "✅ Sab Active Alerts":
            active_s = {k:v for k,v in st.session_state.saved_alerts.items() if v.get("active",True)}
            if not active_s: st.warning("⚠️ Koi active alert nahi!")
            for n3,c3 in active_s.items(): all_found3.extend(run_saved_alert(n3,c3))
        else:
            if sel_alert3 and sel_alert3 in st.session_state.saved_alerts:
                all_found3 = run_saved_alert(sel_alert3, st.session_state.saved_alerts[sel_alert3])

        if all_found3:
            st.markdown(f"#### 🔔 {len(all_found3)} Alert(s) Found!")
            for al3 in all_found3:
                if al3["type"]=="BUY":
                    st.markdown(f'''<div class="alert-buy">
                        ✅ <b>BUY</b> — <b>{al3["symbol"]}</b> | ⏱ {al3["tf"]} | 💰 ₹{al3["price"]:,}<br>
                        <small>🎯 {al3["cond"]} | 📊 {al3["vals"]} | 🏷 {al3["alert"]}</small>
                    </div>''', unsafe_allow_html=True)
                else:
                    st.markdown(f'''<div class="alert-sell">
                        🔴 <b>SELL</b> — <b>{al3["symbol"]}</b> | ⏱ {al3["tf"]} | 💰 ₹{al3["price"]:,}<br>
                        <small>🎯 {al3["cond"]} | 📊 {al3["vals"]} | 🏷 {al3["alert"]}</small>
                    </div>''', unsafe_allow_html=True)
                if tg_ok:
                    ok3,err3 = send_tg3(st.session_state.tg_token, st.session_state.tg_chat_id, al3["msg"])
                    if ok3: st.caption(f"  📱 Sent: {al3['symbol']} {al3['tf']}")
                    else: st.warning(f"  ⚠️ TG: {err3}")
                st.session_state.alert_log.append(al3)
        elif check_alerts3:
            st.info("⚪ Koi signal nahi mila.")

    # ── Alert Log ─────────────────────────────────
    if st.session_state.alert_log:
        st.divider()
        st.markdown(f"#### 📋 Alert History ({len(st.session_state.alert_log)})")
        log_df3 = pd.DataFrame([{
            "Time":a["time"],"Alert":a.get("alert",""),"Type":a["type"],
            "Symbol":a["symbol"],"TF":a.get("tf",""),"Price":f"₹{a['price']:,}",
            "Condition":a.get("cond",""),"Values":a.get("vals",""),
        } for a in st.session_state.alert_log[::-1]])
        def hl3(v):
            if v=="BUY":  return "background-color:#0d2818;color:#3fb950;font-weight:bold"
            if v=="SELL": return "background-color:#2d0f0f;color:#f85149;font-weight:bold"
            return ""
        st.dataframe(log_df3.style.map(hl3, subset=["Type"]), use_container_width=True, height=250)
        if st.button("🗑 Clear History", key="al_clr3"): st.session_state.alert_log=[]; st.rerun()


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
                        save_persistent("watchlists", st.session_state.watchlists)
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
                            save_persistent("watchlists", st.session_state.watchlists)
                            st.success(f"✅ {stk} remove ho gaya!")
                            st.rerun()
                    st.write("")

            # ── BULK ADD FROM CATEGORY ───────────
            st.markdown("---")
            st.markdown("**➕ Category se Bulk Add Karo**")
            blk_c1, blk_c2, blk_c3 = st.columns([2, 1, 1])
            with blk_c1:
                blk_opts = ["-- Select --", "⭐ ALL SECTORS", "⭐ Nifty 50 Only",
                            "⭐ Nifty Next 50", "⭐ Indices Only", "⭐ F&O Futures Only"] + list(INDEX_DATABASE.keys())
                blk_cat = st.selectbox("Category", blk_opts, key="wl_blk_cat", label_visibility="collapsed")
            with blk_c2:
                if blk_cat != "-- Select --":
                    if blk_cat == "⭐ ALL SECTORS":
                        blk_n = sum(len([v for v in c.values() if v!="CUSTOM"]) for c in INDEX_DATABASE.values())
                    elif blk_cat == "⭐ Nifty 50 Only":
                        blk_n = len([v for v in INDEX_DATABASE.get("🏢 NIFTY 50 STOCKS",{}).values() if v!="CUSTOM"])
                    elif blk_cat == "⭐ Nifty Next 50":
                        blk_n = len([v for v in INDEX_DATABASE.get("🥈 NIFTY NEXT 50",{}).values() if v!="CUSTOM"])
                    elif blk_cat == "⭐ Indices Only":
                        blk_n = len([v for v in INDEX_DATABASE.get("🏆 NIFTY INDICES",{}).values() if v!="CUSTOM"])
                    elif blk_cat == "⭐ F&O Futures Only":
                        blk_n = len([v for v in INDEX_DATABASE.get("📈 F&O FUTURES",{}).values() if v!="CUSTOM"])
                    else:
                        blk_n = len([v for v in INDEX_DATABASE.get(blk_cat,{}).values() if v!="CUSTOM"])
                    st.caption(f"~{blk_n} stocks")
            with blk_c3:
                if st.button("➕ Bulk Add", key="wl_blk_add_btn", use_container_width=True):
                    if blk_cat == "-- Select --":
                        st.error("Category select karo!")
                    else:
                        added_b = 0
                        def _get_blk_tickers(cat_name):
                            if cat_name == "⭐ ALL SECTORS":
                                t = []
                                for c in INDEX_DATABASE.values():
                                    t += [v for v in c.values() if v!="CUSTOM"]
                                return list(dict.fromkeys(t))
                            elif cat_name == "⭐ Nifty 50 Only":
                                return [v for v in INDEX_DATABASE.get("🏢 NIFTY 50 STOCKS",{}).values() if v!="CUSTOM"]
                            elif cat_name == "⭐ Nifty Next 50":
                                return [v for v in INDEX_DATABASE.get("🥈 NIFTY NEXT 50",{}).values() if v!="CUSTOM"]
                            elif cat_name == "⭐ Indices Only":
                                t  = [v for v in INDEX_DATABASE.get("🏆 NIFTY INDICES",{}).values() if v!="CUSTOM"]
                                t += [v for v in INDEX_DATABASE.get("🏭 NIFTY SECTORS",{}).values() if v!="CUSTOM"]
                                return list(dict.fromkeys(t))
                            elif cat_name == "⭐ F&O Futures Only":
                                return [v for v in INDEX_DATABASE.get("📈 F&O FUTURES",{}).values() if v!="CUSTOM"]
                            else:
                                return [v for v in INDEX_DATABASE.get(cat_name,{}).values() if v!="CUSTOM"]

                        for tkr in _get_blk_tickers(blk_cat):
                            if tkr not in st.session_state.watchlists[active]:
                                st.session_state.watchlists[active].append(tkr)
                                added_b += 1
                        save_persistent("watchlists", st.session_state.watchlists)
                        st.success(f"✅ {added_b} stocks add ho gaye '{active}' mein!")
                        st.rerun()

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
    # Indicator functions now defined globally (see top of file)
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
        scr_cat_opts = ["⭐ ALL SECTORS", "⭐ Nifty 50 Only", "⭐ Indices Only"] + list(INDEX_DATABASE.keys())
        scr_cat = st.selectbox("Category", scr_cat_opts, key="scr_cat")
        if scr_cat == "⭐ ALL SECTORS":
            for cat_v in INDEX_DATABASE.values():
                scr_symbols += [v for v in cat_v.values() if v != "CUSTOM"]
        elif scr_cat == "⭐ Nifty 50 Only":
            scr_symbols = [v for v in INDEX_DATABASE.get("🏢 NIFTY 50 STOCKS",{}).values() if v != "CUSTOM"]
        elif scr_cat == "⭐ Indices Only":
            scr_symbols = [v for v in INDEX_DATABASE.get("🏆 NIFTY INDICES",{}).values() if v != "CUSTOM"]
            scr_symbols += [v for v in INDEX_DATABASE.get("🏭 NIFTY SECTORS",{}).values() if v != "CUSTOM"]
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

# ─────────────────────────────────────────────────────────────────
# AUTO-REFRESH (if enabled) — NON-BLOCKING version
# Purana time.sleep(60) + st.rerun() Streamlit server thread ko
# 60 second tak block karta tha — isse resource usage badhta hai
# aur app sleep/slow-wake ka chance zyada hota hai.
# Ab browser hi JS ke through 60s baad page reload karega —
# server thread free rehta hai, koi blocking nahi.
# ─────────────────────────────────────────────────────────────────
if auto_refresh:
    import streamlit.components.v1 as components
    components.html(
        """
        <script>
            setTimeout(function() {
                window.parent.location.reload();
            }, 60000);
        </script>
        """,
        height=0,
    )
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
