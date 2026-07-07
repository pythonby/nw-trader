"""
NW Band Scanner — Standalone Alert Checker
Ye script GitHub Actions se har 15 minute mein chalti hai.
"""
import os, json, math, time, requests
import numpy as np
import pandas as pd
import yfinance as yf
from datetime import datetime

TG_TOKEN   = os.environ.get("TG_TOKEN", "")
TG_CHAT_ID = os.environ.get("TG_CHAT_ID", "")
ALERTS_JSON = os.environ.get("ALERTS_JSON", "")

TIMEFRAMES = {
    "1m":("1m","7d"), "2m":("2m","60d"), "5m":("5m","60d"),
    "15m":("15m","60d"), "30m":("30m","60d"), "1H":("1h","180d"),
    "4H":("4h","730d"), "1D":("1d","5y"), "1W":("1wk","10y"),
}

def gauss(x,h): return math.exp(-(x**2)/(h*h*2))

def compute_nwe(prices, h=8.0, mult=3.5, lookback=200):
    n=len(prices); lb=min(lookback,n)
    coefs=np.array([gauss(i,h) for i in range(lb)]); den=coefs.sum()
    nwe=np.full(n,np.nan)
    for idx in range(lb-1,n):
        w=prices[idx-lb+1:idx+1][::-1]; nwe[idx]=np.dot(w,coefs[:len(w)])/den
    mae=np.full(n,np.nan)
    for idx in range(lb-1,n):
        w=prices[idx-lb+1:idx+1][::-1]; nw=nwe[idx-lb+1:idx+1][::-1]
        mae[idx]=np.nanmean(np.abs(w-nw))*mult
    return nwe, nwe+mae, nwe-mae

def compute_rsi(prices, period=14):
    s=pd.Series(prices); d=s.diff()
    g=d.where(d>0,0.0); l=-d.where(d<0,0.0)
    ag=g.ewm(alpha=1/period,min_periods=period,adjust=False).mean()
    al=l.ewm(alpha=1/period,min_periods=period,adjust=False).mean()
    rs=ag/al.replace(0,np.nan)
    return (100-(100/(1+rs))).values

def compute_ema(prices, period):
    return pd.Series(prices).ewm(span=period,adjust=False).mean().values

def compute_sma(prices, period):
    return pd.Series(prices).rolling(period).mean().values

def fetch_data(symbol, interval, period):
    try:
        df=yf.download(symbol,interval=interval,period=period,progress=False,auto_adjust=True)
        if df.empty: return pd.DataFrame()
        df.columns=[c[0] if isinstance(c,tuple) else c for c in df.columns]
        return df[["Open","High","Low","Close","Volume"]].dropna()
    except Exception as e:
        print(f"  Fetch error {symbol}: {e}")
        return pd.DataFrame()

def check_condition(df, al_cfg):
    ind=al_cfg.get("indicator_used","NW Envelope / Bollinger Bands (Band Touch)")
    params=al_cfg.get("ind_params",{})
    buy_c=al_cfg.get("buy",True); sell_c=al_cfg.get("sell",False)
    prices=df["Close"].values.flatten().astype(float)
    high=df["High"].values.flatten().astype(float) if "High" in df.columns else prices
    low=df["Low"].values.flatten().astype(float) if "Low" in df.columns else prices
    n=len(prices)
    if n<20: return False,"","",{}
    triggered=False; sig=""; cond_str=al_cfg.get("condition_desc","Band Touch"); vals={}

    if "NW" in ind or "Bollinger" in ind or "Band" in ind:
        _,upper,lower=compute_nwe(prices)
        pl=prices[-1]; up=float(upper[-1]) if not np.isnan(upper[-1]) else 0
        lo=float(lower[-1]) if not np.isnan(lower[-1]) else 0
        du=round((up-pl)/pl*100,2) if up else 999
        dl=round((pl-lo)/pl*100,2) if lo else 999
        vals={"Upper":round(up,2),"Lower":round(lo,2),"Price":round(pl,2)}
        if (du<=0.5 or pl>=up) and sell_c: triggered=True;sig="SELL";cond_str=f"Upper Band Touch ({du}%)"
        elif (dl<=0.5 or pl<=lo) and buy_c: triggered=True;sig="BUY";cond_str=f"Lower Band Touch ({dl}%)"

    elif ind=="RSI":
        p=int(params.get("rsi_period",14)); cnd=params.get("rsi_condition","RSI > Value (Above)")
        val=float(params.get("rsi_value",60)); rsi=compute_rsi(prices,p)
        cur=float(rsi[-1]); prv=float(rsi[-2]) if n>1 else cur
        vals={f"RSI({p})":round(cur,2)}
        if "Above" in cnd and "Crosses" not in cnd: triggered=cur>val
        elif "Below" in cnd and "Crosses" not in cnd: triggered=cur<val
        elif "Crosses Above" in cnd: triggered=cur>val and prv<=val
        elif "Crosses Below" in cnd: triggered=cur<val and prv>=val
        sig="BUY" if buy_c else "SELL"

    elif "EMA Cross" in ind:
        ef=int(params.get("ema_fast",9)); es=int(params.get("ema_slow",21))
        ef_a=compute_ema(prices,ef); es_a=compute_ema(prices,es)
        triggered=(ef_a[-1]>es_a[-1] and ef_a[-2]<=es_a[-2]) if buy_c else (ef_a[-1]<es_a[-1] and ef_a[-2]>=es_a[-2])
        vals={f"EMA({ef})":round(float(ef_a[-1]),2),f"EMA({es})":round(float(es_a[-1]),2)}
        sig="BUY" if buy_c else "SELL"

    elif "MACD" in ind:
        mf=int(params.get("macd_fast",12)); ms_p=int(params.get("macd_slow",26))
        msig=int(params.get("macd_signal",9)); mc=params.get("macd_cond","MACD crosses ABOVE Signal (BUY)")
        ml=compute_ema(prices,mf)-compute_ema(prices,ms_p); sl=compute_ema(ml,msig)
        if "ABOVE" in mc: triggered=ml[-1]>sl[-1] and ml[-2]<=sl[-2]
        elif "BELOW" in mc: triggered=ml[-1]<sl[-1] and ml[-2]>=sl[-2]
        vals={"MACD":round(float(ml[-1]),4),"Signal":round(float(sl[-1]),4)}
        sig="BUY" if "ABOVE" in mc else "SELL"

    return triggered, sig, cond_str, vals

