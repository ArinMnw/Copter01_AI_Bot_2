from config import *
from bot_log import log_event
from mt5_utils import connect_mt5, open_order, find_swing_tp, should_cancel_pending, get_existing_tp, has_previous_bar_trade
from trailing import fvg_order_tickets, pending_order_tf, position_tf, position_sid


async def check_fvg_pending(app):
    """
    ตรวจ real-time ว่าราคาย้อนมาแตะ FVG Entry หรือยัง
    ถ้าแตะครั้งแรก → ตั้ง Limit Order ทันที
    """
    if not fvg_pending:
        return

    tick = mt5.symbol_info_tick(SYMBOL)
    if not tick:
        return

    ask = tick.ask
    bid = tick.bid
    now = now_bkk().strftime("%H:%M:%S")
    to_remove = []

    for key, p in fvg_pending.items():
        tf         = p["tf"]
        signal     = p["signal"]
        entry      = p["entry"]
        candle_key = p["candle_key"]

        # debug: แสดงสถานะทุก pending
        tick_now = mt5.symbol_info_tick(SYMBOL)
        cur_price = (tick_now.ask if signal == "BUY" else tick_now.bid) if tick_now else 0
        dist = round(cur_price - entry, 2) if signal == "BUY" else round(entry - cur_price, 2)
        print(f"[{now}] 🔎 FVG pending [{tf}] {signal} entry={entry} price={cur_price} dist={dist:+.2f}")

        # ถ้าเทรดแท่งนี้ไปแล้ว → ลบออก
        if last_traded_per_tf.get(tf) == candle_key:
            to_remove.append(key)
            continue

        if has_previous_bar_trade(tf, candle_key):
            prev_traded = last_traded_per_tf.get(tf)
            print(f"[{now}] ⏭️ FVG [{tf}] ข้าม: previous-bar already traded prev={prev_traded} now={candle_key}")
            to_remove.append(key)
            continue

        # ตรวจว่าควรยกเลิก (ราคาผ่านไป หรือ กลืนกิน Swing)
        rates_now = mt5.copy_rates_from_pos(SYMBOL, TF_OPTIONS.get(tf, mt5.TIMEFRAME_M1), 1, 25)
        if rates_now is not None and len(rates_now) >= 5:
            cancel, cancel_reason = should_cancel_pending(rates_now, signal, entry)
            if cancel:
                to_remove.append(key)
                print(f"\U0001f6ab [{now}] FVG [{tf}] \u0e22\u0e01\u0e40\u0e25\u0e34\u0e01: {cancel_reason[:60]}")
                await tg(app, f"\U0001f6ab *FVG {signal} [{tf}] \u0e22\u0e01\u0e40\u0e25\u0e34\u0e01 Pending*\\n{cancel_reason}")
                continue

        # เช็คว่าราคาแตะ entry หรือยัง
        # ราคาแตะ entry: BUY → ask ≤ entry (ราคามาถึงแล้ว)
        # SELL → bid ≥ entry
        # tolerance ±0.1 เพื่อรับ spread เล็กน้อย
        touched = (signal == "BUY"  and ask <= entry + 0.1) or                   (signal == "SELL" and bid >= entry - 0.1)

        if touched:
            sig_e = "🟢" if signal == "BUY" else "🔴"
            print(f"🎯 [{now}] {tf}: FVG ราคาแตะ Entry {entry}!")
            await tg(app, (
                    f"{sig_e} *FVG {signal} [{tf}]*\n"
                    f"\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\n"
                    f"\U0001f4ca \u0e23\u0e32\u0e04\u0e32\u0e22\u0e49\u0e2d\u0e19\u0e21\u0e32\u0e41\u0e15\u0e30 Entry!\n"
                    f"Gap: `{p['gap_bot']}` \u2013 `{p['gap_top']}`\n"
                    f"\U0001f4cc Entry 90%: `{entry}`\n"
                    f"\U0001f6d1 SL: `{p['sl']}` | \U0001f3af TP: `{p['tp']}`\n"
                    f"\u23f3 \u0e15\u0e31\u0e49\u0e07 Limit Order..."
                ))
            # TP เดียวกับ Order แรก ถ้ามี
            fvg_tp = get_existing_tp(signal, entry, tf) or p["tp"]
            order = open_order(signal, get_volume(), p["sl"], fvg_tp, entry_price=entry, tf=tf, sid=2, pattern=p.get("pattern", f"FVG {signal} [{tf}]"))
            if order["success"]:
                last_traded_per_tf[tf] = candle_key
                ot_name = order.get("order_type", "LIMIT")
                # ── register ตรวจคุณภาพแท่งหลัง order เข้า ──
                if order.get("ticket"):
                    fvg_order_tickets[order["ticket"]] = {
                        "tf":      tf,
                        "signal":  signal,
                        "checked": False,
                    }
                    pending_order_tf[order["ticket"]] = {
                        "tf": tf,
                        "gap_bot": p["gap_bot"],
                        "gap_top": p["gap_top"],
                        "detect_bar_time": candle_key,
                        "signal": signal,
                        "sid": 2,
                        "pattern": f"FVG {signal} [{tf}]",
                    }
                    position_tf[order["ticket"]] = tf
                    position_sid[order["ticket"]] = 2
                    from trailing import position_pattern as _pos_pat
                    _pos_pat[order["ticket"]] = f"FVG {signal} [{tf}]"
                    log_event(
                        "ORDER_CREATED",
                        f"FVG {signal} [{tf}]",
                        tf=tf,
                        sid=2,
                        signal=signal,
                        entry=entry,
                        sl=p["sl"],
                        tp=fvg_tp,
                        ticket=order["ticket"],
                        order_type=ot_name,
                    )
                await tg(app, (
                        f"\u2705 *{ot_name} FVG \u0e2a\u0e33\u0e40\u0e23\u0e47\u0e08!*\n"
                        f"{sig_e} {ot_name} [{tf}]\n"
                        f"\U0001f4cc Entry: `{order['price']}`\n"
                        f"\U0001f516 Ticket: `{order['ticket']}`"
                    ))
            else:
                log_event(
                    "ORDER_SKIPPED" if order.get("skipped") else "ORDER_FAILED",
                    order.get("error", ""),
                    tf=tf,
                    sid=2,
                    signal=signal,
                    entry=entry,
                    sl=p["sl"],
                    tp=fvg_tp,
                )
                if not order.get("skipped"):
                    await tg(app, f"❌ FVG [{tf}] ไม่สำเร็จ: `{order['error']}`")
            to_remove.append(key)

    for k in to_remove:
        fvg_pending.pop(k, None)


