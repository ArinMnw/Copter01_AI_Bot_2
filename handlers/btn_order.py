import re, os
from datetime import datetime, timedelta, timezone
from config import *
from mt5_utils import connect_mt5, open_order, get_existing_tp
from handlers.keyboard import (main_keyboard, build_strategy_keyboard,
    build_tf_keyboard, build_tf_keyboard_with_back,
    build_scan_keyboard, build_scan_keyboard_with_back)

BOT_LOG_FILE = os.path.join("logs", "bot.log")

# events ที่ต้องการดึงมาแสดง
_WANT_EVENTS = {
    "ORDER_CREATED":               "📝 สร้าง Order",
    "ENTRY_FILL":                  "✅ Fill",
    "PDFIBOPLUS":                  "🛡️ PD Fibo Plus",
    "PD_ZONE_CHECK":               "🛡️ PD Zone",
    "TREND_RECHECK":               "📈 Trend Recheck",
    "ENTRY_FILL_RSI_RECHECK_FAIL": "⚠️ RSI Fail",
    "ENTRY_CANDLE":                "🕯️ Entry Candle",
    "ENTRY_QUALITY":               "📊 Entry Quality",
    "TSO_REGISTERED":              "⚡ TSO",
    "POSITION_CLOSED":             "🛑 ปิด",
}

_SHOW_FIELDS = {
    "ORDER_CREATED":               ["sid", "signal", "tf", "entry", "sl", "tp"],
    "ENTRY_FILL":                  ["price", "sl", "tp", "trend", "rsi", "rsi2_state"],
    "PDFIBOPLUS":                  ["result", "price", "h", "l", "eq"],
    "PD_ZONE_CHECK":               ["result", "price", "h", "l", "eq"],
    "TREND_RECHECK":               ["allowed", "why", "close_price"],
    "ENTRY_FILL_RSI_RECHECK_FAIL": ["rsi", "side", "tf"],
    "ENTRY_CANDLE":                ["body_pct", "open", "high", "low", "close"],
    "ENTRY_QUALITY":               ["state", "close_price", "reason"],
    "TSO_REGISTERED":              ["base_volume", "scaled_volume", "n_steps"],
    "POSITION_CLOSED":             ["close_price", "profit", "reason"],
}


def _fld(line, key):
    m = re.search(rf'(?<![a-zA-Z_]){key}=([^|\s]+)', line)
    return m.group(1).strip() if m else None


def _load_log_lines() -> list[str]:
    """อ่าน bot.log ทั้งหมดเป็น list — cache ใน module level ต่อ request"""
    if not os.path.exists(BOT_LOG_FILE):
        return []
    try:
        with open(BOT_LOG_FILE, encoding='utf-8', errors='replace') as f:
            return f.readlines()
    except Exception:
        return []


def _read_order_meta(ticket: int, all_lines: list) -> tuple[str, str, str]:
    """ดึง (pattern, sid, tf) จาก ORDER_CREATED log สำหรับ ticket นี้
    ใช้เป็น fallback เมื่อ position_pattern/sid/tf dict ว่าง (เช่น หลัง bot restart)"""
    tk_str = str(ticket)
    tk_re = re.compile(rf'\b{tk_str}\b')
    for line in all_lines:
        if not tk_re.search(line):
            continue
        if '] ORDER_CREATED |' not in line:
            continue
        # pattern = field แรกหลัง ORDER_CREATED |
        m = re.match(r'^\[.+?\]\s+ORDER_CREATED \| ([^|]+)', line)
        pattern = m.group(1).strip() if m else ""
        sid = _fld(line, 'sid') or ""
        tf  = _fld(line, 'tf') or ""
        return pattern, sid, tf
    return "", "", ""


