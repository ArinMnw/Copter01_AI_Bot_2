import config
from config import *
from mt5_utils import get_structure, find_swing_tp
from strategy4 import _find_prev_pivot_swing_high, _find_prev_pivot_swing_low
from entry_calculator import (
    calc_tp_sl_s1_buy_A, calc_tp_sl_s1_sell_A,
    calc_tp_sl_s1_buy_B, calc_tp_sl_s1_sell_B,
    calc_tp_sl_s1_buy_C, calc_tp_sl_s1_sell_C,
)


def _get_s1_structure(rates):
    ms = get_structure(rates)
    left = max(1, int(getattr(config, "SWING_PIVOT_LEFT", 15) or 15))
    right = max(1, int(getattr(config, "SWING_PIVOT_RIGHT", 10) or 10))
    lookback = len(rates)

    sh_info = _find_prev_pivot_swing_high(rates, lookback=lookback, left=left, right=right)
    sl_info = _find_prev_pivot_swing_low(rates, lookback=lookback, left=left, right=right)

    if sh_info:
        ms["swing_high"] = float(sh_info["price"])
    if sl_info:
        ms["swing_low"] = float(sl_info["price"])
    return ms


def _attach_s1_zone_meta(payload: dict, use_zone: bool, signal: str, zone_price: float, swing_price: float, zone_ok: bool):
    payload["s1_zone_meta"] = {
        "enabled": bool(use_zone),
        "signal": str(signal or ""),
        "zone_price": round(float(zone_price), 2),
        "swing_price": round(float(swing_price), 2),
        "zone_ok_initial": bool(zone_ok),
    }
    return payload


def evaluate_s1_zone_status(rates, signal: str, zone_price: float) -> dict:
    use_zone = (S1_ZONE_MODE == "zone")
    if not use_zone:
        return {
            "enabled": False,
            "in_zone": True,
            "zone_price": float(zone_price),
            "swing_price": 0.0,
            "boundary_price": 0.0,
            "buf": 0.0,
        }

    ms = _get_s1_structure(rates)
    swing_high = float(ms["swing_high"])
    swing_low = float(ms["swing_low"])
    buf = float(ms["atr"]) * ZONE_BUFFER

    if str(signal or "").upper() == "BUY":
        boundary_price = swing_low + buf
        in_zone = float(zone_price) <= boundary_price
        swing_price = swing_low
    else:
        boundary_price = swing_high - buf
        in_zone = float(zone_price) >= boundary_price
        swing_price = swing_high

    return {
        "enabled": True,
        "in_zone": bool(in_zone),
        "zone_price": float(zone_price),
        "swing_price": float(swing_price),
        "boundary_price": float(boundary_price),
        "buf": float(buf),
    }

