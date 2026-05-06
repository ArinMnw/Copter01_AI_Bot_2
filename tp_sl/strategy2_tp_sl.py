from config import SYMBOL, SL_BUFFER()
from mt5_utils import find_swing_tp


def calc_fvg_buy(rates, gap_bot, gap_top, l2):
    """FVG BUY: Entry=98%Gap จากล่าง, SL=Low[2]-200"""
    gap_size = gap_top - gap_bot
    entry    = round(gap_bot + gap_size * 0.98, 2)
    sl       = round(l2 - SL_BUFFER(), 2)
    tp_swing = find_swing_tp(rates, "BUY", entry, sl)
    tp       = tp_swing if tp_swing else round(entry + (entry - sl) * 1.0, 2)
    return entry, sl, tp


def calc_fvg_sell(rates, gap_bot, gap_top, h2):
    """FVG SELL: Entry=98%Gap จากบน, SL=High[2]+200"""
    gap_size = gap_top - gap_bot
    entry    = round(gap_top - gap_size * 0.98, 2)
    sl       = round(h2 + SL_BUFFER(), 2)
    tp_swing = find_swing_tp(rates, "SELL", entry, sl)
    tp       = tp_swing if tp_swing else round(entry - (sl - entry) * 1.0, 2)
    return entry, sl, tp
