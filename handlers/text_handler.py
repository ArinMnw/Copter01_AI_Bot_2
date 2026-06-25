from config import *
import config
from handlers.keyboard import main_keyboard, show_main_settings_menu, show_strategy_menu

from handlers.btn_price import handle_btn_price
from handlers.btn_balance import handle_btn_balance
from handlers.btn_buy import handle_btn_buy
from handlers.btn_sell import handle_btn_sell
from handlers.btn_order import handle_btn_order
from handlers.btn_close_all import handle_btn_close_all
from handlers.btn_scan_now import handle_btn_scan_now
from handlers.btn_auto import handle_btn_auto
from handlers.btn_pending import handle_btn_pending
from handlers.btn_cancel_pending import handle_btn_cancel_pending
from handlers.btn_settings import handle_btn_settings
from handlers.btn_tf import handle_btn_tf
from handlers.btn_profit import handle_btn_profit
from handlers.btn_tg_status import handle_btn_tg_status
from mt5_utils import connect_mt5
from handlers.keyboard import main_keyboard
from datetime import datetime, timedelta


# ── Markdown escape helper ─────────────────────────────────────
# Telegram Markdown มีตัวอักษรพิเศษที่ทำให้ parser พังถ้าไม่ escape:
#   ` * _ [ ] (และ \ เอง)
# ใช้ทั้ง user input และค่าจาก MT5 ที่อาจมี backtick ใน comment
def _md_escape(s) -> str:
    if s is None:
        return ""
    text = str(s)
    # escape \ ก่อน (เพื่อไม่ให้กระทบ escape ตัวอื่น)
    text = text.replace("\\", "\\\\")
    for ch in ("`", "*", "_", "[", "]"):
        text = text.replace(ch, f"\\{ch}")
    return text


# ── Safe reply: ลอง Markdown ก่อน ถ้า parse fail → fallback plain text ──
async def _safe_reply_md(message, text: str, **kwargs):
    """
    พยายามตอบด้วย parse_mode='Markdown' ถ้า BadRequest (entity error)
    → ลอง plain text เป็น fallback
    """
    try:
        return await message.reply_text(text, parse_mode="Markdown", **kwargs)
    except Exception as e:
        emsg = str(e).lower()
        if "can't parse entities" in emsg or "parse entities" in emsg:
            # Markdown พัง — strip markers แล้วส่ง plain text
            # หมายเหตุ: ไม่ลบ '_' เพราะมันอยู่ใน field names (base_volume, rsi2_state ฯลฯ)
            try:
                import re as _re
                plain = _re.sub(r'`([^`\n]*)`?', r'\1', text)
                plain = plain.replace('`', '').replace('*', '')
                return await message.reply_text(plain, **kwargs)
            except Exception:
                pass
        raise


# Route map: ข้อความปุ่ม → handler function
BUTTON_ROUTES = {
    "📈 ราคาทอง":        handle_btn_price,
    "💰 ยอดเงิน":         handle_btn_balance,
    "🟢 BUY":             handle_btn_buy,
    "🔴 SELL":            handle_btn_sell,
    "📊 Order":           handle_btn_order,
    "❌ ปิดทั้งหมด":      handle_btn_close_all,
    "🤖 สแกนตอนนี้":     handle_btn_scan_now,
    "⚙️ สถานะ Auto":      handle_btn_auto,
    "⏳ Pending Orders":  handle_btn_pending,
    "🗑️ ยกเลิก Pending": handle_btn_cancel_pending,
    "⚙️ ตั้งค่า":         handle_btn_settings,
    "🕐 เลือก Timeframe": handle_btn_tf,
    "📊 สรุปกำไร":        handle_btn_profit,
    "🚦 TG Status":       handle_btn_tg_status,
}