def strategy_1(rates):
    if len(rates) < 3:
        return {"signal": "WAIT", "reason": "ข้อมูลไม่เพียงพอ"}

    def c(i):
        r = rates[i]
        o, h, l, cl = float(r['open']), float(r['high']), float(r['low']), float(r['close'])
        return o, h, l, cl, cl > o

    o0,h0,l0,cl0,bull0 = c(-1)
    o1,h1,l1,cl1,bull1 = c(-2)
    o2,h2,l2,cl2,bull2 = c(-3)
    engulf_gap = engulf_min_price()
    has_c3 = len(rates) >= 4
    if has_c3:
        o3,h3,l3,cl3,bull3 = c(-4)

    ms   = _get_s1_structure(rates)
    sh   = ms["swing_high"]
    sl_z = ms["swing_low"]
    atr  = ms["atr"]
    buf  = atr * ZONE_BUFFER
    zone_low_3 = min(l0, l1, l2)
    zone_high_3 = max(h0, h1, h2)
    if has_c3:
        zone_low_4 = min(l0, l1, l2, l3)
        zone_high_4 = max(h0, h1, h2, h3)

    # Zone mode: "zone" = ตรวจ zone ปกติ, "normal" = ไม่สนใจ zone
    use_zone = (S1_ZONE_MODE == "zone")

    def bull_engulf(close_price, ref_high):
        return close_price > (ref_high + engulf_gap)

    def bear_engulf(close_price, ref_low):
        return close_price < (ref_low - engulf_gap)

    # ── Doji check แท่ง[0] ──────────────────────────────
    body0  = abs(cl0 - o0)
    range0 = h0 - l0
    if range0 > 0 and body0 < range0 * 0.15:
        return {"signal": "WAIT", "reason": "❌ แท่ง[0] Doji"}

    # ── Marubozu check แท่ง[0] ──────────────────────────
    # BUY  → เขียวตัน ไม่มีไส้บน (<5%) = momentum หมด → ยกเลิก
    # SELL → แดงตัน ไม่มีไส้ล่าง (<5%) = momentum หมด → ยกเลิก
    # ยกเว้น: ถ้าแท่ง[-1] (แท่งถัดจาก[0]) กลืนกิน/ตำหนิ/ย้อนโครงสร้าง
    #         ทิศทางเดิมและปิดในทิศทางนั้น → ใช้แท่ง[-1] เป็น [0] ใหม่
    # ปิดเงื่อนไข marubozu ชั่วคราว แต่เก็บโค้ดเดิมไว้
    if False and range0 > 0:
        wick_top    = h0 - max(o0, cl0)
        wick_bottom = min(o0, cl0) - l0
        is_buy_maru  = bull0 and wick_top < range0 * 0.05
        is_sell_maru = (not bull0) and wick_bottom < range0 * 0.05

        if is_buy_maru or is_sell_maru:
            # ── BUY: [0] เขียวตัน ────────────────────────────────
            # แท่ง[next] ต้องกลืนกิน [0] (Close[next] > High[0]) และปิดเขียว
            # ถ้าใช่ → ส่ง WAIT ให้ scan รอบถัดไปตรวจใหม่ทั้งหมด
            # (Bot จะ scan แท่งถัดมาในรอบ scan ถัดไปตามปกติ)
            if is_buy_maru:
                return {
                    "signal": "WAIT",
                    "reason": (
                        "\u23f3 BUY: [0] \u0e40\u0e02\u0e35\u0e22\u0e27\u0e15\u0e31\u0e19 \u0e44\u0e21\u0e48\u0e21\u0e35\u0e44\u0e2a\u0e49\u0e1a\u0e19\n"
                        "\u0e23\u0e2d\u0e41\u0e17\u0e48\u0e07\u0e16\u0e31\u0e14\u0e21\u0e32\u0e01\u0e25\u0e37\u0e19\u0e01\u0e34\u0e19 (Close > High[0]) \u0e41\u0e25\u0e30\u0e1b\u0e34\u0e14\u0e40\u0e02\u0e35\u0e22\u0e27\n"
                        "Bot \u0e08\u0e30\u0e15\u0e23\u0e27\u0e08\u0e43\u0e2b\u0e21\u0e48\u0e23\u0e2d\u0e1a\u0e16\u0e31\u0e14\u0e44\u0e1b\u0e2d\u0e31\u0e15\u0e42\u0e19\u0e21\u0e31\u0e15\u0e34"
                    )
                }
            # ── SELL: [0] แดงตัน ─────────────────────────────────
            if is_sell_maru:
                return {
                    "signal": "WAIT",
                    "reason": (
                        "\u23f3 SELL: [0] \u0e41\u0e14\u0e07\u0e15\u0e31\u0e19 \u0e44\u0e21\u0e48\u0e21\u0e35\u0e44\u0e2a\u0e49\u0e25\u0e48\u0e32\u0e07\n"
                        "\u0e23\u0e2d\u0e41\u0e17\u0e48\u0e07\u0e16\u0e31\u0e14\u0e21\u0e32\u0e01\u0e25\u0e37\u0e19\u0e01\u0e34\u0e19 (Close < Low[0]) \u0e41\u0e25\u0e30\u0e1b\u0e34\u0e14\u0e41\u0e14\u0e07\n"
                        "Bot \u0e08\u0e30\u0e15\u0e23\u0e27\u0e08\u0e43\u0e2b\u0e21\u0e48\u0e23\u0e2d\u0e1a\u0e16\u0e31\u0e14\u0e44\u0e1b\u0e2d\u0e31\u0e15\u0e42\u0e19\u0e21\u0e31\u0e15\u0e34"
                    )
                }

    # ══════════════════════════════════════════════
    #  BUY Pattern A — กลืนกิน
    #  [2] แดง → [1] เขียว Close > High[2]
    #  → [0] เขียวกลืนกิน Close > High[1]  ← ยืนยัน
    # ══════════════════════════════════════════════
    buy_wait_reason = None
    buy_e_wait_reason = None
    if not bull2 and bull1 and bull0:
        c1_engulf  = bull_engulf(cl1, h2)        # [1] กลืนกิน: Close > High[2] + gap
        c0_engulf  = bull_engulf(cl0, h1)        # [0] กลืนกิน: Close > High[1] + gap (ยืนยัน)
        zone       = (not use_zone) or (zone_low_3 <= sl_z + buf)
        # body ≥ 35% ของ [1] เท่านั้น ([2] ไม่จำกัด)
        r1 = h1 - l1; b1 = abs(cl1 - o1)
        r2 = h2 - l2; b2 = abs(cl2 - o2)
        body1_ok = r1 > 0 and b1 / r1 >= 0.35
        body1_pct = round(b1/r1*100) if r1 > 0 else 0
        body2_pct = round(b2/r2*100) if r2 > 0 else 0

        if c1_engulf and c0_engulf and body1_ok:
            # ข้อ 1: SL = min(l0,l1,l2) - SL_BUFFER() เหมือน Pattern B
            lowest   = min(l0, l1, l2)
            entry    = round((h1 + l1) / 2, 2)
            sl       = round(lowest - SL_BUFFER(), 2)
            tp_swing = find_swing_tp(rates, "BUY", entry, sl)
            tp       = tp_swing if tp_swing else round(entry + (entry-sl)*1.0, 2)
            tp_note  = f"Swing High:{tp}" if tp_swing else "RR1:1 (ไม่พบ Swing ≥1:1)"
            return _attach_s1_zone_meta({
                "signal": "BUY", "entry": entry, "sl": sl, "tp": tp,
                "pattern": "ท่าที่ 1 กลืนกิน/ตำหนิ/ย้อนโครงสร้าง 🟢 BUY — Pattern กลืนกิน",
                "reason": (
                    f"✅ แท่ง[2] แดง Body:{body2_pct}%\n"
                    f"✅ แท่ง[1] เขียวกลืน Close:{cl1:.2f} > High[2]:{h2:.2f} Body:{body1_pct}%\n"
                    f"✅ แท่ง[0] เขียวกลืน Close:{cl0:.2f} > High[1]:{h1:.2f}\n"
                    f"✅ ใกล้ Swing Low:{sl_z:.2f}\n"
                    f"📌 Entry Fibo 50% High-Low[1] | SL Low ต่ำสุด-SL_BUFFER\n"
                    f"🎯 TP: {tp_note}"
                ),
                "candles": [rates[-3],rates[-2],rates[-1]],
                "swing_high": sh, "swing_low": sl_z,
            }, use_zone, "BUY", zone_low_3, sl_z, zone)
        if not zone:
            buy_wait_reason = f"⚠️ BUY A ไม่อยู่ Low Zone (Low:{zone_low_3:.2f} | Swing:{sl_z:.2f})"
        elif not body1_ok:
            buy_wait_reason = f"⚠️ BUY A แท่ง[1] Body:{body1_pct}% < 35%"
        elif not c1_engulf:
            buy_wait_reason = f"⚠️ BUY A [1] Close:{cl1:.2f} ≤ High[2]:{h2:.2f}"
        else:
            buy_wait_reason = f"⚠️ BUY A [0] Close:{cl0:.2f} ≤ High[1]:{h1:.2f} รอแท่งกลืนยืนยัน"

    # ══════════════════════════════════════════════
    #  BUY Pattern B — ตำหนิ (ลำดับใหม่)
    #  [2] แดง → [1] เขียวตำหนิ → [0] เขียวกลืนกิน Close > High[1]
    #
    #  ตั้ง Limit ได้ 2 วิธี:
    #  วิธี 1: รอ [0] ปิดสมบูรณ์ แล้วค่อยตั้ง Limit
    #  วิธี 2: ถ้าราคาแตะ 50% Body[1] ระหว่างที่ [0] กำลังวิ่ง → ตั้งได้เลย
    #  Entry = 50% Body[1] | SL = min(l0,l1,l2) - 200
    # ══════════════════════════════════════════════
    if not bull2 and bull1 and bull0:
        range1     = h1 - l1
        body1      = abs(cl1 - o1)
        # [1] ตำหนิ: High[1] อยู่ใน zone หรือเหนือ High[2] + Body ≥ 35%
        c1_in_zone = h1 >= o2              # ไส้บน[1] เข้า zone แดง[2]
        c1_body_ok = (range1 > 0) and (body1 / range1 >= 0.35)  # ตำหนิ body ≥ 35%
        c0_engulf  = bull_engulf(cl0, h1)             # [0] กลืนกิน: Close > High[1] + gap
        zone       = (not use_zone) or (zone_low_3 <= sl_z + buf)

        if c1_in_zone and c1_body_ok and c0_engulf:
            body1_pct = round(body1/range1*100) if range1 > 0 else 0
            entry    = round((h1 + l1) / 2, 2)
            lowest   = min(l0, l1, l2)
            sl       = round(lowest - SL_BUFFER(), 2)
            tp_swing = find_swing_tp(rates, "BUY", entry, sl)
            tp       = tp_swing if tp_swing else round(entry + (entry-sl)*1.0, 2)  # fallback RR 1:1
            tp_note  = f"Swing High:{tp}" if tp_swing else "RR1:1 (ไม่พบ Swing ≥1:1)"
            return _attach_s1_zone_meta({
                "signal": "BUY", "entry": entry, "sl": sl, "tp": tp,
                "pattern": "ท่าที่ 1 กลืนกิน/ตำหนิ/ย้อนโครงสร้าง 🟢 BUY — Pattern ตำหนิ",
                "reason": (
                    f"✅ แท่ง[2] แดง\n"
                    f"⚠️ แท่ง[1] เขียวตำหนิ High:{h1:.2f} ≥ Open:{o2:.2f} | Body:{body1_pct}%\n"
                    f"✅ แท่ง[0] เขียวกลืน Close:{cl0:.2f} > High[1]:{h1:.2f}\n"
                    f"✅ ใกล้ Swing Low:{sl_z:.2f}\n"
                    f"📌 Entry Fibo 50% High-Low[1] | SL Low ต่ำสุด-SL_BUFFER\n"
                    f"🎯 TP: {tp_note}"
                ),
                "candles": [rates[-3],rates[-2],rates[-1]],
                "swing_high": sh, "swing_low": sl_z,
            }, use_zone, "BUY", zone_low_3, sl_z, zone)

    # ══════════════════════════════════════════════
    #  SELL Pattern A — กลืนกิน
    #  [2] เขียว → [1] แดง Close < Low[2]
    #  → [0] แดงกลืนกิน Close < Low[1]  ← ยืนยัน
    # ══════════════════════════════════════════════
    sell_wait_reason = None
    sell_e_wait_reason = None
    if bull2 and not bull1 and not bull0:
        c1_engulf  = bear_engulf(cl1, l2)        # [1] กลืนกิน: Close < Low[2] - gap
        c0_engulf  = bear_engulf(cl0, l1)        # [0] กลืนกิน: Close < Low[1] - gap (ยืนยัน)
        zone       = (not use_zone) or (zone_high_3 >= sh - buf)
        # body ≥ 35% ของ [1] เท่านั้น ([2] ไม่จำกัด)
        r1 = h1 - l1; b1 = abs(cl1 - o1)
        r2 = h2 - l2; b2 = abs(cl2 - o2)
        body1_ok = r1 > 0 and b1 / r1 >= 0.35
        body1_pct = round(b1/r1*100) if r1 > 0 else 0
        body2_pct = round(b2/r2*100) if r2 > 0 else 0

        if c1_engulf and c0_engulf and body1_ok:
            # ข้อ 1: SL = max(h0,h1,h2) + SL_BUFFER() เหมือน Pattern B
            highest  = max(h0, h1, h2)
            entry    = round((h1 + l1) / 2, 2)
            sl       = round(highest + SL_BUFFER(), 2)
            tp_swing = find_swing_tp(rates, "SELL", entry, sl)
            tp       = tp_swing if tp_swing else round(entry - (sl-entry)*1.0, 2)
            tp_note  = f"Swing Low:{tp}" if tp_swing else "RR1:1 (ไม่พบ Swing ≥1:1)"
            return _attach_s1_zone_meta({
                "signal": "SELL", "entry": entry, "sl": sl, "tp": tp,
                "pattern": "ท่าที่ 1 กลืนกิน/ตำหนิ/ย้อนโครงสร้าง 🔴 SELL — Pattern กลืนกิน",
                "reason": (
                    f"✅ แท่ง[2] เขียว Body:{body2_pct}%\n"
                    f"✅ แท่ง[1] แดงกลืน Close:{cl1:.2f} < Low[2]:{l2:.2f} Body:{body1_pct}%\n"
                    f"✅ แท่ง[0] แดงกลืน Close:{cl0:.2f} < Low[1]:{l1:.2f}\n"
                    f"✅ ใกล้ Swing High:{sh:.2f}\n"
                    f"📌 Entry Fibo 50% High-Low[1] | SL High สูงสุด+SL_BUFFER\n"
                    f"🎯 TP: {tp_note}"
                ),
                "candles": [rates[-3],rates[-2],rates[-1]],
                "swing_high": sh, "swing_low": sl_z,
            }, use_zone, "SELL", zone_high_3, sh, zone)
        if not zone:
            sell_wait_reason = f"⚠️ SELL A ไม่อยู่ High Zone (High:{zone_high_3:.2f} | Swing:{sh:.2f})"
        elif not body1_ok:
            sell_wait_reason = f"⚠️ SELL A แท่ง[1] Body:{body1_pct}% < 35%"
        elif not c1_engulf:
            sell_wait_reason = f"⚠️ SELL A [1] Close:{cl1:.2f} ≥ Low[2]:{l2:.2f}"
        else:
            sell_wait_reason = f"⚠️ SELL A [0] Close:{cl0:.2f} ≥ Low[1]:{l1:.2f} รอแท่งกลืนยืนยัน"

    # ══════════════════════════════════════════════
    #  SELL Pattern B — ตำหนิ (ลำดับใหม่)
    #  [2] เขียว → [1] แดงตำหนิ → [0] แดงกลืนกิน Close < Low[1]
    #
    #  ตั้ง Limit ได้ 2 วิธี:
    #  วิธี 1: รอ [0] ปิดสมบูรณ์ แล้วค่อยตั้ง Limit
    #  วิธี 2: ถ้าราคาแตะ 50% Body[1] ระหว่างที่ [0] กำลังวิ่ง → ตั้งได้เลย
    #  Entry = 50% Body[1] | SL = max(h0,h1,h2) + 200
    # ══════════════════════════════════════════════
    if bull2 and not bull1 and not bull0:
        range1     = h1 - l1
        body1      = abs(cl1 - o1)
        # [1] ตำหนิ: Low[1] อยู่ใน zone หรือใต้ Low[2] + Body ≥ 35%
        c1_in_zone = l1 <= o2              # ไส้ล่าง[1] เข้า zone เขียว[2]
        c1_body_ok = (range1 > 0) and (body1 / range1 >= 0.35)  # ตำหนิ body ≥ 35%
        c0_engulf  = bear_engulf(cl0, l1)             # [0] กลืนกิน: Close < Low[1] - gap
        zone       = (not use_zone) or (zone_high_3 >= sh - buf)

        if c1_in_zone and c1_body_ok and c0_engulf:
            body1_pct = round(body1/range1*100) if range1 > 0 else 0
            entry    = round((h1 + l1) / 2, 2)
            highest  = max(h0, h1, h2)
            sl       = round(highest + SL_BUFFER(), 2)
            tp_swing = find_swing_tp(rates, "SELL", entry, sl)
            tp       = tp_swing if tp_swing else round(entry - (sl-entry)*1.0, 2)  # fallback RR 1:1
            tp_note  = f"Swing Low:{tp}" if tp_swing else "RR1:1 (ไม่พบ Swing ≥1:1)"
            return _attach_s1_zone_meta({
                "signal": "SELL", "entry": entry, "sl": sl, "tp": tp,
                "pattern": "ท่าที่ 1 กลืนกิน/ตำหนิ/ย้อนโครงสร้าง 🔴 SELL — Pattern ตำหนิ",
                "reason": (
                    f"✅ แท่ง[2] เขียว\n"
                    f"⚠️ แท่ง[1] แดงตำหนิ Low:{l1:.2f} ≤ Open:{o2:.2f} | Body:{body1_pct}%\n"
                    f"✅ แท่ง[0] แดงกลืน Close:{cl0:.2f} < Low[1]:{l1:.2f}\n"
                    f"✅ ใกล้ Swing High:{sh:.2f}\n"
                    f"📌 Entry Fibo 50% High-Low[1] | SL High สูงสุด+SL_BUFFER\n"
                    f"🎯 TP: {tp_note}"
                ),
                "candles": [rates[-3],rates[-2],rates[-1]],
                "swing_high": sh, "swing_low": sl_z,
            }, use_zone, "SELL", zone_high_3, sh, zone)

    # ══════════════════════════════════════════════
    #  BUY Pattern C — ย้อนโครงสร้าง
    #  [2] แดง → [1] เขียว Body≥35% → [0] เขียว Close > High[1]
    #  Entry = 50% Body[1] | SL = min(l0,l1,l2) - 200
    # ══════════════════════════════════════════════
    if not bull2 and bull1 and bull0:
        r1_c = h1 - l1; b1_c = abs(cl1 - o1)
        body1_c_ok = r1_c > 0 and b1_c / r1_c >= 0.35  # [1] body ≥ 35%
        c0_engulf = bull_engulf(cl0, h1)
        zone      = (not use_zone) or (zone_low_3 <= sl_z + buf)

        if c0_engulf and body1_c_ok:
            entry    = round((h1 + l1) / 2, 2)
            lowest   = min(l0, l1, l2)
            sl       = round(lowest - SL_BUFFER(), 2)
            tp_swing = find_swing_tp(rates, "BUY", entry, sl)
            tp       = tp_swing if tp_swing else round(entry + (entry-sl)*1.0, 2)  # fallback RR 1:1
            tp_note  = f"Swing High:{tp}" if tp_swing else "RR1:1 (ไม่พบ Swing ≥1:1)"
            return _attach_s1_zone_meta({
                "signal": "BUY", "entry": entry, "sl": sl, "tp": tp,
                "pattern": "ท่าที่ 1 กลืนกิน/ตำหนิ/ย้อนโครงสร้าง 🟢 BUY — Pattern ย้อนโครงสร้าง",
                "reason": (
                    f"\u2705 แท่ง[2] แดง\n"
                    f"\u2705 แท่ง[1] เขียว (ไม่ต้องกลืนกิน)\n"
                    f"\u2705 แท่ง[0] เขียวกลืน Close:{cl0:.2f} > High[1]:{h1:.2f}\n"
                    f"\u2705 ใกล้ Swing Low:{sl_z:.2f}\n"
                    f"\U0001f4cd Entry 50% Body[1] | SL Low ต่ำสุด-200\n"
                    f"\U0001f3af TP: {tp_note}"
                ),
                "candles": [rates[-3],rates[-2],rates[-1]],
                "swing_high": sh, "swing_low": sl_z,
            }, use_zone, "BUY", zone_low_3, sl_z, zone)

    # ══════════════════════════════════════════════
    #  SELL Pattern C — ย้อนโครงสร้าง
    #  [2] เขียว → [1] แดง Body≥35% → [0] แดง Close < Low[1]
    #  Entry = 50% Body[1] | SL = max(h0,h1,h2) + 200
    # ══════════════════════════════════════════════
    if bull2 and not bull1 and not bull0:
        r1_c = h1 - l1; b1_c = abs(cl1 - o1)
        body1_c_ok = r1_c > 0 and b1_c / r1_c >= 0.35  # [1] body ≥ 35%
        c0_engulf = bear_engulf(cl0, l1)
        zone      = (not use_zone) or (zone_high_3 >= sh - buf)

        if c0_engulf and body1_c_ok:
            entry    = round((h1 + l1) / 2, 2)
            highest  = max(h0, h1, h2)
            sl       = round(highest + SL_BUFFER(), 2)
            tp_swing = find_swing_tp(rates, "SELL", entry, sl)
            tp       = tp_swing if tp_swing else round(entry - (sl-entry)*1.0, 2)  # fallback RR 1:1
            tp_note  = f"Swing Low:{tp}" if tp_swing else "RR1:1 (ไม่พบ Swing ≥1:1)"
            return _attach_s1_zone_meta({
                "signal": "SELL", "entry": entry, "sl": sl, "tp": tp,
                "pattern": "ท่าที่ 1 กลืนกิน/ตำหนิ/ย้อนโครงสร้าง 🔴 SELL — Pattern ย้อนโครงสร้าง",
                "reason": (
                    f"\u2705 แท่ง[2] เขียว\n"
                    f"\u2705 แท่ง[1] แดง (ไม่ต้องกลืนกิน)\n"
                    f"\u2705 แท่ง[0] แดงกลืน Close:{cl0:.2f} < Low[1]:{l1:.2f}\n"
                    f"\u2705 ใกล้ Swing High:{sh:.2f}\n"
                    f"\U0001f4cd Entry 50% Body[1] | SL High สูงสุด+200\n"
                    f"\U0001f3af TP: {tp_note}"
                ),
                "candles": [rates[-3],rates[-2],rates[-1]],
                "swing_high": sh, "swing_low": sl_z,
            }, use_zone, "SELL", zone_high_3, sh, zone)

    # ══════════════════════════════════════════════
    #  BUY Pattern E — กลืนกิน 2 แดง
    #  [2] แดง → [1] แดง → [0] เขียว Close > High[1] + Body ≥ 35%
    #  Entry = 50% Body[0] | SL = min(l0,l1,l2) - SL_BUFFER
    #  ยกเลิก limit หลัง 1 แท่ง
    # ══════════════════════════════════════════════
    if not bull2 and not bull1 and bull0:
        r0 = h0 - l0; b0 = abs(cl0 - o0)
        body0_ok = r0 > 0 and b0 / r0 >= 0.35
        body0_pct = round(b0/r0*100) if r0 > 0 else 0
        c0_engulf = bull_engulf(cl0, h1)
        zone = (not use_zone) or (zone_low_3 <= sl_z + buf)

        if c0_engulf and body0_ok:
            entry    = round((h0 + l0) / 2, 2)
            lowest   = min(l0, l1, l2)
            sl       = round(lowest - SL_BUFFER(), 2)
            tp_swing = find_swing_tp(rates, "BUY", entry, sl)
            tp       = tp_swing if tp_swing else round(entry + (entry - sl) * 1.0, 2)
            tp_note  = f"Swing High:{tp}" if tp_swing else "RR1:1 (ไม่พบ Swing ≥1:1)"
            return _attach_s1_zone_meta({
                "signal": "BUY", "entry": entry, "sl": sl, "tp": tp,
                "pattern": "ท่าที่ 1 กลืนกิน/ตำหนิ/ย้อนโครงสร้าง 🟢 BUY — Pattern กลืนกิน 2 แดง",
                "cancel_bars": 1,
                "reason": (
                    f"✅ แท่ง[2] แดง\n"
                    f"✅ แท่ง[1] แดง\n"
                    f"✅ แท่ง[0] เขียวกลืน Close:{cl0:.2f} > High[1]:{h1:.2f} Body:{body0_pct}%\n"
                    f"✅ ใกล้ Swing Low:{sl_z:.2f}\n"
                    f"📌 Entry 50% Body[0] | ยกเลิกหลัง 1 แท่ง\n"
                    f"🎯 TP: {tp_note}"
                ),
                "candles": [rates[-3], rates[-2], rates[-1]],
                "swing_high": sh, "swing_low": sl_z,
            }, use_zone, "BUY", zone_low_3, sl_z, zone)
        if not zone:
            buy_e_wait_reason = f"⚠️ BUY E ไม่อยู่ Low Zone (Low:{zone_low_3:.2f} | Swing:{sl_z:.2f})"
        elif not body0_ok:
            buy_e_wait_reason = f"⚠️ BUY E แท่ง[0] Body:{body0_pct}% < 35%"
        else:
            buy_e_wait_reason = f"⚠️ BUY E [0] Close:{cl0:.2f} <= High[1]:{h1:.2f}"

    # ══════════════════════════════════════════════
    #  SELL Pattern E — กลืนกิน 2 เขียว
    #  [2] เขียว → [1] เขียว → [0] แดง Close < Low[1] + Body ≥ 35%
    #  Entry = 50% Body[0] | SL = max(h0,h1,h2) + SL_BUFFER
    #  ยกเลิก limit หลัง 1 แท่ง
    # ══════════════════════════════════════════════
    if bull2 and bull1 and not bull0:
        r0 = h0 - l0; b0 = abs(cl0 - o0)
        body0_ok = r0 > 0 and b0 / r0 >= 0.35
        body0_pct = round(b0/r0*100) if r0 > 0 else 0
        c0_engulf = bear_engulf(cl0, l1)
        zone = (not use_zone) or (zone_high_3 >= sh - buf)

        if c0_engulf and body0_ok:
            entry    = round((h0 + l0) / 2, 2)
            highest  = max(h0, h1, h2)
            sl       = round(highest + SL_BUFFER(), 2)
            tp_swing = find_swing_tp(rates, "SELL", entry, sl)
            tp       = tp_swing if tp_swing else round(entry - (sl - entry) * 1.0, 2)
            tp_note  = f"Swing Low:{tp}" if tp_swing else "RR1:1 (ไม่พบ Swing ≥1:1)"
            return _attach_s1_zone_meta({
                "signal": "SELL", "entry": entry, "sl": sl, "tp": tp,
                "pattern": "ท่าที่ 1 กลืนกิน/ตำหนิ/ย้อนโครงสร้าง 🔴 SELL — Pattern กลืนกิน 2 เขียว",
                "cancel_bars": 1,
                "reason": (
                    f"✅ แท่ง[2] เขียว\n"
                    f"✅ แท่ง[1] เขียว\n"
                    f"✅ แท่ง[0] แดงกลืน Close:{cl0:.2f} < Low[1]:{l1:.2f} Body:{body0_pct}%\n"
                    f"✅ ใกล้ Swing High:{sh:.2f}\n"
                    f"📌 Entry 50% Body[0] | ยกเลิกหลัง 1 แท่ง\n"
                    f"🎯 TP: {tp_note}"
                ),
                "candles": [rates[-3], rates[-2], rates[-1]],
                "swing_high": sh, "swing_low": sl_z,
            }, use_zone, "SELL", zone_high_3, sh, zone)
        if not zone:
            sell_e_wait_reason = f"⚠️ SELL E ไม่อยู่ High Zone (High:{zone_high_3:.2f} | Swing:{sh:.2f})"
        elif not body0_ok:
            sell_e_wait_reason = f"⚠️ SELL E แท่ง[0] Body:{body0_pct}% < 35%"
        else:
            sell_e_wait_reason = f"⚠️ SELL E [0] Close:{cl0:.2f} >= Low[1]:{l1:.2f}"

    # Pattern ใหม่ 4 แท่ง
    # BUY: [3] แดง [2] เขียว Body≥35% [1] เขียวแต่ close < high[2] [0] เขียว close >= high[1]
    # Entry = 50% body ของแท่ง [2]
    if has_c3 and (not bull3) and bull2 and bull1 and bull0 and cl1 < h2 and bull_engulf(cl0, h1):
        r2_d = h2 - l2; b2_d = abs(cl2 - o2)
        body2_d_ok = r2_d > 0 and b2_d / r2_d >= 0.35  # [2] body ≥ 35%
        zone = (not use_zone) or (zone_low_4 <= sl_z + buf)
        if body2_d_ok:
            body2 = abs(cl2 - o2)
            entry = round((h2 + l2) / 2, 2)
            lowest = min(l0, l1, l2, l3)
            sl = round(lowest - SL_BUFFER(), 2)
            tp_swing = find_swing_tp(rates, "BUY", entry, sl)
            tp = tp_swing if tp_swing else round(entry + (entry - sl) * 1.0, 2)
            tp_note = f"Swing High:{tp}" if tp_swing else "RR1:1 (ไม่พบ Swing >=1:1)"
            return _attach_s1_zone_meta({
                "signal": "BUY", "entry": entry, "sl": sl, "tp": tp,
                "pattern": "ท่าที่ 1 กลืนกิน/ตำหนิ/ย้อนโครงสร้าง 🟢 BUY — Pattern ใหม่ 4 แท่ง",
                "reason": (
                    f"✅ แท่ง[3] แดง\n"
                    f"✅ แท่ง[2] เขียว\n"
                    f"✅ แท่ง[1] เขียว Close:{cl1:.2f} < High[2]:{h2:.2f}\n"
                    f"✅ แท่ง[0] เขียว Close:{cl0:.2f} >= High[1]:{h1:.2f}\n"
                    f"📍 Entry 50% Body[2]\n"
                    f"🎯 TP: {tp_note}"
                ),
                "candles": [rates[-4], rates[-3], rates[-2], rates[-1]],
                "swing_high": sh, "swing_low": sl_z,
            }, use_zone, "BUY", zone_low_4, sl_z, zone)

    # SELL: [3] เขียว [2] แดง Body≥35% [1] แดงแต่ close > low[2] [0] แดง close <= low[1]
    # Entry = 50% body ของแท่ง [2]
    if has_c3 and bull3 and (not bull2) and (not bull1) and (not bull0) and cl1 > l2 and bear_engulf(cl0, l1):
        r2_d = h2 - l2; b2_d = abs(cl2 - o2)
        body2_d_ok = r2_d > 0 and b2_d / r2_d >= 0.35  # [2] body ≥ 35%
        zone = (not use_zone) or (zone_high_4 >= sh - buf)
        if body2_d_ok:
            body2 = abs(cl2 - o2)
            entry = round((h2 + l2) / 2, 2)
            highest = max(h0, h1, h2, h3)
            sl = round(highest + SL_BUFFER(), 2)
            tp_swing = find_swing_tp(rates, "SELL", entry, sl)
            tp = tp_swing if tp_swing else round(entry - (sl - entry) * 1.0, 2)
            tp_note = f"Swing Low:{tp}" if tp_swing else "RR1:1 (ไม่พบ Swing >=1:1)"
            return _attach_s1_zone_meta({
                "signal": "SELL", "entry": entry, "sl": sl, "tp": tp,
                "pattern": "ท่าที่ 1 กลืนกิน/ตำหนิ/ย้อนโครงสร้าง 🔴 SELL — Pattern ใหม่ 4 แท่ง",
                "reason": (
                    f"✅ แท่ง[3] เขียว\n"
                    f"✅ แท่ง[2] แดง\n"
                    f"✅ แท่ง[1] แดง Close:{cl1:.2f} > Low[2]:{l2:.2f}\n"
                    f"✅ แท่ง[0] แดง Close:{cl0:.2f} <= Low[1]:{l1:.2f}\n"
                    f"📍 Entry 50% Body[2]\n"
                    f"🎯 TP: {tp_note}"
                ),
                "candles": [rates[-4], rates[-3], rates[-2], rates[-1]],
                "swing_high": sh, "swing_low": sl_z,
            }, use_zone, "SELL", zone_high_4, sh, zone)

    if buy_e_wait_reason:
        return {"signal": "WAIT", "reason": buy_e_wait_reason}
    if sell_e_wait_reason:
        return {"signal": "WAIT", "reason": sell_e_wait_reason}
    if buy_wait_reason:
        return {"signal": "WAIT", "reason": buy_wait_reason}
    if sell_wait_reason:
        return {"signal": "WAIT", "reason": sell_wait_reason}
    return {"signal": "WAIT", "reason": "ไม่มี Setup ที่ตรงเงื่อนไข"}









# ============================================================
#  Strategy 2 — FVG (Fair Value Gap)
#
#  FVG BUY:
#    [1] อะไรก็ได้  [2] Imbalance  [3] อะไรก็ได้
#    Gap = High[1] (สูงสุดแท่ง1) ถึง Low[3] (ต่ำสุดแท่ง3)
#    เงื่อนไข: High[1] > Low[3]  → Gap ยังเหลืออยู่
#    Entry = High[1] - Gap*0.90  (90% จากบนลงมา ชิดขอบล่าง)
#    SL    = Low[3] - 200
#    TP    = Swing High ย่อย (RR >= 1:1)
#    แท่ง[3] เป็นอะไรก็ได้: เขียวกลืนกิน / ตำหนิ / แดง
#
#  FVG SELL (สลับสี):
#    Gap = Low[1] ถึง High[3]
#    Entry = Low[1] + Gap*0.90
#    SL    = High[3] + 200
# ============================================================

fvg_pending = {}  # {key: {tf, signal, entry, sl, tp, gap_top, gap_bot, candle_key}}
