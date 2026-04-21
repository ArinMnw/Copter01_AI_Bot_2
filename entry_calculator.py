from config import *
from mt5_utils import find_swing_tp


# ─────────────────────────────────────────────────────────────────
# TP/SL Calculator แต่ละท่า
# ─────────────────────────────────────────────────────────────────

def calc_tp_sl_s1_buy_A(rates, o1, h1, l1, cl1):
    """
    ท่าที่ 1 Pattern A BUY
    Entry = 50% Body[1]  (แท่ง[1] = แท่งกลืนกิน)
    SL    = Low[1] - SL_BUFFER (200 จุด)
    TP    = Swing High ย่อย/หลัก ที่ RR≥1:1 | fallback RR 1:1
    """
    entry    = round(o1 + abs(cl1 - o1) * 0.5, 2)
    sl       = round(l1 - SL_BUFFER(), 2)
    tp_swing = find_swing_tp(rates, "BUY", entry, sl)
    tp       = tp_swing if tp_swing else round(entry + (entry - sl) * 1.0, 2)
    tp_note  = f"Swing High:{tp}" if tp_swing else "RR1:1 (ไม่พบ Swing ≥1:1)"
    return entry, sl, tp, tp_note


def calc_tp_sl_s1_sell_A(rates, o1, h1, l1, cl1):
    """
    ท่าที่ 1 Pattern A SELL
    Entry = 50% Body[1]
    SL    = High[1] + SL_BUFFER()
    TP    = Swing Low ย่อย/หลัก ที่ RR≥1:1 | fallback RR 1:1
    """
    entry    = round(o1 - abs(cl1 - o1) * 0.5, 2)
    sl       = round(h1 + SL_BUFFER(), 2)
    tp_swing = find_swing_tp(rates, "SELL", entry, sl)
    tp       = tp_swing if tp_swing else round(entry - (sl - entry) * 1.0, 2)
    tp_note  = f"Swing Low:{tp}" if tp_swing else "RR1:1 (ไม่พบ Swing ≥1:1)"
    return entry, sl, tp, tp_note


def calc_tp_sl_s1_buy_B(rates, o1, h1, l1, cl1, l0, l2):
    """
    ท่าที่ 1 Pattern B BUY
    Entry = 50% Body[1]
    SL    = min(Low[0], Low[1], Low[2]) - SL_BUFFER()
    TP    = Swing High ย่อย/หลัก ที่ RR≥1:1 | fallback RR 1:1
    """
    body1    = abs(cl1 - o1)
    entry    = round(o1 + body1 * 0.5, 2)
    lowest   = min(l0, l1, l2)
    sl       = round(lowest - SL_BUFFER(), 2)
    tp_swing = find_swing_tp(rates, "BUY", entry, sl)
    tp       = tp_swing if tp_swing else round(entry + (entry - sl) * 1.0, 2)
    tp_note  = f"Swing High:{tp}" if tp_swing else "RR1:1 (ไม่พบ Swing ≥1:1)"
    return entry, sl, tp, tp_note


def calc_tp_sl_s1_sell_B(rates, o1, h1, l1, cl1, h0, h2):
    """
    ท่าที่ 1 Pattern B SELL
    Entry = 50% Body[1]
    SL    = max(High[0], High[1], High[2]) + SL_BUFFER()
    TP    = Swing Low ย่อย/หลัก ที่ RR≥1:1 | fallback RR 1:1
    """
    body1    = abs(cl1 - o1)
    entry    = round(o1 - body1 * 0.5, 2)
    highest  = max(h0, h1, h2)
    sl       = round(highest + SL_BUFFER(), 2)
    tp_swing = find_swing_tp(rates, "SELL", entry, sl)
    tp       = tp_swing if tp_swing else round(entry - (sl - entry) * 1.0, 2)
    tp_note  = f"Swing Low:{tp}" if tp_swing else "RR1:1 (ไม่พบ Swing ≥1:1)"
    return entry, sl, tp, tp_note