async def handle_ohlc_lookup(update, context, tf_str: str, date_str: str, time_str: str, symbol_str: str = None):
    """ฟังก์ชันค้นหาและแสดงผล OHLC ของแท่งราคาตามเวลา BKK ที่ระบุ"""
    from datetime import datetime, timezone, timedelta
    import mt5_worker as mt5
    import config

    tf_str = tf_str.upper()
    _TF_MT5 = {
        "M1": 1, "M5": 5, "M15": 15, "M30": 30,
        "H1": 16385, "H4": 16388, "H12": 16396, "D1": 16408,
    }
    _TF_SECS = {
        "M1": 60, "M5": 300, "M15": 900, "M30": 1800,
        "H1": 3600, "H4": 14400, "H12": 43200, "D1": 86400,
    }

    if tf_str not in _TF_MT5:
        await update.effective_message.reply_text(
            f"❌ ไม่พบ Timeframe `{tf_str}` ค่ะพี่\n"
            f"รองรับเฉพาะ: {', '.join(_TF_MT5.keys())}",
            reply_markup=main_keyboard()
        )
        return

    try:
        dt_naive = datetime.strptime(f"{date_str} {time_str}", "%d-%m-%Y %H:%M")
    except ValueError:
        await update.effective_message.reply_text(
            "❌ รูปแบบ วัน-เดือน-ปี หรือ เวลา ไม่ถูกต้องค่ะพี่\n"
            "ตัวอย่างที่ถูกต้อง: `M5 05-06-2026 11:15` (วัน-เดือน-ปี ค.ศ.)",
            reply_markup=main_keyboard()
        )
        return

    BKK = timezone(timedelta(hours=config.TZ_OFFSET))
    dt_bkk = dt_naive.replace(tzinfo=BKK)

    # คำนวณหา timestamp ใน MT5 server time
    ts_query = int(dt_bkk.timestamp()) + config.MT5_SERVER_TZ * 3600

    if not connect_mt5():
        await update.effective_message.reply_text("❌ MT5 ไม่ได้เชื่อมต่อค่ะพี่", reply_markup=main_keyboard())
        return

    # Resolve symbol
    symbol = symbol_str.strip() if symbol_str else config.SYMBOL
    sym_info = mt5.symbol_info(symbol)
    if sym_info is None:
        # Try appending .iux
        if not symbol.endswith(".iux"):
            alt_sym = f"{symbol}.iux"
            if mt5.symbol_info(alt_sym):
                symbol = alt_sym
                sym_info = mt5.symbol_info(symbol)

    if sym_info is None:
        await update.effective_message.reply_text(
            f"❌ ไม่พบ Symbol `{symbol}` ในระบบ MT5 ค่ะพี่\n"
            f"กรุณาตรวจสอบชื่อ Symbol อีกครั้งนะคะ",
            reply_markup=main_keyboard()
        )
        return

    tf_const = _TF_MT5[tf_str]
    tf_secs = _TF_SECS[tf_str]
    
    # ดึงข้อมูลราคาในช่วงเวลานั้น
    start_time = ts_query - tf_secs
    end_time = ts_query + tf_secs
    
    rates = mt5.copy_rates_range(symbol, tf_const, start_time, end_time)
    
    if rates is None or len(rates) == 0:
        # ลองดึงจากตำแหน่งล่าสุดมาค้นหา (เผื่อเวลาพึ่งผ่านมาไม่นาน)
        rates = mt5.copy_rates_from_pos(symbol, tf_const, 0, 1000)

    matching_bar = None
    if rates is not None and len(rates) > 0:
        for r in rates:
            if r['time'] <= ts_query < r['time'] + tf_secs:
                matching_bar = r
                break

    if matching_bar is None:
        await update.effective_message.reply_text(
            f"❌ ไม่พบข้อมูลแท่งราคา `{tf_str}` ที่เวลา BKK `{date_str} {time_str}` ค่ะพี่",
            reply_markup=main_keyboard()
        )
        return

    # แปลงเวลาของแท่งราคากลับเป็น BKK สำหรับแสดงผล
    bar_bkk = config.mt5_ts_to_bkk(matching_bar['time'])
    bar_bkk_str = bar_bkk.strftime("%d-%m-%Y %H:%M") if bar_bkk else "-"
    
    color = "🟢" if matching_bar['close'] >= matching_bar['open'] else "🔴"
    
    requested_str = f"{date_str} {time_str}"
    time_info = f"🕐 เวลา BKK: `{bar_bkk_str}`"
    if bar_bkk_str != requested_str:
        time_info = (
            f"🕐 เวลา BKK ที่ระบุ: `{requested_str}`\n"
            f"🕯️ เวลาแท่งราคา (BKK): `{bar_bkk_str}`"
        )

    o = float(matching_bar['open'])
    h = float(matching_bar['high'])
    l = float(matching_bar['low'])
    c = float(matching_bar['close'])
    rng = h - l
    body = abs(c - o)
    body_pct = (body / rng * 100) if rng > 0 else 0.0

    msg = (
        f"📊 *OHLC Lookup [{tf_str}]*\n"
        f"🪙 Symbol: `{symbol}`\n"
        f"{time_info}\n\n"
        f"{color} Open: `{o:.2f}`\n"
        f"📈 High: `{h:.2f}`\n"
        f"📉 Low: `{l:.2f}`\n"
        f"🔴 Close: `{c:.2f}`\n"
        f"📊 Body: `{body_pct:.1f}%` (Range: `{rng:.2f}`)\n"
        f"📦 Volume: `{matching_bar['tick_volume']}`"
    )

    await update.effective_message.reply_text(
        msg,
        parse_mode="Markdown",
        reply_markup=main_keyboard()
    )


