from config import *
import config
import asyncio
from bot_log import log_block, log_event
from mt5_utils import connect_mt5, open_order, get_existing_tp, should_cancel_pending, find_swing_tp, get_structure, has_previous_bar_trade, TF_SECONDS_MAP
from strategy1 import strategy_1
from strategy2 import strategy_2
from strategy3 import strategy_3
from strategy4 import strategy_4, _find_prev_swing_high, _find_prev_swing_low, _find_hh, _find_ll
from strategy5 import strategy_5
from strategy8 import strategy_8
from pending import check_fvg_pending, check_pb_pending
from trailing import check_engulf_trail_sl, check_fvg_candle_quality, check_opposite_order_tp, check_entry_candle_quality, fvg_order_tickets, pending_order_tf, check_cancel_pending_orders, position_tf, check_breakeven_tp, position_sid, position_pattern, check_s6_trail, _s6_state, _s6i_state, _entry_state, _s8_fill_sl
from notifications import check_sl_tp_hits
_first_scan_done = False
_scan_results: dict = {}   # {tf_name: dict}
_scan_lock = None
_last_scan_summary_telegram = ""
_last_scan_summary_cmd = ""
_last_skip_log_by_tf: dict = {}
_swing_data: dict = {}   # {tf_name: {"sh": str, "sl": str, "prev_sh": str, "prev_sl": str, "hh": str, "ll": str}}
_SCAN_TF_ICONS = {"M1": "🟨", "M5": "🟩", "M15": "🟦", "M30": "🟪", "H1": "🟧", "H4": "🟥", "H12": "🟫", "D1": "⬛"}
_SCAN_STRATEGY_ICONS = {"[ท่า1]": "🟡", "[ท่า2]": "🔵", "[ท่า3]": "🟣", "[ท่า4]": "🟢", "[ท่า6]": "🟠", "[ท่า6i]": "🟤", "[ท่า8]": "🩵"}


def _print_skip_once(tf_name: str, message: str) -> None:
    import re
    normalized = re.sub(r"\[\d{2}:\d{2}(?::\d{2})?\]\s*", "", message)
    key = f"{tf_name}|{normalized}"
    if _last_skip_log_by_tf.get(tf_name) == key:
        return
    _last_skip_log_by_tf[tf_name] = key
    print(message)
    log_event("SCAN_SKIP", normalized, tf=tf_name)


def _find_previous_swing_info(rates, current_info, finder):
    """หา swing ก่อนหน้าของ swing ปัจจุบัน เพื่อใช้แสดงผล"""
    if not current_info:
        return None
    current_time = int(current_info.get("time", 0) or 0)
    prev_rates = [r for r in rates if int(r["time"]) < current_time]
    if len(prev_rates) < 6:
        return None
    try:
        return finder(prev_rates)
    except Exception:
        return None




def _fmt_swing_dt(ts):
    """แปลงเวลาแท่ง/swing เป็น HH:mm dd-MMM-yyyy"""
    if not ts:
        return "-"
    from datetime import datetime, timezone, timedelta
    t = datetime.fromtimestamp(int(ts), tz=timezone.utc) + timedelta(hours=TZ_OFFSET - MT5_SERVER_TZ)
    return t.strftime("%H:%M %d-%b-%Y")


def _parse_pattern(pattern: str, signal: str, description: str,
                   entry=0, sl=0, tp=0) -> dict:
    """แยก pattern string -> skill / zone / pattern_name"""
    skill = ""; zone = ""; pat_name = ""
    if pattern:
        import re
        # zone icon: 🟢/🔴 + BUY/SELL
        zm = re.search(r'(🟢|🔴)\s*(BUY|SELL)', pattern)
        if zm:
            zone = f"{zm.group(1)}{zm.group(2)}"

        # pattern name หลัง " — " และตัด "Pattern " นำหน้าออก
        pm = re.search(r'—\s*(.+)$', pattern)
        if pm:
            pat_name = re.sub(r'^Pattern\s*', '', pm.group(1).strip())

        # skill = ชื่อท่า (ก่อน zone icon)
        sm = re.match(r'(ท่าที่\s*\d+[\w\s/ตำหนิย้อนโครงสร้างกลืนกิน FVG DM SP]+?)(?=🟢|🔴)', pattern)
        if sm:
            skill = sm.group(1).strip()
        elif pattern:
            skill = re.split(r'🟢|🔴', pattern)[0].strip()

    return {
        "status":      signal,
        "skill":       skill,
        "zone":        zone,
        "pattern":     pat_name,
        "description": description,
        "entry": entry, "sl": sl, "tp": tp,
    }


def _vlen(s: str) -> int:
    """visual display width (emoji/wide chars = 2 cols)"""
    import unicodedata
    return sum(2 if unicodedata.east_asian_width(c) in ('W','F') else 1 for c in s)


def _format_log_block(tf_name: str, d: dict, lead: str, pad: str, max_len: int) -> str:
    """
    🔍 [10:37] M1  : 🔵 Status      : WAIT — (🟢BUY)
                     📘 Skill       : ท่าที่ 1 กลืนกิน/ตำหนิ/ย้อนโครงสร้าง
                     🎯 Pattern     : กลืนกิน
                     📝 Description : ⚠️ ไม่อยู่ Low Zone
    """
    C_FIELD = "\033[38;5;75m"   # ฟ้า — field labels
    C_SEP   = "\033[38;5;240m"  # เทาเข้ม — separator ":"
    COLON   = f"{C_SEP} : {RESET}"
    c    = TF_COLOR.get(tf_name, "")
    name = tf_name.ljust(max_len)
    W    = 11   # "Description" = 11 chars (longest label)

    # sub-line indent ใช้ visual width ของ pad + name + " : "
    sub = " " * (_vlen(pad) + max_len + 3)

    # Icon สำหรับแต่ละ field (icon = 1 wide char = 2 cols + 1 space)
    ICONS = {
        "Status":      "🔵",
        "Skill":       "📘",
        "Pattern":     "🎯",
        "Description": "📝",
    }
    def field(label):
        icon = ICONS.get(label, "  ")
        # icon กว้าง 2 cols + 1 space = 3 → label ลด 3 ออก แต่ align W ยังคงเดิม
        return f"{icon} {C_FIELD}{label:<{W}}{RESET}"

    # Status + Zone รวมในบรรทัดเดียว
    zone     = d.get("zone", "")   # เช่น "🟢BUY" หรือ "🔴SELL"
    status   = d.get("status", "WAIT")
    if zone:
        if status == "WAIT":
            status_val = f"⏳WAIT {zone}"
        else:
            status_val = f"📌Entry {zone}"
    else:
        status_val = f"⏳WAIT" if status == "WAIT" else status

    lines = [
        f"{lead}{c}{name}{RESET}{COLON}{field('Status')}{COLON}{status_val}"
    ]
    # Skill แสดงเฉพาะเมื่อมี entry (ได้ order)
    if d.get("skill") and d.get("entry"):
        lines.append(f"{sub}{field('Skill')}{COLON}{d['skill']}")
    if d.get("pattern"):
        lines.append(f"{sub}{field('Pattern')}{COLON}{d['pattern']}")
    if d.get("description"):
        desc_raw   = d["description"]
        desc_lines = desc_raw.split("\n")
        label_str  = f"{field('Description')}{COLON}"
        # คำนวณ indent ให้ตรงกับค่าหลัง " : "
        # sub + icon(2cols) + space(1) + W + " : "(3) = เริ่มค่า
        indent2 = sub + " " * (2 + 1 + W + 3)
        lines.append(f"{sub}{label_str}{desc_lines[0]}")
        for dl in desc_lines[1:]:
            lines.append(f"{indent2}{dl}")
    if d.get("entry"):
        lines.append(
            f"{sub}{'':>{W + 4}}  "
            f"{C_ENTRY}{BOLD}Entry : {d['entry']}{RESET}  "
            f"{C_SL}{BOLD}SL : {d['sl']}{RESET}  "
            f"{C_TP}{BOLD}TP : {d['tp']}{RESET}"
        )
    return "\n".join(lines)
