from config import *
from strategy4 import _find_prev_swing_high, _find_prev_swing_low


def strategy_8(rates):
    """ท่าที่ 8: กินไส้ Swing วาง LIMIT สูตรเดิม แล้วค่อยใส่ SL ตอน breakout"""
    if len(rates) < 10:
        return {"signal": "WAIT", "reason": "ข้อมูลไม่เพียงพอ", "orders": []}

    sh_info = _find_prev_swing_high(rates)
    sl_info = _find_prev_swing_low(rates)
    orders = []
    # Swing High -> SELL LIMIT
    if sh_info and sl_info:
        sh_candle = sh_info["candle"]
        sh_high = float(sh_candle["high"])
        sh_low = float(sh_candle["low"])
        sh_range = sh_high - sh_low

        if sh_range > 0:
            entry = round(sh_high + sh_range * 0.17, 2)
            sl = round(sh_high + sh_range * 0.31, 2)
            tp = float(sl_info["price"])
            if tp < entry:
                orders.append({
                    "signal": "SELL",
                    "entry": entry,
                    "sl": sl,
                    "tp": tp,
                    "pattern": "ท่าที่ 8 กินไส้ Swing 🔴 SELL",
                    "reason": (
                        f"📈 Swing High: {sh_info['price']:.2f} "
                        f"(H:{sh_high:.2f} L:{sh_low:.2f} range:{sh_range:.2f})\n"
                        f"📌 Entry: H+17%={entry:.2f}\n"
                        f"🛑 SL: H+31%={sl:.2f}\n"
                        f"⏳ จะใส่ SL เมื่อ breakout เหนือ Swing High ก่อน\n"
                        f"🎯 TP: Swing Low={tp:.2f}"
                    ),
                    "swing_price": float(sh_info["price"]),
                    "swing_bar_time": int(sh_info["time"]),
                    "candles": [],
                    "swing_high": float(sh_info["price"]),
                    "swing_low": float(sl_info["price"]),
                })

    # Swing Low -> BUY LIMIT
    if sl_info and sh_info:
        sl_candle = sl_info["candle"]
        sl_high = float(sl_candle["high"])
        sl_low = float(sl_candle["low"])
        sl_range = sl_high - sl_low

        if sl_range > 0:
            entry = round(sl_low - sl_range * 0.17, 2)
            sl = round(sl_low - sl_range * 0.31, 2)
            tp = float(sh_info["price"])
            if tp > entry:
                orders.append({
                    "signal": "BUY",
                    "entry": entry,
                    "sl": sl,
                    "tp": tp,
                    "pattern": "ท่าที่ 8 กินไส้ Swing 🟢 BUY",
                    "reason": (
                        f"📉 Swing Low: {sl_info['price']:.2f} "
                        f"(H:{sl_high:.2f} L:{sl_low:.2f} range:{sl_range:.2f})\n"
                        f"📌 Entry: L-17%={entry:.2f}\n"
                        f"🛑 SL: L-31%={sl:.2f}\n"
                        f"⏳ จะใส่ SL เมื่อ breakout ใต้ Swing Low ก่อน\n"
                        f"🎯 TP: Swing High={tp:.2f}"
                    ),
                    "swing_price": float(sl_info["price"]),
                    "swing_bar_time": int(sl_info["time"]),
                    "candles": [],
                    "swing_high": float(sh_info["price"]),
                    "swing_low": float(sl_info["price"]),
                })

    if not orders:
        reason = "ไม่พบ Swing High/Low" if not sh_info or not sl_info else "TP ไม่ valid"
        return {"signal": "WAIT", "reason": reason, "orders": []}

    return {"signal": "MULTI", "orders": orders}