def _batch_find_detect(tf_str: str, windows: "list[tuple[int,int]]") -> "dict[int,str|None]":
    """Batch search log ครั้งเดียวสำหรับหลาย confirm windows
    windows: [(confirm_ts_mt5, deadline_ts_mt5), ...]
    returns: {confirm_ts_mt5: 'YYYY-MM-DD HH:MM:SS' or None}
    """
    import os, re
    from datetime import datetime, timedelta
    import config as _cfg

    result    = {cn: None for cn, _ in windows}
    remaining = set(cn for cn, _ in windows)
    if not remaining:
        return result

    def _to_naive(ts_mt5: int) -> datetime:
        bkk = _cfg.mt5_ts_to_bkk(ts_mt5)
        return bkk.replace(tzinfo=None) if bkk else datetime.utcfromtimestamp(ts_mt5)

    win_naive    = {cn: (_to_naive(cn), _to_naive(dl)) for cn, dl in windows}
    global_start = min(v[0] for v in win_naive.values())
    global_end   = max(v[1] for v in win_naive.values())

    log_dir     = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "logs"))
    old_log_dir = os.path.join(log_dir, "old_logs")
    log_paths: list[str] = []
    for d in [old_log_dir, log_dir]:
        if not os.path.isdir(d):
            continue
        for fn in sorted(os.listdir(d)):
            if fn.startswith("bot") and ".log" in fn:
                p = os.path.join(d, fn)
                if p not in log_paths:
                    log_paths.append(p)

    tf_pat = re.compile(rf'\b{re.escape(tf_str)}\b')
    ts_pat = re.compile(r'^\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\]')

    for path in log_paths:
        if not remaining:
            break
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                for line in f:
                    if not remaining:
                        break
                    m = ts_pat.match(line)
                    if not m:
                        continue
                    line_ts = datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S")
                    if line_ts > global_end:
                        break
                    if line_ts < global_start:
                        continue
                    if "SCAN" not in line or not tf_pat.search(line):
                        continue
                    for cn_ts in list(remaining):
                        cn_naive, dl_naive = win_naive[cn_ts]
                        if cn_naive <= line_ts <= dl_naive:
                            result[cn_ts] = m.group(1)
                            remaining.discard(cn_ts)
                            break
        except Exception:
            continue

    return result


