"""
demo_portfolio.py — Live/demo runner for the "Champion" (P13) and "Max-Yield Blend" (P16)
research portfolios, fully independent from the S1-S20 live bot.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
- ไม่แตะ scanner.py / active_strategies / bot_state.json (ไม่เขียนทับ ไม่ใช้ logic ของบอทหลัก)
- เรียก detect_s<N>() ตัวเดียวกับที่ backtest ใช้ ไม่มี logic ซ้ำ
- วางออเดอร์ด้วย mt5.order_send() ตรงๆ (ไม่ผ่าน mt5_utils.open_order_market เพราะจะโดน
  ML_SCORING_ENABLED / SCALE_OUT_ENABLED ที่ config.py เปิดอยู่โดย default — ทั้งสองตัวจะเปลี่ยน
  volume/filter สัญญาณแบบไม่ตรงกับสมมติฐานที่ backtest ใช้ (MIN_LOT คงที่, fixed SL/TP)
- SL/TP ฝากไว้กับ broker ตรงๆ (research พิสูจน์แล้วว่า fixed SL/TP ดีกว่า trailing/breakeven/
  partial-TP ทุกแบบที่ทดสอบ — ดู create_exit_optimization.md) ไม่ต้องมี exit-management เพิ่ม

⚠️ สำคัญ (เจอบั๊กจริงตอน deploy 2026-07-01): trailing.py มีฟังก์ชัน generic position-management
หลายสิบตัว (check_fill_trend_recheck, SL Guard Group, PD Zone fill check ฯลฯ) ที่สแกน
mt5.positions_get(symbol=SYMBOL) แบบ "ทุกโพซิชั่นในสัญลักษณ์" แล้ว skip เฉพาะ ticket ที่
position_sid.get(ticket) อยู่ใน skip-list ของฟังก์ชันนั้นๆ — ถ้าไม่ลงทะเบียน ticket ของเราไว้เลย
sid จะเป็น None ซึ่งไม่ตรง skip-list ใดๆ ทำให้ไม้ P13/P16 โดน logic ของบอทหลักไปจัดการ/ปิดก่อนถึง
SL/TP จริง (เจอจริง: ปิดขาดทุน -$0.01 ถึง -$0.49 ภายในไม่กี่สิบนาที ทั้งที่ SL ตั้งไกลกว่านั้นมาก)
แก้โดยลงทะเบียน position_sid[ticket] = 21 ทันทีหลังวางออเดอร์สำเร็จ — sid=21 เป็นค่าที่ถูก
"จอง" ไว้แล้วในทุก skip-list หลักของ trailing.py (SL_GUARD_SKIP_SIDS, SL_GUARD_GROUP_SKIP_SIDS,
PDFIBOPLUS_SKIP_SIDS, PENDING_LIMIT_GUARD_SKIP_SIDS, NEWS_FILTER_SKIP_SIDS,
OPPOSITE_ORDER_SKIP_SIDS, และ inline skip-tuple ของ check_fill_trend_recheck) — ตรงกับ
strategy21.py เดิมที่ import ไว้เฉยๆแต่ active_strategies ไม่มี key 21 (ไม่เคยถูกเรียกจริง) จึงใช้
sid นี้ tag ไม้ standalone ได้อย่างปลอดภัย ไม่ชนกับ strategy ไหน — position_sid ถูก
save/restore ผ่าน bot_state.json อยู่แล้ว (ของเดิมในระบบ) จึงรอดข้าม restart อัตโนมัติ
"""

import json
import os
from datetime import datetime, timezone, timedelta

import mt5_worker as mt5
import config

from strategy31 import S31_DEFAULTS, detect_s31
from strategy34 import S34_DEFAULTS, detect_s34
from strategy36 import S36_DEFAULTS, detect_s36
from strategy37 import S37_DEFAULTS, detect_s37
from strategy38 import S38_DEFAULTS, detect_s38
from strategy39 import S39_DEFAULTS, detect_s39
from strategy40 import S40_DEFAULTS, detect_s40
from strategy41 import S41_DEFAULTS, detect_s41
from strategy42 import S42_DEFAULTS, detect_s42
from strategy44 import S44_DEFAULTS, detect_s44
from strategy45 import S45_DEFAULTS, detect_s45
from strategy46 import S46_DEFAULTS, detect_s46
from strategy47 import S47_DEFAULTS, detect_s47
from strategy49 import S49_DEFAULTS, detect_s49
from strategy51 import S51_DEFAULTS, detect_s51
from strategy56 import S56_DEFAULTS, detect_s56