def calc_tp_sl_s1_buy_C(rates, o1, h1, l1, cl1):
    """
    ท่าที่ 1 Pattern C BUY (ย้อนโครงสร้าง)
    Entry = 50% Body[1]
    SL    = Low[1] - SL_BUFFER()
    TP    = Swing High ย่อย/หลัก ที่ RR≥1:1 | fallback RR 1:1
    """
    return calc_tp_sl_s1_buy_A(rates, o1, h1, l1, cl1)


def calc_tp_sl_s1_sell_C(rates, o1, h1, l1, cl1):
    """
    ท่าที่ 1 Pattern C SELL
    Entry = 50% Body[1]
    SL    = High[1] + SL_BUFFER()
    TP    = Swing Low ย่อย/หลัก ที่ RR≥1:1 | fallback RR 1:1
    """
    return calc_tp_sl_s1_sell_A(rates, o1, h1, l1, cl1)


def calc_tp_sl_s2_buy(rates, gap_bot, gap_top, h1, l2):
    """
    ท่าที่ 2 FVG BUY
    Entry = High[1] + Gap × 0.90   (90% ของ Gap)
    SL    = Low[2] - SL_BUFFER     (ใต้ Imbalance candle)
    TP    = Swing High ย่อย/หลัก ที่ RR≥1:1 | fallback RR 1:1
    Gap   = gap_top - gap_bot (Low[3] - High[1])
    """
    gap      = gap_top - gap_bot
    entry    = round(gap_bot + gap * 0.90, 2)   # High[1] + Gap*0.90
    sl       = round(l2 - SL_BUFFER(), 2)
    tp_swing = find_swing_tp(rates, "BUY", entry, sl)
    tp       = tp_swing if tp_swing else round(entry + (entry - sl) * 1.0, 2)
    tp_note  = f"Swing High:{tp}" if tp_swing else "RR1:1 (ไม่พบ Swing ≥1:1)"
    return entry, sl, tp, tp_note


def calc_tp_sl_s2_sell(rates, gap_bot, gap_top, l1, h2):
    """
    ท่าที่ 2 FVG SELL
    Entry = Low[1] - Gap × 0.90   (90% ของ Gap)
    SL    = High[2] + SL_BUFFER   (เหนือ Imbalance candle)
    TP    = Swing Low ย่อย/หลัก ที่ RR≥1:1 | fallback RR 1:1
    Gap   = gap_top - gap_bot (Low[1] - High[3])
    """
    gap      = gap_top - gap_bot
    entry    = round(gap_top - gap * 0.90, 2)   # Low[1] - Gap*0.90
    sl       = round(h2 + SL_BUFFER(), 2)
    tp_swing = find_swing_tp(rates, "SELL", entry, sl)
    tp       = tp_swing if tp_swing else round(entry - (sl - entry) * 1.0, 2)
    tp_note  = f"Swing Low:{tp}" if tp_swing else "RR1:1 (ไม่พบ Swing ≥1:1)"
    return entry, sl, tp, tp_note


def calc_tp_sl_s3_buy(rates, o1, h1, l1):
    """
    ท่าที่ 3 DM SP BUY
    Entry = Open[1]  SL = Low[1] - SL_BUFFER()  TP = Swing/RR1:1
    """
    entry    = round(o1, 2)
    sl       = round(l1 - SL_BUFFER(), 2)
    tp_swing = find_swing_tp(rates, "BUY", entry, sl)
    tp       = tp_swing if tp_swing else round(entry + (entry - sl) * 1.0, 2)
    tp_note  = f"Swing High:{tp}" if tp_swing else "RR1:1 (fallback)"
    return entry, sl, tp, tp_note


def calc_tp_sl_s3_sell(rates, o1, h1, l1):
    """
    ท่าที่ 3 DM SP SELL
    Entry = Open[1]  SL = High[1] + SL_BUFFER()  TP = Swing/RR1:1
    """
    entry    = round(o1, 2)
    sl       = round(h1 + SL_BUFFER(), 2)
    tp_swing = find_swing_tp(rates, "SELL", entry, sl)
    tp       = tp_swing if tp_swing else round(entry - (sl - entry) * 1.0, 2)
    tp_note  = f"Swing Low:{tp}" if tp_swing else "RR1:1 (fallback)"
    return entry, sl, tp, tp_note
