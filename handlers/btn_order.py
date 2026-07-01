import re, os
from datetime import datetime, timedelta, timezone
from config import *
from mt5_utils import connect_mt5, open_order, get_existing_tp
from handlers.keyboard import (main_keyboard, build_strategy_keyboard,
    build_tf_keyboard, build_tf_keyboard_with_back,
    build_scan_keyboard, build_scan_keyboard_with_back)

try:
    from bot_log import BOT_LOG_FILE, OLD_LOG_DIR as BOT_LOG_DIR
except Exception:
    BOT_LOG_FILE  = os.path.join("logs", "bot.log")
    BOT_LOG_DIR   = os.path.join("logs", "old_logs")   # archived bot-YYYY-MM.log

def _all_bot_log_files() -> list[str]:
    """คืน list ของ log files ทั้งหมด (เก่า→ใหม่ = chronological)

    ใช้ helper กลาง `log_sources.bot_log_files()` ซึ่งครอบไฟล์ทุกแบบ:
    - logs/bot.log
    - logs/old_logs/bot-YYYY-MM.log         (monthly)
    - logs/old_logs/bot-YYYY-MM-DD-NN.log   (size-split >100MB)
    - logs/old_logs/bot-*.log.bak-*         (re-archive backup)

    เดิมใช้ glob `bot-YYYY-MM.log` อย่างเดียว → พลาด size-split/.bak
    ทำให้ ticket ที่ log ตกไปอยู่ไฟล์เหล่านั้นขึ้น "ไม่พบ log"
    """
    try:
        from log_sources import bot_log_files
        files = bot_log_files()
        if files:
            return files
    except Exception:
        pass
    # fallback: logic เดิม (เผื่อ import ไม่ได้)
    import glob
    files = []
    if os.path.isdir(BOT_LOG_DIR):
        files += sorted(glob.glob(os.path.join(BOT_LOG_DIR, "bot-2[0-9][0-9][0-9]-[0-9][0-9]*.log")))
        files += sorted(glob.glob(os.path.join(BOT_LOG_DIR, "bot-2[0-9][0-9][0-9]-[0-9][0-9]*.log.bak-*")))
    if os.path.exists(BOT_LOG_FILE):
        files.append(BOT_LOG_FILE)
    return files

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
    "TSO_PARTIAL_CLOSE_TP1":       "💰 TSO TP1",
    "TSO_PARTIAL_CLOSE_TP2":       "💰💰 TSO TP2",
    "TSO_PARTIAL_CLOSE_TP3":       "💰💰💰 TSO TP3",
    "TSO_PARTIAL_CLOSE_TP4":       "💰💰💰💰 TSO TP4",
    "POSITION_CLOSED":             "🛑 ปิด",
    "ORDER_CANCELED":              "❌ Cancel",
    "POSITION_CLOSE_REQUEST":      "🔔 Close Req",
    "SL_GUARD_CLOSE":              "🛡️ SL Guard",
}

_SHOW_FIELDS = {
    "ORDER_CREATED":               ["sid", "signal", "tf", "entry", "sl", "tp"],
    "ENTRY_FILL":                  ["price", "sl", "tp", "trend", "rsi", "rsi2_state"],
    "PDFIBOPLUS":                  ["result", "price", "h", "l", "eq"],
    "PD_ZONE_CHECK":               ["result", "price", "h", "l", "eq"],
    "TREND_RECHECK":               ["allowed", "why", "close_price", "sh", "sl", "sh_t", "sl_t"],
    "ENTRY_FILL_RSI_RECHECK_FAIL": ["rsi", "side", "tf"],
    "ENTRY_CANDLE":                ["body_pct", "open", "high", "low", "close"],
    "ENTRY_QUALITY":               ["state", "close_price", "reason"],
    "TSO_REGISTERED":              ["base_volume", "scaled_volume", "n_steps"],
    "TSO_PARTIAL_CLOSE_TP1":       ["close_price", "entry", "close_volume", "target_dist", "passed_dist", "remaining_steps"],
    "TSO_PARTIAL_CLOSE_TP2":       ["close_price", "entry", "close_volume", "target_dist", "passed_dist", "remaining_steps"],
    "TSO_PARTIAL_CLOSE_TP3":       ["close_price", "entry", "close_volume", "target_dist", "passed_dist", "remaining_steps"],
    "TSO_PARTIAL_CLOSE_TP4":       ["close_price", "entry", "close_volume", "target_dist", "passed_dist", "remaining_steps"],
    "POSITION_CLOSED":             ["close_price", "profit", "reason"],
    "ORDER_CANCELED":              ["entry", "sl", "tp"],
    "POSITION_CLOSE_REQUEST":      ["close_price", "entry"],
    "SL_GUARD_CLOSE":              [],
}

