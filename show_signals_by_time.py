"""
show_signals_by_time.py — ดู signal/order ที่เกิดในช่วงเวลาที่กำหนด ครบ 3 อย่าง:
  1. PATTERN_FOUND  — pattern ที่ scanner เจอ (มีหรือไม่มี order ตามมาก็แสดง)
  2. ORDER_CREATED  — order ที่ถูกสร้างจาก pattern นั้น (ticket/entry/sl/tp)
  3. ผลปิด          — ปิดที่ TP/SL เท่าไหร่ หรือ ORDER_CANCELED/POSITION_CLOSED เพราะอะไร

Usage:
    python show_signals_by_time.py 2026-06-24 18:00
    python show_signals_by_time.py 2026-06-24 18:00 19:00
    python show_signals_by_time.py 2026-06-24 18:00 --window 15

หมายเหตุ timezone: เวลาที่ใส่ต้องเป็น UTC+7 (เวลา BKK จริง) — bot.log เขียน
timestamp ผ่าน now_bkk()/mt5_ts_to_bkk() ซึ่งตรวจสอบแล้วคืนค่า BKK ถูกต้อง
อยู่แล้ว (ยืนยันด้วย ohlc_lookup.py + เทียบ MT5_SERVER_TZ auto-refresh กับ
เวลาจริง) เวลาที่ใส่สคริปต์นี้จึงตรงกับเวลานาฬิกาจริง/เวลาที่พิมพ์ถาม Telegram
ได้เลย ไม่ต้องบวก/ลบชั่วโมงใดๆ
(comment เก่าใน handlers/text_handler.py ที่บอกว่า mt5_ts_to_bkk คืน UTC+6
แล้วต้อง +1h ชดเชย เป็น comment ล้าสมัย/บัค — เขียนไว้ตอน MT5_SERVER_TZ ยัง
hardcode ผิด ก่อนมี auto-refresh logic ปัจจุบัน)
"""
import re, sys, os
from datetime import datetime, timedelta

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.abspath(__file__))


def parse_args():
    args = sys.argv[1:]
    if len(args) < 2:
        print("Usage: python show_signals_by_time.py <date> <start_time> [end_time] [--window N]")
        print("       python show_signals_by_time.py 2026-06-24 18:00")
        print("       python show_signals_by_time.py 2026-06-24 18:00 19:00")
        print("       python show_signals_by_time.py 2026-06-24 18:00 --window 15")
        sys.exit(0)

    date_str = args[0]
    start_str = args[1]
    end_str = None
    window = 1  # default 1 minute window

    i = 2
    while i < len(args):
        if args[i] == "--window" and i + 1 < len(args):
            window = int(args[i + 1])
            i += 2
        elif not args[i].startswith("--"):
            end_str = args[i]
            i += 1
        else:
            i += 1

    start_dt = datetime.strptime(f"{date_str} {start_str}", "%Y-%m-%d %H:%M")
    if end_str:
        end_dt = datetime.strptime(f"{date_str} {end_str}", "%Y-%m-%d %H:%M")
    else:
        end_dt = start_dt + timedelta(minutes=window)

    return start_dt, end_dt


def fld(line, key):
    # field separator คือ " | " (เว้นวรรค-pipe-เว้นวรรค) ไม่ใช่ "|" เปล่าๆ
    # เพราะค่าบางฟิลด์ (เช่น flow_id, order_type) มี "|" ติดกันไม่มีเว้นวรรค
    # อยู่ข้างในค่าของมันเอง (เช่น flow_id=M1|S1|BUY|T...) ถ้าตัดที่ "|" เฉยๆ
    # จะได้ค่าผิด/สั้นเกินไป
    m = re.search(rf"{key}=(.*?)(?:\s\|\s|$)", line)
    return m.group(1) if m else ""


def load_log_files():
    try:
        sys.path.insert(0, ROOT)
        from log_sources import bot_log_files
        files = bot_log_files()
        if files:
            return files
    except Exception:
        pass
    files = []
    log_dir = os.path.join(ROOT, "logs")
    if os.path.isdir(log_dir):
        import glob
        files += sorted(glob.glob(os.path.join(log_dir, "bot-2[0-9][0-9][0-9]-[0-9][0-9]*.log")))
        files += sorted(glob.glob(os.path.join(log_dir, "bot-2[0-9][0-9][0-9]-[0-9][0-9]*.log.bak-*")))
    bot_log = os.path.join(ROOT, "logs", "bot.log")
    if os.path.exists(bot_log):
        files.append(bot_log)
    return files


def parse_ts(line):
    m = re.match(r"^\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\]", line)
    if not m:
        return None
    try:
        return datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None


def extract_pattern_text(line, event_name):
    pm = re.match(rf"^\[.*?\]\s+{event_name}\s+\|\s+([^|]+)\|", line)
    return pm.group(1).strip() if pm else ""


