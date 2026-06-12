"""
strategy16.py — S16 AMD x iFVG
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Win Rate อ้างอิง: 85-90%+ (AMD Cycle + Inversion FVG)

แนวคิด:
  1. คำนวณกรอบเอเชีย (Asian Range) จากราคาช่วง 08:00 - 12:00 BKK
       Asian_High = ราคาสูงสุดในช่วงสะสม
       Asian_Low  = ราคาต่ำสุดในช่วงสะสม
  2. สแกนเทรดเฉพาะช่วง Killzones (London Open: 14:00-17:00 BKK, NY Open: 19:00-22:00 BKK)
  3. ตรวจสอบการกวาดสภาพคล่อง (Sweep):
       BUY : ราคาต่ำสุด (Low) ทะลุใต้ Asian_Low
       SELL: ราคาสูงสุด (High) ทะลุเหนือ Asian_High
  4. มองหา Inversion FVG (iFVG) บน M1:
       BUY : ราคาพุ่งกลับขึ้นมาปิดเหนือ Bearish FVG (Low[2]) ที่สร้างขึ้นตอนทุบลงมา
       SELL: ราคาดิ่งกลับลงมาปิดใต้ Bullish FVG (High[2]) ที่สร้างขึ้นตอนดันราคาขึ้น
  5. Entry: LIMIT ที่ขอบ iFVG หรือ midline
  6. SL: ใต้จุดสูงสุด/ต่ำสุดที่ Sweep
  7. TP: ขอบเอเชียฝั่งตรงข้าม (หรือ fallback RR 1.5R)
"""

import MetaTrader5 as mt5
from datetime import datetime, timedelta, timezone, time
import config
from config import SL_BUFFER
from mt5_utils import calc_atr

# runtime state: บันทึกและกู้คืนโดย config.py
# "fired": one-shot dedup ต่อ (tf, side, killzone window) — แก้เคส 09/06/2026
#   ที่ pending สะสมจน fill พร้อมกัน 13 ไม้ (dup check entry/tp หลุดเพราะ ATR drift)
s16_state = {
    "asian_high": 0.0,
    "asian_low": 0.0,
    "range_date": "",
    "swept_high": False,
    "swept_low": False,
    "fired": {},
}


def _s16_fired_key(tf: str, sig: str, kz_start_ts: int) -> str:
    return f"{tf}|{sig}|{int(kz_start_ts)}"


def _s16_already_fired(tf: str, sig: str, kz_start_ts: int) -> bool:
    fired = s16_state.setdefault("fired", {})
    return _s16_fired_key(tf, sig, kz_start_ts) in fired


def _s16_mark_fired(tf: str, sig: str, kz_start_ts: int) -> None:
    fired = s16_state.setdefault("fired", {})
    fired[_s16_fired_key(tf, sig, kz_start_ts)] = int(kz_start_ts)
    # prune key เก่ากว่า 2 วัน (เทียบจาก kz ปัจจุบัน — ไม่พึ่ง wall clock)
    cutoff = int(kz_start_ts) - 172800
    for k in list(fired.keys()):
        if fired.get(k, 0) < cutoff:
            fired.pop(k, None)
    config.save_runtime_state()

def bkk_to_server_ts(dt_bkk):
    """แปลง BKK datetime เป็น MT5 server timestamp แบบ timezone-safe"""
    dt_server = dt_bkk - timedelta(hours=config.TZ_OFFSET - config.MT5_SERVER_TZ)
    return int(dt_server.replace(tzinfo=timezone.utc).timestamp())

def check_in_killzone(dt_bkk) -> bool:
    """ตรวจสอบว่า BKK time อยู่ในช่วง Killzones หรือไม่"""
    current_time = dt_bkk.time()
    for start_str, end_str in getattr(config, "S16_KILLZONES", [("14:00", "17:00"), ("19:00", "22:00")]):
        sh, sm = map(int, start_str.split(":"))
        eh, em = map(int, end_str.split(":"))
        if time(sh, sm) <= current_time < time(eh, em):
            return True
    return False

