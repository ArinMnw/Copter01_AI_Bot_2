from config import *
import config
from mt5_utils import connect_mt5
from handlers.keyboard import (main_keyboard, build_strategy_keyboard,
    build_strategy_detail_keyboard,
    build_tf_keyboard, build_tf_keyboard_with_back,
    build_scan_keyboard, build_scan_keyboard_with_back,
    build_lot_keyboard,
    build_trail_menu, build_trail_engulf_keyboard,
    show_main_settings_menu, show_debug_menu, build_debug_keyboard,
    show_entry_candle_mode_menu, show_profit_summary, show_profit_strategy_detail,
    show_limit_break_menu, show_engulf_menu,
    show_limit_guard_menu, show_opposite_menu,
    show_trail_focus_menu, show_entry_focus_menu,
    show_trend_filter_menu,
    show_sl_guard_menu, show_sl_guard_per_tf_menu,
    show_sl_guard_combined_menu, show_sl_guard_group_menu,
    show_risk_health_menu)


async def _qanswer(query, text=""):
    """Safe wrapper — silently ignores 'Query is too old' errors."""
    try:
        await query.answer(text)
    except Exception:
        pass


def _log_cb_error(tag, e):
    """บันทึก error ของปุ่ม callback ลง logs/error-YYYY-MM.log"""
    try:
        from bot_log import log_error as _lerr
        _lerr("CALLBACK_ERROR", f"{tag}: {type(e).__name__}: {e}")
    except Exception:
        pass


def _strategy_is_on(sid):
    """สถานะเปิด/ปิดจริงของ strategy — S20.5/S20.6 ใช้ flag แยก ไม่ใช่ active_strategies"""
    if sid == 20.5:
        return getattr(config, "S20_5_ENABLED", False)
    if sid == 20.6:
        return getattr(config, "S20_6_FVG_ENABLED", False)
    return active_strategies.get(sid, False)


_STRATEGY_DESC = {
    1:  "📐 *Pattern A* — กลืนกินซ้อน 3 แท่ง\n"
        "BUY: [2]🔴 [1]🟢Close>High[2]+gap [0]🟢Close>High[1]+gap body≥35%\n"
        "SELL: [2]🟢 [1]🔴Close<Low[2]-gap [0]🔴Close<Low[1]-gap\n\n"
        "📐 *Pattern B* — ตำหนิ + กลืน\n"
        "BUY: [2]🔴 [1]🟢ตำหนิ(ไส้เข้าใน[2]) [0]🟢กลืน[1]\n\n"
        "📐 *Pattern E* — 2 แท่งเดียวกัน + กลืน\n"
        "BUY: [2]🔴 [1]🔴 [0]🟢Close>High[1]+gap body≥35%\n\n"
        "📐 *Pattern C/P4* — ย้อนโครงสร้าง 3-4 แท่ง\n\n"
        "🔹 Zone ON: ยกเลิก pending ถ้าหลุด swing zone\n"
        "🔹 Zone OFF: ไม่เช็ค swing — เข้าทุก setup ที่ผ่าน pattern\n"
        "🔹 Forward Confirm: รอ S1/S2/S3 ฝั่งเดียวภายใน 5 แท่ง\n"
        "🔹 entry = Limit ที่ High/Low ของ pattern",

    2:  "📐 *FVG (Fair Value Gap)*\n"
        "หา imbalance ระหว่าง [2][1][0]\n"
        "BUY: [1]🟢Close>High[2]+gap | Low[0]>High[2] (gap ยังเปิด)\n"
        "SELL: [1]🔴Close<Low[2]-gap | High[0]<Low[2]\n\n"
        "🔹 entry = LIMIT ที่ขอบด้านในของ gap\n"
        "🔹 *ปกติ*: ต้องมี S1/S2/S3 ฝั่งเดียวย้อนหลังก่อน (ยืนยัน trend)\n"
        "🔹 *Parallel*: ไม่ต้องรอยืนยัน — fire ทันทีที่เจอ gap\n"
        "🔹 ถ้า [0] เป็น Marubozu → รอ confirm แท่งถัดไปก่อน",

    3:  "📐 *DM SP / Marubozu*\n"
        "BUY: [2]🟢body≥35% [1]🔴หรือ doji [0]🟢Close>High[1]+gap\n"
        "SELL: [2]🔴body≥35% [1]🟢หรือ doji [0]🔴Close<Low[1]-gap\n\n"
        "🔹 ต้องมี S1/S2/S3 ฝั่งเดียวย้อนหลัง 8 แท่งก่อน\n"
        "🔹 No-Engulf Pending: [0]ถูกทิศแต่ยังไม่กลืน → รอแท่งถัดไปกลืน\n"
        "🔹 Marubozu Pending: [0] marubozu → รอแท่งถัดไป confirm",

    4:  "📐 *นัยยะสำคัญ FVG*\n"
        "FVG ที่กลืน Swing สำคัญจริง ไม่ใช่แค่ gap ธรรมดา\n\n"
        "BUY: [1]🟢High[1]>High[2] | Low[0]>High[2] (gap เปิด)\n"
        "Close[1] > Swing High ก่อนหน้า + ห่าง ≥ engulf_min\n"
        "Swing High นั้นต้องอยู่ 'ใน gap' ด้วย\n\n"
        "SELL: [1]🔴Low[1]<Low[2] | High[0]<Low[2]\n"
        "Close[1] < Swing Low + ห่าง ≥ engulf_min",

    5:  "⚠️ *Scalping* — ยังไม่ใช้งานเต็มรูปแบบ\n"
        "logic ยังไม่ครบ — เปิดก็ได้ แต่แทบไม่ fire",

    6:  "⚙️ *2H2L — State machine ต่อจาก S2/S3*\n"
        "ไม่ใช่ท่าเข้า order — เป็น trailing/re-entry logic\n"
        "จัดการ position ที่มาจากท่า 2 หรือ 3\n"
        "รอราคาทำ 2 High หรือ 2 Low → ตั้ง order ฝั่งตรงข้าม\n"
        "💡 ควรเปิดไว้เสมอถ้าใช้ท่า 2 หรือ 3",

    7:  "⚙️ *2H2L อิสระ (S6i)*\n"
        "เหมือน S6 แต่ทำงานอิสระ ไม่ต้องรอ S2/S3 fire ก่อน\n"
        "สแกน swing H/L เองแล้วรอราคาทำ 2H/2L\n"
        "เมื่อเจอ pattern ฝั่งตรงข้าม → ตั้ง order ใหม่",

    8:  "📐 *กินไส้ Swing*\n"
        "ใช้ Swing High/Low ที่หาได้จากระบบ\n\n"
        "SELL: Entry = SwingHigh + 17% range | SL = SwingHigh + 31% range\n"
        "BUY:  Entry = SwingLow - 17% range  | SL = SwingLow - 31% range\n"
        "TP = ฝั่งตรงข้าม (SwingLow/SwingHigh)\n\n"
        "🔹 ตั้ง Limit ล่วงหน้า รอราคาวิ่งเกิน swing แล้วกลับ\n"
        "🔹 ถ้ามาจาก Limit Sweep ต้องระวัง LL/HH context",

    9:  "📐 *RSI Divergence* — RSI(14) vs pivot ราคา\n\n"
        "🔵 *Regular Bullish*: price LL + RSI HL → BUY\n"
        "🔴 *Regular Bearish*: price HH + RSI LH → SELL\n"
        "🔵 *Hidden Bullish*: price HL + RSI LL → BUY (trend continuation)\n"
        "🔴 *Hidden Bearish*: price LH + RSI HH → SELL\n\n"
        "🔹 หา pivot คู่ติดกัน (immediate prev pivot เท่านั้น)\n"
        "🔹 range ตรวจ: 5–60 แท่ง (pivot left/right = 5)\n"
        "🔹 entry = LIMIT ที่ midpoint ของแท่ง pivot ปัจจุบัน\n"
        "🔹 SL = low/high pivot ± buffer | TP = swing / fallback RR 1:1",

    10: "📐 *CRT TBS* — Candle Range Theory + Three Bar Sweep\n\n"
        "HTF ตรวจ sweep ราคาทะลุ parent H/L แล้วกลับ:\n"
        "🔹 *2bar*: แท่ง sweep + แท่ง confirm\n"
        "🔹 *3bar*: setup + sweep + confirm\n\n"
        "📌 *HTF entry*: Market ทันทีที่ HTF sweep ปิดยืนยัน\n"
        "📌 *MTF entry* (default): หลัง HTF arm → หา pattern บน LTF\n"
        "  Phase 1 Failed-push: LTF close ทะลุ parent H/L\n"
        "  Phase 2 Engulf 2-bar: กลืนกลับยืนยันทิศ\n"
        "  Model 1 Order Block (แนะนำ) → Model 2 FVG 90%\n\n"
        "LTF mapping: D1/H12→M15 | H4→M5 | H1/M30/M15→M1\n"
        "💡 TSO always-4-steps | bypass trend filter ทั้งหมด",

    11: "📐 *Fibo S1* — Hook ต่อจากท่า 1\n"
        "เมื่อ S1 fire → anchor บนแท่งสีเดียวกับ direction\n"
        "BUY: 1=High 0=Low | SELL: 1=Low 0=High\n\n"
        "Trigger → Entry pairs:\n"
        "🔹 wick แตะ KRH1(1.617) → LIMIT ที่ 50%\n"
        "🔹 wick แตะ KRH2(3.097) → LIMIT ที่ 50%\n"
        "🔹 wick แตะ KRH3(5.165) → LIMIT ที่ KRH1(1.617)\n\n"
        "TP = Run Engulfing (7.044) | SL = XXL (-0.31)\n"
        "💡 state ไม่ persist — reset ทุก restart",

    12: "📐 *Range Trading* — M5 only\n"
        "หา pivot Swing H/L → แบ่ง buy zone / sell zone\n"
        "ตั้ง Limit หลายชั้น (S12_ORDER_COUNT) ใน zone\n\n"
        "BUY zone: ใกล้ Swing Low\n"
        "SELL zone: ใกล้ Swing High\n\n"
        "🔹 zone sticky — ค้างจน pivot ใหม่มายืนยัน\n"
        "🔹 SL hit → cooldown 30 นาที ไม่เปิด order ใหม่",

    13: "📐 *EzAlgo V5* — Supertrend crossover\n"
        "BUY: close ตัดขึ้นเหนือ supertrend\n"
        "SELL: close ตัดลงใต้ supertrend\n\n"
        "entry = close ของแท่งสัญญาณ\n"
        "SL BUY: low - ATR×mult | SL SELL: high + ATR×mult\n\n"
        "📦 4 orders TSO อัตโนมัติ:\n"
        "ราคา > entry (BUY): 1 Market #3→TP3 + 3 Limit L1/L2/L3\n"
        "ราคา ≤ entry (BUY): 3 Market #1/#2/#3 + 1 Limit L3\n\n"
        "💡 standalone — bypass Trail SL/Entry Candle/Trend Filter\n"
        "🔹 ใช้ Limit Trend Recheck + RSI Fill Recheck",

    14: "📐 *Sweep RSI* — RSI zone + pattern\n"
        "หา LL/HH zone จาก RSI ย้อนหลัง 50 แท่ง\n\n"
        "BUY patterns:\n"
        "🔹 Engulf: Close[0] < LL_zone (ทะลุลงแล้วปิดใต้)\n"
        "🔹 Sweep: Low[0] < LL_zone แต่ Close กลับเหนือ\n\n"
        "SELL patterns:\n"
        "🔹 Engulf: Close[0] > HH_zone\n"
        "🔹 Sweep: High[0] > HH_zone แต่ Close กลับต่ำกว่า\n\n"
        "💡 Market order ทันที — ไม่มี pending\n"
        "🔹 PD Fibo filter: entry ต้องอยู่ Discount(<38.2%) / Premium(>61.8%)\n"
        "🔹 Flip = ปิด S14 ฝั่งตรงข้าม TF เดียวกันก่อนเปิดใหม่",

    15: "📐 *Volume Profile POC/VAL/VAH*\n"
        "คำนวณ VP จาก tick volume ย้อนหลัง N bars\n"
        "POC = ราคาที่ volume สูงสุด (แม่เหล็กราคา)\n"
        "VAH/VAL = ขอบ Value Area 70%\n\n"
        "Absorption ที่ POC/VAL/VAH:\n"
        "🔹 Long wick sweep: ไส้ ≥ 35% range แต่ปิดกลับเข้าโซน\n"
        "🔹 2-bar reversal: แท่งก่อนสวนสี → แท่งล่าสุดกลับทิศ\n\n"
        "BUY LIMIT: entry=POC/VAL | SL=low-ATR | TP=VAH/swing\n"
        "SELL LIMIT: entry=POC/VAH | SL=high+ATR | TP=VAL/swing\n\n"
        "💡 STRICT_MODE: กรอง setup ไม่ชัด\n"
        "💡 Trend Filter: เปิด/ปิด EMA50 filter\n"
        "📊 WR ~52% หลัง fix 04/06 | ดีสุด M1 BUY VAL (+$63)",

    16: "📐 *AMD x iFVG* — Asian Manipulation + Inversion FVG\n\n"
        "⏰ Asian Range: 08:00–12:00 BKK (คำนวณ H/L)\n"
        "🎯 Killzone: London 14:00–17:00 | NY 19:00–22:00 BKK\n\n"
        "Flow:\n"
        "1️⃣ ราคา sweep ทะลุ Asian Low → เตรียม BUY\n"
        "   ราคา sweep ทะลุ Asian High → เตรียม SELL\n"
        "2️⃣ ราคาพุ่งกลับ ปิดผ่าน FVG ฝั่งตรงข้าม\n"
        "   → FVG นั้นกลายเป็น Inversion FVG (entry zone)\n"
        "3️⃣ LIMIT รอที่ขอบ (Boundary) หรือ midline ของ iFVG\n\n"
        "SL: ใต้/เหนือจุด sweep + ATR buffer\n"
        "TP: ขอบ Asian ฝั่งตรงข้าม / fallback RR 1.5\n\n"
        "💡 M1 only | One-Shot = 1 ไม้/killzone (ป้องกัน dup)\n"
        "🔹 Boundary = entry ที่ขอบ iFVG ใกล้ราคา\n"
        "🔹 Midline = entry ที่กลาง iFVG (conservative)",

    17: "📐 *Sweep Sniper* — 4-Confluence M1\n\n"
        "เข้าเฉพาะ setup ที่ผ่านครบทุกชั้น:\n"
        "1️⃣ *Liquidity Sweep*: ไส้ทะลุ L/H ของ 60 แท่งก่อน\n"
        "   แต่เปิดในกรอบ + ปิดกลับเข้ากรอบ (stop hunt rejected)\n"
        "2️⃣ *Rejection Wick*: ไส้ฝั่ง sweep ≥ 30% ของ range แท่ง\n"
        "3️⃣ *RSI Extreme*: RSI ≤ 32 (BUY) หรือ ≥ 68 (SELL)\n"
        "4️⃣ *PD Fibo Zone*: close อยู่ Discount <38.2% / Premium >61.8%\n"
        "+ Session: London 14-18 / NY 19-23 BKK เท่านั้น\n\n"
        "LIMIT retrace 61.8% ของแท่ง sweep\n"
        "TP = entry ± 0.3×ATR (สั้นมาก by design)\n"
        "SL = ใต้/เหนือไส้ sweep ± 1.0×ATR\n\n"
        "📊 backtest M1 60วัน: 248 ไม้ WR 91.1% P/L +$78.90\n"
        "⚠️ RR ต่ำ ~0.17 — 1 SL กิน TP ≈ 6 ไม้",

    18: "📐 *TJR / ICT Full-Confluence* — Standalone\n\n"
        "เข้าเฉพาะเมื่อครบทุกชั้น:\n"
        "1️⃣ *HTF Bias*: เทรดตามทิศ M15/H1 (โครงสร้าง HHLL)\n"
        "2️⃣ *Liquidity Sweep*: ไส้กวาด swing high/low แล้วปฏิเสธ\n"
        "3️⃣ *MSS/CHOCH*: close ทะลุ internal structure ยืนยันกลับตัว\n"
        "4️⃣ *Entry Zone*: FVG หรือ Order Block ใน OTE (62–79%)\n"
        "5️⃣ *Killzone*: London 14-18 / NY 19-23 BKK เท่านั้น\n\n"
        "🎯 LIMIT ที่โซน | SL หลังไส้ sweep | TP ที่ liquidity ตรงข้าม\n"
        "⚠️ ค่า default ตั้งต้นก่อน backtest — ควรรัน sim_s18_backtest ก่อนใช้จริง",

    19: "🔫 *ICT Advanced — Silver Bullet* — Standalone\n\n"
        "ต่อยอด S18 ด้วยเทคนิค ICT ขั้นสูง:\n"
        "1️⃣ *Silver Bullet*: window แคบ London 13-15 / NY 21-23 BKK\n"
        "2️⃣ *HTF Bias + Sweep + MSS*: เหมือน S18\n"
        "3️⃣ *Power of 3*: sweep ต้องอยู่ใน SB session เดียวกัน\n"
        "4️⃣ *Entry Zone*: Breaker Block → BPR → FVG ใน OTE (62–79%)\n"
        "5️⃣ *TP*: New Day Opening Gap (ถ้าในทิศ) หรือ liquidity ตรงข้าม\n\n"
        "🎯 LIMIT ที่โซน | SL หลังไส้ sweep\n"
        "⚠️ ค่า default ตั้งต้นก่อน backtest — ควรรัน sim_s19_backtest ก่อนใช้จริง",

    20: "🎯 *S20 All in 4s*\n\n"
        "ประกอบด้วย 5 ท่าย่อย (เลือกเปิด/ปิดอิสระ):\n"
        "1️⃣ *S20.1 Classic*: กลืนกิน 2 แท่ง สมบูรณ์ปิดคลุมไส้\n"
        "2️⃣ *S20.2 Wick Fill*: ท่าไม้ตาย ลงไปกินไส้แล้วตบกลับ (แท่งตำหนิ)\n"
        "3️⃣ *S20.3 Solid*: แท่งตันตามเทรนด์ + FVG\n"
        "4️⃣ *S20.4 2L-2H*: ท่าผีเสื้อ ย่อพักตัวสั้นๆ\n"
        "5️⃣ *S20.5 LQ Sweep*: ทะลุหลอกกวาด Liquidity แล้วถูกตบกลับเข้า FVG\n\n"
        "🎯 Entry: LIMIT ครึ่งแท่ง (50%) | TP: Fibo 1.618 | SL: Extreme Wick + ATR Buffer\n"
        "⚠️ แนะนำเปิด Trend Filter และ Session Filter เสมอ",

    20.8: "🎯 *S20.8 ท่าไม้ตายอออิน4วิ 2 (Rejection 2L/2H)*\n\n"
          "เน้นจับแท่ง Rejection บริเวณ High/Low (แท่งตัน ไส้น้อยกว่า 10%)\n"
          "1️⃣ *BUY*: ราคาอยู่ที่ Local Low และปิดเป็นแท่งตัน (ไม่มีไส้ล่าง)\n"
          "2️⃣ *SELL*: ราคาอยู่ที่ Local High และปิดเป็นแท่งตัน (ไม่มีไส้บน)\n\n"
          "🎯 Entry: LIMIT กินไส้ (Buffer 390 จุด)\n"
          "🛑 SL: 100 จุด (หนีท่าผีเสื้อ Trap)\n"
          "🎯 TP: กลับไปที่ปลายไส้ (~150 จุด)",
}