def _norm_dmy_time(s):
    """fill_time/close_time ใน log เก็บเป็น 'HH:MM:SS DD/MM/YYYY' (คนละ format
    กับ bracket timestamp หลักที่เป็น 'YYYY-MM-DD HH:MM:SS') แปลงให้เหมือนกัน
    เพื่อให้เทียบ/อ่านง่าย"""
    if not s:
        return s
    m = re.match(r"(\d{2}:\d{2}:\d{2})\s+(\d{2})/(\d{2})/(\d{4})", s)
    if not m:
        return s
    t, d, mo, y = m.groups()
    return f"{y}-{mo}-{d} {t}"


def show_m1_ohlc_at(dt_bkk):
    """ดึง OHLC ของแท่ง M1 ที่เวลา dt_bkk (BKK จริง, UTC+7) ตรงจาก MT5 — logic
    เดียวกับ ohlc_lookup.py/handle_ohlc_lookup แต่ทำ inline ในตัวนี้เลย"""
    try:
        import config
        from mt5_utils import connect_mt5
        import mt5_worker as mt5
    except Exception as e:
        print(f"(ดึง OHLC M1 ไม่ได้: import ไม่ผ่าน — {e})")
        return

    if not connect_mt5():
        print("(ดึง OHLC M1 ไม่ได้: เชื่อมต่อ MT5 ไม่ได้)")
        return

    from datetime import timezone as _tz
    BKK = _tz(timedelta(hours=config.TZ_OFFSET))
    dt_aware = dt_bkk.replace(tzinfo=BKK)
    ts_query = int(dt_aware.timestamp()) + config.MT5_SERVER_TZ * 3600

    symbol = config.SYMBOL
    tf_secs = 60
    rates = mt5.copy_rates_range(symbol, mt5.TIMEFRAME_M1, ts_query - tf_secs, ts_query + tf_secs)
    if rates is None or len(rates) == 0:
        rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M1, 0, 1000)

    bar = None
    if rates is not None:
        for r in rates:
            if r["time"] <= ts_query < r["time"] + tf_secs:
                bar = r
                break

    if bar is None:
        print(f"(ไม่พบแท่ง M1 ที่เวลา {dt_bkk.strftime('%Y-%m-%d %H:%M')})")
        return

    bar_bkk = config.mt5_ts_to_bkk(bar["time"])
    bar_bkk_str = bar_bkk.strftime("%Y-%m-%d %H:%M") if bar_bkk else "-"
    o, h, l, c = (float(bar[k]) for k in ("open", "high", "low", "close"))
    color = "🟢 GREEN" if c >= o else "🔴 RED"
    print(f"OHLC M1 [{bar_bkk_str}]  {color}  O:{o:.2f}  H:{h:.2f}  L:{l:.2f}  C:{c:.2f}  Vol:{bar['tick_volume']}")