def _read_signal_tg(ticket: int, all_lines: list) -> str:
    """หา TG_SENT ที่เป็น signal notification สำหรับ ticket นี้

    Bug เดิม: signal TG_SENT ถูก log แค่ 300 chars และ ticket อยู่ท้ายข้อความ
    → ticket number ถูกตัดออก → หาไม่เจอ หรือเจอ PD Fibo Check แทน

    Strategy ใหม่:
    1. หา ORDER_CREATED line ของ ticket → ดึง pattern name
    2. หา TG_SENT ใน ±40 lines รอบ ORDER_CREATED ที่ match pattern name (30 chars แรก)
    3. fallback: หา TG_SENT แรกที่ ticket ปรากฏ (เผื่อ ticket อยู่ใน log ตรงๆ)
    """
    tk_str = str(ticket)
    tk_re = re.compile(rf'\b{tk_str}\b')

    # Step 1: หา ORDER_CREATED line และ pattern name
    oc_lineno = None
    pattern_name = None
    for i, line in enumerate(all_lines):
        if not tk_re.search(line):
            continue
        if '] ORDER_CREATED |' not in line:
            continue
        oc_lineno = i
        m = re.match(r'^\[.+?\]\s+ORDER_CREATED \| ([^|]+)', line)
        if m:
            pattern_name = m.group(1).strip()
        break

    if oc_lineno is None:
        return ""

    # Step 2: หา TG_SENT ใกล้ ORDER_CREATED ที่ match pattern name
    if pattern_name:
        key = pattern_name[:40]  # 40 chars แรกของ pattern name พอ unique
        search_start = max(0, oc_lineno - 5)
        search_end   = min(len(all_lines), oc_lineno + 40)
        for line in all_lines[search_start:search_end]:
            if '] TG_SENT |' not in line:
                continue
            if key not in line:
                continue
            m = re.match(r'^\[.+?\]\s+TG_SENT \| (.+)', line)
            if not m:
                continue
            return m.group(1).rstrip().replace(" | ", "\n")

    # Step 3: fallback — TG_SENT แรกที่ ticket ปรากฏ (ถ้า ticket อยู่ใน 300 chars)
    for line in all_lines:
        if not tk_re.search(line):
            continue
        if '] TG_SENT |' not in line:
            continue
        m = re.match(r'^\[.+?\]\s+TG_SENT \| (.+)', line)
        if not m:
            continue
        return m.group(1).rstrip().replace(" | ", "\n")

    return ""


def _read_ticket_logs(ticket: int, all_lines: list) -> list[tuple[str, str, str, list[str]]]:
    """อ่าน bot.log คืน [(time, event, sub, fields), ...] สำหรับ ticket นี้"""
    tk_str = str(ticket)
    tk_re = re.compile(rf'\b{tk_str}\b')
    results = []
    for line in all_lines:
        if not tk_re.search(line):
            continue
        m = re.match(r'^\[(\d{4}-\d{2}-\d{2} (\d{2}:\d{2}:\d{2}))\]\s+(\S+)', line)
        if not m:
            continue
        event = m.group(3)
        if event not in _WANT_EVENTS:
            continue
        time_s = m.group(2)
        parts = line.split("|")
        sub = parts[1].strip() if len(parts) > 1 else ""
        want = _SHOW_FIELDS.get(event, [])
        pairs = []
        for k in want:
            v = _fld(line, k)
            if v and v not in ("-", "None", "none"):
                pairs.append(f"{k}=`{v}`")
        results.append((time_s, event, sub, pairs))
    return results


_SEP = "━━━━━━━━━━━━━━━━━\n━━━━━━━━━━━━━━━━━"


def _format_ticket_logs(logs: list) -> str:
    """log events คั่นด้วย ━━━ เพื่อให้อ่านง่าย"""
    blocks = []
    for time_s, event, sub, pairs in logs:
        label = _WANT_EVENTS.get(event, event)
        # emoji > U+FFFF ใน code span ทำ Telegram Markdown offset ผิด → plain text
        if sub and any(ord(c) > 0xFFFF for c in sub):
            sub_s = f" {sub}"
        else:
            sub_s = f" `{sub}`" if sub else ""
        entry_lines = [f"🕐 `{time_s}` {label}{sub_s}"]
        if pairs:
            entry_lines.append(f"   {' | '.join(pairs)}")
        blocks.append("\n".join(entry_lines))
    return f"\n{_SEP}\n".join(blocks)


_TF_MT5 = {
    "M1": 1, "M5": 5, "M15": 15, "M30": 30,
    "H1": 16385, "H4": 16388, "H12": 16396, "D1": 16408,
}
_BKK = timezone(timedelta(hours=7))


