from config import *
from mt5_utils import find_swing_tp


def strategy_3(rates):
    """
    Strategy 3 - DM SP (Demand/Supply Push)

    BUY:
      [2] bullish body >= 35%
      [1] bearish or doji
      [0] bullish and close > high[1]

    SELL:
      [2] bearish body >= 35%
      [1] bullish or doji
      [0] bearish and close < low[1]
    """
    if len(rates) < 5:
        return {"signal": "WAIT", "reason": "ข้อมูลไม่เพียงพอ"}

    def c(i):
        r = rates[i]
        return {
            "o": float(r["open"]),
            "h": float(r["high"]),
            "l": float(r["low"]),
            "cl": float(r["close"]),
            "range": float(r["high"]) - float(r["low"]),
            "body": abs(float(r["close"]) - float(r["open"])),
        }

    c0 = c(-1)
    c1 = c(-2)
    c2 = c(-3)
    engulf_gap = engulf_min_price()

    min_body_pct = 35.0

    def body_pct(x):
        return (x["body"] / x["range"] * 100) if x["range"] > 0 else 0.0

    def is_bull(x):
        return x["cl"] > x["o"]

    def is_bear(x):
        return x["cl"] < x["o"]

    def is_doji(x):
        return body_pct(x) < 10

    def maru_buy(x):
        return x["range"] > 0 and (x["h"] - x["cl"]) < x["range"] * 0.05

    def maru_sell(x):
        return x["range"] > 0 and (x["cl"] - x["l"]) < x["range"] * 0.05

    def bull_engulf(close_price, ref_high):
        return close_price > (ref_high + engulf_gap)

    def bear_engulf(close_price, ref_low):
        return close_price < (ref_low - engulf_gap)

    buy_wait_reason = None
    sell_wait_reason = None

    if (
        is_bull(c2)
        and (is_bear(c1) or (is_doji(c1) and not is_bull(c1)) or (is_bull(c1) and c1["cl"] < c2["h"]))
        and is_bull(c0)
        and bull_engulf(c0["cl"], c1["h"])
    ):
        entry = round(c1["o"], 2)
        sl = round(c1["l"] - SL_BUFFER(), 2)
        tp_swing = find_swing_tp(rates, "BUY", entry, sl)
        tp = tp_swing if tp_swing else round(entry + (entry - sl), 2)
        tp_note = f"Swing High:{tp}" if tp_swing else "RR1:1 (fallback)"
        rr = round(abs(tp - entry) / abs(entry - sl), 2) if abs(entry - sl) > 0 else 0
        wick_top = round(c0["h"] - c0["cl"], 2)

        if is_doji(c1):
            c1_type = "G_DOJI" if is_bull(c1) else "R_DOJI"
        elif is_bull(c1):
            c1_type = "G"
        else:
            c1_type = "R"
        buy_pattern = f"ท่าที่ 3 DM SP 🟢 BUY [C1:{c1_type}]"

        if maru_buy(c0):
            return {
                "signal": "WAIT",
                "pattern": buy_pattern,
                "reason": (
                    f"⏳ [0] เขียวตัน ไม่มีไส้บน (wick={wick_top}) | "
                    f"รอแท่งถัดไปจบเขียว = ตั้ง Limit | จบแดง = ยกเลิก | "
                    f"Entry:{entry} SL:{sl} TP:{tp}"
                ),
                "marubozu_pending": {
                    "direction": "BUY",
                    "entry": entry,
                    "sl": sl,
                    "tp": tp,
                    "candle_time": int(rates[-1]["time"]),
                    "c1_type": c1_type,
                },
            }

        return {
            "signal": "BUY",
            "pattern": buy_pattern,
            "entry": entry,
            "sl": sl,
            "tp": tp,
            "tp_note": tp_note,
            "reason": (
                f"[2]เขียว body:{body_pct(c2):.0f}% "
                f"[1]{c1_type} "
                f"[0]เขียวกลืน Close:{c0['cl']:.2f}>High[1]:{c1['h']:.2f} "
                f"Entry:{entry} SL:{sl} TP:{tp} RR1:{rr}"
            ),
            "candles": [
                {"open": c2["o"], "high": c2["h"], "low": c2["l"], "close": c2["cl"]},
                {"open": c1["o"], "high": c1["h"], "low": c1["l"], "close": c1["cl"]},
                {"open": c0["o"], "high": c0["h"], "low": c0["l"], "close": c0["cl"]},
            ],
            "swing_high": c0["h"],
            "swing_low": c1["l"],
        }
    elif is_bull(c2):
        if not (is_bear(c1) or (is_doji(c1) and not is_bull(c1)) or (is_bull(c1) and c1["cl"] < c2["h"])):
            buy_wait_reason = (
                f"DM SP BUY: [1] ต้องเป็นแดง/doji หรือเขียว Close < High[2] "
                f"(O:{c1['o']:.2f} C:{c1['cl']:.2f} High[2]:{c2['h']:.2f} body:{body_pct(c1):.0f}%)"
            )
        elif not is_bull(c0):
            buy_wait_reason = f"DM SP BUY: [0] ยังไม่ปิดเขียว (O:{c0['o']:.2f} C:{c0['cl']:.2f})"
        else:
            buy_wait_reason = f"DM SP BUY: Close[0]={c0['cl']:.2f} <= High[1]={c1['h']:.2f}"

    if (
        is_bear(c2)
        and (is_bull(c1) or (is_doji(c1) and not is_bear(c1)) or (is_bear(c1) and c1["cl"] > c2["l"]))
        and is_bear(c0)
        and bear_engulf(c0["cl"], c1["l"])
    ):
        entry = round(c1["o"], 2)
        sl = round(c1["h"] + SL_BUFFER(), 2)
        tp_swing = find_swing_tp(rates, "SELL", entry, sl)
        tp = tp_swing if tp_swing else round(entry - (sl - entry), 2)
        tp_note = f"Swing Low:{tp}" if tp_swing else "RR1:1 (fallback)"
        rr = round(abs(tp - entry) / abs(sl - entry), 2) if abs(sl - entry) > 0 else 0
        wick_bot = round(c0["cl"] - c0["l"], 2)

        if is_doji(c1):
            c1_type = "G_DOJI" if is_bull(c1) else "R_DOJI"
        elif is_bull(c1):
            c1_type = "G"
        else:
            c1_type = "R"
        sell_pattern = f"ท่าที่ 3 DM SP 🔴 SELL [C1:{c1_type}]"

        if maru_sell(c0):
            return {
                "signal": "WAIT",
                "pattern": sell_pattern,
                "reason": (
                    f"⏳ [0] แดงตัน ไม่มีไส้ล่าง (wick={wick_bot}) | "
                    f"รอแท่งถัดไปจบแดง = ตั้ง Limit | จบเขียว = ยกเลิก | "
                    f"Entry:{entry} SL:{sl} TP:{tp}"
                ),
                "marubozu_pending": {
                    "direction": "SELL",
                    "entry": entry,
                    "sl": sl,
                    "tp": tp,
                    "candle_time": int(rates[-1]["time"]),
                    "c1_type": c1_type,
                },
            }

        return {
            "signal": "SELL",
            "pattern": sell_pattern,
            "entry": entry,
            "sl": sl,
            "tp": tp,
            "tp_note": tp_note,
            "reason": (
                f"[2]แดง body:{body_pct(c2):.0f}% "
                f"[1]{c1_type} "
                f"[0]แดงกลืน Close:{c0['cl']:.2f}<Low[1]:{c1['l']:.2f} "
                f"Entry:{entry} SL:{sl} TP:{tp} RR1:{rr}"
            ),
            "candles": [
                {"open": c2["o"], "high": c2["h"], "low": c2["l"], "close": c2["cl"]},
                {"open": c1["o"], "high": c1["h"], "low": c1["l"], "close": c1["cl"]},
                {"open": c0["o"], "high": c0["h"], "low": c0["l"], "close": c0["cl"]},
            ],
            "swing_high": c1["h"],
            "swing_low": c0["l"],
        }
    elif is_bear(c2):
        if not (is_bull(c1) or (is_doji(c1) and not is_bear(c1)) or (is_bear(c1) and c1["cl"] > c2["l"])):
            sell_wait_reason = (
                f"DM SP SELL: [1] ต้องเป็นเขียว/doji หรือแดง Close > Low[2] "
                f"(O:{c1['o']:.2f} C:{c1['cl']:.2f} Low[2]:{c2['l']:.2f} body:{body_pct(c1):.0f}%)"
            )
        elif not is_bear(c0):
            sell_wait_reason = f"DM SP SELL: [0] ยังไม่ปิดแดง (O:{c0['o']:.2f} C:{c0['cl']:.2f})"
        else:
            sell_wait_reason = f"DM SP SELL: Close[0]={c0['cl']:.2f} >= Low[1]={c1['l']:.2f}"

    if buy_wait_reason:
        return {"signal": "WAIT", "reason": buy_wait_reason}
    if sell_wait_reason:
        return {"signal": "WAIT", "reason": sell_wait_reason}
    return {"signal": "WAIT", "reason": "ไม่พบ DM SP Pattern"}