def get_current_killzone_start(dt_bkk):
    """ดึงเวลาเริ่มต้นของ Killzone ปัจจุบัน (BKK datetime)"""
    current_time = dt_bkk.time()
    for start_str, end_str in getattr(config, "S16_KILLZONES", [("14:00", "17:00"), ("19:00", "22:00")]):
        sh, sm = map(int, start_str.split(":"))
        eh, em = map(int, end_str.split(":"))
        if time(sh, sm) <= current_time < time(eh, em):
            return dt_bkk.replace(hour=sh, minute=sm, second=0, microsecond=0)
    return None

def update_asian_range_today(dt_bkk):
    """คำนวณแนวกรอบราคาช่วงเอเชียของวันนี้ (08:00 - 12:00 BKK)"""
    today_str = dt_bkk.strftime("%Y-%m-%d")
    
    # ล้างสถานะเมื่อข้ามวันใหม่
    if s16_state["range_date"] != today_str:
        s16_state["asian_high"] = 0.0
        s16_state["asian_low"] = 0.0
        s16_state["range_date"] = today_str
        s16_state["swept_high"] = False
        s16_state["swept_low"] = False
        config.save_runtime_state()

    # เช็คเงื่อนไขเวลา: ต้องพ้นเวลาสิ้นสุดสะสม (12:00 BKK) ของวันนี้
    eh, em = map(int, getattr(config, "S16_ASIAN_END_BKK", "12:00").split(":"))
    if dt_bkk.time() < time(eh, em):
        return

    # ถ้าคำนวณของวันนี้ไปแล้ว ไม่ต้องทำซ้ำ
    if s16_state["asian_high"] > 0:
        return

    # ดึง M5 rates ย้อนหลัง 300 แท่ง (~25 ชั่วโมง) เพื่อให้ครอบคลุมเวลา 08:00 - 12:00
    rates = mt5.copy_rates_from_pos(config.SYMBOL, mt5.TIMEFRAME_M5, 0, 300)
    if rates is None or len(rates) == 0:
        print(f"[{dt_bkk.strftime('%H:%M:%S')}] ⚠️ S16: ดึงข้อมูล M5 เพื่อตีกรอบเอเชียไม่ได้")
        return

    sh, sm = map(int, getattr(config, "S16_ASIAN_START_BKK", "08:00").split(":"))
    asian_start_time = time(sh, sm)
    asian_end_time = time(eh, em)

    asian_bars = []
    for bar in rates:
        bar_bkk = config.mt5_ts_to_bkk(bar["time"])
        if bar_bkk is None:
            continue
        if bar_bkk.strftime("%Y-%m-%d") == today_str:
            if asian_start_time <= bar_bkk.time() < asian_end_time:
                asian_bars.append(bar)

    if not asian_bars:
        print(f"[{dt_bkk.strftime('%H:%M:%S')}] ⚠️ S16: ไม่พบบาร์ข้อมูลช่วงเอเชียของวันนี้ ({today_str})")
        return

    s16_state["asian_high"] = max(float(bar["high"]) for bar in asian_bars)
    s16_state["asian_low"] = min(float(bar["low"]) for bar in asian_bars)
    s16_state["range_date"] = today_str
    print(f"📊 [S16] ตีกรอบเอเชียสำเร็จ: {s16_state['asian_low']:.2f} – {s16_state['asian_high']:.2f}")
    config.save_runtime_state()

def find_bearish_fvgs_in_range(rates, start_idx, end_idx):
    """หา Bearish FVG บน rates ระหว่าง start_idx ถึง end_idx"""
    fvgs = []
    for i in range(max(2, start_idx), end_idx + 1):
        low_2 = float(rates[i-2]["low"])
        high_0 = float(rates[i]["high"])
        if low_2 > high_0:
            fvgs.append({
                "idx": i,
                "upper_boundary": low_2,
                "lower_boundary": high_0,
                "time": int(rates[i]["time"])
            })
    return fvgs

