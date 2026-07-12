# -*- coding: utf-8 -*-
"""
S108: The Black Box — Pure Machine Learning Alpha (Statistical Features + RandomForest)

ทำไมไม่แย่งออเดอร์กับ S99-S107:
  ทั้ง 9 ตัวแรกตัดสินใจด้วย "กฎที่มนุษย์เขียน" (sweep/box/OB/fakeout)
  S108 ไม่มีกฎ price action เลยแม้แต่ข้อเดียว — มันอ่าน "สถานะเชิงสถิติ"
  ของตลาด (Z-score, BB width, ADX, RSI, ระยะห่างจาก EMA, ชั่วโมง)
  แล้วให้ RandomForest ของระบบ (ml_scoring.py) เป็นคนเคาะ BUY/SELL 100%
  → มันอาจยิงในจังหวะที่ไม่มี pattern ใดๆ ที่ตาคนมองออก

สถาปัตยกรรม:
  1. ทุกแท่งปิด สร้าง feature vector 9 ตัว (ฟอร์แมตเดียวกับ ml_scoring.extract_features)
     สองชุด: สมมుติ BUY และสมมติ SELL
  2. ส่งเข้า ml_scoring.predict_success_probability → prob_buy, prob_sell
  3. เข้าเทรดเมื่อ prob ฝั่งชนะ >= ML_THRESHOLD และทิ้งห่างอีกฝั่ง >= MIN_EDGE
     (ต้อง "มั่นใจและเด็ดขาด" — ไม่ใช่ 0.51 vs 0.49)
  4. SL/TP เป็น ATR-based ล้วน (ไม่มีโครงสร้างราคา): SL = k×ATR, TP = RR×SL
  5. Volatility guard ขั้นต่ำเดียว: ATR ต้องไม่ต่ำผิดปกติ (ตลาดตายโมเดลมั่วง่าย)

⚠️ หมายเหตุความซื่อสัตย์ (สำคัญ):
  - live: ใช้ ml_model.pkl ของระบบผ่าน ml_scoring โดยตรง
  - backtest: ห้ามใช้ ml_model.pkl (เทรนจากอนาคตของช่วงทดสอบ = leakage)
    sim_s108_backtest.py จึงเทรน RandomForest แบบ walk-forward ในตัว
    (เรียนจากอดีตของ timeline เท่านั้น, retrain เป็นช่วงๆ) ด้วย feature เดียวกัน
"""

DEFAULT_CFG = {
    "FEATURES": "v2",          # "v1" = ชุด ml_scoring เดิม / "v2" = ชุด stationary ใหม่
    "ML_THRESHOLD": 0.55,
    "MIN_EDGE": 0.05,          # prob ฝั่งชนะต้องทิ้งอีกฝั่ง >= ค่านี้
    "SL_ATR_MULT": 1.5,
    "TP_RR": 1.0,
    "MIN_ATR": 2.0,            # ATR ขั้นต่ำ (จุด) กันตลาดตาย
    "TIME_FILTER_ENABLED": True,
    "BLOCK_HOURS": (4, 5, 6),
    "V2_MODEL_PATH": "s108_model.pkl",  # โมเดล v2 สำหรับ live (เทรนจาก sim walk-forward ล่าสุด)
}


def _atr(rates, period=14):
    trs = []
    for i in range(len(rates) - period, len(rates)):
        h, l = float(rates[i]["high"]), float(rates[i]["low"])
        pc = float(rates[i - 1]["close"])
        trs.append(max(h - l, abs(h - pc), abs(l - pc)))
    return sum(trs) / len(trs)


# ---------------------------------------------------------------------------
# Feature set v2 — ทุกตัว "stationary" (normalize ด้วย ATR / ratio)
# บทเรียนจาก v1: ema_dist / atr หน่วยดอลลาร์ดิบ → ราคาทองเปลี่ยนระดับแล้วโมเดลเทียบอดีตไม่ได้
# ---------------------------------------------------------------------------
FEAT_V2_KEYS = [
    "hour", "is_buy", "is_sell",
    "rsi14", "z20", "bbw", "adx14",
    "vol_z", "vel5", "acc5",
    "body_ratio", "upwick_ratio", "lowick_ratio",
    "pos100", "atr_ratio",
]


