import re, os
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
                pairs.append(f"{k}={v}")
        results.append((time_s, event, sub, pairs))
    return results


def _format_ticket_logs(logs: list) -> str:
    """3 บรรทัดต่อ 1 log: timestamp+label / fields / blank"""
    lines = []
    for time_s, event, sub, pairs in logs:
        label = _WANT_EVENTS.get(event, event)
        sub_s = f" `{sub}`" if sub else ""
        lines.append(f"🕐 `{time_s}` {label}{sub_s}")
        lines.append(f"   {' | '.join(pairs)}" if pairs else "   —")
        lines.append("")
    return "\n".join(lines).rstrip()


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
        signal_msg   = _read_signal_tg(p.ticket, all_lines)
        signal_block = (signal_msg + "\n━━━━━━━━━━━━━━━━━\n") if signal_msg else ""

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