from bot_log import log_event, log_error

STATE_FILE = os.path.join(os.path.dirname(__file__), "demo_portfolio_state.json")
MAGIC_BASE = 990000  # แยกจาก magic=234001 ของ S1-S20 โดยสิ้นเชิง — P13=990013, P16=990016
MIN_LOT = 0.01
BKK_TZ = timezone(timedelta(hours=7))

_TF_MAP = {"M5": mt5.TIMEFRAME_M5, "M15": mt5.TIMEFRAME_M15}
_TF_SECS = {"M5": 300, "M15": 900}

# ── tuned cfg เดียวกับที่ backtest ใช้เป๊ะๆ (จาก scratch/blend_17way.py) ──────────
_CFG_A = dict(S31_DEFAULTS); _CFG_A.update(SL_ATR_MULT=1.2, TP_RR=1.0)
_CFG_B = dict(S34_DEFAULTS); _CFG_B.update(BREAKOUT_LOOKBACK=8, VOLUME_SURGE_MULT=2.0,
                                            MIN_BREAKOUT_ATR=0.15, SL_ATR_MULT=0.8, TP_RR=1.0)
_CFG_C = dict(S36_DEFAULTS); _CFG_C.update(MIN_GAP_ATR=0.25, MAX_GAP_AGE_BARS=15,
                                            RETRACE_ENTRY_PCT=0.5, SL_ATR_MULT=1.0, TP_RR=0.8)
_CFG_D = dict(S37_DEFAULTS); _CFG_D.update(PIVOT_WING=3, MAX_LEVEL_AGE_BARS=60, TOUCH_ATR_MULT=0.3,
                                            REJECT_ATR_MULT=0.15, SL_ATR_MULT=0.8, TP_RR=1.5)
_CFG_E = dict(S38_DEFAULTS); _CFG_E.update(SWING_LOOKBACK_BARS=25, MIN_SWING_ATR=3.0,
                                            MAX_RETRACE_AGE_BARS=20, SL_ATR_MULT=1.0, TP_RR=1.0)
_CFG_F = dict(S39_DEFAULTS); _CFG_F.update(BASE_BARS=3, BASE_ATR_MULT=1.5, IMPULSE_ATR_MULT=0.8,
                                            MAX_ZONE_AGE_BARS=30, SL_ATR_MULT=0.8, TP_RR=1.5)
_CFG_G = dict(S40_DEFAULTS); _CFG_G.update(ZIGZAG_MIN_ATR=1.5, ZIGZAG_LOOKBACK_BARS=200,
                                            MAX_WAVE4_AGE_BARS=25, ENTRY_BREAK_ATR_MULT=0.1,
                                            SL_ATR_MULT=1.0, TP_RR=1.5)
_CFG_H = dict(S41_DEFAULTS); _CFG_H.update(PIVOT_WING=2, MIN_PRICE_DIFF_ATR=0.3, MIN_RSI_DIFF=3.0,
                                            MAX_CONFIRM_AGE_BARS=8, SL_ATR_MULT=0.8, TP_RR=1.0,
                                            CONFIRMATION_TYPE="htf_trend")
_CFG_I = dict(S42_DEFAULTS); _CFG_I.update(RANGE_BARS=9, SWEEP_ATR_MULT=0.5, MIN_RANGE_ATR=1.0,
                                            SL_ATR_MULT=1.0, TP_RR=1.0, CONFIRMATION_TYPE="htf_trend")
_CFG_K = dict(S44_DEFAULTS); _CFG_K.update(LOOKBACK_BARS=80, BUCKET_ATR_MULT=0.2, TOUCH_ATR_MULT=0.5,
                                            REJECT_ATR_MULT=0.15, SL_ATR_MULT=1.0, TP_RR=1.5)