# คำอธิบาย sub-event ของ TREND_RECHECK เพื่อแสดงใน ticket lookup
_TREND_RECHECK_LABEL = {
    "fill_round1_skip_approach_passed": "⏭️ R1 ข้าม — approach ผ่านก่อน fill แล้ว (ใช้ swing ตอน approach เป็น baseline R2)",
    "fill_round1":                      "🔍 R1 เช็ค trend",
    "fill_round1_pass_wait_pivot":      "⏳ R1 ผ่าน — รอ pivot ยืนยัน (sh/sl baseline R2)",
    "fill_round2":                      "🔍 R2 เช็ค trend",
    "fill_all_rounds_pass":             "✅ ทุก round ผ่าน — ถือ position ต่อ",
    "fill_close_round1":                "❌ R1 trend สวนทาง → ปิด",
    "fill_close_round1_failed":         "⚠️ R1 สั่งปิดแต่ล้มเหลว",
    "fill_close_round2":                "❌ R2 trend สวนทาง → ปิด",
    "fill_close_round2_failed":         "⚠️ R2 สั่งปิดแต่ล้มเหลว",
}


def _fld(line, key):
    m = re.search(rf'(?<![a-zA-Z_]){key}=([^|\s]+)', line)
    return m.group(1).strip() if m else None


def _load_log_lines(max_lines: int = 800_000) -> list[str]:
    """[Legacy] อ่านทุก log files — ใช้สำหรับ caller ที่ไม่รู้ ticket ล่วงหน้า
    ถ้ารู้ ticket ให้ใช้ _grep_ticket_lines(ticket) แทน (เร็วกว่ามาก)
    """
    files = _all_bot_log_files()
    if not files:
        return []
    lines: list[str] = []
    for path in files:
        if len(lines) >= max_lines:
            break
        try:
            with open(path, encoding='utf-8', errors='replace') as f:
                chunk = f.readlines()
            remaining = max_lines - len(lines)
            if len(chunk) > remaining:
                chunk = chunk[-remaining:]
            lines.extend(chunk)
        except Exception:
            pass
    return lines


def _grep_ticket_lines(ticket: int) -> list[str]:
    """เร็วกว่า _load_log_lines มาก — scan ทุก log files
    คืนเฉพาะบรรทัดที่มี ticket number (plain string match, ไม่ใช้ regex)
    เรียงตาม file order: bot.log → bot-2026-06.log → bot-2026-05.log → ...
    """
    tk_str = str(ticket)
    matched: list[str] = []
    seen: set = set()   # dedup บรรทัดซ้ำเป๊ะ — ไฟล์ .bak มัก overlap กับ archive ปัจจุบัน
    for path in _all_bot_log_files():
        try:
            with open(path, encoding='utf-8', errors='replace') as f:
                for line in f:
                    if tk_str in line and line not in seen:
                        seen.add(line)
                        matched.append(line)
        except Exception:
            pass
    return matched


