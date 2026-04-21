from config import *
from mt5_utils import get_structure, find_swing_tp
from datetime import datetime, timezone, timedelta

S5_ATR_MAX_MULT   = 2.5
S5_ZONE_BUFFER    = 1.5
S5_TREND_BARS     = 20
S5_NO_TRADE_HOURS = [(0, 3)]

def _ema(values, period):
    k = 2 / (period + 1)
    ema = values[0]
    for v in values[1:]:
        ema = v * k + ema * (1 - k)
    return ema

def _check_filters(rates, signal, entry, atr, ms, now_h):
    """คืน (ok, reason_fail)"""
    # 1. Time filter
    for (h_start, h_end) in S5_NO_TRADE_HOURS:
        if h_start <= now_h < h_end:
            return False, f"⏰ Time: {now_h:02d}:xx อยู่ใน no-trade ({h_start:02d}-{h_end:02d})"

    # 2. ATR filter
    recent_atrs = [float(rates[i]["high"]) - float(rates[i]["low"])
                   for i in range(-min(20, len(rates)), -1)]
    avg_atr = sum(recent_atrs) / len(recent_atrs) if recent_atrs else atr
    cur_range = float(rates[-1]["high"]) - float(rates[-1]["low"])
    if cur_range > avg_atr * S5_ATR_MAX_MULT:
        return False, f"📊 ATR: range {cur_range:.2f} > avg×{S5_ATR_MAX_MULT} ({avg_atr*S5_ATR_MAX_MULT:.2f})"

    # 3. Trend filter (EMA20)
    n = min(S5_TREND_BARS, len(rates) - 1)
    closes = [float(rates[i]["close"]) for i in range(-n - 1, -1)]
    if len(closes) >= S5_TREND_BARS:
        ema20 = _ema(closes, S5_TREND_BARS)
        last_close = float(rates[-2]["close"])
        if signal == "BUY" and last_close < ema20:
            return False, f"📉 Trend: Close {last_close:.2f} < EMA20 {ema20:.2f}"
        if signal == "SELL" and last_close > ema20:
            return False, f"📈 Trend: Close {last_close:.2f} > EMA20 {ema20:.2f}"

    # 4. Zone filter
    sh = ms["swing_high"]
    sl_z = ms["swing_low"]
    zone_buf = atr * S5_ZONE_BUFFER
    if signal == "BUY" and sh - entry < zone_buf:
        return False, f"🚧 Zone: ใกล้ Swing High {sh:.2f} (ห่าง {sh-entry:.2f} < {zone_buf:.2f})"
    if signal == "SELL" and entry - sl_z < zone_buf:
        return False, f"🚧 Zone: ใกล้ Swing Low {sl_z:.2f} (ห่าง {entry-sl_z:.2f} < {zone_buf:.2f})"

    return True, ""

