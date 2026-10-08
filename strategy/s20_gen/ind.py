# -*- coding: utf-8 -*-
"""ind.py — indicator library แบบ causal ล้วน (checklist ข้อ 1/3)

ทุกฟังก์ชันคืน Series ที่ค่า ณ แท่ง i ใช้ข้อมูลแท่ง <= i เท่านั้น (rolling/ewm ไปข้างหน้า ไม่มี center=True,
ไม่มี shift(-k), ไม่มี pivot ที่ต้องรู้แท่งขวาโดยไม่ delay). engine ตัดสินใจที่ "แท่ง i ปิดแล้ว" และเข้าไม้ที่ open
ของแท่ง i+1 เสมอ → เทียบเท่า shift(1) เมื่อมองจากแท่งที่เข้าไม้
pivot/fractal ที่ต้องใช้แท่งขวา k แท่ง ใช้ confirmed_pivot_* ซึ่งคืนค่า ณ แท่งที่ยืนยันแล้ว (i = pivot + k)
"""
import numpy as np
import pandas as pd


def sma(s, n):
    return s.rolling(n, min_periods=n).mean()


def ema(s, n):
    return s.ewm(span=n, adjust=False, min_periods=n).mean()


def rma(s, n):  # Wilder smoothing
    return s.ewm(alpha=1.0 / n, adjust=False, min_periods=n).mean()


def wma(s, n):
    w = np.arange(1, n + 1, dtype=float)
    return s.rolling(n, min_periods=n).apply(lambda x: np.dot(x, w) / w.sum(), raw=True)


