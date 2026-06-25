"""
ohlc_lookup.py — ดู OHLC ของแท่งราคาตามเวลาที่ระบุ ตรงผ่าน MT5 (CLI, ไม่ต้องผ่าน Telegram)

ใช้ logic เดียวกับ handlers/text_handler.py:handle_ohlc_lookup() เป๊ะๆ
(รวม known bug ของ mt5_ts_to_bkk ที่คืนค่า UTC+6 แล้วต้อง +1h ตอนแสดงผล)
เพื่อให้ผลตรงกับที่พิมพ์ถาม Telegram bot ทุกประการ

หมายเหตุ timezone: เวลาที่พิมพ์ใส่ต้องเป็น "เวลา BKK จริง" (UTC+7) — เหมือนกับ
ที่พิมพ์ถาม Telegram (เช่น `M1 24-06-2026 18:56`) ไม่ใช่ UTC+6 แบบ timestamp
ดิบใน logs/bot.log (ถ้าจะเทียบกับเวลาใน bot.log/show_signals_by_time.py
ต้องบวก 1 ชั่วโมงก่อนใส่ที่นี่)

ใช้ mt5_utils.connect_mt5() (ผ่าน mt5_worker.py) เหมือน bot ตัวจริง — รันแยก
process ได้ปลอดภัย ไม่ชนกับ bot ที่รันอยู่ (read-only, ไม่แก้ order)

Usage:
    python ohlc_lookup.py M1 24-06-2026 18:56
    python ohlc_lookup.py M5 24-06-2026 19:08 XAUUSD.iux
"""
import sys
from datetime import datetime, timezone, timedelta

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import config
from mt5_utils import connect_mt5
import mt5_worker as mt5

_TF_MT5 = {
    "M1": mt5.TIMEFRAME_M1, "M5": mt5.TIMEFRAME_M5, "M15": mt5.TIMEFRAME_M15,
    "M30": mt5.TIMEFRAME_M30, "H1": mt5.TIMEFRAME_H1, "H4": mt5.TIMEFRAME_H4,
    "H12": mt5.TIMEFRAME_H12, "D1": mt5.TIMEFRAME_D1,
}
_TF_SECS = {
    "M1": 60, "M5": 300, "M15": 900, "M30": 1800,
    "H1": 3600, "H4": 14400, "H12": 43200, "D1": 86400,
}


def main():
    args = sys.argv[1:]
    if len(args) < 3:
        print("Usage: python ohlc_lookup.py <TF> <DD-MM-YYYY> <HH:MM> [symbol]")
        print("       python ohlc_lookup.py M1 24-06-2026 18:56")
        print("\n(เวลาที่ใส่ = BKK จริง UTC+7 เหมือนพิมพ์ถาม Telegram — ถ้าเทียบกับ")
        print(" เวลาใน bot.log/show_signals_by_time.py ที่เป็น UTC+6 ต้อง +1 ชั่วโมงก่อน)")
        sys.exit(0)

    tf_str, date_str, time_str = args[0].upper(), args[1], args[2]
    symbol_str = args[3] if len(args) > 3 else None

    if tf_str not in _TF_MT5:
        print(f"ไม่รู้จัก timeframe '{tf_str}' — รองรับ: {', '.join(_TF_MT5)}")
        sys.exit(1)

    try:
        dt_naive = datetime.strptime(f"{date_str} {time_str}", "%d-%m-%Y %H:%M")
    except ValueError:
        print("รูปแบบวันที่/เวลาไม่ถูกต้อง ตัวอย่าง: 24-06-2026 18:56")
        sys.exit(1)

    BKK = timezone(timedelta(hours=config.TZ_OFFSET))
    dt_bkk = dt_naive.replace(tzinfo=BKK)
    ts_query = int(dt_bkk.timestamp()) + config.MT5_SERVER_TZ * 3600

    if not connect_mt5():
        print("เชื่อมต่อ MT5 ไม่ได้")
        sys.exit(1)

    symbol = symbol_str.strip() if symbol_str else config.SYMBOL
    sym_info = mt5.symbol_info(symbol)
    if sym_info is None and not symbol.endswith(".iux"):
        alt = f"{symbol}.iux"
        if mt5.symbol_info(alt):
            symbol = alt
            sym_info = mt5.symbol_info(symbol)
    if sym_info is None:
        print(f"ไม่พบ symbol '{symbol}' ใน MT5")
        sys.exit(1)

    tf_const = _TF_MT5[tf_str]
    tf_secs = _TF_SECS[tf_str]
    start_time = ts_query - tf_secs
    end_time = ts_query + tf_secs
    rates = mt5.copy_rates_range(symbol, tf_const, start_time, end_time)
    if rates is None or len(rates) == 0:
        rates = mt5.copy_rates_from_pos(symbol, tf_const, 0, 1000)

    matching_bar = None
    if rates is not None and len(rates) > 0:
        for r in rates:
            if r["time"] <= ts_query < r["time"] + tf_secs:
                matching_bar = r
                break

    if matching_bar is None:
        print(f"ไม่พบแท่งราคา {tf_str} ที่เวลา BKK {date_str} {time_str}")
        sys.exit(1)

    # mt5_ts_to_bkk คืนเวลา BKK จริงอยู่แล้ว (ตรวจสอบแล้วว่า MT5_SERVER_TZ
    # auto-refresh ปัจจุบันคำนวณถูก) ไม่ต้อง +1h ชดเชยเหมือนใน text_handler.py
    # (comment เก่าตรงนั้นเขียนไว้ตอน MT5_SERVER_TZ ยัง hardcode ผิด — ล้าสมัยแล้ว)
    bar_bkk = config.mt5_ts_to_bkk(matching_bar["time"])
    bar_bkk_str = bar_bkk.strftime("%d-%m-%Y %H:%M") if bar_bkk else "-"

    o, h, l, c = (float(matching_bar[k]) for k in ("open", "high", "low", "close"))
    rng = h - l
    body_pct = (abs(c - o) / rng * 100) if rng > 0 else 0.0
    color = "GREEN" if c >= o else "RED"

    print(f"Symbol: {symbol}  TF: {tf_str}")
    print(f"เวลา BKK ที่ระบุ: {date_str} {time_str}")
    print(f"เวลาแท่งราคา (BKK): {bar_bkk_str}")
    print(f"{color}  Open: {o:.2f}  High: {h:.2f}  Low: {l:.2f}  Close: {c:.2f}")
    print(f"Body: {body_pct:.1f}%  (Range: {rng:.2f})  Volume: {matching_bar['tick_volume']}")


if __name__ == "__main__":
    main()