async def check_pb_pending(app):
    """
    Pattern B วิธี 2: ตรวจว่าราคาปัจจุบันแตะ Entry (50% Body[1]) หรือยัง
    ถ้าแตะ → ตั้ง Limit Order ทันที (แม้แท่ง[0] ยังวิ่งอยู่)
    """
    if not pb_pending:
        return

    tick = mt5.symbol_info_tick(SYMBOL)
    if not tick:
        return

    ask = tick.ask
    bid = tick.bid
    now = now_bkk().strftime("%H:%M:%S")
    to_remove = []

    for key, p in pb_pending.items():
        entry  = p["entry"]
        signal = p["signal"]
        tf     = p["tf"]
        candle_key = p["candle_key"]  # last_candle_time ของแท่ง[1]

        # เช็คว่ายังไม่เคยเทรดแท่งนี้ใน TF นี้
        if last_traded_per_tf.get(tf) == candle_key:
            to_remove.append(key)
            continue

        if has_previous_bar_trade(tf, candle_key):
            prev_traded = last_traded_per_tf.get(tf)
            print(f"[{now}] ⏭️ PB [{tf}] ข้าม: previous-bar already traded prev={prev_traded} now={candle_key}")
            to_remove.append(key)
            continue

        # ตรวจว่าควรยกเลิก (ราคาผ่านไป หรือ กลืนกิน Swing)
        rates_now = mt5.copy_rates_from_pos(SYMBOL, TF_OPTIONS.get(tf, mt5.TIMEFRAME_M1), 1, 25)
        if rates_now is not None and len(rates_now) >= 5:
            cancel, cancel_reason = should_cancel_pending(rates_now, signal, entry)
            if cancel:
                to_remove.append(key)
                print(f"\U0001f6ab [{now}] PB [{tf}] \u0e22\u0e01\u0e40\u0e25\u0e34\u0e01: {cancel_reason[:60]}")
                await tg(app, f"\U0001f6ab *PB {signal} [{tf}] \u0e22\u0e01\u0e40\u0e25\u0e34\u0e01 Pending*\\n{cancel_reason}")
                continue

        # เช็คว่าราคาแตะ entry หรือยัง
        touched = (signal == "BUY"  and ask <= entry) or                   (signal == "SELL" and bid >= entry)

        if touched:
            sig_e = "🟢" if signal == "BUY" else "🔴"
            print(f"🎯 [{now}] {tf}: Pattern B วิธี 2 — ราคาแตะ Entry {entry}!")
            await tg(app, f"{sig_e} *Pattern B \u2014 \u0e15\u0e33\u0e2b\u0e19\u0e34 (\u0e27\u0e34\u0e18\u0e35 2)*\n\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\n\U0001f4ca [{tf}] \u0e23\u0e32\u0e04\u0e32\u0e41\u0e15\u0e30 50% Body[1] \u0e02\u0e13\u0e30\u0e41\u0e17\u0e48\u0e07[0] \u0e27\u0e34\u0e48\u0e07!\n\U0001f4cc \u0e15\u0e31\u0e49\u0e07 Limit \u0e17\u0e35\u0e48: `{entry}`\n\U0001f6d1 SL: `{p['sl']}` | \U0001f3af TP: `{p['tp']}`\n\n\u23f3 \u0e01\u0e33\u0e25\u0e31\u0e07\u0e15\u0e31\u0e49\u0e07 Limit Order...")
            # TP เดียวกับ Order แรก ถ้ามี
            pb_tp = get_existing_tp(signal, entry, tf) or p["tp"]
            order = open_order(signal, get_volume(), p["sl"], pb_tp, entry_price=entry, tf=tf, sid=1, pattern=p.get("pattern", f"Pattern B {signal} [{tf}]"))
            if order["success"]:
                last_traded_per_tf[tf] = candle_key
                if order.get("ticket"):
                    pending_order_tf[order["ticket"]] = {
                        "tf": tf,
                        "gap_bot": round(entry - abs(entry - p["sl"]), 2),
                        "gap_top": round(entry + abs(entry - p["sl"]), 2),
                        "detect_bar_time": candle_key,
                        "signal": signal,
                        "sid": 1,
                        "pattern": f"Pattern B {signal} [{tf}]",
                    }
                    position_tf[order["ticket"]] = tf
                    position_sid[order["ticket"]] = 1
                    from trailing import position_pattern as _pos_pat
                    _pos_pat[order["ticket"]] = f"Pattern B {signal} [{tf}]"
                ot_name = order.get("order_type", "LIMIT")
                log_event(
                    "ORDER_CREATED",
                    f"Pattern B {signal} [{tf}]",
                    tf=tf,
                    sid=1,
                    signal=signal,
                    entry=entry,
                    sl=p["sl"],
                    tp=pb_tp,
                    ticket=order.get("ticket"),
                    order_type=ot_name,
                )
                await tg(app, f"✅ *{ot_name} สำเร็จ! (วิธี 2)*\n{sig_e} {ot_name} {SYMBOL} [{tf}]\n📌 Entry: `{order['price']}`\n🔖 Ticket: `{order['ticket']}`")
            else:
                log_event(
                    "ORDER_SKIPPED" if order.get("skipped") else "ORDER_FAILED",
                    order.get("error", ""),
                    tf=tf,
                    sid=1,
                    signal=signal,
                    entry=entry,
                    sl=p["sl"],
                    tp=pb_tp,
                )
                await tg(app, f"❌ [{tf}] วิธี 2 ไม่สำเร็จ: `{order['error']}`")
            to_remove.append(key)

    for k in to_remove:
        pb_pending.pop(k, None)



# TF → นาที mapping สำหรับ log filter
TF_MINUTES = {
    "M1": 1, "M5": 5, "M15": 15, "M30": 30,
    "H1": 60, "H4": 240, "H12": 720, "D1": 1440,
}

def should_log_tf(tf_name: str, scan_interval: int) -> bool:
    """
    Log เฉพาะ TF ที่ครบรอบเวลา ณ ขณะนี้
    scan 1 นาที → log ทุก TF ที่ minute % tf_minutes == 0
    เช่น scan=1 → log M1 ทุกนาที
         scan=5 → log M1,M5 ทุก 5 นาที
         scan=15 → log M1,M5,M15 ทุก 15 นาที
    """
    tf_min = TF_MINUTES.get(tf_name, 1)
    now_min = now_bkk().minute
    now_hour = now_bkk().hour
    total_min = now_hour * 60 + now_min

    # TF ที่มีค่าน้อยกว่าหรือเท่ากับ scan_interval → log ทุก scan
    if tf_min <= scan_interval:
        return True
    # TF ที่ใหญ่กว่า → log เมื่อครบรอบ
    return total_min % tf_min == 0