def _get_lock():
    global _scan_lock
    if _scan_lock is None:
        _scan_lock = asyncio.Lock()
    return _scan_lock
def tf_label(tf_name: str) -> str:
    """แปลง TF name เป็นชื่อพร้อมสี rainbow"""
    return f"{TF_COLOR.get(tf_name, '')}{tf_name}{RESET}"
def _strip_ansi(text: str) -> str:
    """ลบรหัสสี/format ของ terminal ออกจากข้อความก่อนส่ง Telegram"""
    import re
    if not text:
        return ""
    text = re.sub(r"\x1b\[[0-9;]*m", "", text)
    text = re.sub(r"\[[0-9;]+m", "", text)
    return text.replace(RESET, "").replace(BOLD, "")
def _format_scan_summary_telegram(show_tfs: list[str]) -> tuple[str, str]:
    """สร้าง summary scan สำหรับ Telegram และคืน key สำหรับ dedup"""
    body_lines = []
    for tf in show_tfs:
        d = _scan_results.get(tf, {})
        status = d.get("status", "WAIT")
        desc = d.get("description", "") or "ไม่มีรายละเอียด"
        desc_lines = [line.strip() for line in desc.splitlines() if line.strip()]

        body_lines.append(f"`{tf}` {'⏳ WAIT' if status == 'WAIT' else '📌 ENTRY'}")
        for line in desc_lines:
            body_lines.append(line)
        if d.get("entry"):
            body_lines.append(f"Entry:`{d['entry']}` SL:`{d['sl']}` TP:`{d['tp']}`")
        body_lines.append("")
    body = "\n".join(body_lines).strip()
    text = (
        "🔍 *Scan Summary*\n"
        "━━━━━━━━━━━━━━━━━\n"
        f"🕐 `{now_bkk().strftime('%H:%M:%S %d/%m/%Y')}`\n\n"
        f"{body}"
    )
    return text, body
def _format_scan_summary_telegram_clean(show_tfs: list[str]) -> tuple[str, str]:
    """สร้าง summary scan สำหรับ Telegram แบบ plain text และไม่มี ANSI"""
    body_lines = []
    for tf in show_tfs:
        d = _scan_results.get(tf, {})
        status = d.get("status", "WAIT")
        desc = _strip_ansi(d.get("description", "") or "ไม่มีรายละเอียด")
        desc_lines = [line.strip() for line in desc.splitlines() if line.strip()]

        tf_icon = _SCAN_TF_ICONS.get(tf, "⬜")
        status_icon = "⏳" if status == "WAIT" else "📌"
        body_lines.append(f"{tf_icon} {tf} | {status_icon} {status}")
        for line in desc_lines:
            icon = "⚪"
            strategy_label = ""
            clean_line = line
            for key, value in _SCAN_STRATEGY_ICONS.items():
                if key in line:
                    icon = value
                    strategy_label = key.strip("[]")
                    clean_line = clean_line.replace(f"{key} ", "").replace(key, "")
                    break
            prefix = f"{icon} {strategy_label}".strip()
            body_lines.append(f"{prefix} {clean_line.strip()}".strip())
        if d.get("entry"):
            body_lines.append(f"💰 Entry:{d['entry']} | SL:{d['sl']} | TP:{d['tp']}")
        body_lines.append("")

    # Swing summary รวมทุก TF ท้าย
    swing_lines = []
    for tf in _swing_data:
        sw = _swing_data[tf]
        tf_icon = _SCAN_TF_ICONS.get(tf, "⬜")
        swing_lines.append(f"┌─ {tf_icon} {tf}")
        swing_lines.append(f"│ 📈 H:{sw['sh']}")
        swing_lines.append(f"│ 📈 HH:{sw.get('hh', '—')}")
        swing_lines.append(f"│ 📈 Prev H:{sw.get('prev_sh', '—')}")
        swing_lines.append(f"│ 📉 L:{sw['sl']}")
        swing_lines.append(f"│ 📉 LL:{sw.get('ll', '—')}")
        swing_lines.append(f"│ 📉 Prev L:{sw.get('prev_sl', '—')}")
        swing_lines.append("└────────────────")
    if swing_lines:
        body_lines.append("━━━━━━━━━━━━━━━━━\n📊 Scan Swing\n\n" + "\n".join(swing_lines))

    body = "\n".join(body_lines).strip()
    text = (
        "🔍 Scan Summary\n"
        "━━━━━━━━━━━━━━━━━\n"
        f"🕐 {now_bkk().strftime('%H:%M:%S %d/%m/%Y')}\n\n"
        f"{body}"
    )
    return text, body
async def check_s3_maru_pending(app):
    """
    ท่า 3 Marubozu pending — รอยืนยันแท่งถัดจากแท่ง[0] ตัน
    BUY:  แท่งถัดไปจบเขียว → ตั้ง Limit | จบแดง → ยกเลิก
    SELL: แท่งถัดไปจบแดง  → ตั้ง Limit | จบเขียว → ยกเลิก
    """
    if not s3_maru_pending:
        return
    now      = now_bkk().strftime("%H:%M:%S")
    to_remove = []
    for key, p in list(s3_maru_pending.items()):
        tf         = p["tf"]
        direction  = p["direction"]
        candle_time = p["candle_time"]
        entry      = p["entry"]
        sl         = p["sl"]
        tp         = p["tp"]
        tf_val  = TF_OPTIONS.get(tf, mt5.TIMEFRAME_M1)
        rates   = mt5.copy_rates_from_pos(SYMBOL, tf_val, 1, 5)
        if rates is None or len(rates) < 2:
            continue
        last_bar = rates[-1]
        last_time = int(last_bar["time"])

        # รอแท่งใหม่หลังจากแท่ง[0] ตัน
        if last_time <= candle_time:
            continue   # ยังเป็นแท่งเดิมอยู่

        o  = float(last_bar["open"])
        cl = float(last_bar["close"])
        bull_next = cl > o

        sig_e = "🟢" if direction == "BUY" else "🔴"

        if direction == "BUY":
            if bull_next:
                # ✅ จบเขียว → ตั้ง Limit
                _s3_prev = config.last_traded_sid_tf.get(tf, {}).get(3)
                _s3_adj = _s3_prev and has_previous_bar_trade(tf, candle_time) and (candle_time - _s3_prev) == TF_SECONDS_MAP.get(tf, 0)
                if _s3_adj:
                    print(f"⏭️ [{now}] ท่า3 BUY Maru [{tf}] ข้าม: แท่งติดกับ order ท่าเดียวกัน")
                elif last_traded_per_tf.get(tf) != candle_time:
                    order = open_order(direction, get_volume(), sl, tp, entry_price=entry, tf=tf, sid=3, pattern=f"DM SP Marubozu {direction} [{tf}]")
                    if order["success"]:
                        last_traded_per_tf[tf] = candle_time
                        config.last_traded_sid_tf.setdefault(tf, {})[3] = candle_time
                        position_tf[order["ticket"]] = tf
                        position_pattern[order["ticket"]] = "ท่าที่ 3 DM SP — Marubozu BUY"
                        tick = mt5.symbol_info_tick(SYMBOL)
                        cur_price = (tick.ask if direction == "BUY" else tick.bid) if tick else 0
                        risk = abs(entry - sl)
                        rr   = round(abs(tp - entry) / risk, 2) if risk > 0 else 0
                        await app.bot.send_message(
                            chat_id=MY_USER_ID,
                            text=_order_msg(
                                sig_e, f"ท่าที่ 3 DM SP 🟢 BUY — Marubozu", tf, 3,
                                "", 0.0, 0.0,
                                f"แท่ง[0] เขียวตัน → แท่งถัดไปจบเขียว ✅",
                                cur_price, entry, sl, tp, rr, order["ticket"]
                            ),
                            parse_mode="Markdown"
                        )
                        print(f"✅ [{now}] ท่า3 BUY Maru [{tf}] ยืนยันเขียว Entry={entry}")
            else:
                # ❌ จบแดง → ยกเลิก
                await tg(app, (
                        f"❌ *ท่า3 BUY Marubozu ยกเลิก*\n"
                        f"{sig_e} [{tf}] แท่งถัดไปจบแดง\n"
                        f"Entry:{entry} ไม่ตั้ง Limit"
                    ))
                print(f"❌ [{now}] ท่า3 BUY Maru [{tf}] ยกเลิก (แดง)")
            to_remove.append(key)
        else:  # SELL
            if not bull_next:
                # ✅ จบแดง → ตั้ง Limit
                _s3_prev = config.last_traded_sid_tf.get(tf, {}).get(3)
                _s3_adj = _s3_prev and has_previous_bar_trade(tf, candle_time) and (candle_time - _s3_prev) == TF_SECONDS_MAP.get(tf, 0)
                if _s3_adj:
                    print(f"⏭️ [{now}] ท่า3 SELL Maru [{tf}] ข้าม: แท่งติดกับ order ท่าเดียวกัน")
                elif last_traded_per_tf.get(tf) != candle_time:
                    order = open_order(direction, get_volume(), sl, tp, entry_price=entry, tf=tf, sid=3, pattern=f"DM SP Marubozu {direction} [{tf}]")
                    if order["success"]:
                        last_traded_per_tf[tf] = candle_time
                        config.last_traded_sid_tf.setdefault(tf, {})[3] = candle_time
                        position_tf[order["ticket"]] = tf
                        position_pattern[order["ticket"]] = "ท่าที่ 3 DM SP — Marubozu SELL"
                        tick = mt5.symbol_info_tick(SYMBOL)
                        cur_price = (tick.ask if direction == "BUY" else tick.bid) if tick else 0
                        risk = abs(entry - sl)
                        rr   = round(abs(tp - entry) / risk, 2) if risk > 0 else 0
                        await app.bot.send_message(
                            chat_id=MY_USER_ID,
                            text=_order_msg(
                                sig_e, f"ท่าที่ 3 DM SP 🔴 SELL — Marubozu", tf, 3,
                                "", 0.0, 0.0,
                                f"แท่ง[0] แดงตัน → แท่งถัดไปจบแดง ✅",
                                cur_price, entry, sl, tp, rr, order["ticket"]
                            ),
                            parse_mode="Markdown"
                        )
                        print(f"✅ [{now}] ท่า3 SELL Maru [{tf}] ยืนยันแดง Entry={entry}")
            else:
                # ❌ จบเขียว → ยกเลิก
                await tg(app, (
                        f"❌ *ท่า3 SELL Marubozu ยกเลิก*\n"
                        f"{sig_e} [{tf}] แท่งถัดไปจบเขียว\n"
                        f"Entry:{entry} ไม่ตั้ง Limit"
                    ))
                print(f"❌ [{now}] ท่า3 SELL Maru [{tf}] ยกเลิก (เขียว)")
            to_remove.append(key)
    for k in to_remove:
        s3_maru_pending.pop(k, None)
