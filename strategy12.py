import MetaTrader5 as mt5
import config
import time as _time

_s12_state = {
    "side": None,              # "BUY" | "SELL" | None
    "order_count": 0,          # orders เปิดใน zone ปัจจุบัน
    "last_entry_price": None,  # ราคา entry ของ order ล่าสุด
    "tickets": [],             # tickets ของ S12 positions
    "last_sl_time": 0.0,       # timestamp ครั้งล่าสุดที่ SL hit (Fix 1: cooldown)
}


def s12_get_swing(rates, lookback: int):
    """คืน (swing_high, swing_low) จาก M5 bars"""
    n = min(lookback, len(rates))
    bars = rates[-n:]
    return (
        max(float(r["high"]) for r in bars),
        min(float(r["low"])  for r in bars),
    )


def s12_get_tp(rates_m15, direction: str):
    """คืน TP จาก M15 swing high (BUY) หรือ swing low (SELL)"""
    if rates_m15 is None or len(rates_m15) < 5:
        return None
    n = min(50, len(rates_m15))
    bars = rates_m15[-n:]
    if direction == "BUY":
        return max(float(r["high"]) for r in bars)
    return min(float(r["low"]) for r in bars)


def s12_cleanup_tickets():
    """ลบ ticket ที่ปิดไปแล้ว (TP/SL hit) ออกจาก state
    Fix 1: ถ้าปิดด้วย SL → บันทึก last_sl_time สำหรับ cooldown
    """
    if not _s12_state["tickets"]:
        return
    open_tickets = {p.ticket for p in (mt5.positions_get(symbol=config.SYMBOL) or [])}
    closed = [t for t in _s12_state["tickets"] if t not in open_tickets]
    _s12_state["tickets"] = [t for t in _s12_state["tickets"] if t in open_tickets]

    # Fix 1: ตรวจว่า ticket ที่ปิดไปถูก SL hit หรือไม่
    if closed:
        for t in closed:
            deals = mt5.history_deals_get(position=t)
            if deals:
                close_deal = sorted(deals, key=lambda d: d.time)[-1]
                if getattr(close_deal, "reason", -1) == mt5.DEAL_REASON_SL:
                    _s12_state["last_sl_time"] = _time.time()
                    break  # พบ SL hit แล้ว ไม่ต้องวนต่อ

    if not _s12_state["tickets"]:
        _s12_state["side"] = None
        _s12_state["order_count"] = 0
        _s12_state["last_entry_price"] = None