def _fetch_candle_block(ticket: int, all_lines: list) -> str:
    """ดึง candle OHLC จาก MT5 history เพื่อ reconstruct signal block
    ใช้เมื่อ TG_SENT ถูกตัดกลางคำ (order เก่าที่ log แค่ 300 chars)"""
    oc_time_str = tf_name = entry = sl = tp = sid = signal = trend = hhll_log = None
    tk_str = str(ticket)
    for line in all_lines:
        if tk_str not in line or '] ORDER_CREATED |' not in line:
            continue
        m = re.match(r'^\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\]', line)
        if m:
            oc_time_str = m.group(1)
        tf_name  = _fld(line, 'tf') or ""
        entry    = _fld(line, 'entry')
        sl       = _fld(line, 'sl')
        tp       = _fld(line, 'tp')
        sid      = _fld(line, 'sid')
        signal   = _fld(line, 'signal')
        trend    = _fld(line, 'trend_filter')
        hhll_log = _fld(line, 'hhll_last_label')  # บันทึก ณ ตอนสร้าง order
        break

    if not oc_time_str or not tf_name:
        return ""

    # parse composite TF เช่น [M5_H1] → ใช้ TF แรก
    raw_tf = re.sub(r'[\[\]]', '', tf_name).split('_')[0].split('-')[0]
    mt5_tf_id = _TF_MT5.get(raw_tf)
    if not mt5_tf_id or not connect_mt5():
        return ""

    try:
        oc_dt = datetime.strptime(oc_time_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=_BKK)
        tf_mins = {"M1":1,"M5":5,"M15":15,"M30":30,"H1":60,"H4":240,"H12":720,"D1":1440}
        step = tf_mins.get(raw_tf, 1)
        # ดึงแท่งที่ปิดก่อน oc_time
        # ลบ 60 วินาที เพื่อกัน bar ที่กำลัง form (open_time ≤ oc_time) ถูกรวมเข้ามา
        start = oc_dt - timedelta(minutes=step * 6)
        end   = oc_dt - timedelta(seconds=60)
        rates = mt5.copy_rates_range(SYMBOL, mt5_tf_id, start, end)
        if rates is None or len(rates) < 2:
            return ""

        def _fmt_bar(r, idx):
            bar_dt = datetime.fromtimestamp(r['time'], tz=_BKK)
            bar_str = bar_dt.strftime("%H:%M %d-%b-%Y")
            color = "🟢" if r['close'] >= r['open'] else "🔴"
            return (f"{color} แท่ง[{idx}]: "
                    f"O:{r['open']:.2f} H:{r['high']:.2f} "
                    f"L:{r['low']:.2f} C:{r['close']:.2f} {bar_str}")

        bar0 = rates[-1]
        bar1 = rates[-2]

        # trend label — ใช้ log ที่บันทึกตอนสร้าง order เป็นหลัก (ประวัติที่แม่นยำ)
        # ถ้าไม่มีใน log (order เก่า) → fall back ไปดึง live
        trend_base = (trend or "").upper() or "?"
        if trend_base == "SIDEWAY" and hhll_log:
            # ใช้ hhll_last_label ที่บันทึกตอนสร้าง order → ถูกต้อง 100%
            trend_lbl = f"SIDEWAY/{hhll_log}"
        else:
            # order เก่า (ไม่มี hhll_last_label ในLog) → ดึง live จาก scanner
            try:
                from scanner import get_trend_label as _gtl
                trend_lbl = _gtl(raw_tf) or "?"
            except Exception:
                trend_lbl = "?"
            if not trend_lbl or trend_lbl == "?":
                trend_lbl = trend_base
            # ถ้า live คืน "SIDEWAY" ธรรมดา (ไม่มี /HHLL) → ลอง fetch ตรงจาก hhll_swing
            if trend_lbl == "SIDEWAY":
                try:
                    import hhll_swing as _hs_mod
                    _hs_mod.fetch_hhll(raw_tf)          # force-fetch ถ้าข้อมูลยังไม่พร้อม
                    _hhll_live = _hs_mod.get_hhll_data(raw_tf) or {}
                    _lbl_live  = _hhll_live.get("last_label", "")
                    if _lbl_live:
                        trend_lbl = f"SIDEWAY/{_lbl_live} ⚠️"  # ⚠️ = live ไม่ใช่ตอน order
                except Exception:
                    pass

        lines = [
            f"🕐 {oc_time_str[:10]} {oc_time_str[11:16]}",
            f"📊 Timeframe: {raw_tf}" + (f" | S{sid}" if sid else ""),
            "",
            _fmt_bar(bar1, 1),
            _fmt_bar(bar0, 0),
        ]
        if entry:
            rr_parts = []
            try:
                e, s, t = float(entry), float(sl or 0), float(tp or 0)
                risk = abs(e - s)
                reward = abs(t - e)
                if risk > 0:
                    rr_parts.append(f"R:R 1:{reward/risk:.2f}")
            except Exception:
                pass
            lines += [
                "",
                f"📌 Entry: {entry}"
                + (f" | SL: {sl}" if sl else "")
                + (f" | TP: {tp}" if tp else ""),
                " | ".join(rr_parts) if rr_parts else "",
            ]
        lines.append(f"🧭 Trend: {trend_lbl}")
        return "\n".join(l for l in lines if l is not None)
    except Exception:
        return ""