def hma(s, n):
    return wma(2 * wma(s, n // 2) - wma(s, n), max(2, int(np.sqrt(n))))


def true_range(df):
    pc = df["close"].shift(1)
    return pd.concat([df["high"] - df["low"], (df["high"] - pc).abs(), (df["low"] - pc).abs()], axis=1).max(axis=1)


def atr(df, n=14):
    return rma(true_range(df), n)


def rsi(s, n=14):
    d = s.diff()
    up = rma(d.clip(lower=0), n)
    dn = rma((-d).clip(lower=0), n)
    return 100 - 100 / (1 + up / dn.replace(0, np.nan))


def stoch(df, n=14, k=3, d=3):
    ll = df["low"].rolling(n).min()
    hh = df["high"].rolling(n).max()
    raw = 100 * (df["close"] - ll) / (hh - ll).replace(0, np.nan)
    kk = raw.rolling(k).mean()
    return kk, kk.rolling(d).mean()


def dmi(df, n=14):
    up = df["high"].diff()
    dn = -df["low"].diff()
    pdm = pd.Series(np.where((up > dn) & (up > 0), up, 0.0), index=df.index)
    ndm = pd.Series(np.where((dn > up) & (dn > 0), dn, 0.0), index=df.index)
    tr = rma(true_range(df), n)
    pdi = 100 * rma(pdm, n) / tr
    ndi = 100 * rma(ndm, n) / tr
    dx = 100 * (pdi - ndi).abs() / (pdi + ndi).replace(0, np.nan)
    return pdi, ndi, rma(dx, n)


def cross_up(a, b):
    b = b if isinstance(b, pd.Series) else pd.Series(b, index=a.index)
    return (a > b) & (a.shift(1) <= b.shift(1))


def cross_dn(a, b):
    b = b if isinstance(b, pd.Series) else pd.Series(b, index=a.index)
    return (a < b) & (a.shift(1) >= b.shift(1))


def highest(s, n):
    return s.rolling(n, min_periods=n).max()


def lowest(s, n):
    return s.rolling(n, min_periods=n).min()


def confirmed_pivot_high(df, left=3, right=3):
    """คืน Series: ณ แท่ง i (= pivot + right) ให้ราคา pivot high ที่เพิ่งยืนยัน ไม่งั้น NaN (ไม่ repaint)"""
    h = df["high"]
    win = left + right + 1
    center_max = h.rolling(win).max()
    cand = h.shift(right)
    is_p = cand == center_max
    return cand.where(is_p)


def confirmed_pivot_low(df, left=3, right=3):
    l = df["low"]
    win = left + right + 1
    center_min = l.rolling(win).min()
    cand = l.shift(right)
    return cand.where(cand == center_min)


def body(df):
    return (df["close"] - df["open"]).abs()


def rng(df):
    return (df["high"] - df["low"]).replace(0, np.nan)


def day_key(df):
    return (df["time"] // 86400).astype(np.int64)


def week_key(df):
    # MT5 server time: week starts Sunday/Monday; shift by 4 days so weeks roll on Monday 00:00 (epoch=Thursday)
    return ((df["time"] // 86400 + 3) // 7).astype(np.int64)


def prev_period_hl(df, key):
    """ค่า high/low/close/open ของงวดก่อนหน้า (วัน/สัปดาห์) — ข้อมูลของงวดที่ปิดแล้วเท่านั้น"""
    g = df.groupby(key)
    agg = pd.DataFrame({"h": g["high"].max(), "l": g["low"].min(), "c": g["close"].last(), "o": g["open"].first()})
    prev = agg.shift(1)
    return (key.map(prev["h"]), key.map(prev["l"]), key.map(prev["c"]), key.map(prev["o"]))


def period_running(df, key):
    """high/low สะสมของงวดปัจจุบันจนถึงแท่ง i (รวมแท่ง i ที่ปิดแล้ว) และ open ของงวด"""
    g = df.groupby(key)
    return g["high"].cummax(), g["low"].cummin(), g["open"].transform("first")


def hour(df):
    return ((df["time"] % 86400) // 3600).astype(int)


def dow(df):
    return ((df["time"] // 86400 + 3) % 7).astype(int)  # 0=Mon


def linreg_slope(s, n):
    x = np.arange(n, dtype=float)
    xm = x.mean()
    den = ((x - xm) ** 2).sum()
    return s.rolling(n, min_periods=n).apply(lambda y: ((x - xm) * (y - y.mean())).sum() / den, raw=True)


def linreg_r2(s, n):
    return s.rolling(n, min_periods=n).apply(lambda y: np.corrcoef(np.arange(n), y)[0, 1] ** 2 if y.std() > 0 else 0.0, raw=True)


def zscore(s, n):
    return (s - sma(s, n)) / s.rolling(n, min_periods=n).std().replace(0, np.nan)


def sig_from(buy, sell):
    """รวม boolean buy/sell เป็น int8 {+1,-1,0}; ถ้าชนกันในแท่งเดียวให้ 0 (ไม่เดา)"""
    b = buy.fillna(False).to_numpy(dtype=bool)
    s = sell.fillna(False).to_numpy(dtype=bool)
    out = np.zeros(len(b), dtype=np.int8)
    out[b & ~s] = 1
    out[s & ~b] = -1
    return out


def macd(s, f=12, sl=26, sg=9):
    m = ema(s, f) - ema(s, sl)
    sig = ema(m, sg)
    return m, sig, m - sig


def bbands(s, n=20, k=2.0):
    mid = sma(s, n)
    sd = s.rolling(n, min_periods=n).std(ddof=0)
    return mid - k * sd, mid, mid + k * sd


def keltner(df, n=20, k=1.5, atr_n=None):
    mid = ema(df["close"], n)
    a = atr(df, atr_n or n)
    return mid - k * a, mid, mid + k * a


def heikin_ashi(df):
    hc = (df["open"] + df["high"] + df["low"] + df["close"]) / 4.0
    o = np.empty(len(df))
    ov, cv = df["open"].to_numpy(), hc.to_numpy()
    o[0] = (ov[0] + cv[0]) / 2.0
    for i in range(1, len(df)):
        o[i] = (o[i - 1] + cv[i - 1]) / 2.0
    ho = pd.Series(o, index=df.index)
    hh = pd.concat([df["high"], ho, hc], axis=1).max(axis=1)
    hl = pd.concat([df["low"], ho, hc], axis=1).min(axis=1)
    return ho, hh, hl, hc


def psar(df, step=0.02, mx=0.2):
    """Parabolic SAR แบบวนไปข้างหน้า (causal) คืน (sar, trend +1/-1)"""
    h, l = df["high"].to_numpy(), df["low"].to_numpy()
    n = len(h)
    sar = np.full(n, np.nan)
    tr = np.zeros(n, dtype=int)
    if n < 3:
        return pd.Series(sar, index=df.index), pd.Series(tr, index=df.index)
    up = True
    af, ep, s = step, h[0], l[0]
    for i in range(1, n):
        s = s + af * (ep - s)
        if up:
            s = min(s, l[i - 1], l[i - 2] if i > 1 else l[i - 1])
            if l[i] < s:
                up, s, ep, af = False, ep, l[i], step
            elif h[i] > ep:
                ep, af = h[i], min(mx, af + step)
        else:
            s = max(s, h[i - 1], h[i - 2] if i > 1 else h[i - 1])
            if h[i] > s:
                up, s, ep, af = True, ep, h[i], step
            elif l[i] < ep:
                ep, af = l[i], min(mx, af + step)
        sar[i] = s
        tr[i] = 1 if up else -1
    return pd.Series(sar, index=df.index), pd.Series(tr, index=df.index)


def period_key(df, tf):
    """งวดอ้างอิงสำหรับ pivot/level: วัน สำหรับ TF ≤ H1, สัปดาห์ สำหรับ H4, เดือน(~4 สัปดาห์) สำหรับ D1"""
    if tf in ("H4",):
        return week_key(df)
    if tf == "D1":
        return (week_key(df) // 4).astype(np.int64)
    return day_key(df)