def _grep_tg_sent_near_ts(
    ts_unix: int,
    pattern_key: str,
    window_sec: int = 90,
    ticket: int | None = None,
    expected_tf: str = "",
) -> str:
    """หา TG_SENT ที่ match pattern_key ภายใน ±window_sec วินาทีของ ts_unix
    ใช้แทน line-proximity search ของ _read_signal_tg (ทำงานถูกต้องทุก file)
    """
    _TS_RE_LOG = re.compile(r'^\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\]')
    key = pattern_key[:40]

    def _parse_ts(line: str) -> int:
        m = _TS_RE_LOG.match(line)
        if not m:
            return 0
        try:
            from datetime import timezone as _tz
            dt = datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S")
            # log timestamps ใช้ UTC+6 (user's BKK)
            import config as _cfg
            offset = getattr(_cfg, "TZ_OFFSET", 7) - 1  # UTC+6
            from datetime import timedelta as _td
            return int(dt.replace(tzinfo=timezone(timedelta(hours=offset))).timestamp())
        except Exception:
            return 0

    lo, hi = ts_unix - window_sec, ts_unix + window_sec
    tk_str = str(ticket or "")
    best_score = -1
    best_msg = ""

    def _context_score(line: str) -> int:
        clean = line.replace("\\", "")
        score = 0
        if tk_str and tk_str in clean:
            score += 100
        if expected_tf:
            tf_markers = (
                f"Timeframe: {expected_tf}",
                f"Timeframe: `{expected_tf}`",
                f"Flow: `{expected_tf}-",
                f"TF: {expected_tf}",
                f"[{expected_tf}]",
            )
            if any(marker in clean for marker in tf_markers):
                score += 10
        return score

    for path in _all_bot_log_files():
        try:
            with open(path, encoding='utf-8', errors='replace') as f:
                for line in f:
                    if '] TG_SENT |' not in line:
                        continue
                    # Remove backslashes to handle escaped brackets in logs (e.g. \[H4→M5])
                    clean_line = line.replace("\\", "")
                    clean_key = key.replace("\\", "")
                    if clean_key not in clean_line:
                        continue
                    t = _parse_ts(line)
                    if t == 0 or lo <= t <= hi:
                        m2 = re.match(r'^\[.+?\]\s+TG_SENT \| (.+)', line)
                        if m2:
                            msg = m2.group(1).rstrip().replace(" | ", "\n")
                            score = _context_score(line)
                            if score > best_score:
                                best_score = score
                                best_msg = msg
                            if score >= 100:
                                return msg
        except Exception:
            pass
    return best_msg


def _read_order_meta(ticket: int, all_lines: list) -> tuple[str, str, str]:
    """ดึง (pattern, sid, tf) จาก ORDER_CREATED log สำหรับ ticket นี้
    ถ้า all_lines ว่าง → ใช้ _grep_ticket_lines (fast path)
    """
    lines = all_lines if all_lines else _grep_ticket_lines(ticket)
    tk_str = str(ticket)
    for line in lines:
        if tk_str not in line:
            continue
        if '] ORDER_CREATED |' not in line:
            continue
        m = re.match(r'^\[.+?\]\s+ORDER_CREATED \| ([^|]+)', line)
        pattern = m.group(1).strip() if m else ""
        sid = _fld(line, 'sid') or ""
        tf  = _fld(line, 'tf') or ""
        return pattern, sid, tf
    return "", "", ""


def _read_signal_tg(ticket: int, all_lines: list) -> str:
    """หา TG_SENT ที่เป็น signal notification สำหรับ ticket นี้

    Strategy:
    1. หา ORDER_CREATED line ของ ticket → pattern name + timestamp
    2. ค้น TG_SENT ด้วย timestamp window ±90s (ทำงานถูกต้องข้าม file)
    3. fallback: หา TG_SENT แรกที่ ticket ปรากฏตรงๆ
    """
    _TS_RE_LOG = re.compile(r'^\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\]')

    # ใช้ grep lines ถ้า all_lines ว่าง
    tk_lines = all_lines if all_lines else _grep_ticket_lines(ticket)
    tk_str = str(ticket)

    # Step 1: หา ORDER_CREATED line → pattern name + timestamp
    oc_ts_str    = None
    pattern_name = None
    tf_name      = ""
    for line in tk_lines:
        if tk_str not in line:
            continue
        if '] ORDER_CREATED |' not in line:
            continue
        tm = _TS_RE_LOG.match(line)
        if tm:
            oc_ts_str = tm.group(1)
        m = re.match(r'^\[.+?\]\s+ORDER_CREATED \| ([^|]+)', line)
        if m:
            pattern_name = m.group(1).strip()
        tf_name = _fld(line, 'tf') or ""
        break

    if oc_ts_str is None:
        return ""

    # แปลง timestamp → unix
    oc_unix = 0
    try:
        import config as _cfg
        offset = getattr(_cfg, "TZ_OFFSET", 7) - 1  # log = UTC+6
        dt = datetime.strptime(oc_ts_str, "%Y-%m-%d %H:%M:%S")
        oc_unix = int(dt.replace(tzinfo=timezone(timedelta(hours=offset))).timestamp())
    except Exception:
        pass

    # Step 2: timestamp window search (ไม่ขึ้นกับ line number)
    if pattern_name and oc_unix > 0:
        result = _grep_tg_sent_near_ts(
            oc_unix,
            pattern_name,
            window_sec=90,
            ticket=ticket,
            expected_tf=tf_name,
        )
        if result:
            return result

    # Step 3: fallback — TG_SENT ที่มี ticket ตรงๆ (ข้ามพวกข้อความแจ้งเตือนสถานะเพื่อให้ได้ข้อความ signal Setup แท้)
    for line in tk_lines:
        if tk_str not in line:
            continue
        if '] TG_SENT |' not in line:
            continue
        # ข้าม status notifications เพื่อไม่ดึงข้อความแจ้งเตือนสถานะมาแทน signal Setup
        if any(k in line for k in ["Limit Fill", "SL Hit", "TP Hit", "Position Closed", "PD Fibo Plus Check", "PD Zone Check", "ยกเลิก", "Trailing SL", "Limit Guard"]):
            continue
        m = re.match(r'^\[.+?\]\s+TG_SENT \| (.+)', line)
        if m:
            return m.group(1).rstrip().replace(" | ", "\n")

    return ""