def send_telegram(tok, cid, text):
    try:
        r=requests.post(f"https://api.telegram.org/bot{tok}/sendMessage",
            json={"chat_id":cid,"text":text,"parse_mode":"HTML"},timeout=15)
        return r.status_code==200, r.json().get("description","") if r.status_code!=200 else "OK"
    except Exception as e:
        return False, str(e)

def main():
    print(f"\n{'='*50}")
    print(f"NW Band Scanner Alert Check: {datetime.now().strftime('%d-%b-%Y %H:%M')}")
    print(f"{'='*50}")

    if not TG_TOKEN or not TG_CHAT_ID:
        print("❌ TG_TOKEN/TG_CHAT_ID missing!"); return
    if not ALERTS_JSON:
        print("❌ ALERTS_JSON missing!"); return

    try:
        saved_alerts=json.loads(ALERTS_JSON)
    except Exception as e:
        print(f"❌ JSON parse error: {e}"); return

    active={k:v for k,v in saved_alerts.items() if v.get("active",True)}
    print(f"Active alerts: {len(active)}")
    if not active: return

    total=0
    for al_name,al_cfg in active.items():
        syms=al_cfg.get("symbols",[]); tfs=al_cfg.get("tf_list",[])
        print(f"\n📋 {al_name} | {len(syms)} stocks | {tfs}")
        for tf in tfs:
            if tf not in TIMEFRAMES: continue
            iv,per=TIMEFRAMES[tf]
            for sym in syms[:30]:
                print(f"  {sym} [{tf}]...", end=" ")
                df=fetch_data(sym,iv,per)
                if df.empty or len(df)<20: print("skip"); continue
                triggered,sig,cond_str,vals=check_condition(df,al_cfg)
                if triggered:
                    price=round(float(df["Close"].iloc[-1]),2)
                    ts=str(df.index[-1])[:16]
                    vals_str=" | ".join([f"{k}={v}" for k,v in vals.items()])
                    icon="📈" if sig=="BUY" else "📉"
                    s_ico="✅" if sig=="BUY" else "🔴"
                    msg=(f"{icon} <b>NW Band Scanner</b>\n━━━━━━━━━━━━━\n"
                         f"{s_ico} <b>{sig} SIGNAL</b>\n"
                         f"🏷 Alert: {al_name}\n📌 {sym}\n⏱ {tf}\n"
                         f"🎯 {cond_str}\n📊 {vals_str}\n"
                         f"💰 ₹{price:,}\n🕐 {ts}\n━━━━━━━━━━━━━")
                    ok,err=send_telegram(TG_TOKEN,TG_CHAT_ID,msg)
                    print(f"✅ {sig} sent!" if ok else f"⚠ TG failed: {err}")
                    total+=1
                else:
                    print("no signal")

    print(f"\n✅ Done! Total signals: {total}")

if __name__=="__main__":
    main()
