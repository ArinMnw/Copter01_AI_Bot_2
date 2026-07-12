# -*- coding: utf-8 -*-
"""
S109: The Harmonic Geometry — Fibonacci Sniper (Gartley / Bat / Butterfly ที่จุด D)

ทำไมถึงขุด Edge ใหม่ได้โดยไม่แคร์ความล้มเหลวของ ML (S108):
  S108 ล้มเหลวเพราะให้โมเดล "หา pattern เอง" จาก feature หยาบ — มันหาไม่เจอ
  S109 กลับด้าน: มนุษย์รู้ pattern อยู่แล้ว (สัดส่วน Fibonacci ของ harmonic
  ที่ traders ทั่วโลกเฝ้าจุดเดียวกัน = self-fulfilling zone) เราแค่เขียน
  คณิตศาสตร์จับให้เป๊ะระดับทศนิยม
  ต่างจาก S99-S107: ไม่มีตัวไหนใช้ "สัดส่วนระหว่าง legs" เป็นเงื่อนไขเลย
  (S99-S101 ดู sweep, S102/S106 ดูกรอบ, S104 ดู structure break, S107 ดูโซน)
  Harmonic คือมิติ "รูปทรง" ล้วนๆ และ entry เป็น LIMIT ดักที่ D ล่วงหน้า

ตรรกะ:
  1. ZigZag pivots (left/right = PIVOT) → ลำดับสลับ X-A-B-C ที่ยืนยันแล้ว
     bullish: X(low) A(high) B(low) C(high) → D(low ข้างหน้า) / bearish กลับด้าน
  2. เช็คสัดส่วน:  AB/XA อยู่ในช่วงของ pattern ± TOL
                    BC/AB อยู่ 0.382-0.886 (ทุก pattern)
  3. คำนวณจุด D จาก AD/XA ratio ของ pattern → ตั้ง LIMIT ที่ D (PRZ)
     เงื่อนไข: ราคาปัจจุบันยังไม่ถึง D (กำลังวิ่ง leg CD) และ C เพิ่งยืนยัน (fresh)
  4. SL = เลย D ออกไป SL_XA_PCT ของ XA / TP = ดีดกลับ TP_AD_PCT ของ AD
  5. กฎ Reality Check ครบ: pivot ยืนยันด้วยแท่งปิดแล้วเท่านั้น, limit + spread,
     SL-first (ฝั่ง sim)

Patterns (จุด B และ D คือตัวจำแนก):
  Gartley:   AB/XA ~ 0.618, D = 0.786 XA (D อยู่เหนือ X)
  Bat:       AB/XA 0.382-0.50, D = 0.886 XA (D อยู่เหนือ X, ลึกกว่า Gartley)
  Butterfly: AB/XA ~ 0.786, D = 1.27 XA (D ทะลุ X — sweep แล้วกลับ)
"""

PATTERNS = {
    "Gartley":   {"AB_XA": (0.618, 0.618), "AD_XA": 0.786},
    "Bat":       {"AB_XA": (0.382, 0.500), "AD_XA": 0.886},
    "Butterfly": {"AB_XA": (0.786, 0.786), "AD_XA": 1.270},
}

DEFAULT_CFG = {
    "PIVOT_LEFT": 4,   # sweep: 4/4 ชนะ 3/3 (pattern ใหญ่ขึ้น สัญญาณสะอาดขึ้น)
    "PIVOT_RIGHT": 4,
    "SWING_SCAN_BARS": 120,
    "RATIO_TOL": 0.06,        # ค่าเผื่อของ AB/XA รอบค่ากลาง pattern
    "BC_AB_MIN": 0.382,
    "BC_AB_MAX": 0.886,
    "MIN_XA_ATR": 3.0,        # ขนาด leg XA ขั้นต่ำ (x ATR) — pattern จิ๋วไม่มีความหมาย
    "C_FRESH_BARS": 30,       # C ต้องยืนยันมาไม่เกิน N แท่ง
    "SL_XA_PCT": 0.10,        # SL เลย D ออกไป k ของ XA (sweep: 0.10 > 0.15 > 0.25)
    "TP_AD_PCT": 0.382,       # TP ดีดกลับ k ของ AD จาก D
    "PATTERNS_ENABLED": ("Gartley", "Bat", "Butterfly"),
    "TIME_FILTER_ENABLED": True,
    "BLOCK_HOURS": (4, 5, 6),
    "ML_FILTER_ENABLED": False,
    "ML_SCORE_THRESHOLD": 0.55,
}


def _atr(rates, period=14):
    trs = []
    for i in range(len(rates) - period, len(rates)):
        h, l = float(rates[i]["high"]), float(rates[i]["low"])
        pc = float(rates[i - 1]["close"])
        trs.append(max(h - l, abs(h - pc), abs(l - pc)))
    return sum(trs) / len(trs)


