from config import SYMBOL, SL_BUFFER()
from mt5_utils import find_swing_tp


def calc_s1_buy_a(rates, o1, cl1, l1):
    """Pattern A BUY: Entry=50%Body[1], SL=Low[1]-200"""
    entry    = round(o1 + abs(cl1 - o1) * 0.5, 2)
    sl       = round(l1 - SL_BUFFER(), 2)
    tp_swing = find_swing_tp(rates, "BUY", entry, sl)
    tp       = tp_swing if tp_swing else round(entry + (entry - sl) * 1.0, 2)
    return entry, sl, tp


def calc_s1_sell_a(rates, o1, cl1, h1):
    """Pattern A SELL: Entry=50%Body[1], SL=High[1]+200"""
    entry    = round(o1 - abs(cl1 - o1) * 0.5, 2)
    sl       = round(h1 + SL_BUFFER(), 2)
    tp_swing = find_swing_tp(rates, "SELL", entry, sl)
    tp       = tp_swing if tp_swing else round(entry - (sl - entry) * 1.0, 2)
    return entry, sl, tp


def calc_s1_buy_b(rates, o1, body1, lowest):
    """Pattern B BUY: Entry=50%Body[2], SL=Low ต่ำสุด-200"""
    entry    = round(o1 + body1 * 0.5, 2)
    sl       = round(lowest - SL_BUFFER(), 2)
    tp_swing = find_swing_tp(rates, "BUY", entry, sl)
    tp       = tp_swing if tp_swing else round(entry + (entry - sl) * 1.0, 2)
    return entry, sl, tp


def calc_s1_sell_b(rates, o1, body1, highest):
    """Pattern B SELL: Entry=50%Body[2], SL=High สูงสุด+200"""
    entry    = round(o1 - body1 * 0.5, 2)
    sl       = round(highest + SL_BUFFER(), 2)
    tp_swing = find_swing_tp(rates, "SELL", entry, sl)
    tp       = tp_swing if tp_swing else round(entry - (sl - entry) * 1.0, 2)
    return entry, sl, tp


def calc_s1_buy_c(rates, o1, cl1, lowest):
    """Pattern C BUY: Entry=50%Body[1], SL=Low ต่ำสุด-200"""
    entry    = round(o1 + abs(cl1 - o1) * 0.5, 2)
    sl       = round(lowest - SL_BUFFER(), 2)
    tp_swing = find_swing_tp(rates, "BUY", entry, sl)
    tp       = tp_swing if tp_swing else round(entry + (entry - sl) * 1.0, 2)
    return entry, sl, tp


def calc_s1_sell_c(rates, o1, cl1, highest):
    """Pattern C SELL: Entry=50%Body[1], SL=High สูงสุด+200"""
    entry    = round(o1 - abs(cl1 - o1) * 0.5, 2)
    sl       = round(highest + SL_BUFFER(), 2)
    tp_swing = find_swing_tp(rates, "SELL", entry, sl)
    tp       = tp_swing if tp_swing else round(entry - (sl - entry) * 1.0, 2)
    return entry, sl, tp