async def handle_trend_lookup(update, context, tf_str: str, date_str: str, time_str: str):
    """ค้นหา HHLL trend ณ เวลาที่ระบุ — แสดง 8 swing points ล่าสุดพร้อมราคา bar time confirm detect"""
    from datetime import datetime, timezone, timedelta
    import mt5_worker as mt5
    import config

    tf_str = tf_str.upper()
    _TF_MT5 = {
        "M1": 1, "M5": 5, "M15": 15, "M30": 30,
        "H1": 16385, "H4": 16388, "H12": 16396, "D1": 16408,
    }
    _TF_SECS = {
        "M1": 60, "M5": 300, "M15": 900, "M30": 1800,
        "H1": 3600, "H4": 14400, "H12": 43200, "D1": 86400,
    }

    if tf_str not in _TF_MT5:
        await update.effective_message.reply_text(
            f"❌ ไม่พบ Timeframe `{tf_str}` ค่ะพี่\nรองรับ: {', '.join(_TF_MT5.keys())}",
            parse_mode="Markdown", reply_markup=main_keyboard()
        )
        return

    try:
        dt_naive = datetime.strptime(f"{date_str} {time_str}", "%d-%m-%Y %H:%M")
    except ValueError:
        await update.effective_message.reply_text(
            "❌ รูปแบบไม่ถูกต้องค่ะพี่\nตัวอย่าง: `trend M5 05-06-2026 11:15`",
            parse_mode="Markdown", reply_markup=main_keyboard()
        )
        return

    BKK      = timezone(timedelta(hours=config.TZ_OFFSET))
    dt_bkk   = dt_naive.replace(tzinfo=BKK)
    ts_query = int(dt_bkk.timestamp()) + config.MT5_SERVER_TZ * 3600

    if not connect_mt5():
        await update.effective_message.reply_text("❌ MT5 ไม่ได้เชื่อมต่อค่ะพี่", reply_markup=main_keyboard())
        return

    tf_const = _TF_MT5[tf_str]
    tf_secs  = _TF_SECS[tf_str]

    try:
        from hhll_swing import _build_zz, _classify_pt
        hhll_lb    = int(getattr(config, "HHLL_LOOKBACK", 500))
        hhll_left  = int(getattr(config, "HHLL_LEFT",    5))
        hhll_right = int(getattr(config, "HHLL_RIGHT",   5))
    except Exception as e:
        await update.effective_message.reply_text(f"❌ import hhll_swing ไม่ได้: {e}", reply_markup=main_keyboard())
        return

    need      = hhll_lb + hhll_left + hhll_right + 10
    rates_raw = mt5.copy_rates_range(config.SYMBOL, tf_const,
                                     ts_query - need * tf_secs, ts_query + tf_secs)

    if rates_raw is None or len(rates_raw) == 0:
        await update.effective_message.reply_text(
            f"❌ ไม่พบข้อมูลราคา `{tf_str}` ในช่วงเวลาที่ระบุค่ะพี่",
            parse_mode="Markdown", reply_markup=main_keyboard()
        )
        return

    rates = [r for r in rates_raw if int(r["time"]) <= ts_query]
    if len(rates) < hhll_left + hhll_right + 10:
        await update.effective_message.reply_text(
            f"❌ ข้อมูลไม่พอสำหรับ HHLL (มี {len(rates)} แท่ง)", reply_markup=main_keyboard()
        )
        return

    zz = _build_zz(rates, hhll_left, hhll_right)
    if len(zz) < 5:
        await update.effective_message.reply_text("❌ Zigzag ไม่พอสำหรับ classify ค่ะพี่", reply_markup=main_keyboard())
        return

    # เก็บ list ทั้งหมด (oldest→newest) — ไม่ dedup ต่อ label
    zz_pts: list[tuple[str, float, int]] = []
    for k in range(len(zz)):
        lbl = _classify_pt(zz, k)
        if lbl:
            zz_pts.append((lbl, float(zz[k]["price"]), int(zz[k]["time"])))

    pts_new  = list(reversed(zz_pts))   # newest → oldest
    h_labels = [l for l, _, _ in pts_new if l in ("HH", "LH")]
    l_labels = [l for l, _, _ in pts_new if l in ("HL", "LL")]

    last_label, last_price_v, last_time_v = pts_new[0] if pts_new else ("—", 0, 0)

    if not h_labels or not l_labels:
        trend_str = "❓ UNKNOWN"
    else:
        h0, l0 = h_labels[0], l_labels[0]
        h1 = h_labels[1] if len(h_labels) > 1 else None
        l1 = l_labels[1] if len(l_labels) > 1 else None
        if h0 == "HH" and l0 == "HL":
            trend_str = f"🟢 BULL ({'strong' if h1 == 'HH' and l1 == 'HL' else 'weak'})"
        elif h0 == "LH" and l0 == "LL":
            trend_str = f"🔴 BEAR ({'strong' if h1 == 'LH' and l1 == 'LL' else 'weak'})"
        else:
            trend_str = f"⚪ SIDEWAY (h0={h0} l0={l0})"

    def _fmt_ts(ts_mt5: int) -> str:
        bkk = config.mt5_ts_to_bkk(ts_mt5)
        return bkk.strftime("%d-%m %H:%M") if bkk else "?"

    # SIDEWAY แสดงแค่ 4 จุด (h0 l0 h1 l1), BULL/BEAR แสดง 8 จุด
    n_display   = 4 if trend_str.startswith("⚪") else 8
    display_pts = pts_new[:n_display]

    # Batch log search ครั้งเดียว
    windows = [(bar_ts + hhll_right * tf_secs,
                bar_ts + hhll_right * tf_secs + 2 * 3600)
               for _, _, bar_ts in display_pts]
    detect_map = _batch_find_detect(tf_str, windows)

    struct_display = " ▸ ".join(l for l, _, _ in pts_new[:8]) if pts_new else "—"
    last_bar_str   = f" `{last_price_v:.2f}`  แท่ง `{_fmt_ts(last_time_v)}`" if last_time_v else ""

    swing_lines = []
    for lbl, price, bar_ts in display_pts:
        confirm_ts  = bar_ts + hhll_right * tf_secs
        detect      = detect_map.get(confirm_ts)
        detect_line = f"`{detect}`" if detect else f"`{_fmt_ts(confirm_ts)}` *(est)*"
        swing_lines.append(
            f"`{lbl}` `{price:.2f}`\n"
            f"  แท่ง: `{_fmt_ts(bar_ts)}` | confirm: `{_fmt_ts(confirm_ts)}` | เจอ: {detect_line}"
        )

    lines = [
        f"📊 *HHLL Trend Lookup [{tf_str}]*",
        f"🕐 ณ BKK: `{date_str} {time_str}`",
        "",
        f"📈 Trend: {trend_str}",
        f"🏷 Last label: `{last_label}`{last_bar_str}",
        f"🔗 Structure: `{struct_display}`",
        "",
        "*Swing Points (newest → oldest):*",
        *swing_lines,
    ]

    await _safe_reply_md(update.effective_message, "\n".join(lines), reply_markup=main_keyboard())


