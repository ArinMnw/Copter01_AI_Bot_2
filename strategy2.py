from config import *
from mt5_utils import get_structure


def detect_fvg(rates):
    """
    Strategy 2 - FVG

    BUY:
      [1] bullish imbalance and high[1] > high[2]
      [0] low[0] must stay above high[2] so the gap remains open

    SELL:
      [1] bearish imbalance and low[1] < low[2]
      [0] high[0] must stay below low[2] so the gap remains open
    """
    if len(rates) < 4:
        return None, "ข้อมูลไม่เพียงพอ"

    def c(i):
        r = rates[i]
        o = float(r["open"])
        h = float(r["high"])
        l = float(r["low"])
        cl = float(r["close"])
        return o, h, l, cl, cl > o

    o0, h0, l0, cl0, bull0 = c(-1)
    o1, h1, l1, cl1, bull1 = c(-2)
    o2, h2, l2, cl2, bull2 = c(-3)
    engulf_gap = engulf_min_price()

    ms = get_structure(rates)
    sh = ms["swing_high"]
    sl_z = ms["swing_low"]

    if bull1 and cl1 > h2 + engulf_gap:
        if l0 <= h2:
            return None, f"FVG BUY gap ถูกปิด (Low[0]={l0:.2f} <= High[2]={h2:.2f})"

        gap_bot = h2
        gap_top = l0
        gap_size = gap_top - gap_bot

        if gap_size < engulf_gap:
            return None, f"FVG BUY gap เล็กเกิน ({gap_size:.2f} < {engulf_gap:.2f})"

        entry = round(gap_bot + gap_size * 0.90, 2)
        sl = round(l1 - SL_BUFFER(), 2)

        if bull0 and cl0 > h1:
            c0_type = "เขียวกลืนกิน"
        elif h0 >= h1 and cl0 > h2:
            c0_type = "ปฏิเสธราคา"
        elif not bull0:
            c0_type = "แดง"
        else:
            c0_type = "เขียว"

        # ปิดใช้งาน pattern 3-4 (แดง/เขียว default) — เหลือเฉพาะ "เขียวกลืนกิน" และ "ปฏิเสธราคา"
        if c0_type in ("แดง", "เขียว"):
            return None, f"FVG BUY pattern '{c0_type}' ปิดใช้งาน"

        near_zone = gap_bot <= sl_z + ms["atr"] * 3
        zone_note = "✅ ใกล้ Swing Low" if near_zone else "⚠️ ไม่อยู่ Zone"

        return {
            "signal": "BUY",
            "pattern": f"ท่าที่ 2 FVG 🟢 BUY — {c0_type}",
            "entry": entry,
            "sl": sl,
            "gap_top": gap_top,
            "gap_bot": gap_bot,
            "gap_size": gap_size,
            "c3_type": c0_type,
            "zone_note": zone_note,
            "swing_high": sh,
            "swing_low": sl_z,
        }, None

    if (not bull1) and cl1 < l2 - engulf_gap:
        if h0 >= l2:
            return None, f"FVG SELL gap ถูกปิด (High[0]={h0:.2f} >= Low[2]={l2:.2f})"

        gap_bot = h0
        gap_top = l2
        gap_size = gap_top - gap_bot

        if gap_size < engulf_gap:
            return None, f"FVG SELL gap เล็กเกิน ({gap_size:.2f} < {engulf_gap:.2f})"

        entry = round(gap_top - gap_size * 0.90, 2)
        sl = round(h1 + SL_BUFFER(), 2)

        if (not bull0) and cl0 < l1:
            c0_type = "แดงกลืนกิน"
        elif l0 <= l1 and cl0 < l2:
            c0_type = "ปฏิเสธราคา"
        elif bull0:
            c0_type = "เขียว"
        else:
            c0_type = "แดง"

        # ปิดใช้งาน pattern 3-4 (เขียว/แดง default) — เหลือเฉพาะ "แดงกลืนกิน" และ "ปฏิเสธราคา"
        if c0_type in ("เขียว", "แดง"):
            return None, f"FVG SELL pattern '{c0_type}' ปิดใช้งาน"

        near_zone = gap_top >= sh - ms["atr"] * 3
        zone_note = "✅ ใกล้ Swing High" if near_zone else "⚠️ ไม่อยู่ Zone"

        return {
            "signal": "SELL",
            "pattern": f"ท่าที่ 2 FVG 🔴 SELL — {c0_type}",
            "entry": entry,
            "sl": sl,
            "gap_top": gap_top,
            "gap_bot": gap_bot,
            "gap_size": gap_size,
            "c3_type": c0_type,
            "zone_note": zone_note,
            "swing_high": sh,
            "swing_low": sl_z,
        }, None

    if bull1 and cl1 <= h2 + engulf_gap:
        return None, f"FVG BUY: Close[1]={cl1:.2f} <= High[2]+gap={h2 + engulf_gap:.2f} [1] not engulfing [2] yet"
    if (not bull1) and cl1 >= l2 - engulf_gap:
        return None, f"FVG SELL: Close[1]={cl1:.2f} >= Low[2]-gap={l2 - engulf_gap:.2f} [1] not engulfing [2] yet"

    side = "BUY" if bull1 else "SELL" if cl1 < o1 else "DOJI"
    return None, (
        f"ไม่พบ FVG Pattern: [1] ยังไม่เป็น Imbalance ชัดเจน "
        f"(side={side} O:{o1:.2f} H:{h1:.2f} L:{l1:.2f} C:{cl1:.2f})"
    )


def strategy_2(rates):
    fvg, reason = detect_fvg(rates)
    if fvg:
        def c(i):
            r = rates[i]
            return float(r["open"]), float(r["high"]), float(r["low"]), float(r["close"])

        o0, h0, l0, cl0 = c(-1)
        rng0 = h0 - l0
        bull0 = cl0 > o0

        if rng0 > 0:
            if fvg["signal"] == "BUY":
                wick_top = h0 - cl0
                is_maru = bull0 and wick_top < rng0 * 0.05
            else:
                wick_bot = cl0 - l0
                is_maru = (not bull0) and wick_bot < rng0 * 0.05

            if is_maru:
                return {
                    "signal": "WAIT",
                    "pattern": fvg["pattern"],
                    "reason": (
                        f"⏳ [0] ตัน รอ confirm แท่งถัดไป | "
                        f"Entry:{fvg['entry']} SL:{fvg['sl']} TP:{fvg.get('tp', '?')}"
                    ),
                    "marubozu_pending": {
                        "direction": fvg["signal"],
                        "entry": fvg["entry"],
                        "sl": fvg["sl"],
                        "tp": fvg.get("tp", 0),
                        "candle_time": int(rates[-1]["time"]),
                        "strategy": 2,
                    },
                }

        return {
            "signal": "FVG_DETECTED",
            "fvg": fvg,
            "pattern": fvg["pattern"],
            "reason": (
                f"FVG {fvg['signal']} ตรวจพบ!\n"
                f"Gap: {fvg['gap_bot']} - {fvg['gap_top']} ({fvg['gap_size']:.2f}pt)\n"
                f"Entry 90%: {fvg['entry']}\n"
                f"แท่ง[0]: {fvg.get('c3_type', '')} | {fvg['zone_note']}\n"
                f"ตั้ง Limit ทันที"
            ),
        }

    return {"signal": "WAIT", "reason": reason or "ไม่มี FVG Setup"}