def extract_features_v2(rates, hour):
    """คำนวณ feature เชิงสถิติจากแท่งที่ปิดแล้วล้วนๆ (ต้องการ >= 110 แท่ง)
    คืน dict ที่ยังไม่ใส่ is_buy/is_sell (caller เติมเอง)"""
    n = len(rates)
    closes = [float(r["close"]) for r in rates]
    vols = [float(r["tick_volume"]) for r in rates]

    atr14 = _atr(rates, 14)
    if atr14 <= 0:
        return None

    # RSI14 (Wilder)
    gains, losses = [], []
    for i in range(n - 40, n):
        d = closes[i] - closes[i - 1]
        gains.append(max(d, 0.0))
        losses.append(max(-d, 0.0))
    avg_g = sum(gains[:14]) / 14
    avg_l = sum(losses[:14]) / 14
    for i in range(14, len(gains)):
        avg_g = (avg_g * 13 + gains[i]) / 14
        avg_l = (avg_l * 13 + losses[i]) / 14
    rsi14 = 100.0 if avg_l == 0 else 100.0 - 100.0 / (1.0 + avg_g / avg_l)

    # Z-score 20 + BB width
    w = closes[-20:]
    sma20 = sum(w) / 20
    var = sum((x - sma20) ** 2 for x in w) / 20
    std20 = var ** 0.5
    z20 = (closes[-1] - sma20) / std20 if std20 > 0 else 0.0
    bbw = (4 * std20) / sma20 if sma20 > 0 else 0.0

    # ADX14 (อย่างง่าย)
    plus_dm, minus_dm, trs = [], [], []
    for i in range(n - 30, n):
        up = float(rates[i]["high"]) - float(rates[i - 1]["high"])
        dn = float(rates[i - 1]["low"]) - float(rates[i]["low"])
        plus_dm.append(up if (up > dn and up > 0) else 0.0)
        minus_dm.append(dn if (dn > up and dn > 0) else 0.0)
        h, l = float(rates[i]["high"]), float(rates[i]["low"])
        pc = float(rates[i - 1]["close"])
        trs.append(max(h - l, abs(h - pc), abs(l - pc)))
    dxs = []
    for k in range(14, len(trs) + 1):
        tr14 = sum(trs[k - 14:k])
        if tr14 <= 0:
            continue
        pdi = 100 * sum(plus_dm[k - 14:k]) / tr14
        mdi = 100 * sum(minus_dm[k - 14:k]) / tr14
        if pdi + mdi > 0:
            dxs.append(100 * abs(pdi - mdi) / (pdi + mdi))
    adx14 = sum(dxs[-14:]) / len(dxs[-14:]) if dxs else 25.0

    # Volume z-score (50)
    vw = vols[-50:]
    vmean = sum(vw) / 50
    vvar = sum((x - vmean) ** 2 for x in vw) / 50
    vstd = vvar ** 0.5
    vol_z = (vols[-1] - vmean) / vstd if vstd > 0 else 0.0

    # Velocity / acceleration (หน่วย ATR)
    vel5 = (closes[-1] - closes[-6]) / atr14
    vel5_prev = (closes[-6] - closes[-11]) / atr14
    acc5 = vel5 - vel5_prev

    # Candle anatomy ของแท่งล่าสุด
    o, c = float(rates[-1]["open"]), closes[-1]
    h, l = float(rates[-1]["high"]), float(rates[-1]["low"])
    rng = max(h - l, 1e-9)
    body_ratio = abs(c - o) / rng
    upwick_ratio = (h - max(o, c)) / rng
    lowick_ratio = (min(o, c) - l) / rng

    # ตำแหน่งใน range 100 แท่ง (premium/discount)
    h100 = max(float(r["high"]) for r in rates[-100:])
    l100 = min(float(r["low"]) for r in rates[-100:])
    pos100 = (c - l100) / (h100 - l100) if h100 > l100 else 0.5

    # Volatility regime (ratio — ไม่ใช่ ATR ดิบ)
    atr50 = _atr(rates, 50) if n >= 60 else atr14
    atr_ratio = atr14 / atr50 if atr50 > 0 else 1.0

    return {
        "hour": hour, "rsi14": rsi14, "z20": z20, "bbw": bbw, "adx14": adx14,
        "vol_z": vol_z, "vel5": vel5, "acc5": acc5,
        "body_ratio": body_ratio, "upwick_ratio": upwick_ratio,
        "lowick_ratio": lowick_ratio, "pos100": pos100, "atr_ratio": atr_ratio,
    }