_CFG_L = dict(S45_DEFAULTS); _CFG_L.update(IMPULSE_ATR_MULT=1.5, MAX_OB_AGE_BARS=40,
                                            MAX_VIOLATION_WICK_ATR=0.1, SL_ATR_MULT=1.0, TP_RR=1.5)
_CFG_M = dict(S46_DEFAULTS); _CFG_M.update(OR_SESSION_START="14:00", OR_MINUTES=30,
                                            MAX_BREAKOUT_AGE_MIN=90, MIN_BREAK_ATR=0.1,
                                            SL_ATR_MULT=0.8, TP_RR=1.5)
_CFG_N = dict(S47_DEFAULTS); _CFG_N.update(ST_ATR_PERIOD=20, ST_ATR_MULT=2.0, SL_ATR_MULT=1.5,
                                            TP_RR=2.0, SESSION_FILTER=False, CONFIRMATION_TYPE="htf_trend")
_CFG_P = dict(S49_DEFAULTS); _CFG_P.update(STD_MULT=1.0, TOUCH_ATR_MULT=0.2, REJECT_ATR_MULT=0.1,
                                            SL_ATR_MULT=1.0, TP_RR=1.0)
_CFG_Q = dict(S51_DEFAULTS); _CFG_Q.update(TOUCH_ATR_MULT=0.5, REJECT_ATR_MULT=0.1, SL_ATR_MULT=0.8,
                                            TP_RR=1.5, SESSION_FILTER=False)
_CFG_R = dict(S56_DEFAULTS); _CFG_R.update(TOUCH_ATR_MULT=0.8, REJECT_ATR_MULT=0.15, SL_ATR_MULT=1.0,
                                            TP_RR=1.5, CONFIRMATION_TYPE="none", SESSION_FILTER=False)

# leg registry: (label, detect_fn, cfg, needs_htf, extra_kind)
# extra_kind: None | "bar_dt_list" (S46/S49/S51) | "prev_week_hl" (S56)
_LEG_DEFS = {
    "A": ("S31 Engulfing",         detect_s31, _CFG_A, True,  None),
    "B": ("S34 VolBreak",          detect_s34, _CFG_B, True,  None),
    "C": ("S36 FVG",               detect_s36, _CFG_C, True,  None),
    "D": ("S37 S/R Pivot",         detect_s37, _CFG_D, True,  None),
    "E": ("S38 Fibonacci OTE",     detect_s38, _CFG_E, True,  None),
    "F": ("S39 Demand/Supply",     detect_s39, _CFG_F, True,  None),
    "G": ("S40 Elliott",           detect_s40, _CFG_G, True,  None),
    "H": ("S41 RSI Div",           detect_s41, _CFG_H, True,  None),
    "I": ("S42 CRT",               detect_s42, _CFG_I, True,  None),
    "K": ("S44 VolProfile",        detect_s44, _CFG_K, True,  None),
    "L": ("S45 OrderBlock",        detect_s45, _CFG_L, True,  None),
    "M": ("S46 ORB",               detect_s46, _CFG_M, True,  "bar_dt_list"),
    "N": ("S47 SuperTrend",        detect_s47, _CFG_N, True,  None),
    "P": ("S49 VWAP",              detect_s49, _CFG_P, True,  "bar_dt_list"),
    "Q": ("S51 PDH/PDL",           detect_s51, _CFG_Q, True,  "bar_dt_list"),
    "R": ("S56 PrevWeekHL",        detect_s56, _CFG_R, False, "prev_week_hl"),
}

P13_KEYS = list("BCDFGHIKMNPQR")  # Champion — ถอด A(S31)/E(S38)/L(S45) ที่เป็น sharpe-drag
P16_KEYS = list("ABCDEFGHIKLMNPQR")  # Max-Yield Blend — ครบทุก leg

PORTFOLIOS = {"P13": P13_KEYS, "P16": P16_KEYS}
PORTFOLIO_DISPLAY_NAME = {"P13": "🏆 Champion (P13)", "P16": "💰 Max-Yield Blend (P16)"}