def _read_ticket_logs(ticket: int, all_lines: list) -> list[tuple[str, str, str, list[str]]]:
    """อ่าน log events สำหรับ ticket นี้
    ถ้า all_lines ว่าง → ใช้ _grep_ticket_lines (fast path)
    """
    lines = all_lines if all_lines else _grep_ticket_lines(ticket)
    tk_str = str(ticket)
    results = []
    for line in lines:
        if tk_str not in line:
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
        # TREND_RECHECK: merge sh_t/sl_t timestamp เข้ากับ sh/sl → "4485.12 @HH:MM DD-Mon"
        if event == "TREND_RECHECK":
            for price_key, time_key in (("sh", "sh_t"), ("sl", "sl_t")):
                t_raw = _fld(line, time_key)
                if not t_raw or t_raw in ("0", "None", "-"):
                    continue
                try:
                    dt_bkk = mt5_ts_to_bkk(int(t_raw))
                    time_str = dt_bkk.strftime("%H:%M %d-%b")
                    # หา index ของ pair ที่เป็น price_key แล้วต่อท้าย @time
                    pairs = [
                        p[:-1] + f" @{time_str}`"   # ตัด ` ท้าย ต่อด้วย @time แล้วปิด `
                        if p.startswith(f"{price_key}=`") and p.endswith("`")
                        else p
                        for p in pairs
                    ]
                except Exception:
                    pass
            # ลบ sh_t/sl_t ออกจาก pairs (ไม่ต้องแสดง raw timestamp)
            pairs = [p for p in pairs if not p.startswith("sh_t=") and not p.startswith("sl_t=")]

        # คำนวณ PD Fibo % สำหรับ PDFIBOPLUS และ PD_ZONE_CHECK
        if event in ("PDFIBOPLUS", "PD_ZONE_CHECK"):
            try:
                price = float(_fld(line, "price") or 0)
                h_val = float(_fld(line, "h") or 0)
                l_val = float(_fld(line, "l") or 0)
                if h_val > l_val and price > 0:
                    pct = (price - l_val) / (h_val - l_val) * 100
                    sig = _fld(line, "signal") or ""
                    # BUY: ต้องการ < 50% (discount), SELL: ต้องการ > 50% (premium)
                    # label ตาม signal: BUY ต้องการ discount (<50%), SELL ต้องการ premium (>50%)
                    if sig == "BUY":
                        ok = pct <= 50
                        label = f"{'✅' if ok else '⚠️'} {pct:.1f}% (discount)" if pct < 50 else f"{'⚠️'} {pct:.1f}% (premium)"
                    elif sig == "SELL":
                        ok = pct >= 50
                        label = f"{'✅' if ok else '⚠️'} {pct:.1f}% (premium)" if pct >= 50 else f"{'⚠️'} {pct:.1f}% (discount)"
                    else:
                        label = f"{pct:.1f}%"
                    pairs.append(f"pd%=`{label}`")
            except Exception:
                pass
        results.append((time_s, event, sub, pairs))
    return results