async def handle_buttons(update, context):
    """Route ข้อความปุ่มไปยัง handler ที่ถูกต้อง"""
    global auto_active
    message = update.effective_message
    if message is None or not getattr(message, "text", None):
        return

    if not auth(update):
        await alert_intruder(update)
        return

    text = message.text

    # ── ตรวจ waiting_lot_input ก่อน ──────────────────────────────
    # ── ตรวจ waiting_lot_input ก่อน ──────────────────────────────
    waiting = context.user_data.get("waiting_lot_input")
    if waiting:
        await _handle_lot_input(update, context, text, waiting)
        return

    # ── ตรวจ awaiting_input (S20) ──────────────────────────────
    awaiting = context.user_data.get("awaiting_input")
    if awaiting:
        await _handle_custom_input(update, context, text, awaiting)
        return

    stripped = text.strip()
    if stripped.isdigit():
        await _handle_ticket_lookup(update, int(stripped))
        return

    import re

    # ── trend lookup: "trend M5 05-06-2026 11:15" ────────────────
    trend_match = re.match(
        r'^[Tt]rend\s+(M1|M5|M15|M30|H1|H4|D1|m1|m5|m15|m30|h1|h4|d1)\s+(\d{2}-\d{2}-\d{4})\s+(\d{2}:\d{2})$',
        stripped
    )
    if trend_match:
        tf_str, date_str, time_str = trend_match.groups()
        await handle_trend_lookup(update, context, tf_str, date_str, time_str)
        return

    ohlc_match = re.match(
        r'^(?:([A-Za-z0-9._#-]+)\s+)?(M1|M5|M15|M30|H1|H4|D1|m1|m5|m15|m30|h1|h4|d1)\s+(\d{2}-\d{2}-\d{4})\s+(\d{2}:\d{2})(?:\s+([A-Za-z0-9._#-]+))?$',
        stripped
    )
    if ohlc_match:
        sym_pre, tf_str, date_str, time_str, sym_post = ohlc_match.groups()
        symbol_str = sym_pre or sym_post
        await handle_ohlc_lookup(update, context, tf_str, date_str, time_str, symbol_str)
        return

    handler = BUTTON_ROUTES.get(text)
    if handler:
        await handler(update, context)
    else:
        await update.effective_message.reply_text(
            f"❓ ไม่รู้จักคำสั่ง: {text}",
            reply_markup=main_keyboard()
        )


async def _handle_custom_input(update, context, text, awaiting):
    """รับค่าตัวเลขจาก user สำหรับ settings ต่างๆ"""
    context.user_data.pop("awaiting_input", None)
    
    try:
        val = float(text.strip())
    except ValueError:
        await update.effective_message.reply_text(
            f"❌ ค่าไม่ถูกต้อง: `{text}`\nกรุณากรอกเป็นตัวเลขเท่านั้น",
            parse_mode="Markdown", reply_markup=main_keyboard()
        )
        return

    import config
    if awaiting == "s20_entry_buffer":
        config.S20_ENTRY_BUFFER = val
        config.save_runtime_state()
        await update.effective_message.reply_text(
            f"✅ ตั้งค่า **S20 Entry Buffer** เป็น {val} จุดเรียบร้อย",
            parse_mode="Markdown"
        )
        from handlers.keyboard import show_s20_settings_menu
        await show_s20_settings_menu(update, is_query=False)
    elif awaiting == "s20_sl_2l2h":
        config.S20_SL_2L2H = val
        config.save_runtime_state()
        await update.effective_message.reply_text(
            f"✅ ตั้งค่า **S20 SL 2L/2H** เป็น {val} จุดเรียบร้อย",
            parse_mode="Markdown"
        )
        from handlers.keyboard import show_s20_settings_menu
        await show_s20_settings_menu(update, is_query=False)