def _now_bkk():
    return datetime.now(BKK_TZ)


def _fetch_bars(tf_str, count):
    rates = mt5.copy_rates_from_pos(config.SYMBOL, _TF_MAP[tf_str], 0, count)
    if rates is None or len(rates) == 0:
        return None
    return rates


def _calc_ema_adx_htf(htf_bars, cfg):
    """คัดลอก logic เดียวกับ sim_s30_backtest.build_htf_series/htf_lookup แบบย่อสำหรับ live —
    ใช้เฉพาะแท่ง HTF ที่ปิดสมบูรณ์แล้ว (close_time <= now) เท่านั้น ไม่มี lookahead"""
    import sim_s30_backtest as s30sim
    series = s30sim.build_htf_series(htf_bars, cfg)
    return series


def _htf_ctx_now(htf_series, entry_ts):
    import sim_s30_backtest as s30sim
    return s30sim.htf_lookup(htf_series, entry_ts)


def _build_bar_dt_list(bars):
    return [config.mt5_ts_to_bkk(int(b["time"])) for b in bars]


def _prev_week_hl_now(entry_ts):
    """high/low ของสัปดาห์ก่อนหน้า (W1 bar ก่อนหน้าสัปดาห์ปัจจุบัน) — เหมือน sim_s56_backtest"""
    w1 = mt5.copy_rates_from_pos(config.SYMBOL, mt5.TIMEFRAME_W1, 0, 12)
    if w1 is None or len(w1) == 0:
        return None
    starts = sorted(int(b["time"]) for b in w1)
    hl = {int(b["time"]): (float(b["high"]), float(b["low"])) for b in w1}
    import bisect
    idx = bisect.bisect_right(starts, entry_ts) - 1
    if idx <= 0:
        return None
    return hl[starts[idx - 1]]


def _load_state():
    if not os.path.exists(STATE_FILE):
        return {"active": {"P13": False, "P16": False}, "last_signal_ts": {}, "trades": []}
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"active": {"P13": False, "P16": False}, "last_signal_ts": {}, "trades": []}


def _save_state(state):
    tmp = STATE_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
    os.replace(tmp, STATE_FILE)


def _place_market_order(signal, sl, tp, comment, magic):
    """วางออเดอร์ตรงๆ ผ่าน mt5.order_send() — ไม่ผ่าน mt5_utils.open_order_market() เพื่อเลี่ยง
    ML_SCORING_ENABLED / SCALE_OUT_ENABLED ที่เป็น global toggle ของบอทเดิม (ดู docstring บนไฟล์)"""
    tick = mt5.symbol_info_tick(config.SYMBOL)
    if not tick:
        return {"success": False, "error": "ดึงราคาไม่ได้"}
    price = tick.ask if signal == "BUY" else tick.bid
    order_type = mt5.ORDER_TYPE_BUY if signal == "BUY" else mt5.ORDER_TYPE_SELL
    result = mt5.order_send({
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": config.SYMBOL,
        "volume": MIN_LOT,
        "type": order_type,
        "price": price,
        "sl": sl,
        "tp": tp,
        "deviation": 20,
        "magic": magic,
        "comment": comment[:31],
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_FOK,
    })
    if result is None:
        return {"success": False, "error": f"order_send returned None — {mt5.last_error()}"}
    if result.retcode == mt5.TRADE_RETCODE_DONE:
        return {"success": True, "ticket": result.order, "price": price}
    return {"success": False, "error": f"{result.retcode} — {result.comment}"}