def main():
    start_dt, end_dt = parse_args()

    print(f"\nช่วงเวลา: {start_dt.strftime('%Y-%m-%d %H:%M')} -> {end_dt.strftime('%Y-%m-%d %H:%M')}")
    show_m1_ohlc_at(start_dt)
    print("=" * 110)

    patterns = []          # PATTERN_FOUND ในช่วงเวลา (key: flow_id)
    orders_by_flow = {}    # flow_id -> order dict (อาจอยู่นอกช่วงเวลาที่ระบุได้เล็กน้อยถ้า scan ช้า แต่ปกติจะติดกัน)
    orders_by_ticket = {}  # ticket -> order dict
    closes_by_ticket = {}  # ticket -> close/cancel dict
    fills_by_ticket = {}   # ticket -> fill_time (จาก ENTRY_FILL, มีแค่ order ที่เป็น pending limit/stop ที่โดน fill จริง)

    files = load_log_files()

    # รอบ 1: เก็บ PATTERN_FOUND ในช่วงเวลา + ORDER_CREATED ทั้งหมด (ไว้ match flow_id)
    for path in files:
        try:
            with open(path, encoding="utf-8", errors="replace") as f:
                for line in f:
                    ts = parse_ts(line)
                    if ts is None:
                        continue

                    if "PATTERN_FOUND" in line and (start_dt <= ts < end_dt):
                        flow_id = fld(line, "flow_id")
                        patterns.append({
                            "ts": ts.strftime("%Y-%m-%d %H:%M:%S"),
                            "flow_id": flow_id,
                            "sid": fld(line, "sid"),
                            "tf": fld(line, "tf"),
                            "signal": fld(line, "signal"),
                            "entry": fld(line, "entry"),
                            "sl": fld(line, "sl"),
                            "tp": fld(line, "tp"),
                            "pattern": extract_pattern_text(line, "PATTERN_FOUND"),
                        })

                    if "ORDER_CREATED" in line:
                        flow_id = fld(line, "flow_id")
                        ticket = fld(line, "ticket")
                        order = {
                            "ts": ts.strftime("%Y-%m-%d %H:%M:%S"),
                            "ticket": ticket,
                            "order_type": fld(line, "order_type"),
                            "entry": fld(line, "entry"),
                            "sl": fld(line, "sl"),
                            "tp": fld(line, "tp"),
                        }
                        if flow_id:
                            orders_by_flow[flow_id] = order
                        if ticket:
                            orders_by_ticket[ticket] = order
        except Exception:
            pass

    if not patterns:
        print("  ไม่พบ pattern ในช่วงเวลานี้")
        print()
        return

    needed_tickets = {orders_by_flow[p["flow_id"]]["ticket"]
                       for p in patterns if p["flow_id"] in orders_by_flow}

    # รอบ 2: หาผลปิด (POSITION_CLOSED / ORDER_CANCELED) เฉพาะ ticket ที่เกี่ยวข้อง
    for path in files:
        try:
            with open(path, encoding="utf-8", errors="replace") as f:
                for line in f:
                    if "POSITION_CLOSED" in line:
                        ticket = fld(line, "ticket")
                        if ticket in needed_tickets and ticket not in closes_by_ticket:
                            closes_by_ticket[ticket] = {
                                "kind": "CLOSED",
                                "profit": fld(line, "profit"),
                                "close_price": fld(line, "close_price"),
                                "reason": fld(line, "reason"),
                                "close_time": fld(line, "close_time"),
                            }
                    elif "ORDER_CANCELED" in line:
                        ticket = fld(line, "ticket")
                        if ticket in needed_tickets and ticket not in closes_by_ticket:
                            reason = extract_pattern_text(line, "ORDER_CANCELED")
                            closes_by_ticket[ticket] = {
                                "kind": "CANCELED",
                                "reason": reason,
                            }
                    elif "ENTRY_FILL" in line:
                        ticket = fld(line, "ticket")
                        if ticket in needed_tickets and ticket not in fills_by_ticket:
                            fills_by_ticket[ticket] = fld(line, "fill_time")
        except Exception:
            pass

    patterns.sort(key=lambda r: r["ts"])

    LABEL_W = 14   # ความกว้างคอลัมน์ label (Pattern_Found / Order_Created / ...)
    SEP = "-" * 110

    def row(label, ts, text):
        ts_part = f"[{ts}] " if ts else ""
        print(f"{label:<{LABEL_W}}{ts_part}{text}")

    for idx, p in enumerate(patterns):
        if idx > 0:
            print(SEP)

        sig_icon = "🟢" if p["signal"] == "BUY" else "🔴"
        order = orders_by_flow.get(p["flow_id"])

        # หัวข้อบรรทัดเดียว: pattern + ของ order (ticket/type/entry/sl/tp) ถ้ามี
        # order — ถ้าไม่มี order (โดน guard บล็อก) ใช้ entry/sl/tp ของ pattern แทน
        header = f"{sig_icon} S{p['sid']} {p['tf']}  {p['pattern']}"
        if order:
            header += (f"  ticket={order['ticket']}  type={order['order_type']}  "
                       f"entry={order['entry']}  sl={order['sl']}  tp={order['tp']}")
        else:
            header += f"  entry={p['entry']}  sl={p['sl']}  tp={p['tp']}"
        print(header)
        print()

        row("Pattern_Found", p["ts"], "")

        if not order:
            row("Order_Created", None, "-- ไม่มี order ตามมา (ถูก guard บล็อกตั้งแต่ก่อนสร้าง order)")
            row("Fill_Order", None, "-- (ไม่มี order ให้ fill)")
            row("Close", None, "-- (ไม่มี order ให้ปิด)")
            continue

        row("Order_Created", order["ts"], "")

        fill_time = _norm_dmy_time(fills_by_ticket.get(order["ticket"]))
        if fill_time:
            row("Fill_Order", fill_time, "")
        elif "MARKET" in (order["order_type"] or "") or order["order_type"] in ("BUY", "SELL"):
            row("Fill_Order", order["ts"], "(market order — fill ทันทีตอนสร้าง)")
        else:
            row("Fill_Order", None, "-- ยังไม่เจอ fill (อาจยังไม่ถูก fill หรือยังเป็น pending)")

        close = closes_by_ticket.get(order["ticket"])
        if not close:
            row("Close", None, "-- ยังไม่ปิด/ไม่พบผล (อาจยังเปิดอยู่ หรืออยู่นอก log ที่มี)")
        elif close["kind"] == "CANCELED":
            row("Close", None, f"CANCELED -- เหตุผล: {close['reason']}")
        else:
            profit = close["profit"]
            try:
                profit_f = float(profit)
                profit_tag = "✅ กำไร" if profit_f > 0 else ("❌ ขาดทุน" if profit_f < 0 else "⚪ เท่าทุน")
            except ValueError:
                profit_tag = ""
            close_time = _norm_dmy_time(close["close_time"])
            row("Close", close_time,
                f"@ {close['close_price']}  profit={profit} {profit_tag}  เหตุผล: {close['reason']}")

    print(SEP)
    print(f"รวม {len(patterns)} pattern ที่เจอในช่วงเวลานี้")
    print()


if __name__ == "__main__":
    main()