async def _handle_lot_input(update, context, text, waiting):
    """รับ lot size จาก user input"""
    context.user_data.pop("waiting_lot_input", None)

    try:
        lot = round(float(text.strip()), 2)
        if lot < 0.01 or lot > 10.0:
            raise ValueError("out of range")
    except (ValueError, TypeError):
        await update.effective_message.reply_text(
            f"❌ ค่าไม่ถูกต้อง: `{text}`\n"
            "กรุณากรอกตัวเลข เช่น `0.03` (ขั้นต่ำ 0.01 สูงสุด 10.0)",
            parse_mode="Markdown",
            reply_markup=main_keyboard()
        )
        return

    if waiting == "auto":
        # ตั้งค่า lot สำหรับ auto trade
        import config as cfg_mod
        cfg_mod.AUTO_VOLUME = lot
        config.AUTO_VOLUME  = lot
        save_runtime_state()
        await update.effective_message.reply_text(
            f"✅ *ตั้งค่า Lot Auto สำเร็จ*\n📦 Lot: `{lot}`",
            parse_mode="Markdown",
            reply_markup=main_keyboard()
        )

    elif waiting.startswith("manual_"):
        # manual order BUY/SELL ด้วย lot ที่กรอก
        # format: manual_buy_4600.5 หรือ manual_sell_4600.5
        parts   = waiting.split("_")
        direction = parts[1]
        price_str = parts[2]

        if not connect_mt5():
            await update.effective_message.reply_text("❌ MT5 ไม่ได้เชื่อมต่อ", reply_markup=main_keyboard())
            return

        try:
            price = float(price_str)
        except ValueError:
            tick  = mt5.symbol_info_tick(SYMBOL)
            price = (tick.ask if direction == "buy" else tick.bid) if tick else 0

        ot  = mt5.ORDER_TYPE_BUY if direction == "buy" else mt5.ORDER_TYPE_SELL
        sl  = round(price - 15, 2) if direction == "buy" else round(price + 15, 2)
        tp  = round(price + 30, 2) if direction == "buy" else round(price - 30, 2)
        e   = "🟢" if direction == "buy" else "🔴"

        r = mt5.order_send({
            "action": mt5.TRADE_ACTION_DEAL, "symbol": SYMBOL,
            "volume": lot, "type": ot, "price": price,
            "sl": sl, "tp": tp, "deviation": 20, "magic": 234001,
            "comment": "Manual-Custom", "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_FOK,
        })
        if r and r.retcode == mt5.TRADE_RETCODE_DONE:
            await update.effective_message.reply_text(
                f"✅ *เปิดสำเร็จ!* {e} {direction.upper()} `{lot}` lot @ `{price}`\n"
                f"🛑 `{sl}` 🎯 `{tp}` 🔖 `{r.order}`",
                parse_mode="Markdown",
                reply_markup=main_keyboard()
            )
        else:
            err = r.retcode if r else "no result"
            await update.effective_message.reply_text(
                f"❌ ไม่สำเร็จ: {err}",
                reply_markup=main_keyboard()
            )


def _fmt_dt(ts):
    try:
        return fmt_mt5_bkk_ts_hist(ts, "%d/%m %H:%M:%S")
    except Exception:
        return "-"


def _deal_type_name(deal_type):
    mapping = {
        mt5.DEAL_TYPE_BUY: "BUY",
        mt5.DEAL_TYPE_SELL: "SELL",
        mt5.DEAL_TYPE_BALANCE: "BAL",
        mt5.DEAL_TYPE_CREDIT: "CREDIT",
        mt5.DEAL_TYPE_CHARGE: "CHARGE",
        mt5.DEAL_TYPE_CORRECTION: "CORR",
        mt5.DEAL_TYPE_BONUS: "BONUS",
        mt5.DEAL_TYPE_COMMISSION: "COMM",
        mt5.DEAL_TYPE_COMMISSION_DAILY: "COMM_DAY",
        mt5.DEAL_TYPE_COMMISSION_MONTHLY: "COMM_MON",
        mt5.DEAL_TYPE_COMMISSION_AGENT_DAILY: "COMM_AG_DAY",
        mt5.DEAL_TYPE_COMMISSION_AGENT_MONTHLY: "COMM_AG_MON",
        mt5.DEAL_TYPE_INTEREST: "INTEREST",
        mt5.DEAL_TYPE_BUY_CANCELED: "BUY_CANCEL",
        mt5.DEAL_TYPE_SELL_CANCELED: "SELL_CANCEL",
    }
    return mapping.get(deal_type, str(deal_type))


def _deal_entry_name(entry_type):
    mapping = {
        mt5.DEAL_ENTRY_IN: "IN",
        mt5.DEAL_ENTRY_OUT: "OUT",
        mt5.DEAL_ENTRY_INOUT: "INOUT",
        mt5.DEAL_ENTRY_OUT_BY: "OUT_BY",
    }
    return mapping.get(entry_type, str(entry_type))


def _order_type_name(order_type):
    mapping = {
        mt5.ORDER_TYPE_BUY: "BUY",
        mt5.ORDER_TYPE_SELL: "SELL",
        mt5.ORDER_TYPE_BUY_LIMIT: "BUY_LIMIT",
        mt5.ORDER_TYPE_SELL_LIMIT: "SELL_LIMIT",
        mt5.ORDER_TYPE_BUY_STOP: "BUY_STOP",
        mt5.ORDER_TYPE_SELL_STOP: "SELL_STOP",
        mt5.ORDER_TYPE_BUY_STOP_LIMIT: "BUY_STOP_LIMIT",
        mt5.ORDER_TYPE_SELL_STOP_LIMIT: "SELL_STOP_LIMIT",
        mt5.ORDER_TYPE_CLOSE_BY: "CLOSE_BY",
    }
    return mapping.get(order_type, str(order_type))