async def _show_strategy_detail(query, sid: int, answer_text: str = ""):
    """แสดงหน้า detail ของ strategy แต่ละตัว และ answer query"""
    name   = STRATEGY_NAMES.get(sid, f"ท่าที่ {sid}")
    # S20.5/S20.6 ใช้ flag แยก (S20_5_ENABLED/S20_6_FVG_ENABLED) ไม่ใช่ active_strategies
    if sid == 20.5:
        is_on = getattr(config, "S20_5_ENABLED", False)
    elif sid == 20.6:
        is_on = getattr(config, "S20_6_FVG_ENABLED", False)
    else:
        is_on = active_strategies.get(sid, False)
    status = "🟢 เปิดอยู่" if is_on else "🔴 ปิดอยู่"
    desc   = _STRATEGY_DESC.get(sid, "")
    text   = (
        f"📋 *{name}*\n"
        f"━━━━━━━━━━━━━━━━━\n"
        f"สถานะ: *{status}*\n\n"
        f"{desc}\n\n" if desc else
        f"📋 *{name}*\n"
        f"━━━━━━━━━━━━━━━━━\n"
        f"สถานะ: *{status}*\n\n"
    ) + "เลือกตัวเลือกด้านล่าง:"
    try:
        await query.edit_message_text(text, parse_mode="Markdown",
                                      reply_markup=build_strategy_detail_keyboard(sid))
    except Exception as e:
        if "not modified" not in str(e).lower():
            _log_cb_error("show_strategy_detail", e)
    await _qanswer(query, answer_text)