def _zigzag_pivots(rates, left, right, scan_bars):
    """คืนลำดับ pivot สลับ high/low: [(idx, price, 'H'|'L'), ...] เรียงตามเวลา
    ถ้า pivot ชนิดเดียวกันติดกัน เก็บตัว extreme กว่า"""
    n = len(rates)
    raw = []
    start = max(left, n - scan_bars)
    for i in range(start, n - right):
        h = float(rates[i]["high"])
        l = float(rates[i]["low"])
        if all(float(rates[j]["high"]) < h for j in range(i - left, i + right + 1) if j != i):
            raw.append((i, h, "H"))
        if all(float(rates[j]["low"]) > l for j in range(i - left, i + right + 1) if j != i):
            raw.append((i, l, "L"))
    raw.sort(key=lambda p: p[0])
    zz = []
    for p in raw:
        if zz and zz[-1][2] == p[2]:
            if (p[2] == "H" and p[1] >= zz[-1][1]) or (p[2] == "L" and p[1] <= zz[-1][1]):
                zz[-1] = p
        else:
            zz.append(p)
    return zz


def detect_s109(rates, tf="", dt_bkk=None, cfg=None, **kwargs):
    c = dict(DEFAULT_CFG)
    if cfg:
        c.update(cfg)

    if len(rates) < 150:
        return {"signal": "WAIT", "reason": "Not enough data"}

    if c["TIME_FILTER_ENABLED"] and dt_bkk is not None:
        if dt_bkk.hour in c["BLOCK_HOURS"]:
            return {"signal": "WAIT", "reason": f"Blocked hour {dt_bkk.hour}"}

    atr = _atr(rates)
    if atr <= 0:
        return {"signal": "WAIT", "reason": "ATR zero"}

    zz = _zigzag_pivots(rates, int(c["PIVOT_LEFT"]), int(c["PIVOT_RIGHT"]),
                        int(c["SWING_SCAN_BARS"]))
    if len(zz) < 4:
        return {"signal": "WAIT", "reason": "Not enough pivots"}

    n = len(rates)
    x_p, a_p, b_p, c_p = zz[-4], zz[-3], zz[-2], zz[-1]

    # C ต้องสด (เพิ่งยืนยัน) — กัน emit ซ้ำและ pattern ค้างคืน
    if (n - 1) - c_p[0] > int(c["C_FRESH_BARS"]):
        return {"signal": "WAIT", "reason": "C pivot stale"}

    last_close = float(rates[-1]["close"])
    tol = float(c["RATIO_TOL"])

    def _ml_ok(direction, entry):
        if not c["ML_FILTER_ENABLED"]:
            return True, 1.0
        import ml_scoring
        prob = ml_scoring.score_signal('XAUUSD.iux', tf, direction, entry,
                                       dt_bkk, historical_rates=rates)
        return prob >= float(c["ML_SCORE_THRESHOLD"]), prob

    def _check(direction):
        """direction BUY: X=L, A=H, B=L, C=H → D ต่ำกว่า / SELL กลับด้าน"""
        want = ("L", "H", "L", "H") if direction == "BUY" else ("H", "L", "H", "L")
        if (x_p[2], a_p[2], b_p[2], c_p[2]) != want:
            return None
        X, A, B, C = x_p[1], a_p[1], b_p[1], c_p[1]
        xa = abs(A - X)
        ab = abs(A - B)
        bc = abs(C - B)
        if xa <= 0 or ab <= 0 or bc <= 0:
            return None
        if xa < atr * float(c["MIN_XA_ATR"]):
            return None
        ab_xa = ab / xa
        bc_ab = bc / ab
        if not (float(c["BC_AB_MIN"]) <= bc_ab <= float(c["BC_AB_MAX"])):
            return None
        for name in c["PATTERNS_ENABLED"]:
            spec = PATTERNS[name]
            lo, hi = spec["AB_XA"]
            if not (lo - tol <= ab_xa <= hi + tol):
                continue
            ad = spec["AD_XA"] * xa
            D = A - ad if direction == "BUY" else A + ad
            # ราคาต้องยังไม่ถึง D (กำลังวิ่ง leg CD เข้าหา) และ D อยู่ฝั่งถูกของราคา
            if direction == "BUY":
                if last_close <= D:
                    continue
                sl = D - xa * float(c["SL_XA_PCT"])
                tp = D + ad * float(c["TP_AD_PCT"])
            else:
                if last_close >= D:
                    continue
                sl = D + xa * float(c["SL_XA_PCT"])
                tp = D - ad * float(c["TP_AD_PCT"])
            return name, D, sl, tp, ab_xa, bc_ab
        return None

    for direction in ("BUY", "SELL"):
        hit = _check(direction)
        if hit:
            name, D, sl, tp, ab_xa, bc_ab = hit
            risk = abs(D - sl)
            reward = abs(tp - D)
            if risk <= 0 or reward <= 0:
                continue
            ok, prob = _ml_ok(direction, D)
            if not ok:
                return {"signal": "WAIT", "reason": f"blocked by ML ({prob:.2f})"}
            return {
                "signal": direction,
                "entry": round(D, 2),
                "sl": round(sl, 2),
                "tp": round(tp, 2),
                "order_type": "limit",
                "pattern": f"S109 {name} {'🟢 BUY' if direction == 'BUY' else '🔴 SELL'}",
                "reason": (f"{name} @D (AB/XA {ab_xa:.3f}, BC/AB {bc_ab:.3f}, "
                           f"AD={PATTERNS[name]['AD_XA']}XA)"),
                "candles": [rates[-1]],
            }

    return {"signal": "WAIT", "reason": "No harmonic pattern forming"}