_SEP = "━━━━━━━━━━━━━━━━━\n━━━━━━━━━━━━━━━━━"


def _format_ticket_logs(logs: list) -> str:
    """log events คั่นด้วย ━━━ เพื่อให้อ่านง่าย"""
    blocks = []
    for time_s, event, sub, pairs in logs:
        label = _WANT_EVENTS.get(event, event)
        # TREND_RECHECK: แปลง sub-event code → คำอธิบายภาษาไทย
        if event == "TREND_RECHECK" and sub in _TREND_RECHECK_LABEL:
            sub_s = f"\n   📌 {_TREND_RECHECK_LABEL[sub]}"
        elif sub and any(ord(c) > 0xFFFF for c in sub):
            # emoji > U+FFFF ใน code span ทำ Telegram Markdown offset ผิด → plain text
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
_UTC6 = timezone(timedelta(hours=6))
_UTC7 = timezone(timedelta(hours=7))  # BKK จริง — log timestamp (_now_bkk()) ใช้ UTC+7 ไม่ใช่ chart time UTC+6


def _fetch_ticket_metadata_from_mt5(ticket: int) -> dict | None:
    """ดึงข้อมูลของ ticket โดยตรงจาก MT5 เมื่อไม่มีข้อมูลใน log"""
    import mt5_worker as mt5
    # 1. ลองดึงจาก active position
    pos = mt5.positions_get(ticket=ticket)
    if pos:
        p = pos[0]
        return {
            "symbol": p.symbol,
            "comment": p.comment,
            "type": "BUY" if p.type == mt5.ORDER_TYPE_BUY else "SELL",
            "time_setup": p.time,  # ใช้เวลาเปิดเป็นเวลาตั้งต้น
            "price_open": p.price_open,
            "sl": p.sl,
            "tp": p.tp,
            "volume": p.volume,
        }
    
    # 2. ลองดึงจาก active pending order
    orders = mt5.orders_get(ticket=ticket)
    if orders:
        o = orders[0]
        direction = "BUY"
        if o.type in (mt5.ORDER_TYPE_SELL, mt5.ORDER_TYPE_SELL_LIMIT, mt5.ORDER_TYPE_SELL_STOP, mt5.ORDER_TYPE_SELL_STOP_LIMIT):
            direction = "SELL"
        return {
            "symbol": o.symbol,
            "comment": o.comment,
            "type": direction,
            "time_setup": o.time_setup,
            "price_open": o.price_open,
            "sl": o.sl,
            "tp": o.tp,
            "volume": getattr(o, "volume_current", o.volume_initial),
        }
        
    # 3. ลองดึงจาก history orders
    hist_orders = mt5.history_orders_get(ticket=ticket)
    if hist_orders:
        ho = hist_orders[0]
        direction = "BUY"
        if ho.type in (mt5.ORDER_TYPE_SELL, mt5.ORDER_TYPE_SELL_LIMIT, mt5.ORDER_TYPE_SELL_STOP, mt5.ORDER_TYPE_SELL_STOP_LIMIT):
            direction = "SELL"
        return {
            "symbol": ho.symbol,
            "comment": ho.comment,
            "type": direction,
            "time_setup": ho.time_setup,
            "price_open": ho.price_open,
            "sl": ho.sl,
            "tp": ho.tp,
            "volume": ho.volume_initial,
        }
        
    # 4. ลองดึงจาก history deals
    now = datetime.now()
    from_date = now - timedelta(days=90)
    to_date = now + timedelta(days=1)
    deals = mt5.history_deals_get(from_date, to_date) or []
    pos_deals = [d for d in deals if d.position_id == ticket or d.order == ticket]
    if pos_deals:
        pos_deals = sorted(pos_deals, key=lambda x: x.time)
        in_deal = None
        for d in pos_deals:
            if d.entry == mt5.DEAL_ENTRY_IN:
                in_deal = d
                break
        if not in_deal:
            in_deal = pos_deals[0]
            
        hist_orders = mt5.history_orders_get(ticket=ticket)
        comment = hist_orders[0].comment if hist_orders else in_deal.comment
        
        direction = "BUY"
        if in_deal.type in (mt5.DEAL_TYPE_SELL, mt5.DEAL_TYPE_SELL_CANCELED):
            direction = "SELL"
            
        sl = hist_orders[0].sl if hist_orders else 0
        tp = hist_orders[0].tp if hist_orders else 0
        
        return {
            "symbol": in_deal.symbol,
            "comment": comment,
            "type": direction,
            "time_setup": in_deal.time,
            "price_open": in_deal.price,
            "sl": sl,
            "tp": tp,
            "volume": in_deal.volume,
        }
        
    return None