async def _handle_ticket_lookup(update, ticket: int):
    """พิมพ์เลข ticket ใน Telegram เพื่อดู log/order history ของใบนั้น
    แสดงในรูปแบบเดียวกับ handle_btn_order: header + signal TG + log events + deal history
    """
    if not connect_mt5():
        await update.effective_message.reply_text("❌ MT5 ไม่ได้เชื่อมต่อ", reply_markup=main_keyboard())
        return

    import trailing
    from handlers.btn_order import (
        _grep_ticket_lines, _read_order_meta, _read_signal_tg,
        _read_ticket_logs, _format_ticket_logs, _fetch_candle_block,
    )

    now = datetime.now()
    dt_from = now - timedelta(days=30)
    dt_to   = now + timedelta(days=1)

    positions   = mt5.positions_get() or []
    orders_now  = mt5.orders_get() or []
    deals       = mt5.history_deals_get(dt_from, dt_to) or []
    orders_hist = mt5.history_orders_get(dt_from, dt_to) or []

    pos       = next((p for p in positions   if int(p.ticket) == ticket), None)
    cur_order = next((o for o in orders_now  if int(o.ticket) == ticket), None)
    linked_orders = [
        o for o in orders_hist
        if int(getattr(o, "ticket",      0)) == ticket
        or int(getattr(o, "position_id", 0)) == ticket
    ]
    linked_deals = [
        d for d in deals
        if int(getattr(d, "position_id", 0)) == ticket
        or int(getattr(d, "order",       0)) == ticket
        or int(getattr(d, "ticket",      0)) == ticket
    ]

    if not pos and not cur_order and not linked_orders and not linked_deals:
        await _safe_reply_md(
            update.effective_message,
            f"🔎 ไม่พบข้อมูล ticket `{ticket}` ใน current/history 30 วัน",
            reply_markup=main_keyboard()
        )
        return

    # ── grep เฉพาะบรรทัดที่มี ticket (เร็วกว่า load ทุกบรรทัดมาก) ──
    all_lines = _grep_ticket_lines(ticket)

    # ── pattern / sid / tf ─────────────────────────────────────
    sid     = str(trailing.position_sid.get(ticket, "")
                  or trailing.pending_order_tf.get(ticket, {}).get("sid", ""))
    pattern = str(trailing.position_pattern.get(ticket, ""))
    tf      = str(trailing.position_tf.get(ticket, "")
                  or trailing.pending_order_tf.get(ticket, {}).get("tf", ""))

    if not pattern or not sid or not tf:
        _pat, _sid, _tf = _read_order_meta(ticket, all_lines)
        if not pattern: pattern = _pat
        if not sid:     sid     = _sid
        if not tf:      tf      = _tf

    # ── Header ─────────────────────────────────────────────────
    if pos:
        # Open position
        t   = "BUY" if pos.type == mt5.ORDER_TYPE_BUY else "SELL"
        e   = "🟢" if t == "BUY" else "🔴"
        pe  = "🟢" if pos.profit >= 0 else "🔴"
        header = (
            f"{e} *{t}* {pos.volume}lot @ `{pos.price_open}`\n"
            f"🛑`{pos.sl}` 🎯`{pos.tp}` | {pe}`{pos.profit:.2f}` USD\n"
        )
    elif cur_order:
        # Pending order
        t  = _order_type_name(cur_order.type)
        e  = "🟢" if "BUY" in t else "🔴"
        vol = getattr(cur_order, "volume_current", cur_order.volume_initial)
        header = (
            f"{e} *{t}* {vol}lot @ `{cur_order.price_open}`\n"
            f"🛑`{cur_order.sl}` 🎯`{cur_order.tp}` | ⏳ Pending\n"
        )
    else:
        # ปิดไปแล้ว — ดึงจาก deal history
        in_deals  = [d for d in linked_deals if d.entry == mt5.DEAL_ENTRY_IN]
        out_deals = [d for d in linked_deals if d.entry == mt5.DEAL_ENTRY_OUT]
        if in_deals:
            in_d   = in_deals[0]
            t      = "BUY" if in_d.type == mt5.DEAL_TYPE_BUY else "SELL"
            e      = "🟢" if t == "BUY" else "🔴"
            total_profit = sum(float(getattr(d, "profit", 0)) for d in out_deals)
            pe     = "🟢" if total_profit >= 0 else "🔴"
            cl_str = f"→ ปิด `{out_deals[-1].price}`" if out_deals else "→ ยังไม่ปิด"
            header = (
                f"{e} *{t}* {in_d.volume}lot @ `{in_d.price}` {cl_str}\n"
                f"{pe} P/L: `{total_profit:.2f}` USD\n"
            )
        else:
            header = f"🔎 *Ticket: {ticket}*\n"

    header += (
        f"🔖 `#{ticket}`"
        + (f" | S{sid}" if sid else "")
        + (f" | {tf}"   if tf  else "")
        + "\n"
        + (f"📝 {pattern}\n" if pattern else "")
        + "━━━━━━━━━━━━━━━━━\n"
    )

    # ── Signal TG block ─────────────────────────────────────────
    signal_msg = _read_signal_tg(ticket, all_lines)
    
    # ข้ามข้อความที่เป็นแจ้งเตือนสถานะ เพื่อให้ fallback ไปสร้าง candle block แทน
    is_status_msg = False
    if signal_msg:
        is_status_msg = any(k in signal_msg for k in [
            "Limit Fill", "SL Hit", "TP Hit", "Position Closed", 
            "PD Fibo Plus Check", "PD Zone Check", "ยกเลิก", "CANCELED", 
            "Trailing SL", "Limit Guard"
        ])
    if is_status_msg:
        signal_msg = None

    if signal_msg:
        import re as _re
        sig_clean = _re.sub(r'`([^`\n]*)`?', r'\1', signal_msg)
        sig_clean = sig_clean.replace('`', '').replace('*', '')
        # ถ้า TG_SENT ถูกตัดกลางคำ → fetch candle จาก MT5 แทน
        # แต่ถ้า signal มี OHLC อยู่แล้ว (มี "O:") แปลว่าครบแล้ว → ไม่ต้อง fetch ใหม่
        raw_line_len = len(signal_msg.replace('\n', ' | '))
        if raw_line_len >= 295 and 'O:' not in sig_clean:
            mt5_block = _fetch_candle_block(ticket, all_lines)
            if mt5_block:
                sig_clean = mt5_block
        signal_block = sig_clean + "\n━━━━━━━━━━━━━━━━━\n"
    else:
        # ไม่มี TG_SENT เลย → ใช้ MT5 candle โดยตรง
        mt5_block = _fetch_candle_block(ticket, all_lines)
        signal_block = (mt5_block + "\n━━━━━━━━━━━━━━━━━\n") if mt5_block else ""

    # ── Log events ───────────────────────────────────────────────
    logs      = _read_ticket_logs(ticket, all_lines)
    log_block = (_format_ticket_logs(logs) + "\n") if logs else "_ไม่พบ log_\n"

    # ── Deal history (compact, ท้ายสุด) ──────────────────────────
    deal_lines = []
    if linked_deals:
        deal_lines.append("*📋 Deal History*")
        for d in sorted(linked_deals, key=lambda x: getattr(x, "time", 0))[-8:]:
            deal_lines.append(
                f"`{_fmt_dt(getattr(d, 'time', 0))}` "
                f"{_deal_type_name(d.type)}/{_deal_entry_name(d.entry)} "
                f"price=`{getattr(d, 'price', 0)}` "
                f"profit=`{round(float(getattr(d, 'profit', 0.0)), 2)}`"
            )
    deal_block = "\n".join(deal_lines) if deal_lines else ""

    msg = header + signal_block + log_block + deal_block

    if len(msg) > 4000:
        msg = msg[:4000] + "\n…(ตัดออก)"

    await _safe_reply_md(update.effective_message, msg, reply_markup=main_keyboard())

async def start(update, context):
    if not auth(update):
        await alert_intruder(update)
        return
    status = "▶️ ทำงาน" if auto_active else "⏸️ หยุด"
    await update.effective_message.reply_text(
        f"🤖 *Copter Gold Bot — ท่าที่ 1*\n"
        f"━━━━━━━━━━━━━━━━━\n"
        f"📊 A: กลืนกิน (เขียว/แดง 2 แท่ง)\n"
        f"📊 B: ตำหนิ (เขียว/แดง 2 แท่ง)\n"
        f"⏰ สแกนทุก {config.SCAN_INTERVAL} นาที\n"
        f"🕐 TF: {', '.join([tf for tf,on in TF_ACTIVE.items() if on and not (tf == 'M1' and SYMBOL and 'BTCUSD' in SYMBOL)]) or 'ยังไม่ได้เลือก'}\n"
        f"📦 Lot:{AUTO_VOLUME} | Max:{MAX_ORDERS} | Auto:{status}",
        parse_mode='Markdown', reply_markup=main_keyboard()
    )


# alias สำหรับ main.py
handle_text = handle_buttons