async def handle_callback(update, ctx):
    global SCAN_INTERVAL, TF_CURRENT, TF_ACTIVE, active_strategies
    query = update.callback_query
    _uid = update.effective_user.id if update.effective_user else None
    if _uid != MY_USER_ID:
        _log_cb_error("auth_blocked", RuntimeError(f"uid={_uid} != MY_USER_ID={MY_USER_ID}"))
        await _qanswer(query)
        return
    data = query.data

    if data == "cancel":
        await query.edit_message_reply_markup(reply_markup=None)
        await _qanswer(query,"ปิดแล้ว")

    elif data == "toggle_auto":
        config.auto_active = not config.auto_active
        status = "▶️ ทำงาน" if config.auto_active else "⏸️ หยุด"
        if config.auto_active:
            try:
                checker = ctx.application.bot_data.get("check_symbol_switch")
                if checker:
                    await checker()
            except Exception as e:
                print(f"[{now_bkk().strftime('%H:%M:%S')}] ⚠️ toggle_auto symbol check error: {e}")
                try:
                    from bot_log import log_error as _lerr
                    _lerr("CALLBACK_ERROR", f"toggle_auto symbol check: {type(e).__name__}: {e}")
                except Exception:
                    pass
        try:
            await query.edit_message_text(
                f"⚙️ *Auto Trade: {status}*\n⏰ สแกนทุก {config.SCAN_INTERVAL} นาที",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("⏸️ หยุด" if config.auto_active else "▶️ เปิด", callback_data="toggle_auto")
                ]])
            )
        except Exception as e:
            if "not modified" not in str(e).lower():
                _log_cb_error("toggle_auto", e)
        await _qanswer(query,f"{'เปิด' if config.auto_active else 'หยุด'} Auto แล้ว")

    elif data == "open_strategy_menu":
        active_list = [STRATEGY_NAMES[s] for s in active_strategies if _strategy_is_on(s)]
        summary = " + ".join(active_list) if active_list else "ไม่มี"
        new_text = (
            "📋 *เลือก Strategy*\n"
            "━━━━━━━━━━━━━━━━━\n"
            f"🔄 ที่เปิดอยู่: *{summary}*\n\n"
            "กดที่ท่าไหนเพื่อดู option และเปิด/ปิดใช้งาน:"
        )
        try:
            await query.edit_message_text(
                new_text,
                parse_mode="Markdown",
                reply_markup=build_strategy_keyboard()
            )
        except Exception as e:
            if "not modified" not in str(e).lower():
                try:
                    from bot_log import log_error as _lerr
                    _lerr("CALLBACK_ERROR", f"open_strategy_menu: {type(e).__name__}: {e}")
                except Exception:
                    pass
        await _qanswer(query)

    elif data.startswith("open_strategy_detail_"):
        try:
            _sid_val = float(data.replace("open_strategy_detail_", "")); sid = int(_sid_val) if _sid_val.is_integer() else _sid_val
        except ValueError:
            await _qanswer(query)
            return
        await _show_strategy_detail(query, sid)

    elif data == "reset_config_prompt":
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("✅ ยืนยัน Reset", callback_data="confirm_reset_config"),
            InlineKeyboardButton("🔙 กลับ", callback_data="back_to_settings"),
        ]])
        try:
            await query.edit_message_text(
                "♻️ *Reset Config*\n"
                "━━━━━━━━━━━━━━━━━\n"
                "จะรีเซทค่าตั้งค่าทั้งหมดให้กลับไปตรงกับค่าเริ่มต้นใน `config.py`\n"
                "และบันทึกทับ state ปัจจุบันทันที\n\n"
                "ยืนยันหรือไม่?",
                parse_mode="Markdown",
                reply_markup=kb
            )
        except Exception as e:
            if "not modified" not in str(e).lower():
                _log_cb_error("reset_config_prompt", e)
        await _qanswer(query)

    elif data == "confirm_reset_config":
        config.reset_runtime_config_to_defaults(save_state=True)
        await show_main_settings_menu(query, is_query=True)
        await _qanswer(query,"รีเซท config ตาม config.py แล้ว")

    elif data == "lot_custom_input":
        # เข้าสู่ mode รับ input lot สำหรับ auto
        ctx.user_data["waiting_lot_input"] = "auto"
        try:
            await query.edit_message_text(
                "✏️ *กรอก Lot Size สำหรับ Auto Trade*\n"
                "━━━━━━━━━━━━━━━━━\n"
                f"📦 ปัจจุบัน: *{config.AUTO_VOLUME}*\n\n"
                "พิมพ์ตัวเลข เช่น `0.03` หรือ `0.15`\n"
                "_(ขั้นต่ำ 0.01 สูงสุด 10.0)_",
                parse_mode="Markdown"
            )
        except Exception as e:
            if "not modified" not in str(e).lower():
                _log_cb_error("lot_custom_input", e)
        await _qanswer(query,"พิมพ์ lot size ใน chat ได้เลย")

    elif data.startswith("lot_manual_"):
        # format: lot_manual_{direction}_custom_{price}
        parts     = data.split("_")
        direction = parts[2]   # buy / sell
        price_str = parts[4]   # ราคา
        ctx.user_data["waiting_lot_input"] = f"manual_{direction}_{price_str}"
        e = "🟢" if direction == "buy" else "🔴"
        try:
            await query.edit_message_text(
                f"✏️ *กรอก Lot Size — {e} {direction.upper()}*\n"
                "━━━━━━━━━━━━━━━━━\n"
                f"💰 ราคา: `{price_str}`\n\n"
                "พิมพ์ตัวเลข เช่น `0.03` หรือ `0.15`\n"
                "_(ขั้นต่ำ 0.01 สูงสุด 10.0)_",
                parse_mode="Markdown"
            )
        except Exception as e:
            if "not modified" not in str(e).lower():
                _log_cb_error("lot_manual", e)
        await _qanswer(query,"พิมพ์ lot size ใน chat ได้เลย")

    elif data == "open_lot_menu":
        try:
            await query.edit_message_text(
                f"📦 *ตั้งค่า Lot Size — Auto Trade*\n━━━━━━━━━━━━━━━━━\n"
                f"📦 ปัจจุบัน: *{config.AUTO_VOLUME} lot*\n\nเลือก Lot:",
                parse_mode="Markdown",
                reply_markup=build_lot_keyboard()
            )
        except Exception as e:
            if "not modified" not in str(e).lower():
                _log_cb_error("open_lot_menu", e)
        await _qanswer(query)

    elif data.startswith("set_lot_"):
        new_lot = float(data.split("_")[-1])
        config.AUTO_VOLUME = new_lot
        import config as cfg_mod
        cfg_mod.AUTO_VOLUME = new_lot
        save_runtime_state()
        try:
            await query.edit_message_text(
                f"📦 *ตั้งค่า Lot Size — Auto Trade*\n━━━━━━━━━━━━━━━━━\n"
                f"📦 ปัจจุบัน: *{config.AUTO_VOLUME} lot*\n\nเลือก Lot:",
                parse_mode="Markdown",
                reply_markup=build_lot_keyboard()
            )
        except Exception as e:
            if "not modified" not in str(e).lower():
                _log_cb_error("set_lot", e)
        await _qanswer(query,f"✅ Lot Auto = {config.AUTO_VOLUME}")

    elif data == "open_scan_menu":
        try:
            await query.edit_message_text(
                f"⏰ *ตั้งค่า Scan Interval*\n━━━━━━━━━━━━━━━━━\n⏰ ปัจจุบัน: *ทุก {config.SCAN_INTERVAL} นาที*\n\nเลือกความถี่:",
                parse_mode="Markdown",
                reply_markup=build_scan_keyboard_with_back()
            )
        except Exception as e:
            if "not modified" not in str(e).lower():
                _log_cb_error("open_scan_menu", e)
        await _qanswer(query)

    elif data == "open_trail_menu":
        trail_mode_label = "รวม phase" if config.TRAIL_SL_ENGULF_MODE == "combined" else "แยก phase"
        try:
            await query.edit_message_text(
                "📐 *ตั้งค่า Trail SL*\n"
                "━━━━━━━━━━━━━━━━━\n"
                f"โหมดปัจจุบัน: *Engulf / {trail_mode_label}*\n"
                f"Trail ทันที: *{'ON' if config.TRAIL_SL_IMMEDIATE else 'OFF'}*\n\n"
                "เลือกประเภท Trail SL:",
                parse_mode="Markdown",
                reply_markup=build_trail_menu()
            )
        except Exception as e:
            if "not modified" not in str(e).lower():
                _log_cb_error("open_trail_menu", e)
        await _qanswer(query)

    elif data == "open_trail_engulf_menu":
        trail_mode_label = "รวม phase" if config.TRAIL_SL_ENGULF_MODE == "combined" else "แยก phase"
        try:
            await query.edit_message_text(
                "📐 *Trail SL -> Engulf*\n"
                "━━━━━━━━━━━━━━━━━\n"
                "เลือกวิธีการทำงาน:\n"
                f"ปัจจุบัน: *{trail_mode_label}*\n\n"
                "รวม phase = ดูทุก TF ใน group พร้อมกัน และเลื่อน SL ต่อเนื่องเมื่อเจอ engulf\n"
                "แยก phase = TF เล็กกว่า -> TF order -> จบ",
                parse_mode="Markdown",
                reply_markup=build_trail_engulf_keyboard()
            )
        except Exception as e:
            if "not modified" not in str(e).lower():
                _log_cb_error("open_trail_engulf_menu", e)
        await _qanswer(query)

    elif data == "open_tf_menu":
        active_tfs = [tf for tf, on in TF_ACTIVE.items() if on and not (tf == 'M1' and SYMBOL and 'BTCUSD' in SYMBOL)]
        tf_summary = ", ".join(active_tfs) if active_tfs else "ยังไม่ได้เลือก"
        try:
            await query.edit_message_text(
                f"🕐 *เลือก Timeframe*\n━━━━━━━━━━━━━━━━━\n📊 ที่เปิดอยู่: *{tf_summary}*\n\nกดเลือกได้หลาย TF:",
                parse_mode="Markdown",
                reply_markup=build_tf_keyboard_with_back()
            )
        except Exception as e:
            if "not modified" not in str(e).lower():
                _log_cb_error("open_tf_menu", e)
        await _qanswer(query)

    elif data == "back_to_settings":
        await show_main_settings_menu(query, is_query=True)
        await _qanswer(query)

    elif data == "toggle_entry_candle_tp":
        config.ENTRY_CANDLE_UPDATE_TP = not config.ENTRY_CANDLE_UPDATE_TP
        save_runtime_state()
        await show_main_settings_menu(query, is_query=True)
        status = "ON" if config.ENTRY_CANDLE_UPDATE_TP else "OFF"
        await _qanswer(query,f"Entry Candle TP: {status}")

    elif data == "open_entry_candle_mode_menu":
        await show_entry_candle_mode_menu(query, is_query=True)
        await _qanswer(query)

    elif data == "set_entry_candle_mode_classic":
        config.ENTRY_CANDLE_MODE = "classic"
        save_runtime_state()
        await show_entry_candle_mode_menu(query, is_query=True)
        await _qanswer(query,"Entry Candle Mode: Classic")

    elif data == "set_entry_candle_mode_close":
        config.ENTRY_CANDLE_MODE = "close"
        save_runtime_state()
        await show_entry_candle_mode_menu(query, is_query=True)
        await _qanswer(query,"Entry Candle Mode: Close")

    elif data == "set_entry_candle_mode_close_percentage":
        config.ENTRY_CANDLE_MODE = "close_percentage"
        save_runtime_state()
        await show_entry_candle_mode_menu(query, is_query=True)
        await _qanswer(query,"Entry Candle Mode: Close Percentage")

    elif data == "toggle_entry_close_reverse_market":
        config.ENTRY_CLOSE_REVERSE_MARKET = not config.ENTRY_CLOSE_REVERSE_MARKET
        save_runtime_state()
        await show_entry_candle_mode_menu(query, is_query=True)
        await _qanswer(query,f"Close -> Market: {'ON' if config.ENTRY_CLOSE_REVERSE_MARKET else 'OFF'}")

    elif data == "toggle_entry_close_reverse_limit":
        config.ENTRY_CLOSE_REVERSE_LIMIT = not config.ENTRY_CLOSE_REVERSE_LIMIT
        save_runtime_state()
        await show_entry_candle_mode_menu(query, is_query=True)
        await _qanswer(query,f"Close -> Limit: {'ON' if config.ENTRY_CLOSE_REVERSE_LIMIT else 'OFF'}")

    elif data == "open_opposite_menu":
        await show_opposite_menu(query, is_query=True)
        await _qanswer(query)

    elif data == "set_opposite_mode_tp_close":
        config.OPPOSITE_ORDER_MODE = "tp_close"
        save_runtime_state()
        await show_opposite_menu(query, is_query=True)
        await _qanswer(query,"Opposite Order: ตั้ง TP+ปิด")

    elif data == "set_opposite_mode_sl_protect":
        config.OPPOSITE_ORDER_MODE = "sl_protect"
        save_runtime_state()
        await show_opposite_menu(query, is_query=True)
        await _qanswer(query,"Opposite Order: ตั้ง SL Protect")

    elif data == "toggle_s20_8_enabled":
        config.S20_8_ENABLED = not config.S20_8_ENABLED
        save_runtime_state()
        await show_main_settings_menu(query, is_query=True)
        await _qanswer(query,f"S20_8: {'ON' if config.S20_8_ENABLED else 'OFF'}")

    elif data == "toggle_trail_sl_enabled":
        config.TRAIL_SL_ENABLED = not config.TRAIL_SL_ENABLED
        save_runtime_state()
        trail_mode_label = "รวม phase" if config.TRAIL_SL_ENGULF_MODE == "combined" else "แยก phase"
        try:
            await query.edit_message_text(
                "📐 *ตั้งค่า Trail SL*\n"
                "━━━━━━━━━━━━━━━━━\n"
                f"สถานะ: *{'ON' if config.TRAIL_SL_ENABLED else 'OFF'}*\n"
                f"โหมดปัจจุบัน: *Engulf / {trail_mode_label}*\n"
                f"Trail ทันที: *{'ON' if config.TRAIL_SL_IMMEDIATE else 'OFF'}*\n\n"
                "เลือกประเภท Trail SL:",
                parse_mode="Markdown",
                reply_markup=build_trail_menu()
            )
        except Exception as e:
            if "not modified" not in str(e).lower():
                _log_cb_error("toggle_trail_sl_enabled", e)
        await _qanswer(query,f"Trail SL: {'ON' if config.TRAIL_SL_ENABLED else 'OFF'}")

    elif data == "toggle_trail_reversal_override":
        config.TRAIL_SL_REVERSAL_OVERRIDE_ENABLED = not config.TRAIL_SL_REVERSAL_OVERRIDE_ENABLED
        save_runtime_state()
        await show_main_settings_menu(query, is_query=True)
        await _qanswer(query,
            f"จุดกลับตัว -> Trail SL: {'ON' if config.TRAIL_SL_REVERSAL_OVERRIDE_ENABLED else 'OFF'}"
        )

    elif data == "toggle_entry_candle_enabled":
        config.ENTRY_CANDLE_ENABLED = not config.ENTRY_CANDLE_ENABLED
        save_runtime_state()
        await show_entry_candle_mode_menu(query, is_query=True)
        await _qanswer(query,f"Entry Candle: {'ON' if config.ENTRY_CANDLE_ENABLED else 'OFF'}")

    elif data == "toggle_opposite_enabled":
        config.OPPOSITE_ORDER_ENABLED = not config.OPPOSITE_ORDER_ENABLED
        save_runtime_state()
        await show_opposite_menu(query, is_query=True)
        await _qanswer(query,f"Opposite Order: {'ON' if config.OPPOSITE_ORDER_ENABLED else 'OFF'}")

    elif data == "open_debug_menu":
        await show_debug_menu(query, is_query=True)
        await _qanswer(query)

    elif data == "toggle_debug_queue":
        config.TG_QUEUE_DEBUG = not config.TG_QUEUE_DEBUG
        try:
            import config as cfg_mod
            cfg_mod.TG_QUEUE_DEBUG = config.TG_QUEUE_DEBUG
        except Exception:
            pass
        save_runtime_state()
        await show_debug_menu(query, is_query=True)
        await _qanswer(query,f"Queue Debug: {'ON' if config.TG_QUEUE_DEBUG else 'OFF'}")

    elif data == "toggle_debug_sltp":
        config.SLTP_AUDIT_DEBUG = not config.SLTP_AUDIT_DEBUG
        try:
            import config as cfg_mod
            cfg_mod.SLTP_AUDIT_DEBUG = config.SLTP_AUDIT_DEBUG
        except Exception:
            pass
        save_runtime_state()
        await show_debug_menu(query, is_query=True)
        await _qanswer(query,f"SL/TP Audit Debug: {'ON' if config.SLTP_AUDIT_DEBUG else 'OFF'}")

    elif data == "toggle_debug_trade":
        config.TRADE_DEBUG = not config.TRADE_DEBUG
        try:
            import config as cfg_mod
            cfg_mod.TRADE_DEBUG = config.TRADE_DEBUG
        except Exception:
            pass
        save_runtime_state()
        await show_debug_menu(query, is_query=True)
        await _qanswer(query,f"Trade Debug: {'ON' if config.TRADE_DEBUG else 'OFF'}")

    elif data == "close_settings":
        try:
            await query.message.delete()
        except Exception as e:
            _log_cb_error("close_settings", e)
        await _qanswer(query,"ปิดเมนูแล้ว")

    elif data.startswith("set_interval_"):
        SCAN_INTERVAL = int(data.split("_")[-1])
        config.SCAN_INTERVAL = SCAN_INTERVAL  # sync กลับ config module
        save_runtime_state()
        # อัพเดท scheduler — ดึงจาก application.bot_data
        try:
            scheduler = ctx.application.bot_data.get("scheduler")
            if scheduler:
                scheduler.reschedule_job("auto_scan_job", trigger="interval", minutes=SCAN_INTERVAL)
                print(f"[{now_bkk().strftime('%H:%M:%S')}] ✅ Reschedule scan → ทุก {SCAN_INTERVAL} นาที")
            else:
                print(f"[{now_bkk().strftime('%H:%M:%S')}] ⚠️ scheduler ไม่พบใน bot_data")
        except Exception as e:
            print(f"[{now_bkk().strftime('%H:%M:%S')}] ⚠️ reschedule error: {e}")
            try:
                from bot_log import log_error as _lerr
                _lerr("CALLBACK_ERROR", f"reschedule: {type(e).__name__}: {e}")
            except Exception:
                pass
        try:
            await query.edit_message_text(
                f"⏰ *ตั้งค่า Scan Interval*\n━━━━━━━━━━━━━━━━━\n⏰ ปัจจุบัน: *ทุก {config.SCAN_INTERVAL} นาที*\n\nเลือกความถี่:",
                parse_mode="Markdown",
                reply_markup=build_scan_keyboard_with_back()
            )
        except Exception as e:
            if "not modified" not in str(e).lower():
                _log_cb_error("set_interval", e)
        await _qanswer(query,f"✅ Scan ทุก {config.SCAN_INTERVAL} นาที")

    elif data.startswith("set_tf_"):
        tf_key = data.replace("set_tf_", "")
        if tf_key == "ALL":
            # Toggle เลือกทั้งหมด / ยกเลิกทั้งหมด
            all_active = all(TF_ACTIVE.values())
            for k in TF_ACTIVE:
                TF_ACTIVE[k] = not all_active
            config.TF_ACTIVE.update(TF_ACTIVE)
            msg_answer = "ยกเลิกทุก TF แล้ว" if all_active else "เลือกทุก TF แล้ว"
        elif tf_key in TF_ACTIVE:
            # ถ้าเลือกทุก TF อยู่แล้ว และกด TF อื่น = deselect เฉพาะ TF นั้น
            all_currently = all(TF_ACTIVE.values())
            if all_currently:
                # deselect เฉพาะ TF ที่กด
                TF_ACTIVE[tf_key] = False
                config.TF_ACTIVE[tf_key] = False
                msg_answer = f"ยกเลิก {tf_key} (เหลือ TF อื่น)"
            else:
                # toggle ปกติ
                TF_ACTIVE[tf_key] = not TF_ACTIVE[tf_key]
                config.TF_ACTIVE[tf_key] = TF_ACTIVE[tf_key]
                status = "เปิด" if TF_ACTIVE[tf_key] else "ปิด"
                msg_answer = f"{status} {tf_key} แล้ว"
        else:
            msg_answer = "ไม่พบ TF นี้"

        active_tfs = [tf for tf, on in TF_ACTIVE.items() if on and not (tf == 'M1' and SYMBOL and 'BTCUSD' in SYMBOL)]
        tf_summary = ", ".join(active_tfs) if active_tfs else "ไม่มี"
        try:
            await query.edit_message_text(
                f"🕐 *เลือก Timeframe*\n━━━━━━━━━━━━━━━━━\n📊 ที่เปิดอยู่: *{tf_summary}*\n\nกดเลือกได้หลาย TF:",
                parse_mode="Markdown",
                reply_markup=build_tf_keyboard_with_back()
            )
        except Exception as e:
            if "not modified" not in str(e).lower():
                _log_cb_error("set_tf", e)
        save_runtime_state()
        await _qanswer(query,msg_answer)

    elif data.startswith("set_s1_zone_mode_"):
        mode = data.replace("set_s1_zone_mode_", "")
        config.S1_ZONE_MODE = mode
        save_runtime_state()
        if mode == "zone":
            label = "Zone (ต้องใกล้ Swing)"
        elif mode == "swing":
            label = "Swing (ภายใน 4 แท่ง)"
        else:
            label = "ปกติ (ไม่สนใจ Zone)"
        await _show_strategy_detail(query, 1, f"✅ ท่า 1: {label}")

    elif data in ("toggle_rsi9_regular", "toggle_rsi9_hidden"):
        if data == "toggle_rsi9_regular":
            currently_on = config.RSI9_PLOT_BULLISH and config.RSI9_PLOT_BEARISH
            new_state = not currently_on
            config.RSI9_PLOT_BULLISH = new_state
            config.RSI9_PLOT_BEARISH = new_state
            label = f"Regular: {'ON' if new_state else 'OFF'}"
        else:
            currently_on = config.RSI9_PLOT_HIDDEN_BULLISH and config.RSI9_PLOT_HIDDEN_BEARISH
            new_state = not currently_on
            config.RSI9_PLOT_HIDDEN_BULLISH = new_state
            config.RSI9_PLOT_HIDDEN_BEARISH = new_state
            label = f"Hidden: {'ON' if new_state else 'OFF'}"
        save_runtime_state()
        await _show_strategy_detail(query, 9, f"✅ ท่า 9: {label}")

    elif data.startswith("set_crt_bar_mode_"):
        mode = data.replace("set_crt_bar_mode_", "")
        if mode in ("2bar", "3bar"):
            config.CRT_BAR_MODE = mode
            save_runtime_state()
            await _show_strategy_detail(query, 10, f"✅ ท่า 10: {mode}")
        else:
            await _qanswer(query, "Mode ไม่ถูกต้อง")

    elif data.startswith("set_crt_entry_mode_"):
        mode = data.replace("set_crt_entry_mode_", "")
        if mode in ("htf", "mtf"):
            config.CRT_ENTRY_MODE = mode
            save_runtime_state()
            label = "HTF entry" if mode == "htf" else "MTF (LTF entry)"
            await _show_strategy_detail(query, 10, f"✅ ท่า 10: {label}")
        else:
            await _qanswer(query, "Entry mode ไม่ถูกต้อง")

    elif data == "toggle_crt_wait_htf_close":
        config.CRT_WAIT_HTF_CLOSE = not getattr(config, "CRT_WAIT_HTF_CLOSE", False)
        save_runtime_state()
        status = "รอ HTF sweep ปิด" if config.CRT_WAIT_HTF_CLOSE else "ไม่รอ HTF sweep ปิด"
        await _show_strategy_detail(query, 10, f"✅ ท่า 10: {status}")

    elif data == "toggle_s10_retry_after_sl":
        config.S10_RETRY_AFTER_SL = not getattr(config, "S10_RETRY_AFTER_SL", False)
        save_runtime_state()
        status = "เปิด" if config.S10_RETRY_AFTER_SL else "ปิด"
        await _show_strategy_detail(query, 10, f"✅ ท่า 10 Retry SL: {status}")

    elif data in ("toggle_fvg_normal", "toggle_fvg_parallel"):
        if data == "toggle_fvg_normal":
            config.FVG_NORMAL = not config.FVG_NORMAL
        else:
            config.FVG_PARALLEL = not config.FVG_PARALLEL
        save_runtime_state()
        parts = []
        if config.FVG_NORMAL:
            parts.append("ปกติ")
        if config.FVG_PARALLEL:
            parts.append("Parallel")
        label = "+".join(parts) if parts else "(ปิดหมด)"
        await _show_strategy_detail(query, 2, f"✅ ท่า 2: {label}")

    elif data == "toggle_s14_sweep_swing":
        config.S14_SWEEP_SWING = not getattr(config, "S14_SWEEP_SWING", True)
        save_runtime_state()
        status = "ON" if config.S14_SWEEP_SWING else "OFF"
        await _show_strategy_detail(query, 14, f"✅ ท่า 14 Sweep Swing: {status}")

    elif data == "toggle_s14_engulf_swing":
        config.S14_ENGULF_SWING = not getattr(config, "S14_ENGULF_SWING", True)
        save_runtime_state()
        status = "ON" if config.S14_ENGULF_SWING else "OFF"
        await _show_strategy_detail(query, 14, f"✅ ท่า 14 Engulf Swing: {status}")

    elif data == "toggle_s14_sweep_return":
        config.S14_SWEEP_RETURN = not getattr(config, "S14_SWEEP_RETURN", True)
        save_runtime_state()
        status = "ON" if config.S14_SWEEP_RETURN else "OFF"
        await _show_strategy_detail(query, 14, f"✅ ท่า 14 Sweep กลับตัว: {status}")

    elif data == "toggle_s14_flip":
        config.S14_FLIP_ENABLED = not getattr(config, "S14_FLIP_ENABLED", True)
        save_runtime_state()
        status = "ON" if config.S14_FLIP_ENABLED else "OFF"
        await _show_strategy_detail(query, 14, f"✅ ท่า 14 Flip: {status}")

    elif data == "toggle_s14_engulf_breakeven":
        config.S14_ENGULF_BREAKEVEN = not getattr(config, "S14_ENGULF_BREAKEVEN", True)
        save_runtime_state()
        status = "ON" if config.S14_ENGULF_BREAKEVEN else "OFF"
        await _show_strategy_detail(query, 14, f"✅ ท่า 14 Engulf Breakeven: {status}")

    elif data == "toggle_s15_trend_filter":
        config.S15_TREND_FILTER = not getattr(config, "S15_TREND_FILTER", True)
        save_runtime_state()
        status = "ON" if config.S15_TREND_FILTER else "OFF"
        await _show_strategy_detail(query, 15, f"✅ ท่า 15 Trend Filter: {status}")

    elif data == "toggle_s15_strict_mode":
        config.S15_STRICT_MODE = not getattr(config, "S15_STRICT_MODE", True)
        save_runtime_state()
        status = "ON" if config.S15_STRICT_MODE else "OFF"
        await _show_strategy_detail(query, 15, f"✅ ท่า 15 Strict Mode: {status}")

    elif data.startswith("set_s15_cooldown_"):
        cd_map = {"5": 5, "15": 15, "30": 30}
        cd_str = data.replace("set_s15_cooldown_", "")
        if cd_str not in cd_map:
            await _qanswer(query, "ค่า Cooldown ไม่ถูกต้อง")
            return
        config.S15_LEVEL_COOLDOWN_BARS = cd_map[cd_str]
        save_runtime_state()
        await _show_strategy_detail(query, 15, f"✅ ท่า 15 Cooldown: {config.S15_LEVEL_COOLDOWN_BARS} bars")

    elif data == "toggle_s15_rsi_filter":
        config.S15_RSI_FILTER = not getattr(config, "S15_RSI_FILTER", True)
        save_runtime_state()
        status = "ON" if config.S15_RSI_FILTER else "OFF"
        await _show_strategy_detail(query, 15, f"✅ ท่า 15 RSI Filter: {status}")

    elif data == "toggle_s15_val_vah":
        config.S15_USE_VAL_VAH = not getattr(config, "S15_USE_VAL_VAH", True)
        save_runtime_state()
        status = "ON" if config.S15_USE_VAL_VAH else "OFF"
        await _show_strategy_detail(query, 15, f"✅ ท่า 15 VAL/VAH: {status}")

    elif data.startswith("set_s15_lookback_"):
        lb_map = {"50": 50, "100": 100, "200": 200}
        lb_str = data.replace("set_s15_lookback_", "")
        if lb_str not in lb_map:
            await _qanswer(query, "ค่า Lookback ไม่ถูกต้อง")
            return
        config.S15_LOOKBACK = lb_map[lb_str]
        save_runtime_state()
        await _show_strategy_detail(query, 15, f"✅ ท่า 15 Lookback: {config.S15_LOOKBACK} bars")

    elif data.startswith("set_s15_min_rr_"):
        rr_map = {"10": 1.0, "15": 1.5, "20": 2.0}
        rr_str = data.replace("set_s15_min_rr_", "")
        if rr_str not in rr_map:
            await _qanswer(query, "ค่า R:R ไม่ถูกต้อง")
            return
        config.S15_MIN_RR = rr_map[rr_str]
        save_runtime_state()
        await _show_strategy_detail(query, 15, f"✅ ท่า 15 Min R:R: {config.S15_MIN_RR}")

    elif data.startswith("set_s16_entry_mode_"):
        mode = data.replace("set_s16_entry_mode_", "")
        if mode not in ("boundary", "midline"):
            await _qanswer(query, "ค่าไม่ถูกต้อง")
            return
        config.S16_ENTRY_MODE = mode
        save_runtime_state()
        await _show_strategy_detail(query, 16, f"✅ ท่า16 Entry Mode: {mode}")

    elif data == "toggle_s16_kz_one_shot":
        config.S16_KZ_ONE_SHOT = not getattr(config, "S16_KZ_ONE_SHOT", True)
        save_runtime_state()
        status = "ON" if config.S16_KZ_ONE_SHOT else "OFF"
        await _show_strategy_detail(query, 16, f"✅ ท่า16 KZ One-Shot: {status}")

    elif data.startswith("set_s16_min_rr_"):
        rr_map = {"10": 1.0, "15": 1.5, "20": 2.0}
        rr_str = data.replace("set_s16_min_rr_", "")
        if rr_str not in rr_map:
            await _qanswer(query, "ค่า R:R ไม่ถูกต้อง")
            return
        config.S16_MIN_RR = rr_map[rr_str]
        save_runtime_state()
        await _show_strategy_detail(query, 16, f"✅ ท่า16 Min R:R: {config.S16_MIN_RR}")

    elif data == "toggle_s17_session_filter":
        config.S17_SESSION_FILTER = not getattr(config, "S17_SESSION_FILTER", True)
        save_runtime_state()
        status = "ON" if config.S17_SESSION_FILTER else "OFF"
        await _show_strategy_detail(query, 17, f"✅ ท่า17 Session Filter: {status}")

    elif data == "toggle_s17_pd_filter":
        config.S17_PD_FILTER = not getattr(config, "S17_PD_FILTER", True)
        save_runtime_state()
        status = "ON" if config.S17_PD_FILTER else "OFF"
        await _show_strategy_detail(query, 17, f"✅ ท่า17 PD Filter: {status}")

    elif data == "toggle_s17_trend_filter":
        config.S17_TREND_FILTER = not getattr(config, "S17_TREND_FILTER", False)
        save_runtime_state()
        status = "ON" if config.S17_TREND_FILTER else "OFF"
        await _show_strategy_detail(query, 17, f"✅ ท่า17 Trend Filter: {status}")

    elif data.startswith("set_s17_entry_mode_"):
        mode = data.replace("set_s17_entry_mode_", "")
        if mode not in ("limit_618", "limit_50", "market"):
            await _qanswer(query, "ค่าไม่ถูกต้อง")
            return
        config.S17_ENTRY_MODE = mode
        save_runtime_state()
        await _show_strategy_detail(query, 17, f"✅ ท่า17 Entry Mode: {mode}")

    elif data == "toggle_s18_session_filter":
        config.S18_SESSION_FILTER = not getattr(config, "S18_SESSION_FILTER", True)
        save_runtime_state()
        status = "ON" if config.S18_SESSION_FILTER else "OFF"
        await _show_strategy_detail(query, 18, f"✅ ท่า18 Killzone Filter: {status}")

    elif data == "toggle_s18_rsi_filter":
        config.S18_RSI_FILTER = not getattr(config, "S18_RSI_FILTER", True)
        save_runtime_state()
        status = "ON" if config.S18_RSI_FILTER else "OFF"
        await _show_strategy_detail(query, 18, f"✅ ท่า18 RSI Filter: {status}")

    elif data.startswith("set_s18_zone_prefer_"):
        zp = data.replace("set_s18_zone_prefer_", "")
        if zp not in ("fvg", "ob"):
            await _qanswer(query, "ค่าไม่ถูกต้อง")
            return
        config.S18_ZONE_PREFER = zp
        save_runtime_state()
        await _show_strategy_detail(query, 18, f"✅ ท่า18 Zone Prefer: {zp.upper()}")

    elif data.startswith("set_s18_entry_mode_"):
        mode = data.replace("set_s18_entry_mode_", "")
        if mode not in ("zone_edge", "zone_mid"):
            await _qanswer(query, "ค่าไม่ถูกต้อง")
            return
        config.S18_ENTRY_MODE = mode
        save_runtime_state()
        await _show_strategy_detail(query, 18, f"✅ ท่า18 Entry Mode: {mode}")

    elif data.startswith("set_s18_min_rr_"):
        rr_map = {"10": 1.0, "15": 1.5, "20": 2.0}
        rr_str = data.replace("set_s18_min_rr_", "")
        if rr_str not in rr_map:
            await _qanswer(query, "ค่า R:R ไม่ถูกต้อง")
            return
        config.S18_MIN_RR = rr_map[rr_str]
        save_runtime_state()
        await _show_strategy_detail(query, 18, f"✅ ท่า18 Min R:R: {config.S18_MIN_RR}")

    elif data == "toggle_s19_session_filter":
        config.S19_SESSION_FILTER = not getattr(config, "S19_SESSION_FILTER", True)
        save_runtime_state()
        status = "ON" if config.S19_SESSION_FILTER else "OFF"
        await _show_strategy_detail(query, 19, f"✅ ท่า19 Silver Bullet: {status}")

    elif data == "toggle_s19_p3":
        config.S19_P3_SESSION_SWEEP = not getattr(config, "S19_P3_SESSION_SWEEP", True)
        save_runtime_state()
        status = "ON" if config.S19_P3_SESSION_SWEEP else "OFF"
        await _show_strategy_detail(query, 19, f"✅ ท่า19 Power of 3: {status}")

    elif data == "toggle_s19_ndog":
        config.S19_USE_NDOG = not getattr(config, "S19_USE_NDOG", True)
        save_runtime_state()
        status = "ON" if config.S19_USE_NDOG else "OFF"
        await _show_strategy_detail(query, 19, f"✅ ท่า19 NDOG TP: {status}")

    elif data.startswith("set_s19_zone_prefer_"):
        zp = data.replace("set_s19_zone_prefer_", "")
        if zp not in ("breaker", "bpr", "fvg"):
            await _qanswer(query, "ค่าไม่ถูกต้อง")
            return
        config.S19_ZONE_PREFER = zp
        save_runtime_state()
        await _show_strategy_detail(query, 19, f"✅ ท่า19 Zone Prefer: {zp.upper()}")

    elif data.startswith("set_s19_min_rr_"):
        rr_map = {"10": 1.0, "15": 1.5, "20": 2.0}
        rr_str = data.replace("set_s19_min_rr_", "")
        if rr_str not in rr_map:
            await _qanswer(query, "ค่า R:R ไม่ถูกต้อง")
            return
        config.S19_MIN_RR = rr_map[rr_str]
        save_runtime_state()
        await _show_strategy_detail(query, 19, f"✅ ท่า19 Min R:R: {config.S19_MIN_RR}")

    
    elif data == "toggle_s20_5_enabled":
        config.S20_5_ENABLED = not getattr(config, "S20_5_ENABLED", False)
        # sync active_strategies ให้ตรงกับ flag จริง (สำหรับ display ในรายการ Strategy)
        active_strategies[20.5] = config.S20_5_ENABLED
        config.active_strategies[20.5] = config.S20_5_ENABLED
        save_runtime_state()
        await _show_strategy_detail(query, 20.5)

    elif data == "toggle_s20_6_enabled":
        config.S20_6_FVG_ENABLED = not getattr(config, "S20_6_FVG_ENABLED", False)
        active_strategies[20.6] = config.S20_6_FVG_ENABLED
        config.active_strategies[20.6] = config.S20_6_FVG_ENABLED
        save_runtime_state()
        await _show_strategy_detail(query, 20.6)

    elif data == "toggle_s20_7_enabled":
        config.S20_7_ENABLED = not getattr(config, "S20_7_ENABLED", False)
        active_strategies[20.7] = config.S20_7_ENABLED
        config.active_strategies[20.7] = config.S20_7_ENABLED
        save_runtime_state()
        await _show_strategy_detail(query, 20.7)

    elif data == "toggle_s20_8_enabled":
        # S20.8 uses active_strategies directly since it's a standard strategy
        current_val = active_strategies.get(20.8, False)
        active_strategies[20.8] = not current_val
        config.active_strategies[20.8] = not current_val
        save_runtime_state()
        await _show_strategy_detail(query, 20.8)

    elif data == "toggle_s20_enabled":
        config.S20_ENABLED = not getattr(config, "S20_ENABLED", False)
        save_runtime_state()
        status = "ON" if config.S20_ENABLED else "OFF"
        await _show_strategy_detail(query, 20, f"✅ ท่า 20 (Master): {status}")

    elif data.startswith("toggle_s20_trigger_"):
        trigger_id = data.replace("toggle_s20_trigger_", "")
        key_map = {
            "defect": "S20_TRIGGER_DEFECT",
            "2l2h": "S20_TRIGGER_2L2H",
            "solid": "S20_TRIGGER_SOLID_CLEAR",
            "fvg": "S20_TRIGGER_FVG_OB",
            "fibo": "S20_TRIGGER_FIBO_ENTRY"
        }
        key = key_map.get(trigger_id)
        if key:
            new_val = not getattr(config, key, True)
            setattr(config, key, new_val)
            save_runtime_state()
            status = "ON" if new_val else "OFF"
            await _show_strategy_detail(query, 20, f"✅ S20 Trigger ({trigger_id.upper()}): {status}")
        else:
            await _qanswer(query, "Trigger ไม่ถูกต้อง")

    elif data.startswith("toggle_s20_mod_"):
        mod_id = data.replace("toggle_s20_mod_", "")
        key_map = {
            "magic": "S20_MODIFIER_MAGIC_NUM",
            "nobody": "S20_MODIFIER_NO_BODY_BRK",
            "fibo": "S20_MODIFIER_FIBO_CONF"
        }
        key = key_map.get(mod_id)
        if key:
            new_val = not getattr(config, key, True)
            setattr(config, key, new_val)
            save_runtime_state()
            status = "ON" if new_val else "OFF"
            await _show_strategy_detail(query, 20, f"✅ S20 Modifier ({mod_id.upper()}): {status}")
        else:
            await _qanswer(query, "Modifier ไม่ถูกต้อง")

    elif data == "toggle_s20_trend":
        config.S20_TREND_FILTER = not getattr(config, "S20_TREND_FILTER", True)
        save_runtime_state()
        status = "ON" if config.S20_TREND_FILTER else "OFF"
        await _show_strategy_detail(query, 20, f"✅ ท่า 20 Trend Filter: {status}")

    elif data == "toggle_s20_session":
        config.S20_SESSION_FILTER = not getattr(config, "S20_SESSION_FILTER", True)
        save_runtime_state()
        status = "ON" if config.S20_SESSION_FILTER else "OFF"
        await _show_strategy_detail(query, 20, f"✅ ท่า 20 Session Filter: {status}")

    elif data.startswith("set_trail_engulf_mode_"):
        mode = data.replace("set_trail_engulf_mode_", "")
        if mode not in ("combined", "separate"):
            await _qanswer(query,"ไม่พบโหมดนี้")
            return

        config.TRAIL_SL_MODE = "engulf"
        config.TRAIL_SL_ENGULF_MODE = mode

        try:
            import trailing
            trailing._trail_state.clear()
            trailing._bar_count.clear()
        except Exception:
            pass

        trail_mode_label = "รวม phase" if config.TRAIL_SL_ENGULF_MODE == "combined" else "แยก phase"
        try:
            await query.edit_message_text(
                "📐 *Trail SL -> Engulf*\n"
                "━━━━━━━━━━━━━━━━━\n"
                "เลือกวิธีการทำงาน:\n"
                f"ปัจจุบัน: *{trail_mode_label}*\n\n"
                "รวม phase = ดูทุก TF ใน group พร้อมกัน และเลื่อน SL ต่อเนื่องเมื่อเจอ engulf\n"
                "แยก phase = TF เล็กกว่า -> TF order -> จบ",
                parse_mode="Markdown",
                reply_markup=build_trail_engulf_keyboard()
            )
        except Exception as e:
            if "not modified" not in str(e).lower():
                _log_cb_error("set_trail_engulf_mode", e)
        save_runtime_state()
        await _qanswer(query,f"✅ Trail SL Engulf: {trail_mode_label}")

    elif data == "toggle_trail_immediate":
        config.TRAIL_SL_IMMEDIATE = not config.TRAIL_SL_IMMEDIATE
        save_runtime_state()
        trail_mode_label = "รวม phase" if config.TRAIL_SL_ENGULF_MODE == "combined" else "แยก phase"
        imm_status = "เปิด" if config.TRAIL_SL_IMMEDIATE else "ปิด"
        try:
            await query.edit_message_text(
                "📐 *ตั้งค่า Trail SL*\n"
                "━━━━━━━━━━━━━━━━━\n"
                f"โหมดปัจจุบัน: *Engulf / {trail_mode_label}*\n"
                f"Trail ทันที: *{'ON' if config.TRAIL_SL_IMMEDIATE else 'OFF'}*\n\n"
                "เลือกประเภท Trail SL:",
                parse_mode="Markdown",
                reply_markup=build_trail_menu()
            )
        except Exception as e:
            if "not modified" not in str(e).lower():
                _log_cb_error("toggle_trail_immediate", e)
        await _qanswer(query,f"Trail ทันที: {imm_status}")

    elif data == "open_trail_focus_menu":
        await show_trail_focus_menu(query, is_query=True)
        await _qanswer(query)

    elif data == "toggle_trail_focus_new":
        config.TRAIL_SL_FOCUS_NEW_ENABLED = not config.TRAIL_SL_FOCUS_NEW_ENABLED
        if config.TRAIL_SL_FOCUS_NEW_ENABLED:
            from trailing import reset_focus_frozen_side
            reset_focus_frozen_side("trail_sl")
        save_runtime_state()
        await show_trail_focus_menu(query, is_query=True)
        await _qanswer(query,f"Trail Focus: {'ON' if config.TRAIL_SL_FOCUS_NEW_ENABLED else 'OFF'}")

    elif data == "toggle_tfn_tf_mode":
        config.TRAIL_SL_FOCUS_NEW_TF_MODE = (
            "combined" if config.TRAIL_SL_FOCUS_NEW_TF_MODE == "separate" else "separate"
        )
        save_runtime_state()
        await show_trail_focus_menu(query, is_query=True)
        tf_desc = "รวมทุก TF" if config.TRAIL_SL_FOCUS_NEW_TF_MODE == "combined" else "แยกตาม TF"
        await _qanswer(query,f"Trail Focus TF: {tf_desc}")

    elif data.startswith("set_tfn_pts_"):
        pts = int(data.replace("set_tfn_pts_", ""))
        config.TRAIL_SL_FOCUS_NEW_POINTS = pts
        save_runtime_state()
        await show_trail_focus_menu(query, is_query=True)
        await _qanswer(query,f"Trail Focus Threshold: {pts} จุด")

    elif data == "open_entry_focus_menu":
        await show_entry_focus_menu(query, is_query=True)
        await _qanswer(query)

    elif data == "toggle_entry_focus_new":
        config.ENTRY_CANDLE_FOCUS_NEW_ENABLED = not config.ENTRY_CANDLE_FOCUS_NEW_ENABLED
        if config.ENTRY_CANDLE_FOCUS_NEW_ENABLED:
            from trailing import reset_focus_frozen_side
            reset_focus_frozen_side("entry_candle")
        save_runtime_state()
        await show_entry_focus_menu(query, is_query=True)
        await _qanswer(query,f"Entry Focus: {'ON' if config.ENTRY_CANDLE_FOCUS_NEW_ENABLED else 'OFF'}")

    elif data == "toggle_efn_tf_mode":
        config.ENTRY_CANDLE_FOCUS_NEW_TF_MODE = (
            "combined" if config.ENTRY_CANDLE_FOCUS_NEW_TF_MODE == "separate" else "separate"
        )
        save_runtime_state()
        await show_entry_focus_menu(query, is_query=True)
        tf_desc = "รวมทุก TF" if config.ENTRY_CANDLE_FOCUS_NEW_TF_MODE == "combined" else "แยกตาม TF"
        await _qanswer(query,f"Entry Focus TF: {tf_desc}")

    elif data.startswith("set_efn_pts_"):
        pts = int(data.replace("set_efn_pts_", ""))
        config.ENTRY_CANDLE_FOCUS_NEW_POINTS = pts
        save_runtime_state()
        await show_entry_focus_menu(query, is_query=True)
        await _qanswer(query,f"Entry Focus Threshold: {pts} จุด")

    elif data == "open_trend_filter_menu":
        await show_trend_filter_menu(query, is_query=True)
        await _qanswer(query)

    elif data == "open_sl_guard_menu":
        await show_sl_guard_menu(query, is_query=True)
        await _qanswer(query)

    elif data == "select_sl_guard_per_tf":
        config.SL_GUARD_ENABLED = True
        config.SL_GUARD_COMBINED_ENABLED = False
        config.SL_GUARD_GROUP_ENABLED = False
        save_runtime_state()
        await show_sl_guard_menu(query, is_query=True)
        await _qanswer(query, "SL Guard: แบบแยก (Per-TF)")

    elif data == "select_sl_guard_combined":
        config.SL_GUARD_ENABLED = False
        config.SL_GUARD_COMBINED_ENABLED = True
        config.SL_GUARD_GROUP_ENABLED = False
        save_runtime_state()
        await show_sl_guard_menu(query, is_query=True)
        await _qanswer(query, "SL Guard: แบบรวม (Combined)")

    elif data == "select_sl_guard_group":
        config.SL_GUARD_ENABLED = False
        config.SL_GUARD_COMBINED_ENABLED = False
        config.SL_GUARD_GROUP_ENABLED = True
        save_runtime_state()
        await show_sl_guard_menu(query, is_query=True)
        await _qanswer(query, "SL Guard: แบบ Group")

    elif data == "select_sl_guard_off":
        config.SL_GUARD_ENABLED = False
        config.SL_GUARD_COMBINED_ENABLED = False
        config.SL_GUARD_GROUP_ENABLED = False
        save_runtime_state()
        await show_sl_guard_menu(query, is_query=True)
        await _qanswer(query, "SL Guard: ปิดทั้งหมด")

    elif data == "open_sl_guard_per_tf":
        await show_sl_guard_per_tf_menu(query, is_query=True)
        await _qanswer(query)

    elif data == "open_sl_guard_combined":
        await show_sl_guard_combined_menu(query, is_query=True)
        await _qanswer(query)

    elif data == "open_sl_guard_group":
        await show_sl_guard_group_menu(query, is_query=True)
        await _qanswer(query)

    elif data.startswith("toggle_trend_filter_per_tf_"):
        tf = data.replace("toggle_trend_filter_per_tf_", "")
        if tf == "ALL":
            all_on = all(config.TREND_FILTER_PER_TF.values())
            for t in config.TREND_FILTER_PER_TF:
                config.TREND_FILTER_PER_TF[t] = not all_on
            save_runtime_state()
            await show_trend_filter_menu(query, is_query=True)
            await _qanswer(query,"ยกเลิกทุก TF" if all_on else "เลือกทุก TF")
        elif tf in config.TREND_FILTER_PER_TF:
            config.TREND_FILTER_PER_TF[tf] = not config.TREND_FILTER_PER_TF[tf]
            save_runtime_state()
            await show_trend_filter_menu(query, is_query=True)
            await _qanswer(query,f"Per-TF {tf}: {'ON' if config.TREND_FILTER_PER_TF[tf] else 'OFF'}")
        else:
            await _qanswer(query,"TF ไม่ถูกต้อง")

    elif data in ("noop_trend_filter", "noop_sl_atr"):
        await _qanswer(query)

    elif data == "toggle_trend_filter_higher_tf":
        config.TREND_FILTER_HIGHER_TF_ENABLED = not config.TREND_FILTER_HIGHER_TF_ENABLED
        save_runtime_state()
        await show_trend_filter_menu(query, is_query=True)
        await _qanswer(query,f"Trend Filter Higher TF: {'ON' if config.TREND_FILTER_HIGHER_TF_ENABLED else 'OFF'}")

    elif data == "toggle_trend_filter_trail_sl_override":
        config.TREND_FILTER_TRAIL_SL_OVERRIDE_ENABLED = not config.TREND_FILTER_TRAIL_SL_OVERRIDE_ENABLED
        save_runtime_state()
        await show_trend_filter_menu(query, is_query=True)
        await _qanswer(query,
            f"Trend Filter Trail SL Override: {'ON' if config.TREND_FILTER_TRAIL_SL_OVERRIDE_ENABLED else 'OFF'}"
        )

    elif data.startswith("set_trend_filter_higher_tf_"):
        tf = data.replace("set_trend_filter_higher_tf_", "")
        if tf in TF_OPTIONS:
            config.TREND_FILTER_HIGHER_TF = tf
            save_runtime_state()
            await show_trend_filter_menu(query, is_query=True)
            await _qanswer(query,f"Higher TF: {tf}")
        else:
            await _qanswer(query,"TF ไม่ถูกต้อง")

    elif data.startswith("set_trend_filter_mode_"):
        mode = data.replace("set_trend_filter_mode_", "")
        if mode in ("basic", "breakout"):
            config.TREND_FILTER_MODE = mode
            save_runtime_state()
            await show_trend_filter_menu(query, is_query=True)
            await _qanswer(query,f"Trend Filter Mode: {mode}")
        else:
            await _qanswer(query,"Mode ไม่ถูกต้อง")

    elif data.startswith("toggle_strategy_"):
        _sid_val = float(data.split("_")[-1]); sid = int(_sid_val) if _sid_val.is_integer() else _sid_val
        if sid in active_strategies:
            active_strategies[sid] = not active_strategies[sid]
            config.active_strategies[sid] = active_strategies[sid]
            save_runtime_state()
            name      = STRATEGY_NAMES.get(sid, f"ท่าที่ {sid}")
            status_th = "เปิด ✅" if active_strategies[sid] else "ปิด ❌"
            await _show_strategy_detail(query, sid, f"{name}: {status_th}")

    elif data in ("strategy_all_on", "strategy_all_off"):
        # strategy_all_on = เปิดทั้งหมด, strategy_all_off = ปิดทั้งหมด
        turn_on = (data == "strategy_all_on")
        for sid in active_strategies:
            active_strategies[sid] = turn_on
            config.active_strategies[sid] = turn_on
        # S20.5/S20.6 ใช้ flag แยก — sync ตามด้วยเพื่อให้ execution ตรงกับที่กด
        config.S20_5_ENABLED = turn_on
        config.S20_6_FVG_ENABLED = turn_on
        save_runtime_state()
        active_list = [STRATEGY_NAMES[s] for s in active_strategies if _strategy_is_on(s)]
        summary = " + ".join(active_list) if active_list else "ไม่มี"
        new_text = (
            "📋 *เลือก Strategy*\n"
            "━━━━━━━━━━━━━━━━━\n"
            f"🔄 ที่เปิดอยู่: *{summary}*\n\n"
            "กดเพื่อเปิด/ปิด (เลือกพร้อมกันได้):"
        )
        try:
            await query.edit_message_text(
                new_text,
                parse_mode="Markdown",
                reply_markup=build_strategy_keyboard()
            )
        except Exception as e:
            if "not modified" not in str(e).lower():
                raise
        await _qanswer(query,"เปิดทั้งหมด ✅" if turn_on else "ปิดทั้งหมด ❌")

    elif data == "cancel_pending":
        await _qanswer(query,"⏳ กำลังยกเลิก...")
        if not connect_mt5():
            await query.edit_message_text("❌ MT5 ไม่ได้เชื่อมต่อ")
            return
        orders = mt5.orders_get(symbol=SYMBOL)
        if not orders:
            await query.edit_message_text("📭 ไม่มี Pending Order")
            return
        cancelled = 0
        failed    = 0
        for o in orders:
            r = mt5.order_send({
                "action": mt5.TRADE_ACTION_REMOVE,
                "order":  o.ticket,
            })
            if r and r.retcode == mt5.TRADE_RETCODE_DONE:
                cancelled += 1
            else:
                failed += 1
        txt = f"✅ ยกเลิก Pending สำเร็จ {cancelled} Order"
        if failed:
            txt += "\n⚠️ ยกเลิกไม่สำเร็จ " + str(failed) + " Order"
        # ล้าง fvg_pending และ pb_pending ด้วย
        fvg_pending.clear()
        pb_pending.clear()
        save_runtime_state()
        await query.edit_message_text(txt)

    elif data == "confirm_close":
        await query.edit_message_text("⏳ ปิดทุก Order...")
        if not connect_mt5():
            await query.edit_message_text("❌ MT5 ไม่ได้เชื่อมต่อ")
            return
        positions = mt5.positions_get(symbol=SYMBOL)
        if not positions:
            await query.edit_message_text("📭 ไม่มี Order")
            return
        closed = 0
        for p in positions:
            tick = mt5.symbol_info_tick(p.symbol)
            if not tick:
                continue
            price = tick.bid if p.type == mt5.ORDER_TYPE_BUY else tick.ask
            ct    = mt5.ORDER_TYPE_SELL if p.type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY
            r     = mt5.order_send({
                "action": mt5.TRADE_ACTION_DEAL, "symbol": p.symbol,
                "volume": p.volume, "type": ct, "position": p.ticket,
                "price": price, "deviation": 20, "magic": 234001,
                "comment": "CloseAll", "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_FOK,
            })
            if r.retcode == mt5.TRADE_RETCODE_DONE:
                closed += 1
        await query.edit_message_text(f"✅ ปิดสำเร็จ {closed} Order")
        await _qanswer(query,"ปิด Order แล้ว")

    elif data == "open_limit_guard_menu":
        await show_limit_guard_menu(query, is_query=True)
        await _qanswer(query)

    elif data == "open_limit_break_menu":
        await show_limit_break_menu(query, is_query=True)
        await _qanswer(query)

    elif data == "open_engulf_menu":
        await show_engulf_menu(query, is_query=True)
        await _qanswer(query)

    elif data == "toggle_limit_sweep":
        config.LIMIT_SWEEP = not config.LIMIT_SWEEP
        save_runtime_state()
        await show_main_settings_menu(query, is_query=True)
        await _qanswer(query,f"Limit Sweep: {'ON' if config.LIMIT_SWEEP else 'OFF'}")

    elif data == "toggle_scale_out":
        # ── Toggle Triple Scale-Out (TSO) ──────────────────────────
        new_state = not config.SCALE_OUT_ENABLED
        config.SCALE_OUT_ENABLED = new_state
        # ถ้าเปลี่ยนเป็น OFF → ปิด position TSO ทั้งหมด + ลด lot pending กลับเป็น base
        cleanup_msg = ""
        if not new_state:
            try:
                from trailing import scale_out_cleanup_on_disable
                summary = scale_out_cleanup_on_disable()
                cleanup_msg = (
                    f"\n• ปิด position: {summary.get('closed', 0)}"
                    f"\n• Reset pending lot: {summary.get('reset_pending', 0)}"
                )
                if summary.get("errors"):
                    cleanup_msg += f"\n⚠️ errors: {summary['errors']}"
            except Exception as e:
                cleanup_msg = f"\n⚠️ cleanup error: {e}"
        save_runtime_state()
        await show_main_settings_menu(query, is_query=True)
        status_label = "ON" if new_state else "OFF"
        await _qanswer(query,f"Scale-Out 4X: {status_label}{cleanup_msg}")

    elif data == "open_risk_health_menu":
        await show_risk_health_menu(query, is_query=True)
        await _qanswer(query)

    elif data == "toggle_news_filter":
        new_val = not getattr(config, "NEWS_FILTER_ENABLED", False)
        setattr(config, "NEWS_FILTER_ENABLED", new_val)
        save_runtime_state()
        await show_main_settings_menu(query, is_query=True)
        await _qanswer(query, f"News Filter: {'ON' if new_val else 'OFF'}")

    elif data == "toggle_ml_scoring":
        new_val = not getattr(config, "ML_SCORING_ENABLED", False)
        setattr(config, "ML_SCORING_ENABLED", new_val)
        save_runtime_state()
        await show_main_settings_menu(query, is_query=True)
        await _qanswer(query, f"ML Scoring: {'ON' if new_val else 'OFF'}")

    elif data == "toggle_observable_mode":
        new_val = not getattr(config, "OBSERVABLE_MODE", False)
        setattr(config, "OBSERVABLE_MODE", new_val)
        save_runtime_state()
        await show_main_settings_menu(query, is_query=True)
        await _qanswer(query, f"Observable Mode: {'ON' if new_val else 'OFF'}")

    elif data == "toggle_daily_loss_limit":
        config.DAILY_LOSS_LIMIT_ENABLED = not config.DAILY_LOSS_LIMIT_ENABLED
        save_runtime_state()
        await show_risk_health_menu(query, is_query=True)
        await _qanswer(query, f"Daily Loss Limit: {'ON' if config.DAILY_LOSS_LIMIT_ENABLED else 'OFF'}")

    elif data.startswith("set_dll_usd_"):
        try:
            config.DAILY_LOSS_LIMIT_USD = float(int(data.replace("set_dll_usd_", "")))
            save_runtime_state()
        except Exception as e:
            _log_cb_error("set_dll_usd", e)
        await show_risk_health_menu(query, is_query=True)
        await _qanswer(query, f"เพดานขาดทุน: ${config.DAILY_LOSS_LIMIT_USD:.0f}")

    elif data == "toggle_daily_summary":
        config.DAILY_SUMMARY_ENABLED = not config.DAILY_SUMMARY_ENABLED
        save_runtime_state()
        await show_risk_health_menu(query, is_query=True)
        await _qanswer(query, f"Daily Summary: {'ON' if config.DAILY_SUMMARY_ENABLED else 'OFF'}")

    elif data == "send_daily_summary_now":
        connect_mt5()
        try:
            await query.message.reply_text(config.build_daily_summary_text(), parse_mode="Markdown")
        except Exception as e:
            _log_cb_error("send_daily_summary_now", e)
        await _qanswer(query, "ส่งสรุปแล้ว")

    elif data == "toggle_risk_percent":
        config.RISK_PERCENT_ENABLED = not config.RISK_PERCENT_ENABLED
        save_runtime_state()
        await show_risk_health_menu(query, is_query=True)
        await _qanswer(query, f"Dynamic Lot: {'ON' if config.RISK_PERCENT_ENABLED else 'OFF'}")

    elif data.startswith("set_risk_pct_"):
        try:
            config.RISK_PERCENT = float(data.replace("set_risk_pct_", ""))
            save_runtime_state()
        except Exception as e:
            _log_cb_error("set_risk_pct", e)
        await show_risk_health_menu(query, is_query=True)
        await _qanswer(query, f"Risk: {config.RISK_PERCENT}%")

    elif data == "toggle_watchdog":
        config.WATCHDOG_ENABLED = not config.WATCHDOG_ENABLED
        save_runtime_state()
        await show_risk_health_menu(query, is_query=True)
        await _qanswer(query, f"Watchdog: {'ON' if config.WATCHDOG_ENABLED else 'OFF'}")

    elif data == "cycle_delay_sl":
        cycle = {"off": "time", "time": "price", "price": "off"}
        config.DELAY_SL_MODE = cycle.get(config.DELAY_SL_MODE, "off")
        save_runtime_state()
        label = {"off": "ปิด", "time": "ช่วงท้าย TF", "price": "ราคาผ่าน Entry"}.get(config.DELAY_SL_MODE, "ปิด")
        await show_main_settings_menu(query, is_query=True)
        await _qanswer(query,f"Delay SL: {label}")

    elif data == "toggle_trend_filter_scan_block":
        config.TREND_FILTER_SCAN_BLOCK = not config.TREND_FILTER_SCAN_BLOCK
        save_runtime_state()
        await show_trend_filter_menu(query, is_query=True)
        await _qanswer(query,f"Scan Block: {'ON' if config.TREND_FILTER_SCAN_BLOCK else 'OFF'}")

    elif data == "toggle_limit_trend_recheck":
        config.LIMIT_TREND_RECHECK = not config.LIMIT_TREND_RECHECK
        save_runtime_state()
        await show_trend_filter_menu(query, is_query=True)
        await _qanswer(query,f"Trend Recheck: {'ON' if config.LIMIT_TREND_RECHECK else 'OFF'}")

    elif data.startswith("set_ltr_rounds_"):
        rds = int(data.replace("set_ltr_rounds_", ""))
        if rds in (1, 2, 3):
            config.LIMIT_TREND_RECHECK_ROUNDS = rds
            save_runtime_state()
            await show_trend_filter_menu(query, is_query=True)
            await _qanswer(query, f"Trend Recheck: {rds} round(s)")

    elif data == "toggle_pending_trend_check":
        config.PENDING_TREND_CHECK_ENABLED = not config.PENDING_TREND_CHECK_ENABLED
        save_runtime_state()
        await show_trend_filter_menu(query, is_query=True)
        await _qanswer(query, f"Pending Trend Check: {'ON' if config.PENDING_TREND_CHECK_ENABLED else 'OFF'}")

    elif data.startswith("set_ptc_pts_"):
        pts = int(data.replace("set_ptc_pts_", ""))
        config.PENDING_TREND_CHECK_POINTS = pts
        save_runtime_state()
        await show_trend_filter_menu(query, is_query=True)
        await _qanswer(query, f"Pending Trend Check: {pts}pt")

    elif data.startswith("set_ptc_rounds_"):
        rds = int(data.replace("set_ptc_rounds_", ""))
        if rds in (1, 2):
            config.PENDING_TREND_CHECK_ROUNDS = rds
            save_runtime_state()
            await show_trend_filter_menu(query, is_query=True)
            await _qanswer(query, f"Pending Trend Check: {rds} round(s)")

    elif data == "toggle_near_approach_cancel":
        config.NEAR_APPROACH_CANCEL_ENABLED = not config.NEAR_APPROACH_CANCEL_ENABLED
        save_runtime_state()
        await show_trend_filter_menu(query, is_query=True)
        await _qanswer(query,f"Near Approach Cancel: {'ON' if config.NEAR_APPROACH_CANCEL_ENABLED else 'OFF'}")

    elif data.startswith("set_nac_pts_"):
        pts = int(data.replace("set_nac_pts_", ""))
        config.NEAR_APPROACH_CANCEL_POINTS = pts
        save_runtime_state()
        await show_trend_filter_menu(query, is_query=True)
        await _qanswer(query,f"Near Approach Cancel: {pts}pt")

    elif data == "toggle_recheck_combined_mode":
        config.RECHECK_COMBINED_MODE = not config.RECHECK_COMBINED_MODE
        save_runtime_state()
        await show_trend_filter_menu(query, is_query=True)
        mode_txt = "รวม 2/3" if config.RECHECK_COMBINED_MODE else "แยก"
        await _qanswer(query, f"Recheck Mode: {mode_txt}")

    elif data == "toggle_pdfiboplus":
        config.PDFIBOPLUS_ENABLED = not config.PDFIBOPLUS_ENABLED
        save_runtime_state()
        await show_trend_filter_menu(query, is_query=True)
        await _qanswer(query, f"PD Fibo Plus: {'ON' if config.PDFIBOPLUS_ENABLED else 'OFF'}")

    elif data == "toggle_sideway_hhll_filter":
        config.TREND_FILTER_SIDEWAY_HHLL = not getattr(config, "TREND_FILTER_SIDEWAY_HHLL", True)
        save_runtime_state()
        await show_trend_filter_menu(query, is_query=True)
        await _qanswer(query, f"Sideway HHLL Filter: {'ON' if config.TREND_FILTER_SIDEWAY_HHLL else 'OFF'}")

    elif data == "toggle_sweep_filter":
        import sweep_filter as _swf
        config.SWEEP_FILTER_ENABLED = not getattr(config, "SWEEP_FILTER_ENABLED", False)
        if not config.SWEEP_FILTER_ENABLED:
            _swf.reset_all()   # clear state เมื่อปิด
        save_runtime_state()
        await show_trend_filter_menu(query, is_query=True)
        await _qanswer(query, f"Sweep Filter: {'ON' if config.SWEEP_FILTER_ENABLED else 'OFF'}")

    elif data == "show_sweep_status":
        import sweep_filter as _swf
        txt = _swf.get_status_text()
        try:
            await query.message.reply_text(txt, parse_mode="Markdown")
        except Exception:
            await query.message.reply_text(txt.replace("*", "").replace("_", "").replace("`", ""))
        await _qanswer(query)

    elif data == "toggle_sl_atr":
        config.SL_ATR_ENABLED = not getattr(config, "SL_ATR_ENABLED", True)
        save_runtime_state()
        await show_advanced_settings(query, is_query=True)
        _mult = int(getattr(config, "SL_ATR_MULT", 2))
        await _qanswer(query, f"SL ATR: {'ON ×' + str(_mult) if config.SL_ATR_ENABLED else 'OFF (Fixed buffer)'}")

    elif data.startswith("set_sl_atr_mult_"):
        _m = int(data.replace("set_sl_atr_mult_", ""))
        if _m in (1, 2, 3, 4, 5):
            config.SL_ATR_MULT = _m
            save_runtime_state()
        await show_advanced_settings(query, is_query=True)
        await _qanswer(query, f"SL ATR Mult: ×{_m}")

    elif data == "toggle_sl_guard":
        # ถ้าเปิดอยู่ → ปิดทั้งหมด; ถ้าปิดอยู่ → เปิดแบบแยก (select mode)
        if config.SL_GUARD_ENABLED:
            config.SL_GUARD_ENABLED = False
        else:
            config.SL_GUARD_ENABLED = True
            config.SL_GUARD_COMBINED_ENABLED = False
            config.SL_GUARD_GROUP_ENABLED = False
        save_runtime_state()
        await show_sl_guard_per_tf_menu(query, is_query=True)
        await _qanswer(query, f"SL Guard Per-TF: {'ON' if config.SL_GUARD_ENABLED else 'OFF'}")

    elif data.startswith("set_sl_guard_count_"):
        cnt = int(data.replace("set_sl_guard_count_", ""))
        config.SL_GUARD_COUNT = cnt
        save_runtime_state()
        await show_sl_guard_per_tf_menu(query, is_query=True)
        await _qanswer(query, f"SL Guard Count: {cnt}x")

    elif data.startswith("set_sl_guard_pts_"):
        pts = int(data.replace("set_sl_guard_pts_", ""))
        config.SL_GUARD_NEAR_POINTS = pts
        save_runtime_state()
        await show_sl_guard_per_tf_menu(query, is_query=True)
        await _qanswer(query, f"SL Guard Near: {pts}pt")

    elif data == "toggle_sl_guard_loss":
        config.SL_GUARD_LOSS_ENABLED = not getattr(config, "SL_GUARD_LOSS_ENABLED", False)
        save_runtime_state()
        await show_sl_guard_menu(query, is_query=True)
        await _qanswer(query, f"Loss Guard: {'ON' if config.SL_GUARD_LOSS_ENABLED else 'OFF'}")

    elif data == "toggle_sl_guard_close_activate":
        config.SL_GUARD_CLOSE_ON_ACTIVATE = not getattr(config, "SL_GUARD_CLOSE_ON_ACTIVATE", True)
        save_runtime_state()
        await show_sl_guard_menu(query, is_query=True)
        await _qanswer(query, f"Close on Activate: {'ON' if config.SL_GUARD_CLOSE_ON_ACTIVATE else 'OFF'}")

    elif data.startswith("set_sl_guard_loss_thr_"):
        thr = float(data.replace("set_sl_guard_loss_thr_", ""))
        config.SL_GUARD_LOSS_THRESHOLD = thr
        save_runtime_state()
        await show_sl_guard_menu(query, is_query=True)
        await _qanswer(query, f"Loss Guard Threshold: ${thr:.0f}")

    elif data == "toggle_sl_guard_combined":
        if config.SL_GUARD_COMBINED_ENABLED:
            config.SL_GUARD_COMBINED_ENABLED = False
        else:
            config.SL_GUARD_ENABLED = False
            config.SL_GUARD_COMBINED_ENABLED = True
            config.SL_GUARD_GROUP_ENABLED = False
        save_runtime_state()
        await show_sl_guard_combined_menu(query, is_query=True)
        await _qanswer(query, f"Combined Guard: {'ON' if config.SL_GUARD_COMBINED_ENABLED else 'OFF'}")

    elif data.startswith("set_slgc_count_"):
        try:
            cnt = int(data.replace("set_slgc_count_", ""))
            config.SL_GUARD_COMBINED_COUNT = max(1, cnt)
            save_runtime_state()
            await show_sl_guard_combined_menu(query, is_query=True)
            await _qanswer(query, f"Combined Guard Count: {cnt}x")
        except (ValueError, TypeError):
            await _qanswer(query, "ค่าไม่ถูกต้อง")

    elif data.startswith("toggle_slgc_tf_"):
        tf_toggle = data.replace("toggle_slgc_tf_", "")
        _tf_all = ["M1", "M5", "M15", "M30", "H1", "H4", "H12", "D1"]
        if tf_toggle in _tf_all:
            _tfs = list(getattr(config, "SL_GUARD_COMBINED_TFS", []) or [])
            if tf_toggle in _tfs:
                _tfs.remove(tf_toggle)
            else:
                _tfs.append(tf_toggle)
            config.SL_GUARD_COMBINED_TFS = _tfs
            save_runtime_state()
            await show_sl_guard_combined_menu(query, is_query=True)
            _on = tf_toggle in config.SL_GUARD_COMBINED_TFS
            await _qanswer(query, f"Combined Guard TF {tf_toggle}: {'ON' if _on else 'OFF'}")

    elif data == "toggle_sl_guard_group":
        if config.SL_GUARD_GROUP_ENABLED:
            config.SL_GUARD_GROUP_ENABLED = False
        else:
            config.SL_GUARD_ENABLED = False
            config.SL_GUARD_COMBINED_ENABLED = False
            config.SL_GUARD_GROUP_ENABLED = True
        save_runtime_state()
        await show_sl_guard_group_menu(query, is_query=True)
        await _qanswer(query, f"Group Guard: {'ON' if config.SL_GUARD_GROUP_ENABLED else 'OFF'}")

    elif data.startswith("set_slgg_count_"):
        try:
            cnt = int(data.replace("set_slgg_count_", ""))
            config.SL_GUARD_GROUP_COUNT = max(1, cnt)
            save_runtime_state()
            await show_sl_guard_group_menu(query, is_query=True)
            await _qanswer(query, f"Group Guard Count: {cnt}x")
        except (ValueError, TypeError):
            await _qanswer(query, "ค่าไม่ถูกต้อง")

    elif data == "toggle_pending_rsi_recheck":
        config.PENDING_RSI_RECHECK_ENABLED = not config.PENDING_RSI_RECHECK_ENABLED
        save_runtime_state()
        await show_trend_filter_menu(query, is_query=True)
        await _qanswer(query,f"Pending RSI Recheck: {'ON' if config.PENDING_RSI_RECHECK_ENABLED else 'OFF'}")

    elif data in ("set_rsi_mode_1", "set_rsi_mode_2", "set_rsi_mode_3"):
        _mode_map  = {"set_rsi_mode_1": 1, "set_rsi_mode_2": 2, "set_rsi_mode_3": 3}
        _mode_name = {"set_rsi_mode_1": "Level", "set_rsi_mode_2": "Cross", "set_rsi_mode_3": "Both"}
        config.PENDING_RSI_RECHECK_MODE = _mode_map[data]
        save_runtime_state()
        await show_trend_filter_menu(query, is_query=True)
        await _qanswer(query,f"RSI Mode: {_mode_name[data]}")

    elif data == "toggle_limit_break_cancel":
        config.LIMIT_BREAK_CANCEL = not config.LIMIT_BREAK_CANCEL
        save_runtime_state()
        await show_limit_break_menu(query, is_query=True)
        await _qanswer(query,f"Limit TP/SL Break: {'ON' if config.LIMIT_BREAK_CANCEL else 'OFF'}")

    elif data == "toggle_lbc_tf_ALL":
        all_on = all(config.LIMIT_BREAK_CANCEL_TF.values())
        for tf_name in config.LIMIT_BREAK_CANCEL_TF:
            config.LIMIT_BREAK_CANCEL_TF[tf_name] = not all_on
        save_runtime_state()
        await show_limit_break_menu(query, is_query=True)
        await _qanswer(query,"เลือกทุก TF แล้ว" if not all_on else "ยกเลิกทุก TF แล้ว")

    elif data.startswith("toggle_lbc_tf_"):
        tf_name = data.replace("toggle_lbc_tf_", "")
        if tf_name in config.LIMIT_BREAK_CANCEL_TF:
            config.LIMIT_BREAK_CANCEL_TF[tf_name] = not config.LIMIT_BREAK_CANCEL_TF[tf_name]
            save_runtime_state()
            await show_limit_break_menu(query, is_query=True)
            await _qanswer(query,f"Limit TP/SL Break TF {tf_name}: {'ON' if config.LIMIT_BREAK_CANCEL_TF[tf_name] else 'OFF'}")
        else:
            await _qanswer(query,"ไม่พบ TF นี้")

    elif data == "toggle_limit_guard":
        config.LIMIT_GUARD = not config.LIMIT_GUARD
        save_runtime_state()
        await show_limit_guard_menu(query, is_query=True)
        await _qanswer(query,f"Limit Guard: {'ON' if config.LIMIT_GUARD else 'OFF'}")

    elif data == "toggle_lg_tf_mode":
        config.LIMIT_GUARD_TF_MODE = "combined" if config.LIMIT_GUARD_TF_MODE == "separate" else "separate"
        save_runtime_state()
        await show_limit_guard_menu(query, is_query=True)
        tf_desc = "รวมทุก TF" if config.LIMIT_GUARD_TF_MODE == "combined" else "แยกตาม TF"
        await _qanswer(query,f"Limit Guard TF: {tf_desc}")

    elif data.startswith("set_lg_pts_"):
        pts = int(data.replace("set_lg_pts_", ""))
        config.LIMIT_GUARD_POINTS = pts
        save_runtime_state()
        await show_limit_guard_menu(query, is_query=True)
        await _qanswer(query,f"Limit Guard: {pts} จุด")

    elif data.startswith("set_engulf_pts_"):
        pts = int(data.replace("set_engulf_pts_", ""))
        config.ENGULF_MIN_POINTS = pts
        save_runtime_state()
        await show_engulf_menu(query, is_query=True)
        await _qanswer(query,f"Engulf ขั้นต่ำ: {pts} จุด")

    elif data.startswith("profit_sid_"):
        # format: profit_sid_{year}_{month}_{sid}_{trend_filter}
        # trend_filter อาจมี underscore (bull_strong, bear_weak ฯลฯ) ต้อง join ส่วนที่เหลือ
        parts = data.split("_")
        year = int(parts[2])
        month = int(parts[3])
        sid = int(parts[4])
        trend_filter_key = "_".join(parts[5:]) if len(parts) > 5 else "all"
        await show_profit_strategy_detail(query, year, month, sid, trend_filter_key, is_query=True)
        await _qanswer(query)

    elif data.startswith("profit_"):
        # format: profit_{year}_{month}_{trend_filter}
        # trend_filter อาจมี underscore (bull_strong, bear_weak ฯลฯ) ต้อง join ส่วนที่เหลือ
        parts = data.split("_")
        year = int(parts[1])
        month = int(parts[2])
        trend_filter_key = "_".join(parts[3:]) if len(parts) > 3 else "all"
        await show_profit_summary(query, year, month, trend_filter_key, is_query=True)
        await _qanswer(query)

    elif data.startswith("buy_") or data.startswith("sell_"):
        parts     = data.split("_")
        direction = parts[0]
        volume    = float(parts[1])
        if not connect_mt5():
            await query.edit_message_text("❌ MT5 ไม่ได้เชื่อมต่อ")
            return
        tick = mt5.symbol_info_tick(SYMBOL)
        if not tick:
            await query.edit_message_text("❌ ดึงราคาไม่ได้")
            return
        price = tick.ask if direction == "buy" else tick.bid
        sl    = round(price - 15, 2) if direction == "buy" else round(price + 15, 2)
        tp    = round(price + 30, 2) if direction == "buy" else round(price - 30, 2)
        ot    = mt5.ORDER_TYPE_BUY if direction == "buy" else mt5.ORDER_TYPE_SELL
        r     = mt5.order_send({
            "action": mt5.TRADE_ACTION_DEAL, "symbol": SYMBOL,
            "volume": volume, "type": ot, "price": price,
            "sl": sl, "tp": tp, "deviation": 20, "magic": 234001,
            "comment": "Manual", "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_FOK,
        })
        e = "🟢" if direction == "buy" else "🔴"
        if r.retcode == mt5.TRADE_RETCODE_DONE:
            await query.edit_message_text(
                f"✅ *เปิดสำเร็จ!* {e} {direction.upper()} {volume}lot @ `{price}`\n🛑`{sl}` 🎯`{tp}` 🔖`{r.order}`",
                parse_mode='Markdown'
            )
            await _qanswer(query,'เปิด Order สำเร็จ!')
        else:
            await query.edit_message_text(f"❌ ไม่สำเร็จ: {r.retcode} — {r.comment}")
            await _qanswer(query,'เปิด Order ไม่สำเร็จ')

    elif data == 'open_s20_settings_menu':
        from handlers.keyboard import show_s20_settings_menu
        await show_s20_settings_menu(query, is_query=True)

    elif data.startswith('set_s20_trigger_'):
        trigger_id = data.replace("set_s20_trigger_", "")
        key_map = {
            "defect": "S20_TRIGGER_DEFECT",
            "2l2h": "S20_TRIGGER_2L2H",
            "solid": "S20_TRIGGER_SOLID",
            "fvg": "S20_TRIGGER_FVG",
            "fibo_entry": "S20_TRIGGER_FIBO_ENTRY"
        }
        key = key_map.get(trigger_id)
        if key:
            new_val = not getattr(config, key, True)
            setattr(config, key, new_val)
            config.save_runtime_state()
            from handlers.keyboard import show_s20_settings_menu
            await show_s20_settings_menu(query, is_query=True)

    elif data.startswith('set_s20_mod_'):
        mod_id = data.replace("set_s20_mod_", "")
        key_map = {
            "magic": "S20_MODIFIER_MAGIC_NUM",
            "nobody": "S20_MODIFIER_NO_BODY_BRK",
            "fibo": "S20_MODIFIER_FIBO_CONF"
        }
        key = key_map.get(mod_id)
        if key:
            new_val = not getattr(config, key, True)
            setattr(config, key, new_val)
            config.save_runtime_state()
            from handlers.keyboard import show_s20_settings_menu
            await show_s20_settings_menu(query, is_query=True)

    elif data == 'prompt_s20_entry_buffer':
        from config import tg
        msg = await query.message.reply_text("✏️ พิมพ์จำนวนจุดสำหรับ **Entry Buffer** (เช่น 390):")
        ctx.user_data['awaiting_input'] = 's20_entry_buffer'
        ctx.user_data['prompt_msg_id'] = msg.message_id
        await _qanswer(query)

    elif data == 'prompt_s20_sl_2l2h':
        from config import tg
        msg = await query.message.reply_text("✏️ พิมพ์จำนวนจุดสำหรับ **SL 2L/2H** (เช่น 100):")
        ctx.user_data['awaiting_input'] = 's20_sl_2l2h'
        ctx.user_data['prompt_msg_id'] = msg.message_id
        await _qanswer(query)

    else:
        # catch-all: ปิด spinner กันค้าง + log callback_data ที่ไม่มี handler รองรับ
        _log_cb_error("unhandled_callback", RuntimeError(f"no handler for data={data!r}"))
        await _qanswer(query)