async def demo_scan(app, portfolio_name: str):
    """สแกน 1 รอบสำหรับ portfolio ที่ระบุ (P13 หรือ P16) — เรียก detect_s<N>() ของทุก leg
    ด้วยข้อมูล live ล่าสุด ถ้ามี signal ใหม่ (และไม่ติด cooldown) วางออเดอร์ตลาดทันที"""
    if not config.DEMO_PORTFOLIO_ACTIVE.get(portfolio_name, False):
        return

    state = _load_state()
    keys = PORTFOLIOS[portfolio_name]
    magic = MAGIC_BASE + int(portfolio_name[1:])  # P13->990013, P16->990016

    entry_bars = _fetch_bars("M5", 400)
    if entry_bars is None:
        log_error("DEMO_PORTFOLIO", f"{portfolio_name}: fetch M5 bars failed")
        return
    htf_bars = _fetch_bars("M15", 200)
    now = _now_bkk()
    entry_ts = int(entry_bars[-1]["time"])

    for key in keys:
        label, detect_fn, cfg, needs_htf, extra_kind = _LEG_DEFS[key]
        leg_id = f"{portfolio_name}-{key}"

        # cooldown เดียวกับ MIN_GAP_BARS=1 ของ backtest — ห้ามยิงซ้ำในแท่งเดียวกัน
        last_ts = state["last_signal_ts"].get(leg_id)
        if last_ts == entry_ts:
            continue

        htf_ctx = None
        if needs_htf and cfg.get("CONFIRMATION_TYPE", "htf_trend") != "none" and htf_bars is not None:
            htf_series = _calc_ema_adx_htf(htf_bars, cfg)
            htf_ctx = _htf_ctx_now(htf_series, entry_ts)

        kwargs = {"tf": "M5", "dt_bkk": now, "cfg": cfg, "htf_ctx": htf_ctx}
        if extra_kind == "bar_dt_list":
            kwargs["bar_dt_list"] = _build_bar_dt_list(entry_bars[:-1])
        elif extra_kind == "prev_week_hl":
            kwargs["prev_week_hl"] = _prev_week_hl_now(entry_ts)

        try:
            res = detect_fn(entry_bars, **kwargs)
        except Exception as e:
            log_error("DEMO_PORTFOLIO", f"{leg_id} detect error: {type(e).__name__}: {e}")
            continue

        sig = res.get("signal")
        if sig not in ("BUY", "SELL"):
            continue

        state["last_signal_ts"][leg_id] = entry_ts
        sl, tp = float(res["sl"]), float(res["tp"])
        comment = f"DEMO-{leg_id}"
        result = _place_market_order(sig, sl, tp, comment, magic)

        if result.get("success") and result.get("ticket"):
            # ⚠️ ต้องลงทะเบียนด้วย sid=21 ทันที ไม่งั้น trailing.py จะเห็น sid=None แล้วไม่ skip
            # (บั๊กจริงที่เจอ 2026-07-01 — ดู docstring บนไฟล์นี้) sid=21 = ค่าจองไว้แล้วในทุก
            # skip-list หลักของ trailing.py สำหรับ standalone strategy โดยเฉพาะ
            try:
                from trailing import position_sid
                position_sid[result["ticket"]] = 21
            except Exception as e:
                log_error("DEMO_PORTFOLIO", f"register position_sid failed: {type(e).__name__}: {e}")

        trade_log = {
            "ts": now.isoformat(), "entry_bar_ts": entry_ts, "leg": leg_id, "label": label,
            "signal": sig, "sl": sl, "tp": tp, "success": result.get("success"),
            "ticket": result.get("ticket"), "error": result.get("error"),
        }
        # entry_bar_ts = MT5 server timestamp ดิบของแท่งที่ยิง signal (ไม่ใช่ BKK wall-clock)
        # เก็บไว้ให้ tool ตรวจสอบย้อนหลัง (เช่น verify_signal_consistency.py) fetch ราคาย้อนหลัง
        # ตรงเป๊ะได้โดยไม่ต้องคำนวณ timezone กลับไปกลับมา (เคยพลาดตรงนี้มาก่อน)
        state["trades"].append(trade_log)
        state["trades"] = state["trades"][-500:]  # กัน state file โตไม่จำกัด
        _save_state(state)

        log_event("DEMO_PORTFOLIO_SIGNAL",
                   f"{leg_id} {sig} sl={sl} tp={tp} success={result.get('success')} "
                   f"ticket={result.get('ticket')} err={result.get('error')}")

        if app is not None and result.get("success"):
            try:
                msg = (f"📡 *{PORTFOLIO_DISPLAY_NAME[portfolio_name]}*\n"
                       f"Leg: `{label}` ({key})\n"
                       f"{'🟢 BUY' if sig=='BUY' else '🔴 SELL'} @ market\n"
                       f"SL `{sl:.2f}` TP `{tp:.2f}`\n"
                       f"Ticket: `{result.get('ticket')}`")
                await app.bot.send_message(chat_id=config.MY_USER_ID, text=msg, parse_mode="Markdown")
            except Exception:
                pass
        elif app is not None and not result.get("success") and not result.get("skipped"):
            try:
                await app.bot.send_message(
                    chat_id=config.MY_USER_ID,
                    text=f"⚠️ Demo Portfolio {leg_id} order failed: {result.get('error')}",
                )
            except Exception:
                pass