async def _safe_reply(update, text):
    """ส่ง reply โดยลอง Markdown ก่อน — ถ้า parse error (เช่น signal block ที่
    ถูกตัด 300 char จาก TG_SENT ทำให้ markdown ไม่ balanced) → fallback เป็น plain text
    กัน message ทั้งก้อนส่งไม่ออก"""
    try:
        await update.message.reply_text(
            text, parse_mode='Markdown', reply_markup=main_keyboard()
        )
    except Exception:
        # ลบ markdown markers ออกแล้วส่ง plain
        plain = text.replace('`', '').replace('*', '').replace('_', '')
        await update.message.reply_text(plain, reply_markup=main_keyboard())


async def handle_btn_order(update, context):
    if not auth(update): return
    if not connect_mt5():
        await update.message.reply_text("❌ MT5 ไม่ได้เชื่อมต่อ")
        return
    positions = mt5.positions_get(symbol=SYMBOL)
    if not positions:
        await update.message.reply_text("📭 ไม่มี Order", reply_markup=main_keyboard())
        return

    # อ่าน log ครั้งเดียวแล้วแชร์ทุก position (ไม่ต้องเปิดไฟล์ซ้ำ)
    all_lines = _load_log_lines()

    total = sum(p.profit for p in positions)
    te = "🟢" if total >= 0 else "🔴"

    for p in positions:
        t  = "BUY" if p.type == mt5.ORDER_TYPE_BUY else "SELL"
        e  = "🟢" if t == "BUY" else "🔴"
        pe = "🟢" if p.profit >= 0 else "🔴"

        # ดึงจาก runtime dict ก่อน — ถ้าว่าง (เช่น หลัง bot restart) ดึงจาก log
        sid     = position_sid.get(p.ticket, "")
        pattern = position_pattern.get(p.ticket, "")
        tf      = position_tf.get(p.ticket, "")

        if not pattern or not sid or not tf:
            _pat, _sid, _tf = _read_order_meta(p.ticket, all_lines)
            if not pattern: pattern = _pat
            if not sid:     sid     = _sid
            if not tf:      tf      = _tf

        header = (
            f"{e} *{t}* {p.volume}lot @ `{p.price_open}`\n"
            f"🛑`{p.sl}` 🎯`{p.tp}` | {pe}`{p.profit:.2f}` USD\n"
            f"🔖 `#{p.ticket}`"
            + (f" | S{sid}" if sid else "")
            + (f" | {tf}" if tf else "")
            + "\n"
            + (f"📝 {pattern}\n" if pattern else "")
            + "━━━━━━━━━━━━━━━━━\n"
        )

        # Signal TG message (ตอนสร้าง order) — ใช้ all_lines แทนอ่านไฟล์ใหม่
        signal_msg = _read_signal_tg(p.ticket, all_lines)
        if signal_msg:
            # strip markdown markers ออกก่อน — TG_SENT ถูก truncate 300 chars
            # → backtick/asterisk อาจไม่ balanced → ทำให้ Markdown ทั้งก้อน fail
            sig_clean = re.sub(r'`([^`\n]*)`?', r'\1', signal_msg)   # ลบ code span
            sig_clean = sig_clean.replace('`', '').replace('*', '')
            # แสดงหัวใจความว่าตัดมาจาก signal (300 char limit)
            suffix = "\n…(ข้อความบางส่วนถูกตัดออกเนื่องจากจำกัดที่ 1200 ตัวอักษร)" \
                     if len(signal_msg.replace('\n', ' | ')) >= 1195 else ""
            signal_block = sig_clean + suffix + "\n━━━━━━━━━━━━━━━━━\n"
        else:
            signal_block = ""

        # Log events หลัง signal
        logs      = _read_ticket_logs(p.ticket, all_lines)
        log_block = _format_ticket_logs(logs) if logs else "_ไม่พบ log_"

        msg = header + signal_block + log_block

        if len(msg) > 4000:
            msg = msg[:4000] + "\n…(ตัดออก)"

        await _safe_reply(update, msg)

    await _safe_reply(
        update,
        f"━━━━━━━━━━━━━━━━━\n{te} *รวม {len(positions)} positions: {total:.2f} USD*"
    )