def _order_msg(sig_e, pattern, tf_name, sid, candle_rows, swing_h, swing_l,
               reason_txt, current_price, entry, sl, tp, rr, ticket=None, extra_note="",
               swing_h_text="", swing_l_text=""):
    """สร้าง Telegram message format มาตรฐานสำหรับทุกท่า"""
    price_diff = round(abs(current_price - entry), 2)
    ticket_line = f"\n🔖 Ticket: `{ticket}`" if ticket else ""
    note_line = f"\n{extra_note}" if extra_note else ""
    swing_h_suffix = f" {swing_h_text}" if swing_h_text else ""
    swing_l_suffix = f" {swing_l_text}" if swing_l_text else ""
    return (
        f"{sig_e} *{pattern}*\n"
        f"━━━━━━━━━━━━━━━━━\n"
        f"🕐 {now_bkk().strftime('%H:%M %d/%m/%Y')}\n"
        f"📊 *Timeframe: {tf_name}* | ท่าที่ {sid}\n\n"
        f"{candle_rows}\n"
        f"📈 Swing High:`{swing_h:.2f}`{swing_h_suffix} | Low:`{swing_l:.2f}`{swing_l_suffix}\n\n"
        f"💬 *เหตุผล:*\n{reason_txt}\n\n"
        f"━━━━━━━━━━━━━━━━━\n"
        f"💰 ราคาปัจจุบัน: `{current_price:.2f}`\n"
        f"📌 *Limit ที่:* `{entry}` (ห่าง {price_diff})\n"
        f"🛑 SL: `{sl}` | 🎯 TP: `{tp}`\n"
        f"⚖️ R:R `1:{rr}` | 📦 `{AUTO_VOLUME}` lot"
        f"{ticket_line}{note_line}"
    )
def _fvg_find_parallel_intersection(new_tf: str, signal: str, gap_bot: float, gap_top: float):
    """
    หา intersection ของ gap ระหว่าง new_tf กับ TF อื่นในกลุ่มเดียวกัน
    คืน (int_bot, int_top, tfs_list, tickets_to_cancel)
    ถ้าไม่มี overlap คืน (None, None, [new_tf], [])
    """
    TF_MIN = {"M1":1,"M5":5,"M15":15,"M30":30,"H1":60,"H4":240,"H12":720,"D1":1440}
    def tf_min(tf): return TF_MIN.get(tf, 9999)

    # หา group ที่ครบ และต้องมี TF อื่นนอกจาก new_tf ด้วย
    my_groups = []
    for group in config.FVG_PARALLEL_GROUPS:
        if new_tf in group and all(tf in TF_ACTIVE for tf in group):
            # group ต้องมี TF อื่นที่ไม่ใช่ new_tf
            if any(tf != new_tf for tf in group):
                my_groups.append(group)
    if not my_groups:
        return None, None, [new_tf], []
    orders = mt5.orders_get(symbol=SYMBOL)
    if not orders:
        return None, None, [new_tf], []
    target_type = mt5.ORDER_TYPE_BUY_LIMIT if signal == "BUY" else mt5.ORDER_TYPE_SELL_LIMIT

    # รวม gap ของทุก TF ที่ overlap
    all_gaps = [{"tf": new_tf, "bot": gap_bot, "top": gap_top, "ticket": None}]
    for order in orders:
        if order.type != target_type:
            continue
        info = pending_order_tf.get(order.ticket)
        if not info or not isinstance(info, dict):
            continue
        ex_tf  = info.get("tf")
        ex_bot = info.get("gap_bot", order.price_open)   # raw gap ของ TF นั้น
        ex_top = info.get("gap_top", order.price_open)

        # ตรวจว่าอยู่ใน group เดียวกัน และไม่ใช่ TF เดียวกัน
        if ex_tf == new_tf:
            continue
        in_group = any(ex_tf in g and new_tf in g for g in my_groups)
        if not in_group:
            continue

        # ตรวจ overlap กับ new_tf gap
        overlap = not (gap_top < ex_bot or gap_bot > ex_top)
        if not overlap:
            continue

        all_gaps.append({"tf": ex_tf, "bot": ex_bot, "top": ex_top, "ticket": order.ticket})
    if len(all_gaps) == 1:
        # ไม่มี TF อื่น overlap → ตั้ง order ปกติ
        return None, None, [new_tf], []

    # คำนวณ intersection ของทุก gap
    int_bot = max(g["bot"] for g in all_gaps)
    int_top = min(g["top"] for g in all_gaps)
    if int_bot >= int_top:
        return None, None, [new_tf], []

    # intersection gap ต้องมีขนาด ≥ 0.5pt (เหมือน FVG ปกติ)
    if int_top - int_bot < 0.5:
        return None, None, [new_tf], []

    # เรียง TF จากเล็กไปใหญ่ และ dedup (กัน M15+M15)
    all_gaps.sort(key=lambda g: tf_min(g["tf"]))
    seen_tfs = set()
    deduped  = []
    for g in all_gaps:
        if g["tf"] not in seen_tfs:
            seen_tfs.add(g["tf"])
            deduped.append(g)
        elif g["ticket"]:
            # TF ซ้ำ → cancel order นั้นด้วย
            r = mt5.order_send({"action": mt5.TRADE_ACTION_REMOVE, "order": g["ticket"]})
            if r and r.retcode == mt5.TRADE_RETCODE_DONE:
                pending_order_tf.pop(g["ticket"], None)
                print(f"[{now_bkk().strftime('%H:%M:%S')}] 🔄 Parallel dedup: ลบ order {g['ticket']} TF={g['tf']} ซ้ำ")
    all_gaps = deduped
    tfs_list = [g["tf"] for g in all_gaps]
    tickets_to_cancel = [g["ticket"] for g in all_gaps if g["ticket"] is not None]
    return round(int_bot, 2), round(int_top, 2), tfs_list, tickets_to_cancel