async def demo_scan_job(app):
    """เรียกจาก scheduler ใน main.py ทุก DEMO_PORTFOLIO_SCAN_INTERVAL นาที — no-op ถ้าไม่มี
    portfolio ไหน active เลย"""
    if not any(config.DEMO_PORTFOLIO_ACTIVE.values()):
        return
    for name in ("P13", "P16"):
        if config.DEMO_PORTFOLIO_ACTIVE.get(name, False):
            try:
                await demo_scan(app, name)
            except Exception as e:
                log_error("DEMO_PORTFOLIO", f"{name} scan error: {type(e).__name__}: {e}")


def _fetch_leg_pnl(portfolio_name: str):
    """
    ดึงกำไร/ขาดทุนแยกตาม leg ทั้ง 2 แบบ:
    - "total"/"n_closed" = realized (ไม้ที่ปิดจบแล้วจริงๆ ผ่าน SL/TP ที่ broker) — ย้อนดู deal
      history ของ MT5 เพราะ Python ไม่ได้คอยเช็คเอง
    - "floating" = unrealized (ไม้ที่ยังเปิดอยู่ตอนนี้ ราคายังไม่แตะ SL/TP) — ดึงจาก
      positions_get() ตรงๆ (ลอยได้ทั้งบวกและลบ ยังไม่ใช่กำไรจริงจนกว่าจะปิด)
    match กลับด้วย ticket ที่บันทึกไว้ตอนวางออเดอร์ (state["trades"])

    คืน dict: {leg_id: {"total": float, "n_closed": int, "floating": float, "first_ts": str}}
    """
    state = _load_state()
    tickets = {t["ticket"]: (t["leg"], t["ts"]) for t in state["trades"]
               if t.get("success") and t.get("ticket") and t["leg"].startswith(f"{portfolio_name}-")}
    result = {}
    for leg_id, ts in tickets.values():
        d = result.setdefault(leg_id, {"total": 0.0, "n_closed": 0, "floating": 0.0, "first_ts": ts})
        if ts < d["first_ts"]:
            d["first_ts"] = ts

    if not tickets:
        return result

    magic = MAGIC_BASE + int(portfolio_name[1:])

    # ── floating (ไม้ที่ยังเปิดอยู่ตอนนี้) ──────────────────────────────────
    open_positions = mt5.positions_get(symbol=config.SYMBOL)
    if open_positions:
        for p in open_positions:
            if p.magic != magic:
                continue
            leg_info = tickets.get(p.ticket)
            if leg_info is None:
                continue
            d = result.setdefault(leg_info[0], {"total": 0.0, "n_closed": 0, "floating": 0.0,
                                                 "first_ts": leg_info[1]})
            d["floating"] += float(p.profit) + float(p.swap)

    # ── realized (ไม้ที่ปิดจบแล้ว) ───────────────────────────────────────────
    from datetime import timedelta as _td
    date_from = datetime.now(timezone.utc) - _td(days=200)
    date_to = datetime.now(timezone.utc) + _td(days=1)
    deals = mt5.history_deals_get(date_from, date_to)
    if not deals:
        return result

    for deal in deals:
        if deal.magic != magic:
            continue
        if deal.entry != mt5.DEAL_ENTRY_OUT:  # เอาเฉพาะ deal ที่ "ปิด" position (มีกำไร/ขาดทุนจริง)
            continue
        leg_info = tickets.get(deal.position_id)
        if leg_info is None:
            continue
        leg_id = leg_info[0]
        d = result.setdefault(leg_id, {"total": 0.0, "n_closed": 0, "floating": 0.0,
                                        "first_ts": leg_info[1]})
        d["total"] += float(deal.profit) + float(deal.swap) + float(deal.commission)
        d["n_closed"] += 1
    return result