def find_bullish_fvgs_in_range(rates, start_idx, end_idx):
    """หา Bullish FVG บน rates ระหว่าง start_idx ถึง end_idx"""
    fvgs = []
    for i in range(max(2, start_idx), end_idx + 1):
        high_2 = float(rates[i-2]["high"])
        low_0 = float(rates[i]["low"])
        if low_0 > high_2:
            fvgs.append({
                "idx": i,
                "lower_boundary": high_2,
                "upper_boundary": low_0,
                "time": int(rates[i]["time"])
            })
    return fvgs

def strategy_16(rates, tf: str = ""):
    """
    S16: AMD x iFVG
    รันสแกนตรวจสอบการ Sweep กรอบเอเชีย และการเกิด Inversion FVG
    """

    dt_bkk = config.now_bkk()
    update_asian_range_today(dt_bkk)

    a_high = s16_state["asian_high"]
    a_low = s16_state["asian_low"]
    if a_high == 0.0 or a_low == 0.0:
        return {"signal": "WAIT", "reason": "รอตีกรอบเอเชียหลังเวลา 12:00 BKK"}

    if not check_in_killzone(dt_bkk):
        return {"signal": "WAIT", "reason": "อยู่นอกเวลา Killzones (14:00-17:00 / 19:00-22:00)"}

    kz_start_bkk = get_current_killzone_start(dt_bkk)
    if kz_start_bkk is None:
        return {"signal": "WAIT", "reason": "อยู่นอกเวลา Killzones"}

    # หาตำแหน่งบาร์ใน rates ที่เริ่มเข้าช่วง Killzone ปัจจุบัน
    kz_start_ts = bkk_to_server_ts(kz_start_bkk)
    
    # กรอง rates เฉพาะแท่งที่อยู่ในช่วง Killzone ปัจจุบัน
    kz_bars_indices = [idx for idx, bar in enumerate(rates) if int(bar["time"]) >= kz_start_ts]
    min_bars = 5 if tf in ("M1", "M5") else 3
    if len(kz_bars_indices) < min_bars:
        return {"signal": "WAIT", "reason": f"ข้อมูลบาร์ {tf} ใน Killzone ปัจจุบันยังมีไม่พอ"}

    kz_start_idx = kz_bars_indices[0]
    n_rates = len(rates)

    # 1. ค้นหาจุดต่ำสุดและสูงสุดใน Killzone ปัจจุบัน เพื่อตรวจสอบการ Sweep
    kz_low_price = min(float(rates[idx]["low"]) for idx in kz_bars_indices)
    kz_low_idx = next(idx for idx in kz_bars_indices if float(rates[idx]["low"]) == kz_low_price)

    kz_high_price = max(float(rates[idx]["high"]) for idx in kz_bars_indices)
    kz_high_idx = next(idx for idx in kz_bars_indices if float(rates[idx]["high"]) == kz_high_price)

    # ดึงค่า ATR เพื่อใช้คำนวณ SL Buffer
    atr = calc_atr(rates, 14)
    if not atr or atr <= 0:
        atr = 1.0 # fallback
    # SL buffer ของ S16 เอง (ค่า ATR mult) — fallback SL_BUFFER กลางถ้าตั้ง None
    _s16_slb = getattr(config, "S16_SL_ATR_BUFFER", None)
    sl_buf = (atr * float(_s16_slb)) if _s16_slb is not None else SL_BUFFER(atr)
    # risk cap: skip setup ที่ SL ห่างเกิน ATR × นี้ (0 = ปิด) — ข้อมูลจริง 06/2026 แพ้เฉลี่ย -$30..-$49/ไม้
    max_risk = atr * float(getattr(config, "S16_MAX_RISK_ATR_MULT", 0) or 0)
    min_rr = float(getattr(config, "S16_MIN_RR", 1.5))
    entry_mode = getattr(config, "S16_ENTRY_MODE", "boundary")

    # ── BUY SETUP (กวาดล้างกรอบล่างเอเชีย - Low Sweep) ──
    if kz_low_price < a_low:
        s16_state["swept_low"] = True
        
        # 1a. หาจุดเริ่มต้นของ Manipulation Leg (จุดสูงสุดก่อนทุบลงไปทำ Sweep Low)
        manip_start_idx = kz_start_idx
        highest_before_sweep = max(float(rates[idx]["high"]) for idx in range(kz_start_idx, kz_low_idx + 1))
        manip_start_idx = next(idx for idx in range(kz_start_idx, kz_low_idx + 1) if float(rates[idx]["high"]) == highest_before_sweep)

        # 1b. ค้นหา Bearish FVG ทั้งหมดที่เกิดขึ้นใน Manipulation Leg
        bearish_fvgs = find_bearish_fvgs_in_range(rates, manip_start_idx, kz_low_idx)
        
        # 1c. ตรวจหาการปิดทะลุ (Inversion) ใน Distribution Leg (หลังทำ Low ต่ำสุด)
        inverted_fvgs = []
        for fvg in bearish_fvgs:
            fvg_idx = fvg["idx"]
            upper_bound = fvg["upper_boundary"]
            lower_bound = fvg["lower_boundary"]
            
            # เช็คว่ามีแท่ง M1 หลัง sweep_low ที่ปิดเหนือขอบบนของ FVG นี้ไหม
            for j in range(kz_low_idx + 1, n_rates):
                if float(rates[j]["close"]) > upper_bound:
                    inverted_fvgs.append({
                        "fvg_idx": fvg_idx,
                        "upper": upper_bound,
                        "lower": lower_bound,
                        "inversion_bar_idx": j,
                        "time": fvg["time"]
                    })
                    break

        if inverted_fvgs:
            # เลือก FVG ที่เพิ่งกลับตัวล่าสุด (เกิดใกล้ sweep low ที่สุด = ดึงข้อมูลตัวที่ดัชนี FVG สูงสุด)
            target_fvg = max(inverted_fvgs, key=lambda f: f["fvg_idx"])
            
            if entry_mode == "midline":
                entry = (target_fvg["upper"] + target_fvg["lower"]) / 2.0
            else: # boundary
                entry = target_fvg["upper"]

            sl = kz_low_price - sl_buf
            tp = a_high # ตั้ง TP ที่ Asian_High

            # ตรวจสอบความถูกต้องและคำนวณ RR
            risk = entry - sl
            if risk > 0 and (max_risk <= 0 or risk <= max_risk) \
                    and not _s16_already_fired(tf, "BUY", kz_start_ts):
                # ตรวจว่าราคาปัจจุบัน (close ล่าสุด) อยู่เหนือ entry หรือไม่ เพื่อให้เป็น LIMIT Order
                cur_close = float(rates[-1]["close"])
                if cur_close > entry:
                    reward = tp - entry
                    if reward / risk < min_rr:
                        # ขยับ TP เป็นขั้นต่ำตามอัตราส่วน RR
                        tp = entry + (risk * min_rr)
                    
                    # บันทึกแท่งเทียนที่ทำให้เกิด Setup
                    trigger_candles = list(rates[target_fvg["fvg_idx"] - 2 : target_fvg["fvg_idx"] + 1])

                    _s16_mark_fired(tf, "BUY", kz_start_ts)
                    return {
                        "signal":      "BUY",
                        "entry":       round(entry, 2),
                        "sl":          round(sl, 2),
                        "tp":          round(tp, 2),
                        "pattern":     "ท่าที่ 16 AMD x iFVG 🟢 BUY",
                        "reason":      f"Asian Range: {a_low:.2f} – {a_high:.2f}\n"
                                       f"Sweep Low: {kz_low_price:.2f} | iFVG Inverted ที่ {target_fvg['upper']:.2f}\n"
                                       f"Entry Mode: {entry_mode}",
                        "order_mode":  "limit",
                        "entry_label": "BUY LIMIT (iFVG Inversion)",
                        "candles":     trigger_candles
                    }

    # ── SELL SETUP (กวาดล้างกรอบบนเอเชีย - High Sweep) ──
    if kz_high_price > a_high:
        s16_state["swept_high"] = True

        # 2a. หาจุดเริ่มต้นของ Manipulation Leg (จุดต่ำสุดก่อนดันขึ้นไปทำ Sweep High)
        manip_start_idx = kz_start_idx
        lowest_before_sweep = min(float(rates[idx]["low"]) for idx in range(kz_start_idx, kz_high_idx + 1))
        manip_start_idx = next(idx for idx in range(kz_start_idx, kz_high_idx + 1) if float(rates[idx]["low"]) == lowest_before_sweep)

        # 2b. ค้นหา Bullish FVG ทั้งหมดที่เกิดขึ้นใน Manipulation Leg
        bullish_fvgs = find_bullish_fvgs_in_range(rates, manip_start_idx, kz_high_idx)

        # 2c. ตรวจหาการปิดทะลุ (Inversion) ใน Distribution Leg (หลังทำ High สูงสุด)
        inverted_fvgs = []
        for fvg in bullish_fvgs:
            fvg_idx = fvg["idx"]
            lower_bound = fvg["lower_boundary"]
            upper_bound = fvg["upper_boundary"]

            # เช็คว่ามีแท่ง M1 หลัง sweep_high ที่ปิดต่ำกว่าขอบล่างของ FVG นี้ไหม
            for j in range(kz_high_idx + 1, n_rates):
                if float(rates[j]["close"]) < lower_bound:
                    inverted_fvgs.append({
                        "fvg_idx": fvg_idx,
                        "lower": lower_bound,
                        "upper": upper_bound,
                        "inversion_bar_idx": j,
                        "time": fvg["time"]
                    })
                    break

        if inverted_fvgs:
            # เลือก FVG ที่เพิ่งกลับตัวล่าสุด
            target_fvg = max(inverted_fvgs, key=lambda f: f["fvg_idx"])

            if entry_mode == "midline":
                entry = (target_fvg["upper"] + target_fvg["lower"]) / 2.0
            else: # boundary
                entry = target_fvg["lower"]

            sl = kz_high_price + sl_buf
            tp = a_low # ตั้ง TP ที่ Asian_Low

            risk = sl - entry
            if risk > 0 and (max_risk <= 0 or risk <= max_risk) \
                    and not _s16_already_fired(tf, "SELL", kz_start_ts):
                cur_close = float(rates[-1]["close"])
                if cur_close < entry:
                    reward = entry - tp
                    if reward / risk < min_rr:
                        tp = entry - (risk * min_rr)

                    trigger_candles = list(rates[target_fvg["fvg_idx"] - 2 : target_fvg["fvg_idx"] + 1])

                    _s16_mark_fired(tf, "SELL", kz_start_ts)
                    return {
                        "signal":      "SELL",
                        "entry":       round(entry, 2),
                        "sl":          round(sl, 2),
                        "tp":          round(tp, 2),
                        "pattern":     "ท่าที่ 16 AMD x iFVG 🔴 SELL",
                        "reason":      f"Asian Range: {a_low:.2f} – {a_high:.2f}\n"
                                       f"Sweep High: {kz_high_price:.2f} | iFVG Inverted ที่ {target_fvg['lower']:.2f}\n"
                                       f"Entry Mode: {entry_mode}",
                        "order_mode":  "limit",
                        "entry_label": "SELL LIMIT (iFVG Inversion)",
                        "candles":     trigger_candles
                    }

    return {"signal": "WAIT", "reason": "S16: ยังไม่พบการกวาดขอบราคาเอเชีย หรือการยืนยัน iFVG ในตลาด"}