async def auto_scan(app):
    """สแกนทุก Timeframe ที่เปิดอยู่พร้อมกัน"""
    global auto_active, _first_scan_done, _last_scan_summary_telegram, _last_scan_summary_cmd
    if not auto_active:
        return
    if not connect_mt5():
        await tg(app, "\u26a0\ufe0f MT5 \u0e44\u0e21\u0e48\u0e44\u0e14\u0e49\u0e40\u0e0a\u0e37\u0e48\u0e2d\u0e21\u0e15\u0e48\u0e2d")
        return
    await check_sl_tp_hits(app)
    await check_cancel_pending_orders(app)
    await check_engulf_trail_sl(app)
    # await check_breakeven_tp(app)  # ปิดชั่วคราว
    await check_opposite_order_tp(app)
    await check_entry_candle_quality(app)
    await check_s3_maru_pending(app)
    await check_fvg_pending(app)
    await check_pb_pending(app)
    positions  = mt5.positions_get(symbol=SYMBOL)
    open_count = len(positions) if positions else 0
    if open_count >= MAX_ORDERS:
        print(f"[{now_bkk().strftime('%H:%M:%S')}] \u26a0\ufe0f Order \u0e40\u0e15\u0e47\u0e21 {open_count}/{MAX_ORDERS}")
        return
    active_tfs = [tf for tf, on in TF_ACTIVE.items() if on]
    if not active_tfs:
        print(f"[{now_bkk().strftime('%H:%M:%S')}] \u26a0\ufe0f \u0e44\u0e21\u0e48\u0e21\u0e35 Timeframe \u0e17\u0e35\u0e48\u0e40\u0e1b\u0e34\u0e14\u0e2d\u0e22\u0e39\u0e48")
        return
    now = now_bkk().strftime("%H:%M:%S")
    is_first = not _first_scan_done
    if is_first:
        _first_scan_done = True
        strat_names = [STRATEGY_NAMES[k] for k, v in active_strategies.items() if v]
        print(f"\U0001f680 [{now}] Auto Scan \u0e40\u0e23\u0e34\u0e48\u0e21! {'  '.join(tf_label(tf) for tf in active_tfs)}{RESET}")
        print(f"   Strategy: {strat_names}")
        print(f"   Scan Interval: {config.SCAN_INTERVAL} \u0e19\u0e32\u0e17\u0e35")
        await app.bot.send_message(
            chat_id=MY_USER_ID,
            text=(
                "\U0001f680 *Auto Scan \u0e40\u0e23\u0e34\u0e48\u0e21\u0e15\u0e49\u0e19!*\n"
                "\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\n"
                f"\U0001f4cb Strategy: *{chr(44).join(strat_names) or chr(0xe44)+chr(0xe21)+chr(0xe48)+chr(0xe21)+chr(0xe35)}*\n"
                f"\u23f0 Interval: *{config.SCAN_INTERVAL} \u0e19\u0e32\u0e17\u0e35*\n"
                f"\U0001f550 Timeframes: *{chr(44).join(active_tfs)}*"
            ),
            parse_mode="Markdown"
        )
        log_tfs = active_tfs
    else:
        log_tfs = [tf for tf in active_tfs if should_log_tf(tf, config.SCAN_INTERVAL)]

    # เคลียร์ log เดิม แล้ว scan ทุก TF พร้อมกัน
    _scan_results.clear()
    _swing_data.clear()
    await asyncio.gather(*[scan_one_tf(app, tf) for tf in active_tfs])

    # print log รวมเป็น block เดียว
    if _scan_results:
        show_tfs = [tf for tf in active_tfs
                    if tf in _scan_results and (is_first or should_log_tf(tf, config.SCAN_INTERVAL))]
        if show_tfs:
            prefix  = f"\U0001f50d [{now}] "
            pad     = " " * _vlen(prefix)   # visual width เพื่อให้ตรงกับ emoji
            max_len = max(len(tf) for tf in show_tfs)
            blocks  = []
            for i, tf in enumerate(show_tfs):
                lead = prefix if i == 0 else pad
                d    = _scan_results[tf]
                blocks.append(_format_log_block(tf, d, lead, pad, max_len))
            tg_text, tg_key = _format_scan_summary_telegram_clean(show_tfs)
            # Swing summary block รวมทุก TF
            C_SW = "\033[38;5;228m"
            swing_lines = []
            for tf in _swing_data:
                sw = _swing_data[tf]
                c = TF_COLOR.get(tf, "")
                swing_lines.append(f"  ┌─ {c}{tf}{RESET}")
                swing_lines.append(f"  │ 📈 {C_SW}H:{sw['sh']}{RESET}")
                swing_lines.append(f"  │ 📈 {C_SW}HH:{sw.get('hh', '—')}{RESET}")
                swing_lines.append(f"  │ 📈 {C_SW}Prev H:{sw.get('prev_sh', '—')}{RESET}")
                swing_lines.append(f"  │ 📉 {C_SW}L:{sw['sl']}{RESET}")
                swing_lines.append(f"  │ 📉 {C_SW}LL:{sw.get('ll', '—')}{RESET}")
                swing_lines.append(f"  │ 📉 {C_SW}Prev L:{sw.get('prev_sl', '—')}{RESET}")
                swing_lines.append("  └────────────────")
            if swing_lines:
                blocks.append("\n".join(swing_lines))
            if tg_key and tg_key != _last_scan_summary_cmd:
                print("\n".join(blocks))
                log_block("SCAN_SUMMARY", tg_text)
                _last_scan_summary_cmd = tg_key
            if tg_key and tg_key != _last_scan_summary_telegram:
                await tg(app, tg_text, parse_mode=None)
                _last_scan_summary_telegram = tg_key
                print(f"[{now_bkk().strftime('%H:%M:%S')}] SCAN_SUMMARY_TG queued")