def get_status_text(portfolio_name: str) -> str:
    """สรุปสถานะสำหรับ Telegram status view — รวมกำไรเฉลี่ยต่อวัน/เดือน/กำไรรวม แยกราย leg"""
    state = _load_state()
    is_active = config.DEMO_PORTFOLIO_ACTIVE.get(portfolio_name, False)
    keys = PORTFOLIOS[portfolio_name]
    magic = MAGIC_BASE + int(portfolio_name[1:])

    today = _now_bkk().date().isoformat()
    trades_today = [t for t in state["trades"]
                    if t["leg"].startswith(f"{portfolio_name}-") and t["ts"].startswith(today)]
    n_success = sum(1 for t in trades_today if t.get("success"))

    lines = [
        f"{PORTFOLIO_DISPLAY_NAME[portfolio_name]}",
        f"สถานะ: {'🟢 ทำงานอยู่' if is_active else '⚪ หยุดอยู่'}",
        f"จำนวน leg: {len(keys)}",
        f"Magic: {magic}",
        f"ออเดอร์วันนี้: {n_success} ไม้",
    ]

    open_positions = mt5.positions_get(symbol=config.SYMBOL)
    if open_positions:
        pf_positions = [p for p in open_positions if p.magic == magic]
        if pf_positions:
            lines.append(f"\nโพซิชั่นเปิดอยู่: {len(pf_positions)} ไม้")
            for p in pf_positions[:10]:
                lines.append(f"  #{p.ticket} {'BUY' if p.type==0 else 'SELL'} "
                             f"{p.volume} SL:{p.sl:.2f} TP:{p.tp:.2f} PnL:{p.profit:.2f}")

    # ── กำไร/ขาดทุนแยกราย leg: realized (ปิดแล้ว) + floating (ยังเปิดอยู่) ─────────
    pnl_by_leg = _fetch_leg_pnl(portfolio_name)
    if pnl_by_leg:
        now = _now_bkk()
        lines.append(f"\n💵 *กำไร/ขาดทุน แยกราย leg:*")
        total_realized = 0.0
        total_floating = 0.0
        sort_key = lambda k: pnl_by_leg[k]["total"] + pnl_by_leg[k]["floating"]
        for leg_id in sorted(pnl_by_leg, key=sort_key, reverse=True):
            d = pnl_by_leg[leg_id]
            key = leg_id.split("-", 1)[1]  # "P13-D" -> "D"
            label = _LEG_DEFS.get(key, (key,))[0]
            first_dt = datetime.fromisoformat(d["first_ts"])
            days_elapsed = max((now - first_dt).total_seconds() / 86400.0, 1.0)
            per_day = d["total"] / days_elapsed
            per_month = per_day * 30
            total_realized += d["total"]
            total_floating += d["floating"]
            float_part = f" | ลอยอยู่ `${d['floating']:+.2f}` (ยังไม่ปิด)" if d["floating"] != 0 else ""
            lines.append(
                f"  `{key}` {label}: ปิดแล้ว `${d['total']:+.2f}` "
                f"({d['n_closed']} ไม้){float_part}\n"
                f"      เฉลี่ย/วัน `${per_day:+.2f}` | เฉลี่ย/เดือน `${per_month:+.2f}`"
            )
        lines.append(
            f"\n**รวม realized (ปิดแล้ว): ${total_realized:+.2f}**\n"
            f"**รวม floating (ยังไม่ปิด): ${total_floating:+.2f}**\n"
            f"**รวมทั้งหมด: ${total_realized + total_floating:+.2f}**"
        )
    else:
        lines.append("\n_ยังไม่มีไม้เข้าเลย — รอสัญญาณแรกก่อน_")

    return "\n".join(lines)