def _parse_comment(comment: str) -> tuple[str, str, str]:
    """แยก tf_name, sid, pattern จาก comment ของ order/position"""
    if not comment:
        return "", "", ""
    m_sid = re.search(r'_?S(\d+)', comment)
    if m_sid:
        sid = m_sid.group(1)
        tf_name = comment[:m_sid.start()].strip()
        pattern_code = comment[m_sid.end():].strip("_ ")
    else:
        parts = comment.split("_")
        if len(parts) >= 2:
            tf_name = parts[0]
            if parts[1].startswith("S") and parts[1][1:].isdigit():
                sid = parts[1][1:]
                pattern_code = "_".join(parts[2:])
            else:
                sid = ""
                pattern_code = "_".join(parts[1:])
        else:
            tf_name = comment
            sid = ""
            pattern_code = ""
    return tf_name, sid, pattern_code


def _fetch_candle_block(ticket: int, all_lines: list) -> str:
    """ดึง candle OHLC จาก MT5 history เพื่อ reconstruct signal block
    ใช้เมื่อ TG_SENT ถูกตัดกลางคำ (order เก่าที่ log แค่ 300 chars)"""
    oc_time_str = tf_name = entry = sl = tp = sid = signal = trend = hhll_log = None
    htf_ltf = sub_pattern_log = None
    setup_bar_time = 0
    s14_ref_bar_time = s14_signal_bar_time = 0
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
        m_flow_t = re.search(r'flow_id=.*?\|T(\d+)(?:\||\s|$)', line)
        if m_flow_t:
            try:
                setup_bar_time = int(m_flow_t.group(1))
            except (TypeError, ValueError):
                setup_bar_time = 0
        htf_ltf         = _fld(line, 'htf_ltf')
        sub_pattern_log = _fld(line, 'sub_pattern') or ""
        try:
            s14_ref_bar_time    = int(_fld(line, 's14_ref_bar_time') or 0)
            s14_signal_bar_time = int(_fld(line, 's14_signal_bar_time') or 0)
        except (ValueError, TypeError):
            pass
        break

    symbol = SYMBOL
    if not oc_time_str or not tf_name:
        if not connect_mt5():
            return ""
        meta = _fetch_ticket_metadata_from_mt5(ticket)
        if meta:
            symbol = meta["symbol"]
            clean_tf, parsed_sid, pattern_code = _parse_comment(meta["comment"])
            clean_tf = re.sub(r'[\[\]]', '', clean_tf)
            tf_name = meta["comment"] if meta["comment"] else f"[{clean_tf}]"
            entry = str(meta["price_open"])
            sl = str(meta["sl"]) if meta["sl"] else ""
            tp = str(meta["tp"]) if meta["tp"] else ""
            sid = parsed_sid
            signal = meta["type"]
            
            # meta["time_setup"] = MT5 server timestamp → แปลงเป็น BKK จริง (UTC+7)
            # ด้วย MT5_SERVER_TZ ของ "วันนั้น" จาก history กัน server tz เปลี่ยนข้ามวัน
            # แล้วแสดงผลผิด (เคยใช้ _UTC6 ตรงๆ ทำให้ ticket เก่าที่ไม่มี ORDER_CREATED
            # ใน log ให้ grep เจอ แสดงเวลาช้าไป 1h จากความเป็นจริง)
            # re-tag เป็น _UTC7 (แบบเดียวกับ branch ล่างที่ใช้ oc_time_str จาก log)
            # เพื่อให้ .timestamp() ด้านล่างคืนค่า true UTC instant ถูกต้องเหมือนกัน
            _oc_dt_hist = mt5_ts_to_bkk_hist(int(meta["time_setup"]))
            oc_time_str = _oc_dt_hist.strftime("%Y-%m-%d %H:%M:%S")
            oc_dt = datetime.strptime(oc_time_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=_UTC7)
            
            if sid == '10' and ("_" in clean_tf or "-" in clean_tf):
                htf_ltf = clean_tf.replace("-", "_")
        else:
            return ""
    else:
        try:
            # oc_time_str มาจาก prefix log ([YYYY-MM-DD HH:MM:SS]) ซึ่งเขียนด้วย _now_bkk()
            # = เวลา BKK จริง (UTC+7) ไม่ใช่ chart time (UTC+6) — ห้ามใช้ _UTC6 ตรงนี้
            oc_dt = datetime.strptime(oc_time_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=_UTC7)
        except Exception:
            return ""

    # parse composite TF เช่น [M5_H1] → ใช้ TF แรก
    raw_tf = re.sub(r'[\[\]]', '', tf_name).split('_')[0].split('-')[0]
    if not connect_mt5():
        return ""

    try:
        tf_mins = {"M1":1,"M5":5,"M15":15,"M30":30,"H1":60,"H4":240,"H12":720,"D1":1440}
        
        # Parse composite or MTF mapping
        htf_tf = None
        ltf_tf = raw_tf
        if htf_ltf and "_" in htf_ltf:
            htf_tf, ltf_tf = htf_ltf.split("_")
        
        def _get_rates(tf_str, count, closed_only=False):
            tf_id = _TF_MT5.get(tf_str)
            if not tf_id:
                return None
            step = tf_mins.get(tf_str, 1)
            tf_secs = step * 60
            if setup_bar_time and (not htf_tf or tf_str == ltf_tf):
                raw = mt5.copy_rates_from(symbol, tf_id, int(setup_bar_time), count)
                if raw is not None and len(raw) >= count:
                    return raw[-count:]
            # ดึงแท่งที่ปิดก่อน oc_time
            start = oc_dt - timedelta(minutes=step * (count + 4))
            end   = oc_dt - timedelta(seconds=1)
            raw = mt5.copy_rates_range(symbol, tf_id, start, end)
            if raw is not None and len(raw) >= count:
                # r['time'] = server-local encoded (unix ของ server time) ของ "วันนั้น"
                # oc_dt.timestamp() = TRUE UTC → ต้องบวก MT5_SERVER_TZ ของวันนั้น (ไม่ใช่
                # ค่าปัจจุบัน) เพื่อให้เทียบกับ r['time'] ถูกต้อง แม้ broker เปลี่ยน
                # server tz ไปแล้วตั้งแต่วันที่ order นี้สร้าง
                _oc_true_ts = int(oc_dt.timestamp())
                oc_ts = _oc_true_ts + mt5_server_tz_for_ts(_oc_true_ts) * 3600
                if closed_only:
                    # เอาเฉพาะแท่งที่ปิดสมบูรณ์ก่อน order (กัน bar ที่เพิ่งเปิด เข้ามาแทน CRT bars)
                    filtered = [r for r in raw if int(r["time"]) + tf_secs <= oc_ts]
                else:
                    filtered = [r for r in raw if int(r["time"]) < oc_ts]
                return filtered[-count:] if len(filtered) >= count else (filtered or None)
            return raw

        def _fmt_bar(r, idx, tf_str):
            bar_dt = mt5_ts_to_bkk_hist(r['time'])  # BKK จริง ใช้ MT5_SERVER_TZ ของวันนั้น
            bar_str = bar_dt.strftime("%H:%M %d-%b-%Y")
            color = "🟢" if r['close'] >= r['open'] else "🔴"
            return (f"{color} แท่ง[{idx}]: "
                    f"O:`{r['open']:.2f}` H:`{r['high']:.2f}` "
                    f"L:`{r['low']:.2f}` C:`{r['close']:.2f}` {bar_str}")

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
            f"📊 Timeframe: {tf_name}" + (f" | S{sid}" if sid else ""),
            "",
        ]

        if sid == '10' and htf_tf:
            # Reconstruct S10 MTF candle block: parent + sweep + confirm
            htf_rates = _get_rates(htf_tf, 3, closed_only=True)
            ltf_rates = _get_rates(ltf_tf, 3, closed_only=True)

            if htf_rates is not None and len(htf_rates) >= 2:
                lines.append(f"📍 *HTF {htf_tf}* (เจอ CRT):")
                htf_secs = tf_mins.get(htf_tf, 60) * 60

                if len(htf_rates) >= 3:
                    lines.append(_fmt_bar(htf_rates[0], 2, htf_tf) + " ← parent")
                    lines.append(_fmt_bar(htf_rates[1], 1, htf_tf) + " ← sweep")
                    ts_0 = int(htf_rates[2]["time"])
                    in_progress = (ts_0 + htf_secs) > int(oc_dt.timestamp()) + MT5_SERVER_TZ * 3600
                    progress_tag = " ⏳(in-progress)" if in_progress else ""
                    lines.append(_fmt_bar(htf_rates[2], 0, htf_tf) + progress_tag)
                else:
                    lines.append(_fmt_bar(htf_rates[0], 1, htf_tf) + " ← sweep")
                    ts_0 = int(htf_rates[1]["time"])
                    in_progress = (ts_0 + htf_secs) > int(oc_dt.timestamp()) + MT5_SERVER_TZ * 3600
                    progress_tag = " ⏳(in-progress)" if in_progress else ""
                    lines.append(_fmt_bar(htf_rates[1], 0, htf_tf) + progress_tag)
                lines.append("")
                
            if ltf_rates is not None and len(ltf_rates) >= 3:
                lines.append(f"📍 *LTF {ltf_tf}* (trigger):")
                lines.append(_fmt_bar(ltf_rates[0], 2, ltf_tf))
                lines.append(_fmt_bar(ltf_rates[1], 1, ltf_tf))
                lines.append(_fmt_bar(ltf_rates[2], 0, ltf_tf))
                lines.append("")
        elif sid == '14' and (s14_ref_bar_time or s14_signal_bar_time):
            # S14: แสดง ref bar และ engulf/sweep bar โดยตรง
            tf_id_ltf = _TF_MT5.get(ltf_tf)
            step_ltf = tf_mins.get(ltf_tf, 5)
            tf_secs_ltf = step_ltf * 60
            if tf_id_ltf:
                def _fetch_bar_at(ts: int):
                    if not ts:
                        return None
                    raw = mt5.copy_rates_range(symbol, tf_id_ltf, ts, ts + tf_secs_ltf)
                    if raw is not None and len(raw) > 0:
                        return raw[0]
                    return None

                ref_bar = _fetch_bar_at(s14_ref_bar_time)
                sig_bar = _fetch_bar_at(s14_signal_bar_time)
                if ref_bar is not None:
                    lines.append("📍 Ref (LL/HL):")
                    lines.append(_fmt_bar(ref_bar, "ref", ltf_tf))
                if sig_bar is not None:
                    label = "engulf" if "engulf" in (sub_pattern_log or "") or "direct" in (sub_pattern_log or "") else "sweep"
                    lines.append(f"📍 {label.capitalize()} Bar:")
                    lines.append(_fmt_bar(sig_bar, label, ltf_tf))
                lines.append("")
        else:
            # Reconstruct single TF candle block (3 bars for S1, S2, S3, S4, S16; 2 bars for others)
            count = 3 if sid in ('1', '2', '3', '4', '16') else 2
            rates = _get_rates(ltf_tf, count, closed_only=True)
            if rates is not None and len(rates) >= count:
                for idx, r in enumerate(rates):
                    lines.append(_fmt_bar(r, count - 1 - idx, ltf_tf))
                lines.append("")

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
                f"📌 Entry: {entry}"
                + (f" | SL: {sl}" if sl else "")
                + (f" | TP: {tp}" if tp else ""),
                " | ".join(rr_parts) if rr_parts else "",
            ]
        lines.append(f"🧭 Trend: {trend_lbl}")
        
        # Cleanup trailing empty lines
        while lines and lines[-1] == "":
            lines.pop()
            
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