def detect_s108(rates, tf="", dt_bkk=None, cfg=None, scorer=None, **kwargs):
    """scorer: ฟังก์ชัน (features)->prob สำหรับ backtest walk-forward
    ถ้า None จะใช้ ml_scoring ของระบบ (live mode)"""
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)

    if len(rates) < 100:
        return {"signal": "WAIT", "reason": "Not enough data"}

    if c["TIME_FILTER_ENABLED"] and dt_bkk is not None:
        if dt_bkk.hour in c["BLOCK_HOURS"]:
            return {"signal": "WAIT", "reason": f"Blocked hour {dt_bkk.hour}"}

    atr = _atr(rates)
    if atr < float(c["MIN_ATR"]):
        return {"signal": "WAIT", "reason": f"ATR too low ({atr:.2f})"}

    last_close = float(rates[-1]["close"])

    if c.get("FEATURES") == "v2":
        base = extract_features_v2(rates, dt_bkk.hour if dt_bkk else 12)
        if base is None:
            return {"signal": "WAIT", "reason": "Features not ready"}
        feat_buy = dict(base, is_buy=1, is_sell=0)
        feat_sell = dict(base, is_buy=0, is_sell=1)
        if scorer is not None:
            prob_buy = scorer(feat_buy)
            prob_sell = scorer(feat_sell)
        else:
            # live mode: โหลดโมเดล v2 ของ S108 เอง (ไม่ใช้ ml_model.pkl ของระบบ)
            import os
            try:
                import joblib
            except ImportError:
                return {"signal": "WAIT", "reason": "joblib not available"}
            path = c["V2_MODEL_PATH"]
            if not os.path.exists(path):
                return {"signal": "WAIT", "reason": f"No v2 model ({path})"}
            model = joblib.load(path)
            prob_buy = float(model.predict_proba(
                [[feat_buy[k] for k in FEAT_V2_KEYS]])[0][1])
            prob_sell = float(model.predict_proba(
                [[feat_sell[k] for k in FEAT_V2_KEYS]])[0][1])
    else:
        import ml_scoring
        feat_buy = ml_scoring.extract_features(
            "XAUUSD.iux", tf, "BUY", last_close, dt_bkk, historical_rates=rates)
        feat_sell = dict(feat_buy)
        feat_sell["is_buy"], feat_sell["is_sell"] = 0, 1
        if scorer is not None:
            prob_buy = scorer(feat_buy)
            prob_sell = scorer(feat_sell)
        else:
            prob_buy = ml_scoring.predict_success_probability(feat_buy)
            prob_sell = ml_scoring.predict_success_probability(feat_sell)

    if prob_buy is None or prob_sell is None:
        return {"signal": "WAIT", "reason": "Model not ready"}

    th = float(c["ML_THRESHOLD"])
    edge = float(c["MIN_EDGE"])
    direction = None
    if prob_buy >= th and prob_buy - prob_sell >= edge:
        direction = "BUY"
        prob = prob_buy
    elif prob_sell >= th and prob_sell - prob_buy >= edge:
        direction = "SELL"
        prob = prob_sell
    if direction is None:
        return {"signal": "WAIT",
                "reason": f"No ML conviction (B {prob_buy:.2f} / S {prob_sell:.2f})"}

    sl_dist = atr * float(c["SL_ATR_MULT"])
    if direction == "BUY":
        entry = last_close
        sl = entry - sl_dist
        tp = entry + sl_dist * float(c["TP_RR"])
    else:
        entry = last_close
        sl = entry + sl_dist
        tp = entry - sl_dist * float(c["TP_RR"])

    return {
        "signal": direction,
        "entry": round(entry, 2),
        "sl": round(sl, 2),
        "tp": round(tp, 2),
        "order_type": "market",
        "pattern": f"S108 Black Box {'🟢 BUY' if direction == 'BUY' else '🔴 SELL'}",
        "reason": f"ML conviction {prob:.2f} (B {prob_buy:.2f} / S {prob_sell:.2f})",
        "candles": [rates[-1]],
        "ml_prob": prob,
    }