async def scan_one_tf(app, tf_name: str) -> bool:
    """สแกน 1 Timeframe — return True ถ้าเปิด Order สำเร็จ"""
    tf_val = TF_OPTIONS[tf_name]
    now    = now_bkk().strftime("%H:%M")
    lookback = TF_LOOKBACK.get(tf_name, SWING_LOOKBACK)

    # จำนวนวินาทีต่อแท่งของแต่ละ TF
    TF_SECONDS = {"M1": 60, "M5": 300, "M15": 900, "M30": 1800, "H1": 3600, "H4": 14400, "H12": 43200, "D1": 86400}
    tf_secs = TF_SECONDS.get(tf_name, 60)

    # ดึงแท่งปัจจุบัน (index=0) ก่อน เพื่อตรวจสอบว่าแท่งก่อนหน้าปิดสมบูรณ์แล้ว
    current_bar = mt5.copy_rates_from_pos(SYMBOL, tf_val, 0, 1)
    if current_bar is None or len(current_bar) == 0:
        return False
    current_bar_time = int(current_bar[0]["time"])

    # ดึงแท่งที่ปิดแล้ว (start=1 ข้ามแท่งปัจจุบัน)
    rates = mt5.copy_rates_from_pos(SYMBOL, tf_val, 1, lookback + 6)
    if rates is None or len(rates) < lookback + 4:
        return False
    last_candle_time = int(rates[-1]["time"])

    # ── Log Swing High / Low ของ TF นี้ (ทำก่อน guard เพื่อแสดงทุก TF เสมอ) ──
    _sh_info = _find_prev_swing_high(rates)
    _sl_info = _find_prev_swing_low(rates)
    _prev_sh_info = _find_previous_swing_info(rates, _sh_info, _find_prev_swing_high)
    _prev_sl_info = _find_previous_swing_info(rates, _sl_info, _find_prev_swing_low)
    _hh_info = _find_hh(rates, _sh_info)
    _ll_info = _find_ll(rates, _sl_info)
    def _swing_fmt(info, label):
        if not info: return "—"
        from datetime import datetime, timezone, timedelta
        t = datetime.fromtimestamp(info["time"], tz=timezone.utc) + timedelta(hours=TZ_OFFSET - MT5_SERVER_TZ)
        return f"{info['price']:.2f} [{info['bar_from_2']+3}] {t.strftime('%H:%M %d-%b-%Y')}"
    _swing_data[tf_name] = {
        "sh": _swing_fmt(_sh_info, "H"),
        "sl": _swing_fmt(_sl_info, "L"),
        "prev_sh": _swing_fmt(_prev_sh_info, "H"),
        "prev_sl": _swing_fmt(_prev_sl_info, "L"),
        "hh": _swing_fmt(_hh_info, "HH"),
        "ll": _swing_fmt(_ll_info, "LL"),
    }
    # Guard: แท่งล่าสุดจะถือว่าปิดสมบูรณ์ ก็ต่อเมื่อแท่งใหม่เริ่มแล้ว
    # ดังนั้นใช้ current_bar_time > last_candle_time ก็พอ
    # ตัวอย่าง M5: last=14:44 และ current=14:45 แปลว่าแท่ง 14:44 ปิดแล้ว
    if current_bar_time <= last_candle_time:
        _scan_results[tf_name] = _parse_pattern("", "WAIT", "แท่ง[0] ยังวิ่งอยู่")
        _print_skip_once(tf_name, f"⏳ [{now}] {tf_label(tf_name)}: แท่ง[0] ยังวิ่งอยู่ (current={current_bar_time} == last={last_candle_time})")
        return False

    # กัน Order ซ้ำในแท่งเดิมของ TF นี้
    if last_traded_per_tf.get(tf_name) == last_candle_time:
        _scan_results[tf_name] = _parse_pattern("", "WAIT", "เทรดแท่งนี้ไปแล้ว")
        _print_skip_once(tf_name, f"⏭️ [{now}] {tf_label(tf_name)}: เทรดแท่งนี้ไปแล้ว")
        return False

    # กัน Order แท่งติดกัน — ย้ายไปเช็กแยกตาม sid ที่จุด order แทน
    # (ท่าต่างกันสามารถ trade แท่งติดกันได้)

    # ── รัน 3 Strategy พร้อมกันอิสระ ────────────────────────────
    r1 = strategy_1(rates) if active_strategies.get(1, False) else {"signal": "WAIT", "reason": "S1 ปิด"}
    r2 = strategy_2(rates) if active_strategies.get(2, False) else {"signal": "WAIT", "reason": "S2 ปิด"}
    r3 = strategy_3(rates) if active_strategies.get(3, False) else {"signal": "WAIT", "reason": "S3 ปิด"}
    r4 = strategy_4(rates) if active_strategies.get(4, False) else {"signal": "WAIT", "reason": "S4 ปิด"}
    r5 = strategy_5(rates) if active_strategies.get(5, False) else {"signal": "WAIT", "reason": "S5 ปิด"}
    r8 = strategy_8(rates) if active_strategies.get(8, False) else {"signal": "WAIT", "reason": "S8 ปิด", "orders": []}

    # ── S2 FVG — ตั้ง Limit ทันที ────────────────────────────────
    if r2.get("signal") == "FVG_DETECTED":
        fvg     = r2["fvg"]
        fvg_key = f"{tf_name}_{last_candle_time}"
        # adjacent bar check per-sid
        _s2_prev = config.last_traded_sid_tf.get(tf_name, {}).get(2)
        _s2_adjacent = _s2_prev and (last_candle_time - _s2_prev) == tf_secs
        if fvg_key not in fvg_pending and last_traded_per_tf.get(tf_name) != last_candle_time and not _s2_adjacent:
            tp_swing = find_swing_tp(rates, fvg["signal"], fvg["entry"], fvg["sl"])
            tp = tp_swing if tp_swing else round(
                fvg["entry"] + abs(fvg["entry"] - fvg["sl"]) if fvg["signal"] == "BUY"
                else fvg["entry"] - abs(fvg["sl"] - fvg["entry"]), 2
            )
            tp_note = ("Swing High:" + str(tp)) if (tp_swing and fvg["signal"] == "BUY") else \
                      ("Swing Low:"  + str(tp)) if tp_swing else "RR1:1 (fallback)"
            sig_e = "🟢" if fvg["signal"] == "BUY" else "🔴"

            # ── Parallel mode: หา intersection gap ก่อนตั้ง order ──
            final_gap_bot = fvg["gap_bot"]
            final_gap_top = fvg["gap_top"]
            parallel_tfs  = [tf_name]   # TF ที่ gap ซ้อนกัน

            if config.FVG_PARALLEL:
                int_bot, int_top, int_tfs, to_cancel_tickets = \
                    _fvg_find_parallel_intersection(
                        tf_name, fvg["signal"], fvg["gap_bot"], fvg["gap_top"]
                    )
                if int_bot is not None:
                    final_gap_bot = int_bot
                    final_gap_top = int_top
                    parallel_tfs  = int_tfs
                    # ลบ order ของ TF ที่ซ้อนออก (จะตั้ง order ใหม่แทน)
                    for t in to_cancel_tickets:
                        # หา tf ของ order ก่อน pop
                        t_info = pending_order_tf.get(t)
                        t_tf   = t_info.get("tf") if isinstance(t_info, dict) else t_info
                        mt5.order_send({"action": mt5.TRADE_ACTION_REMOVE, "order": t})
                        pending_order_tf.pop(t, None)
                        if t_tf:
                            last_traded_per_tf.pop(t_tf, None)

            # ทั้งปกติและ parallel ปิดหมด → ไม่ order
            if not config.FVG_NORMAL and not config.FVG_PARALLEL:
                return False

            # parallel เปิดอยู่แต่เจอ TF เดียว → ข้ามถ้าไม่ได้เปิด normal ด้วย
            if len(parallel_tfs) < 2 and config.FVG_PARALLEL and not config.FVG_NORMAL:
                scan_results.append({"tf": tf_name, "sid": 2, "signal": "WAIT",
                    "reason": f"FVG {fvg['signal']} [{tf_name}] รอ TF อื่นซ้อนทับ (parallel)"})
                fvg_pending[fvg_key] = True
                return False

            # คำนวณ entry จาก final gap
            gap_size   = final_gap_top - final_gap_bot
            if fvg["signal"] == "BUY":
                final_entry = round(final_gap_bot + gap_size * 0.90, 2)
            else:
                final_entry = round(final_gap_top - gap_size * 0.90, 2)
            tf_label_str = "+".join(parallel_tfs) if len(parallel_tfs) > 1 else tf_name
            fvg_tp = get_existing_tp(fvg["signal"], final_entry, tf_name) or tp
            order  = open_order(fvg["signal"], get_volume(), fvg["sl"], fvg_tp, entry_price=final_entry, tf=tf_name, sid=2, pattern=fvg["pattern"], parallel_tfs=parallel_tfs)
            if order["success"]:
                # mark ทุก TF ใน parallel group เพื่อกัน re-detect
                for ptf in parallel_tfs:
                    last_traded_per_tf[ptf] = last_candle_time
                    config.last_traded_sid_tf.setdefault(ptf, {})[2] = last_candle_time
                last_traded_per_tf[tf_name] = last_candle_time
                config.last_traded_sid_tf.setdefault(tf_name, {})[2] = last_candle_time
                ot_name = order.get("order_type", "LIMIT")
                if order.get("ticket"):
                    # Parallel: ใช้ TF เล็กสุดใน group สำหรับ entry candle check
                    TF_MIN_MAP = {"M1":1,"M5":5,"M15":15,"M30":30,"H1":60,"H4":240,"H12":720,"D1":1440}
                    check_tf = min(parallel_tfs, key=lambda t: TF_MIN_MAP.get(t, 9999))
                    fvg_order_tickets[order["ticket"]] = {
                        "tf": check_tf, "signal": fvg["signal"], "checked": False,
                    }
                    _pend_info = {
                        "tf":              tf_name,
                        "gap_bot":         fvg["gap_bot"],   # raw gap ของ TF นี้ (ไม่ใช่ intersection)
                        "gap_top":         fvg["gap_top"],   # ใช้สำหรับ intersection ครั้งต่อไป
                        "final_gap_bot":   final_gap_bot,    # intersection ที่ใช้ตั้ง order
                        "final_gap_top":   final_gap_top,
                        "detect_bar_time": last_candle_time,
                        "signal":          fvg["signal"],
                        "sid":             2,
                        "pattern":         fvg["pattern"],
                        "c3_type":         fvg.get("c3_type", ""),
                    }
                    # Pattern "ปฏิเสธราคา" → ยกเลิก limit ถ้าไม่ fill ภายใน 1 แท่ง
                    if fvg.get("c3_type") == "ปฏิเสธราคา":
                        _pend_info["cancel_bars"] = 1
                    pending_order_tf[order["ticket"]] = _pend_info
                    position_tf[order["ticket"]] = check_tf
                    position_sid[order["ticket"]] = 2
                    position_pattern[order["ticket"]] = f"ท่าที่ 2 FVG {fvg['signal']} [{tf_label_str}]"
                    log_event(
                        "ORDER_CREATED",
                        fvg["pattern"],
                        tf=tf_label_str,
                        sid=2,
                        signal=fvg["signal"],
                        entry=final_entry,
                        sl=fvg["sl"],
                        tp=tp,
                        ticket=order["ticket"],
                        order_type=ot_name,
                    )
                save_runtime_state()

                # แสดงแท่งเทียน
                candle_txt = ""
                candles    = [
                    {"open": float(rates[-3]["open"]), "high": float(rates[-3]["high"]),
                     "low": float(rates[-3]["low"]),  "close": float(rates[-3]["close"])},  # [2]
                    {"open": float(rates[-2]["open"]), "high": float(rates[-2]["high"]),
                     "low": float(rates[-2]["low"]),  "close": float(rates[-2]["close"])},  # [1]
                    {"open": float(rates[-1]["open"]), "high": float(rates[-1]["high"]),
                     "low": float(rates[-1]["low"]),  "close": float(rates[-1]["close"])},  # [0]
                ]
                labels = ["[2]", "[1]", "[0]"]
                for i, c in enumerate(candles):
                    clr = "🟢" if c["close"] > c["open"] else "🔴"
                    candle_ts = int(rates[-(3 - i)]["time"])
                    candle_txt += (
                        f"{clr} แท่ง{labels[i]}: O:`{c['open']:.2f}` H:`{c['high']:.2f}` "
                        f"L:`{c['low']:.2f}` C:`{c['close']:.2f}` {_fmt_swing_dt(candle_ts)}\n"
                    )

                tick          = mt5.symbol_info_tick(SYMBOL)
                current_price = (tick.ask if fvg["signal"] == "BUY" else tick.bid) if tick else 0
                price_diff    = round(abs(current_price - final_entry), 2)
                rr_val        = round(abs(tp - final_entry) / abs(final_entry - fvg["sl"]), 2) if abs(final_entry - fvg["sl"]) > 0 else 0
                tf_label_str  = "+".join(parallel_tfs) if len(parallel_tfs) > 1 else tf_name
                intersect_note = f" (Intersection {'+'.join(parallel_tfs)})" if len(parallel_tfs) > 1 else ""
                ms = get_structure(rates)
                gap_note = f"📐 Gap: `{final_gap_bot}` – `{final_gap_top}` ({round(final_gap_top-final_gap_bot,2)}pt)"
                reason_txt = f"แท่ง[0]: {fvg.get('c3_type','')} | {fvg['zone_note']}\n{gap_note}"
                swing_h_text = _fmt_swing_dt(_sh_info["time"]) if _sh_info else ""
                swing_l_text = _fmt_swing_dt(_sl_info["time"]) if _sl_info else ""
                await app.bot.send_message(
                    chat_id=MY_USER_ID,
                    text=_order_msg(
                        sig_e, fvg["pattern"], tf_label_str, 2,
                        candle_txt, ms["swing_high"], ms["swing_low"],
                        reason_txt, current_price, final_entry, fvg["sl"], tp, rr_val,
                        order["ticket"], intersect_note,
                        swing_h_text=swing_h_text,
                        swing_l_text=swing_l_text,
                    ),
                    parse_mode="Markdown"
                )
                print(f"✅ [{now}] FVG {fvg['signal']} [{tf_label_str}] Entry={final_entry}")

            elif order.get("skipped"):
                log_event(
                    "ORDER_SKIPPED",
                    order.get("error", ""),
                    tf=tf_name,
                    sid=2,
                    signal=fvg["signal"],
                    entry=final_entry,
                    sl=fvg["sl"],
                    tp=tp,
                )
                fvg_pending[fvg_key] = {
                    "tf": tf_name, "signal": fvg["signal"],
                    "entry": final_entry, "sl": fvg["sl"], "tp": tp,
                    "tp_note": tp_note, "gap_top": final_gap_top,
                    "gap_bot": final_gap_bot, "c3_type": fvg.get("c3_type", ""),
                    "pattern": fvg["pattern"],
                    "candle_key": last_candle_time,
                }
                await app.bot.send_message(
                    chat_id=MY_USER_ID,
                    text=(
                        f"{sig_e} *FVG {fvg['signal']} [{tf_name}]*\n"
                        f"Gap: `{final_gap_bot}` – `{final_gap_top}`\n"
                        f"📌 Entry: `{final_entry}`\n"
                        f"⏭️ ราคาผ่าน entry ไปแล้ว รอย้อนกลับ..."
                    ),
                    parse_mode="Markdown"
                )
            else:
                log_event(
                    "ORDER_FAILED",
                    order.get("error", ""),
                    tf=tf_name,
                    sid=2,
                    signal=fvg["signal"],
                    entry=final_entry,
                    sl=fvg["sl"],
                    tp=tp,
                )
                await app.bot.send_message(
                    chat_id=MY_USER_ID,
                    text=f"⚠️ FVG {fvg['signal']} [{tf_name}] ตั้ง order ไม่สำเร็จ: {order.get('error','')}")

    # ท่า 4 execute ตรงเหมือนท่า 1 (ไม่ใช้ fvg_pending)

    # ── ท่า 3 Marubozu pending — register ถ้า r3 คืน marubozu_pending ──
    if active_strategies.get(3, False) and r3.get("marubozu_pending"):
        mp  = r3["marubozu_pending"]
        key = f"{tf_name}_{mp['candle_time']}_s3maru"
        if key not in s3_maru_pending and last_traded_per_tf.get(tf_name) != last_candle_time:
            s3_maru_pending[key] = {
                "tf":          tf_name,
                "direction":   mp["direction"],
                "entry":       mp["entry"],
                "sl":          mp["sl"],
                "tp":          mp["tp"],
                "candle_time": mp["candle_time"],
            }
            sig_e = "🟢" if mp["direction"] == "BUY" else "🔴"
            print(f"📋 [{now_bkk().strftime('%H:%M:%S')}] {tf_label(tf_name)}: ท่า3 Maru {mp['direction']} รอยืนยันแท่งถัดไป Entry={mp['entry']}")
            await tg(app, (
                    f"⏳ *ท่า3 DM SP {mp['direction']} Marubozu*\n"
                    f"{sig_e} [{tf_name}] [0] แท่งตัน\n"
                    f"📌 Entry:`{mp['entry']}` 🛑 SL:`{mp['sl']}` 🎯 TP:`{mp['tp']}`\n"
                    f"รอแท่งถัดไป..."
                ))

    # ── ท่า 2 Marubozu pending (แท่ง[0] ตัน) ──────────────────────
    if active_strategies.get(2, False) and r2.get("marubozu_pending"):
        mp  = r2["marubozu_pending"]
        key = f"{tf_name}_{mp['candle_time']}_s2maru"
        if key not in s3_maru_pending and last_traded_per_tf.get(tf_name) != last_candle_time:
            s3_maru_pending[key] = {
                "tf":          tf_name,
                "direction":   mp["direction"],
                "entry":       mp["entry"],
                "sl":          mp["sl"],
                "tp":          mp["tp"],
                "candle_time": mp["candle_time"],
            }
            sig_e = "🟢" if mp["direction"] == "BUY" else "🔴"
            print(f"📋 [{now_bkk().strftime('%H:%M:%S')}] {tf_label(tf_name)}: ท่า2 FVG Maru {mp['direction']} รอยืนยัน Entry={mp['entry']}")
            await tg(app, (
                    f"⏳ *ท่า2 FVG {mp['direction']} Marubozu*\n"
                    f"{sig_e} [{tf_name}] [0] แท่งตัน\n"
                    f"📌 Entry:`{mp['entry']}` 🛑 SL:`{mp['sl']}` 🎯 TP:`{mp['tp']}`\n"
                    f"รอแท่งถัดไป..."
                ))

    # ── เลือก result ที่ดีที่สุดสำหรับ execute order ──────────────
    # ── เลือก result ที่จะ execute — แต่ละท่าอิสระ ───────────────
    # ท่า 1, 3, 4 execute ตรง | ท่า 2 FVG_DETECTED รอ pending
    signal_results = []
    for sid, r in [(1, r1), (3, r3), (4, r4), (5, r5), (2, r2)]:
        if not active_strategies.get(sid, False):
            continue
        sig = r.get("signal", "WAIT")
        if sig not in ("WAIT", "FVG_DETECTED"):
            signal_results.append((sid, r))

    # ── S8 Swing Limit — ตั้งทั้ง 2 ฝั่งพร้อมกัน ────────────────
    if r8.get("signal") == "MULTI":
        for s8_order in r8["orders"]:
            signal_results.append((8, s8_order))
    # ── สรุปผลทุกท่าใน TF เดียวกัน เพื่อให้ Scan Summary เห็นครบทุก strategy ──
    parts = []
    has_entry_signal = False
    first_entry_part = None

    for sid, r in [(1, r1), (2, r2), (3, r3), (4, r4), (5, r5)]:
        if not active_strategies.get(sid, False):
            continue
        sig = r.get("signal", "WAIT")
        pat = r.get("pattern", "") or f"ท่าที่ {sid}"
        reas = r.get("reason", "")

        if sig == "FVG_DETECTED":
            fvg_d = r.get("fvg", {})
            pat = fvg_d.get("pattern", "") or "ท่าที่ 2 FVG"
            reas = f"รอราคาย้อน Entry:{fvg_d.get('entry', '')}"
            parsed = _parse_pattern(pat, "WAIT", reas)
        else:
            flat = " | ".join(line.strip() for line in reas.splitlines() if line.strip())
            parsed = _parse_pattern(
                pat, sig, flat,
                r.get("entry", 0), r.get("sl", 0), r.get("tp", 0)
            )
            if sig != "WAIT":
                has_entry_signal = True
                if first_entry_part is None:
                    first_entry_part = parsed.copy()
                extra = f"Entry:{r.get('entry', 0)} | SL:{r.get('sl', 0)} | TP:{r.get('tp', 0)}"
                parsed["description"] = f"{parsed.get('description', '')} | {extra}".strip(" |")
        parts.append((sid, parsed))

    if active_strategies.get(8, False):
        r8_reason = r8.get("reason", "")
        if r8.get("signal") == "WAIT":
            parts.append((8, _parse_pattern("ท่าที่ 8", "WAIT", r8_reason)))
        elif r8.get("signal") == "MULTI":
            s8_descs = []
            for o in r8["orders"]:
                has_entry_signal = True
                if first_entry_part is None:
                    first_entry_part = _parse_pattern(
                        o.get("pattern", "ท่าที่ 8"),
                        o.get("signal", "WAIT"),
                        o.get("reason", ""),
                        o.get("entry", 0), o.get("sl", 0), o.get("tp", 0)
                    )
                s8_descs.append(f"{o['signal']} Entry:{o['entry']} | SL:{o['sl']} | TP:{o['tp']}")
            parts.append((8, _parse_pattern("ท่าที่ 8 กินไส้ Swing", "WAIT", " | ".join(s8_descs))))

    if active_strategies.get(6, False):
        s6_tickets = [t for t, tf in position_tf.items()
                      if tf == tf_name and position_sid.get(t) in (2, 3)]
        if s6_tickets:
            s6_bits = []
            for t in s6_tickets:
                st = _s6_state.get(t)
                if st:
                    phase = st.get("phase", "?")
                    swing = st.get("swing_h", 0)
                    count = st.get("count", 0)
                    trails = st.get("trail_count", 0)
                    if phase == "wait":
                        s6_bits.append(f"#{t} phase=wait swing={swing:.2f}")
                    else:
                        s6_bits.append(f"#{t} phase=count {count}/5 swing={swing:.2f} trail={trails}")
                else:
                    es = _entry_state.get(t, "?")
                    s6_bits.append(f"#{t} รอ entry done (state={es})")
            s6_desc = " | ".join(s6_bits)
        else:
            s6_desc = "ไม่มี position ท่า 2/3"
        parts.append((6, _parse_pattern("", "WAIT", s6_desc)))

    if active_strategies.get(7, False):
        s6i_tickets = [t for t, tf in position_tf.items()
                       if tf == tf_name and t not in _s6_state
                       and _entry_state.get(t) == "done"]
        if s6i_tickets:
            s6i_bits = []
            for t in s6i_tickets:
                st = _s6i_state.get(t)
                if st:
                    phase = st.get("phase", "?")
                    swing = st.get("swing_h1", 0)
                    count = st.get("count", 0)
                    s1 = "S1" if st.get("s1_found") else "-"
                    s6i_bits.append(f"#{t} phase={phase} swing={swing:.2f} cnt={count} {s1}")
                else:
                    s6i_bits.append(f"#{t} รอ init")
            s6i_desc = " | ".join(s6i_bits)
        else:
            s6i_desc = "ไม่มี position"
        parts.append((7, _parse_pattern("", "WAIT", s6i_desc)))

    if parts:
        S_COLOR = {
            1: "\033[38;5;220m",
            2: "\033[38;5;117m",
            3: "\033[38;5;183m",
            4: "\033[38;5;120m",
            6: "\033[38;5;214m",
            7: "\033[38;5;209m",
            8: "\033[38;5;159m",
        }
        SID_LABEL = {7: "6i"}
        desc_lines = [
            f"{S_COLOR.get(sid,'')}{BOLD}[ท่า{SID_LABEL.get(sid, sid)}]{RESET} {p['description']}"
            for sid, p in parts if p.get("description")
        ]
        merged = (first_entry_part or parts[0][1]).copy()
        merged["status"] = "ENTRY" if has_entry_signal else "WAIT"
        merged["description"] = "\n".join(desc_lines)
        merged["desc_multiline"] = True
        if not has_entry_signal:
            merged["entry"] = 0
            merged["sl"] = 0
            merged["tp"] = 0
        _scan_results[tf_name] = merged
    else:
        _scan_results[tf_name] = _parse_pattern("", "WAIT", "ไม่มี Setup ที่ตรงเงื่อนไข")

    if not signal_results:
        return False

    # ── execute แต่ละท่าที่มีสัญญาณ — ทำงานอิสระ ────────────────
    any_success = False
    for sid, result in signal_results:
        signal     = result.get("signal", "WAIT")
        pattern    = result.get("pattern", "")
        raw_reason = result.get("reason", "")
        reason_flat = " | ".join(line.strip() for line in raw_reason.splitlines() if line.strip())
        if signal == "WAIT":
            continue
        # Pattern B pending
        if "Pattern B" in pattern:
            pb_key = f"{tf_name}_{last_candle_time}_{sid}"
            if pb_key not in pb_pending and last_traded_per_tf.get(tf_name) != last_candle_time:
                pb_pending[pb_key] = {
                    "tf": tf_name, "signal": signal,
                    "entry": result["entry"], "sl": result["sl"], "tp": result["tp"],
                    "pattern": pattern,
                    "candle_key": last_candle_time,
                }
                print(f"📋 [{now}] {tf_label(tf_name)}: บันทึก Pattern B ท่า{sid} Entry={result['entry']}")

        sig_e = "🟢" if signal == "BUY" else "🔴"
        entry = result["entry"]
        sl    = result["sl"]
        tp    = result["tp"]
        risk  = abs(entry - sl)
        rr    = round(abs(tp - entry) / risk, 2) if risk > 0 else 0
        candle_txt = ""
        _candles_list = result.get("candles", [])
        _n = len(_candles_list)
        labels = [f"[{_n - 1 - i}]" for i in range(_n)]
        for i, c in enumerate(_candles_list):
            o, h, l, cl = float(c["open"]), float(c["high"]), float(c["low"]), float(c["close"])
            clr = "🟢" if cl > o else "🔴"
            rate_idx = -(_n - i)
            candle_ts = int(rates[rate_idx]["time"]) if len(rates) >= (_n - i) else 0
            candle_txt += (
                f"{clr} แท่ง{labels[i]}: O:`{o:.2f}` H:`{h:.2f}` "
                f"L:`{l:.2f}` C:`{cl:.2f}` {_fmt_swing_dt(candle_ts)}\n"
            )
        tick          = mt5.symbol_info_tick(SYMBOL)
        current_price = (tick.ask if signal == "BUY" else tick.bid) if tick else 0
        # adjacent bar check per-sid (ท่า 8 ข้ามเช็กนี้ — ตั้งแท่งติดกันได้)
        if sid != 8:
            _sid_prev = config.last_traded_sid_tf.get(tf_name, {}).get(sid)
            if _sid_prev and (last_candle_time - _sid_prev) == tf_secs:
                _print_skip_once(tf_name, f"⏭️ [{now}] {tf_label(tf_name)} ท่า{sid}: แท่งติดกับ order ท่าเดียวกัน → ข้าม")
                continue
        cancel, cancel_reason = should_cancel_pending(rates, signal, entry)
        if cancel:
            print(f"🚫 [{now}] {tf_label(tf_name)} ท่า{sid}: {cancel_reason[:60]}")
            await tg(app, f"🚫 *[{tf_name}] ท่า{sid} ยกเลิก*\n{cancel_reason}")
            continue
        async with _get_lock():
            _pos_now = mt5.positions_get(symbol=SYMBOL)
            if _pos_now and len(_pos_now) >= MAX_ORDERS:
                print(f"⚠️ [{now}] {tf_label(tf_name)}: Order เต็ม ({len(_pos_now)}/{MAX_ORDERS})")
                continue

            # ── Shared TP: ถ้ามี Order ทิศเดียวกันอยู่แล้ว ──────────
            # BUY → TP = Swing High ย่อย ร่วมกัน
            # SELL → TP = Swing Low ย่อย ร่วมกัน
            existing_tp = get_existing_tp(signal, entry, tf_name)
            if existing_tp > 0:
                print(f"📌 [{now}] Shared TP {signal} [{tf_name}]: {existing_tp} (ท่า{sid} เดิม: {tp})")
                tp = existing_tp
            order_sl = 0.0 if (sid == 8 or config.DELAY_SL_MODE != "off") else sl
            order = open_order(signal, get_volume(), order_sl, tp, entry_price=entry, tf=tf_name, sid=sid, pattern=pattern)
        if order["success"]:
            last_traded_per_tf[tf_name] = last_candle_time
            config.last_traded_sid_tf.setdefault(tf_name, {})[sid] = last_candle_time
            any_success = True
            ot_name = order.get("order_type", "LIMIT")
            if order.get("ticket"):
                _pend_info = {
                    "tf":              tf_name,
                    "gap_bot":         round(entry - abs(entry - sl), 2),
                    "gap_top":         round(entry + abs(entry - sl), 2),
                    "detect_bar_time": last_candle_time,
                    "signal":          signal,
                    "sid":             sid,
                    "pattern":         pattern,
                }
                if result.get("cancel_bars"):
                    _pend_info["cancel_bars"] = result["cancel_bars"]
                if result.get("swing_price"):
                    _pend_info["swing_price"] = result["swing_price"]
                    _pend_info["swing_bar_time"] = result.get("swing_bar_time", 0)
                if sid == 8 or config.DELAY_SL_MODE != "off":
                    _pend_info["intended_sl"] = sl
                    _pend_info["sl_armed"] = False
                    _s8_fill_sl[order["ticket"]] = sl
                pending_order_tf[order["ticket"]] = _pend_info
                position_tf[order["ticket"]] = tf_name
                position_sid[order["ticket"]] = sid
                position_pattern[order["ticket"]] = pattern
                log_event(
                    "ORDER_CREATED",
                    pattern,
                    tf=tf_name,
                    sid=sid,
                    signal=signal,
                    entry=entry,
                    sl=sl,
                    tp=tp,
                    ticket=order["ticket"],
                    order_type=ot_name,
                )
            save_runtime_state()
            swing_h_text = _fmt_swing_dt(_sh_info["time"]) if _sh_info else ""
            swing_l_text = _fmt_swing_dt(_sl_info["time"]) if _sl_info else ""
            await app.bot.send_message(
                chat_id=MY_USER_ID,
                text=_order_msg(
                    sig_e,
                    pattern,
                    tf_name,
                    sid,
                    candle_txt,
                    result.get("swing_high", 0), result.get("swing_low", 0),
                    raw_reason, current_price, entry, sl, tp, rr,
                    order.get("ticket"),
                    swing_h_text=swing_h_text,
                    swing_l_text=swing_l_text,
                ),
                parse_mode="Markdown"
            )
        elif order.get("skipped"):
            err_flat = order["error"].replace("\n", " | ")
            log_event(
                "ORDER_SKIPPED",
                err_flat,
                tf=tf_name,
                sid=sid,
                signal=signal,
                entry=entry,
                sl=sl,
                tp=tp,
            )
            print(f"⏭️ [{now}] {tf_label(tf_name)} ท่า{sid}: Entry {signal} ผ่านไปแล้ว | Entry:{entry} | {err_flat[:80]}")
            await tg(app, f"⏭️ *[{tf_name}] ท่า{sid} ราคาผ่าน Entry ไปแล้ว*\n`{order['error']}`")
        else:
            err = order.get('error','')
            if '10027' in str(err):
                err = "⚠️ AutoTrading ปิดอยู่ใน MT5 กด Ctrl+E หรือกดปุ่ม AutoTrading ให้เป็นสีเขียว"
            log_event(
                "ORDER_FAILED",
                err,
                tf=tf_name,
                sid=sid,
                signal=signal,
                entry=entry,
                sl=sl,
                tp=tp,
            )
            await tg(app, f"❌ [{tf_name}] ท่า{sid} Limit ไม่สำเร็จ: `{err}`")

    return any_success