def strategy_5(rates):
    """
    ท่าที่ 5 — Scalping (M1/M5/M15)
    Filters: Time / ATR / Trend(EMA20) / Zone(Swing H/L)
    BUY Momentum:  [1]🟢≥60% + [0]🟢 Open≥Close[1]
    BUY Reversal:  [2]🔴≥35% + [1]Doji/ตำหนิ + [0]🟢≥35% Close>High[1]
    SELL: สลับสี
    """
    if len(rates) < 25:
        return {"signal": "WAIT", "reason": "ข้อมูลไม่เพียงพอ"}

    def c(i):
        r = rates[i]
        o = float(r["open"]); h = float(r["high"])
        l = float(r["low"]);  cl = float(r["close"])
        return o, h, l, cl, cl > o

    o0,h0,l0,cl0,bull0 = c(-1)
    o1,h1,l1,cl1,bull1 = c(-2)
    o2,h2,l2,cl2,bull2 = c(-3)

    ms  = get_structure(rates)
    atr = ms["atr"]

    def bp(o,h,l,cl):
        rng = h-l
        return abs(cl-o)/rng if rng > 0 else 0

    now_h = (datetime.now(timezone.utc) + timedelta(hours=7)).hour

    candles = [
        {"open":o2,"high":h2,"low":l2,"close":cl2},
        {"open":o1,"high":h1,"low":l1,"close":cl1},
        {"open":o0,"high":h0,"low":l0,"close":cl0},
    ]

    # ── BUY Momentum ──────────────────────────────────────────
    bp1 = bp(o1,h1,l1,cl1); bp0 = bp(o0,h0,l0,cl0)
    if bull1 and bp1 >= 0.60 and bull0 and o0 >= cl1 - atr*0.1:
        entry = round(o0, 2)
        sl    = round(min(l0,l1) - atr*0.5, 2)
        tp    = round(entry + atr*1.0, 2)
        rr    = round((tp-entry)/(entry-sl), 2) if entry > sl else 0
        ok, fail = _check_filters(rates, "BUY", entry, atr, ms, now_h)
        if not ok:
            return {"signal": "WAIT", "reason": f"[ท่า5 BUY Momentum] {fail}"}
        return {
            "signal": "BUY", "pattern": "ท่าที่ 5 Scalping 🟠 BUY — Momentum",
            "entry": entry, "sl": sl, "tp": tp,
            "reason": (f"[1]🟢 body:{bp1*100:.0f}% [0]🟢 Open:{o0:.2f}≥Close[1]:{cl1:.2f} body:{bp0*100:.0f}%\n"
                       f"EMA20✅ Zone✅ ATR✅ | Entry:{entry} SL:{sl} TP:{tp} RR1:{rr}"),
            "candles": candles, "swing_high": ms["swing_high"], "swing_low": ms["swing_low"],
        }

    # ── BUY Reversal ──────────────────────────────────────────
    body2 = bp(o2,h2,l2,cl2); body1 = bp(o1,h1,l1,cl1); body0 = bp(o0,h0,l0,cl0)
    is_doji1     = body1 < 0.15
    is_tahnit1   = (not bull1) and l1 < l2 and l2 <= cl1 <= h2
    is_tahnit1_up = bull1 and h1 > h2 and l2 <= cl1 <= h2
    confirm_buy  = bull0 and body0 >= 0.35 and cl0 > h1

    if not bull2 and body2 >= 0.35 and (is_doji1 or is_tahnit1 or is_tahnit1_up) and confirm_buy:
        entry = round(l1 + (h1-l1)*0.5, 2)
        sl    = round(l1 - atr*0.5, 2)
        tp    = round(entry + atr*1.5, 2)
        rr    = round((tp-entry)/(entry-sl), 2) if entry > sl else 0
        kind  = "Doji" if is_doji1 else "ตำหนิ"
        ok, fail = _check_filters(rates, "BUY", entry, atr, ms, now_h)
        if not ok:
            return {"signal": "WAIT", "reason": f"[ท่า5 BUY Reversal] {fail}"}
        return {
            "signal": "BUY", "pattern": "ท่าที่ 5 Scalping 🟠 BUY — Reversal",
            "entry": entry, "sl": sl, "tp": tp,
            "reason": (f"[2]🔴 body:{body2*100:.0f}% [1]{kind} [0]🟢 body:{body0*100:.0f}% Close:{cl0:.2f}>High[1]:{h1:.2f}\n"
                       f"EMA20✅ Zone✅ ATR✅ | Entry:{entry} SL:{sl} TP:{tp} RR1:{rr}"),
            "candles": candles, "swing_high": ms["swing_high"], "swing_low": ms["swing_low"],
        }

    # ── SELL Momentum ─────────────────────────────────────────
    bp1s = bp(o1,h1,l1,cl1); bp0s = bp(o0,h0,l0,cl0)
    if (not bull1) and bp1s >= 0.60 and (not bull0) and o0 <= cl1 + atr*0.1:
        entry = round(o0, 2)
        sl    = round(max(h0,h1) + atr*0.5, 2)
        tp    = round(entry - atr*1.0, 2)
        rr    = round((entry-tp)/(sl-entry), 2) if sl > entry else 0
        ok, fail = _check_filters(rates, "SELL", entry, atr, ms, now_h)
        if not ok:
            return {"signal": "WAIT", "reason": f"[ท่า5 SELL Momentum] {fail}"}
        return {
            "signal": "SELL", "pattern": "ท่าที่ 5 Scalping 🟠 SELL — Momentum",
            "entry": entry, "sl": sl, "tp": tp,
            "reason": (f"[1]🔴 body:{bp1s*100:.0f}% [0]🔴 Open:{o0:.2f}≤Close[1]:{cl1:.2f} body:{bp0s*100:.0f}%\n"
                       f"EMA20✅ Zone✅ ATR✅ | Entry:{entry} SL:{sl} TP:{tp} RR1:{rr}"),
            "candles": candles, "swing_high": ms["swing_high"], "swing_low": ms["swing_low"],
        }

    # ── SELL Reversal ─────────────────────────────────────────
    is_doji1_s    = body1 < 0.15
    is_tahnit1_s  = bull1 and h1 > h2 and l2 <= cl1 <= h2
    is_tahnit1_sd = (not bull1) and l1 < l2 and l2 <= cl1 <= h2
    confirm_sell  = (not bull0) and body0 >= 0.35 and cl0 < l1

    if bull2 and body2 >= 0.35 and (is_doji1_s or is_tahnit1_s or is_tahnit1_sd) and confirm_sell:
        entry = round(h1 - (h1-l1)*0.5, 2)
        sl    = round(h1 + atr*0.5, 2)
        tp    = round(entry - atr*1.5, 2)
        rr    = round((entry-tp)/(sl-entry), 2) if sl > entry else 0
        kind  = "Doji" if is_doji1_s else "ตำหนิ"
        ok, fail = _check_filters(rates, "SELL", entry, atr, ms, now_h)
        if not ok:
            return {"signal": "WAIT", "reason": f"[ท่า5 SELL Reversal] {fail}"}
        return {
            "signal": "SELL", "pattern": "ท่าที่ 5 Scalping 🟠 SELL — Reversal",
            "entry": entry, "sl": sl, "tp": tp,
            "reason": (f"[2]🟢 body:{body2*100:.0f}% [1]{kind} [0]🔴 body:{body0*100:.0f}% Close:{cl0:.2f}<Low[1]:{l1:.2f}\n"
                       f"EMA20✅ Zone✅ ATR✅ | Entry:{entry} SL:{sl} TP:{tp} RR1:{rr}"),
            "candles": candles, "swing_high": ms["swing_high"], "swing_low": ms["swing_low"],
        }

    return {"signal": "WAIT", "reason": "ไม่พบ Scalping Setup"}
