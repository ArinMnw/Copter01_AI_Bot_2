"""
sim_s10_backtest.py — จำลอง S10 (CRT TBS) ทุก TF ตั้งแต่ 24-05-2026
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')

import time
_orig_time = time.time
CURRENT_SIM_TIME = 0.0

def mock_time():
    global CURRENT_SIM_TIME
    if CURRENT_SIM_TIME > 0:
        return CURRENT_SIM_TIME
    return _orig_time()

time.time = mock_time

import MetaTrader5 as mt5
from datetime import datetime, timezone, timedelta
import config
from strategy10 import strategy_10, reset_mtf_state, try_pre_arm_htf, _LTF_TO_HTFS, _HTF_TO_LTF
import hhll_swing as _hs

# HHLL support
_HHLL_LB  = int(getattr(config, 'HHLL_LEFT',     5) or 5)
_HHLL_RB  = int(getattr(config, 'HHLL_RIGHT',    5) or 5)
_HHLL_LBK = int(getattr(config, 'HHLL_LOOKBACK', 500) or 500)

def _inject_hhll(tf_name: str, bars_slice: list):
    """คำนวณ HHLL จาก bars_slice แล้ว inject เข้า hhll_swing._hhll_data[tf_name]"""
    max_bars = _HHLL_LBK + _HHLL_LB + _HHLL_RB + 5
    rates = bars_slice[-max_bars:] if len(bars_slice) > max_bars else bars_slice
    if len(rates) < _HHLL_LB + _HHLL_RB + 10:
        return
    zz = _hs._build_zz(rates, _HHLL_LB, _HHLL_RB)
    if len(zz) < 5:
        return
    buckets      = {"HH": None, "HL": None, "LH": None, "LL": None}
    prev_buckets = {"HH": None, "HL": None, "LH": None, "LL": None}
    structure    = []
    for k in range(len(zz)):
        lbl = _hs._classify_pt(zz, k)
        if not lbl:
            continue
        pt = {"price": zz[k]["price"], "time": zz[k]["time"], "label": lbl}
        prev_buckets[lbl] = buckets[lbl]
        buckets[lbl] = pt
        structure.append(lbl)
    _hs._hhll_data[tf_name] = {
        "hh": buckets["HH"], "hl": buckets["HL"],
        "lh": buckets["LH"], "ll": buckets["LL"],
        "prev_hh": prev_buckets["HH"], "prev_hl": prev_buckets["HL"],
        "prev_lh": prev_buckets["LH"], "prev_ll": prev_buckets["LL"],
        "last_label": structure[-1] if structure else "",
        "structure": list(reversed(structure[-6:])),
    }

# PD Fibo Plus check
_PD_ENABLED = getattr(config, 'PDFIBOPLUS_ENABLED', True)

def _check_pd_fibo(signal: str, entry: float, tf_name: str) -> tuple:
    try:
        sh_pt, sl_pt = _hs.get_swing_hl_pts(tf_name)
    except Exception:
        return True, None, None, None, None, None
    if not sh_pt or not sl_pt:
        return True, None, None, None, None, None
    h = float(sh_pt["price"])
    l = float(sl_pt["price"])
    h_time = int(sh_pt["time"])
    l_time = int(sl_pt["time"])
    if h <= l:
        return True, None, None, None, None, None
    fib_382 = l + (h - l) * 0.382
    fib_618 = l + (h - l) * 0.618
    fibo_pct = ((entry - l) / (h - l)) * 100
    if signal == "BUY":
        return entry < fib_382, fibo_pct, h, l, h_time, l_time
    elif signal == "SELL":
        return entry > fib_618, fibo_pct, h, l, h_time, l_time
    return True, fibo_pct, h, l, h_time, l_time


SYMBOL       = config.SYMBOL
SINCE        = datetime(2026, 5, 24, 0, 0, 0, tzinfo=timezone.utc)
VOLUME       = 0.01
PRICE_TO_USD = 100 * VOLUME
def sync_strategy10_runtime_config():
    """Keep strategy10 module-level aliases in sync after config.restore_runtime_state()."""
    import strategy10 as _s10
    _s10.CRT_BAR_MODE = getattr(config, "CRT_BAR_MODE", _s10.CRT_BAR_MODE)
    _s10.CRT_SWEEP_DEPTH_PCT = getattr(config, "CRT_SWEEP_DEPTH_PCT", _s10.CRT_SWEEP_DEPTH_PCT)

TF_SECONDS = {
    "M1": 60, "M5": 300, "M15": 900, "M30": 1800,
    "H1": 3600, "H4": 14400, "H12": 43200, "D1": 86400,
}

TF_MAP = {
    'M1':  mt5.TIMEFRAME_M1,
    'M5':  mt5.TIMEFRAME_M5,
    'M15': mt5.TIMEFRAME_M15,
}

TF_EXTRA_BARS = {
    'M1': 2000, 'M5': 500, 'M15': 300,
}

UTC = timezone.utc
TZ_OFF = getattr(config, 'TZ_OFFSET', 7)
SRV_TZ = getattr(config, 'MT5_SERVER_TZ', 1)
BKK_TZ = timezone(timedelta(hours=TZ_OFF))

def to_bkk(ts: int) -> datetime:
    return datetime.fromtimestamp(ts, tz=UTC) + timedelta(hours=TZ_OFF - SRV_TZ)


def _mt5_range_dt_from_ts(ts: int) -> datetime:
    dt = to_bkk(ts)
    return datetime(dt.year, dt.month, dt.day, dt.hour, dt.minute, dt.second, tzinfo=BKK_TZ)


def _copy_rates_covering_since(symbol: str, tf_val: int, tf_name: str):
    extra = TF_EXTRA_BARS.get(tf_name, 200)
    total = 5000 + extra
    rates = mt5.copy_rates_from_pos(symbol, tf_val, 0, total)
    if rates is None or len(rates) == 0:
        return rates

    since_ts = int(SINCE.timestamp())
    window_needed = 200
    first_needed_ts = since_ts - (window_needed + extra) * TF_SECONDS.get(tf_name, 60)
    if int(rates[0]["time"]) <= first_needed_ts:
        return rates

    end_ts = int(rates[-1]["time"]) + TF_SECONDS.get(tf_name, 60)
    ranged = mt5.copy_rates_range(
        symbol,
        tf_val,
        _mt5_range_dt_from_ts(first_needed_ts),
        _mt5_range_dt_from_ts(end_ts),
    )
    return ranged if ranged is not None and len(ranged) > 0 else rates

def profit(price_diff: float) -> float:
    return round(price_diff * PRICE_TO_USD, 2)


def s10_runtime_feature_coverage() -> list[dict]:
    """Describe S10 runtime feature coverage for replay reports."""
    return [
        {
            "name": "S10 CRT detect / model orders",
            "config_on": bool(config.active_strategies.get(10, False)),
            "runtime": "apply",
            "replay": "apply",
            "note": "HTF arm, LTF model orders, sibling cancel",
        },
        {
            "name": "S10 sweep/structure/parent-touch cancel",
            "config_on": True,
            "runtime": "apply",
            "replay": "apply",
            "note": "Managed in S10 pending invalidation",
        },
        {
            "name": "Fixed SL/TP close",
            "config_on": True,
            "runtime": "apply",
            "replay": "apply",
            "note": "Bar high/low replay",
        },
        {
            "name": "SL Guard",
            "config_on": any([
                getattr(config, "SL_GUARD_ENABLED", False),
                getattr(config, "SL_GUARD_COMBINED_ENABLED", False),
                getattr(config, "SL_GUARD_GROUP_ENABLED", False),
            ]),
            "runtime": "apply",
            "replay": "apply",
            "note": "Per-TF, combined, group; close-on-activate supported",
        },
        {
            "name": "PD Fibo Plus",
            "config_on": getattr(config, "PDFIBOPLUS_ENABLED", True),
            "runtime": "skip_s10",
            "replay": "skip_s10",
            "note": "Skip SIDs: 9,10,13,14,15,16",
        },
        {
            "name": "Trend Recheck",
            "config_on": getattr(config, "LIMIT_TREND_RECHECK", False),
            "runtime": "skip_s10",
            "replay": "skip_s10",
            "note": "S10 CRT-managed",
        },
        {
            "name": "RSI Fill Recheck",
            "config_on": getattr(config, "PENDING_RSI_RECHECK_ENABLED", False),
            "runtime": "apply",
            "replay": "not_implemented",
            "note": "Runtime currently does not skip sid 10; no effect while config is OFF",
        },
        {
            "name": "Entry Candle",
            "config_on": getattr(config, "ENTRY_CANDLE_ENABLED", False),
            "runtime": "skip_s10",
            "replay": "skip_s10",
            "note": "Runtime skip sid 10; includes entry candle mode and TP update",
        },
        {
            "name": "Trail SL",
            "config_on": getattr(config, "TRAIL_SL_ENABLED", False),
            "runtime": "skip_s10",
            "replay": "skip_s10",
            "note": "Runtime skip sid 10; includes reversal trail override",
        },
        {
            "name": "Opposite Order",
            "config_on": getattr(config, "OPPOSITE_ORDER_ENABLED", False),
            "runtime": "skip_s10",
            "replay": "skip_s10",
            "note": "Runtime filters sid 10 positions/orders",
        },
        {
            "name": "Limit Guard",
            "config_on": getattr(config, "LIMIT_GUARD", False),
            "runtime": "skip_s10",
            "replay": "skip_s10",
            "note": "Runtime skip sid 10 pending orders",
        },
        {
            "name": "Limit TP/SL Break Cancel",
            "config_on": getattr(config, "LIMIT_BREAK_CANCEL", False),
            "runtime": "skip_s10",
            "replay": "skip_s10",
            "note": "S10 managed by parent-touch cancel",
        },
        {
            "name": "Delay SL",
            "config_on": getattr(config, "DELAY_SL_MODE", "off") != "off",
            "runtime": "apply",
            "replay": "not_implemented",
            "note": "S10 model limit orders can place SL later when delay SL is ON",
        },
        {
            "name": "Engulf minimum",
            "config_on": True,
            "runtime": "apply",
            "replay": "apply",
            "note": "S10 model-2 FVG uses strategy10.engulf_min_price() in both runtime and replay",
        },
        {
            "name": "Trend Filter Scan Block",
            "config_on": getattr(config, "TREND_FILTER_SCAN_BLOCK", False),
            "runtime": "skip_s10",
            "replay": "skip_s10",
            "note": "S10 bypasses normal trend filter scan block",
        },
        {
            "name": "Strong Trend Block",
            "config_on": (
                getattr(config, "STRONG_TREND_BLOCK_ENABLED", False)
                and 10 in getattr(config, "STRONG_TREND_BLOCK_SIDS", (9, 10, 11, 13, 14, 15, 16))
            ),
            "runtime": "apply",
            "replay": "not_implemented",
            "note": "No effect while config is OFF; replay must be added before enabling for S10 backtests",
        },
        {
            "name": "Limit Sweep",
            "config_on": getattr(config, "LIMIT_SWEEP", False),
            "runtime": "apply",
            "replay": "not_implemented",
            "note": "No effect while config is OFF; replay must be added before using S10 with Limit Sweep ON",
        },
    ]


def s10_unreplayed_active_features() -> list[dict]:
    return [
        item for item in s10_runtime_feature_coverage()
        if item["config_on"] and item["runtime"] == "apply" and item["replay"] != "apply"
    ]


def _sim_point() -> float:
    try:
        info = mt5.symbol_info(SYMBOL)
        return float(getattr(info, "point", 0.01) or 0.01)
    except Exception:
        return 0.01


class SimSLGuard:
    """Small replay model for SL Guard effects used by the live scanner/trailing flow."""

    def __init__(self):
        self.per_tf = {}
        self.combined = {}
        self.group = {}
        self.near_price = float(getattr(config, "SL_GUARD_NEAR_POINTS", 200) or 200) * _sim_point() * config.points_scale()

    def _swing_ref(self, tf: str, side: str) -> float:
        try:
            sh, sl = _hs.get_swing_hl_pts(tf)
            if side == "BUY" and sl:
                return float(sl["price"])
            if side == "SELL" and sh:
                return float(sh["price"])
        except Exception:
            pass
        return 0.0

    def _group_keys(self, tf: str) -> list[tuple]:
        keys = []
        for group in list(getattr(config, "SL_GUARD_GROUP_GROUPS", []) or []):
            if tf in group:
                keys.append(tuple(group))
        return keys

    def check_unblock(self, tf: str, side: str) -> None:
        if getattr(config, "SL_GUARD_ENABLED", False):
            st = self.per_tf.get((tf, side))
            if st and st.get("active"):
                ref = float(st.get("swing_ref", 0.0) or 0.0)
                cur = self._swing_ref(tf, side)
                if cur > 0 and ref > 0 and abs(cur - ref) > 0.01:
                    st["active"] = False

        if getattr(config, "SL_GUARD_COMBINED_ENABLED", False):
            st = self.combined.get(side)
            if st and st.get("tf_blocked", {}).get(tf):
                ref = float(st.get("tf_swing_ref", {}).get(tf, 0.0) or 0.0)
                cur = self._swing_ref(tf, side)
                if cur > 0 and ref > 0 and abs(cur - ref) > 0.01:
                    st["tf_blocked"][tf] = False

        if getattr(config, "SL_GUARD_GROUP_ENABLED", False):
            for key in self._group_keys(tf):
                st = self.group.get((side, key))
                if st and st.get("tf_blocked", {}).get(tf):
                    ref = float(st.get("tf_swing_ref", {}).get(tf, 0.0) or 0.0)
                    cur = self._swing_ref(tf, side)
                    if cur > 0 and ref > 0 and abs(cur - ref) > 0.01:
                        st["tf_blocked"][tf] = False

    def is_blocked(self, tf: str, side: str) -> bool:
        self.check_unblock(tf, side)
        if getattr(config, "SL_GUARD_ENABLED", False):
            st = self.per_tf.get((tf, side))
            if st and st.get("active"):
                return True
        if getattr(config, "SL_GUARD_COMBINED_ENABLED", False):
            st = self.combined.get(side)
            if st and st.get("tf_blocked", {}).get(tf):
                return True
        if getattr(config, "SL_GUARD_GROUP_ENABLED", False):
            for key in self._group_keys(tf):
                st = self.group.get((side, key))
                if st and st.get("tf_blocked", {}).get(tf):
                    return True
        return False

    def near_blocked(self, tf: str, side: str, entry: float, bar: dict) -> bool:
        if not self.is_blocked(tf, side):
            return False
        if side == "BUY":
            probe = float(bar["low"])
        else:
            probe = float(bar["high"])
        return abs(probe - float(entry)) <= self.near_price

    def record_close(self, tf: str, side: str, close_type: str, pnl: float) -> bool:
        loss_guard = (
            getattr(config, "SL_GUARD_LOSS_ENABLED", False)
            and float(pnl) < -float(getattr(config, "SL_GUARD_LOSS_THRESHOLD", 5.0) or 5.0)
        )
        if close_type == "TP":
            self._reset_on_tp(tf, side)
            return False
        if close_type != "SL" and not loss_guard:
            return False
        return self._record_sl(tf, side)

    def _record_sl(self, tf: str, side: str) -> bool:
        activated = False
        if getattr(config, "SL_GUARD_ENABLED", False):
            key = (tf, side)
            st = self.per_tf.setdefault(key, {"count": 0, "active": False, "swing_ref": 0.0})
            st["count"] += 1
            if st["count"] >= int(getattr(config, "SL_GUARD_COUNT", 2) or 2) and not st.get("active"):
                st["active"] = True
                st["swing_ref"] = self._swing_ref(tf, side)
                activated = True

        if getattr(config, "SL_GUARD_COMBINED_ENABLED", False):
            tfs = list(getattr(config, "SL_GUARD_COMBINED_TFS", []) or [])
            if tf in tfs:
                st = self.combined.setdefault(side, {"count": 0, "tf_blocked": {}, "tf_swing_ref": {}})
                st["count"] += 1
                if st["count"] >= int(getattr(config, "SL_GUARD_COMBINED_COUNT", 2) or 2):
                    was_blocked = any(st.get("tf_blocked", {}).values())
                    for t in tfs:
                        st["tf_blocked"][t] = True
                        st["tf_swing_ref"][t] = self._swing_ref(t, side) if t == tf else 0.0
                    activated = activated or not was_blocked

        if getattr(config, "SL_GUARD_GROUP_ENABLED", False):
            for key in self._group_keys(tf):
                st = self.group.setdefault((side, key), {"count": 0, "tf_blocked": {}, "tf_swing_ref": {}})
                st["count"] += 1
                if st["count"] >= int(getattr(config, "SL_GUARD_GROUP_COUNT", 2) or 2):
                    was_blocked = any(st.get("tf_blocked", {}).values())
                    for t in key:
                        st["tf_blocked"][t] = True
                        st["tf_swing_ref"][t] = self._swing_ref(t, side) if t == tf else 0.0
                    activated = activated or not was_blocked
        return activated

    def _reset_on_tp(self, tf: str, side: str) -> None:
        if getattr(config, "SL_GUARD_ENABLED", False):
            self.per_tf[(tf, side)] = {"count": 0, "active": False, "swing_ref": 0.0}
        if getattr(config, "SL_GUARD_COMBINED_ENABLED", False):
            self.combined.pop(side, None)
        if getattr(config, "SL_GUARD_GROUP_ENABLED", False):
            for key in self._group_keys(tf):
                self.group.pop((side, key), None)


def get_htf_rates_at_time(htf_tf: str, ltf_time: int, ltf_bars_so_far: list, htf_rates_all: list) -> list:
    """สร้างข้อมูลแท่งราคา HTF ณ เวลาปัจจุบันของ LTF (ป้องกันการ Lookahead)"""
    htf_secs = TF_SECONDS[htf_tf]
    htf_start_time = (ltf_time // htf_secs) * htf_secs
    
    # 1. แท่ง HTF ที่ปิดแล้ว (เวลาเปิดแท่ง < htf_start_time)
    closed_htf = [r for r in htf_rates_all if r["time"] < htf_start_time]
    
    # 2. จำลองแท่ง HTF ที่กำลังวิ่งอยู่ (In-progress) จากแท่ง LTF ที่เกิดขึ้นแล้ว
    window_ltf = []
    for b in reversed(ltf_bars_so_far):
        if b["time"] < htf_start_time:
            break
        window_ltf.append(b)
        
    if window_ltf:
        window_ltf.reverse()
        in_progress = {
            "time": htf_start_time,
            "open": window_ltf[0]["open"],
            "high": max(b["high"] for b in window_ltf),
            "low": min(b["low"] for b in window_ltf),
            "close": window_ltf[-1]["close"],
        }
        return closed_htf + [in_progress]
        
    return closed_htf


def check_pending_order_invalid(pending, current_ltf_bar, ltf_bars_so_far, htf_rates_all: list) -> str | None:
    """ตรวจสอบเงื่อนไขการยกเลิก Pending Order ของ S10"""
    sig = pending["signal"]
    parent_high = pending.get("s10_parent_high", 0.0)
    parent_low = pending.get("s10_parent_low", 0.0)
    parent_time = pending.get("s10_parent_time", 0)
    sweep_time = pending.get("s10_sweep_time", 0)
    htf_tf = pending.get("s10_htf_tf")
    
    htf_secs = TF_SECONDS[htf_tf]
    parent_close = parent_time + htf_secs
    
    # 1. LTF แตะขอบฝั่งตรงข้ามของ Parent ก่อนถูก fill (Parent High/Low Touch Cancel)
    if current_ltf_bar["time"] >= parent_close:
        if sig == "BUY" and parent_high > 0 and current_ltf_bar["high"] >= parent_high:
            return f"Touched parent high {parent_high:.2f} (BUY pending invalid)"
        elif sig == "SELL" and parent_low > 0 and current_ltf_bar["low"] <= parent_low:
            return f"Touched parent low {parent_low:.2f} (SELL pending invalid)"
            
    # ดึงข้อมูล HTF ณ เวลาปัจจุบันของ LTF
    htf_rates = get_htf_rates_at_time(htf_tf, current_ltf_bar["time"], ltf_bars_so_far, htf_rates_all)
    
    # 2. ตรวจสอบเงื่อนไขเมื่อแท่ง Sweep ของ HTF ปิดตัวลง (Sweep Recheck)
    if current_ltf_bar["time"] >= sweep_time + htf_secs:
        parent_bar = next((r for r in htf_rates if r["time"] == parent_time), None)
        sweep_bar = next((r for r in htf_rates if r["time"] == sweep_time), None)
        if parent_bar and sweep_bar:
            from strategy10 import is_s10_htf_sweep_valid
            bar_mode = pending.get("s10_bar_mode", "2bar")
            valid = is_s10_htf_sweep_valid(parent_bar, sweep_bar, sig, bar_mode)
            if not valid:
                return "Sweep candle failed validation upon HTF close (recheck fail)"
                
    # 3. HTF Structure Engulf (แท่ง HTF หลัง Sweep ปิดทะลุระดับ Parent low/high)
    closed_post_sweep = [r for r in htf_rates if sweep_time < r["time"] and r["time"] + htf_secs <= current_ltf_bar["time"]]
    for r in closed_post_sweep:
        if sig == "BUY" and parent_low > 0 and r["close"] < parent_low:
            return f"HTF bar closed below parent low {parent_low:.2f}"
        elif sig == "SELL" and parent_high > 0 and r["close"] > parent_high:
            return f"HTF bar closed above parent high {parent_high:.2f}"
            
    return None


def check_pending_order_pd_cancel(pending, current_ltf_bar, tf_name: str) -> tuple:
    """จำลองการเช็ค Premium/Discount zone สำหรับ Pending Order (2 รอบ)
    เลียนแบบ _pdfiboplus_process ใน trailing.py
    Return (should_cancel: bool, reason: str)
    """
    pd_enabled = getattr(config, 'PDFIBOPLUS_ENABLED', True)
    if not pd_enabled:
        return False, ""

    # ถ้าผ่าน round2 (pending) แล้ว -> skip ไม่ต้องเช็คซ้ำ
    if pending.get("pd_pending_passed"):
        return False, ""

    signal = pending["signal"]
    entry = pending["entry"]
    
    sh_pt, sl_pt = _hs.get_swing_hl_pts(tf_name)
    if not sh_pt or not sl_pt:
        return False, ""
    h = float(sh_pt["price"])
    l = float(sl_pt["price"])
    if h <= l:
        return False, ""

    # รอบที่ 1: เมื่อพึ่งสร้างออเดอร์ (ยังไม่มี pd_state)
    if "pd_state" not in pending:
        outside_pd = entry < l or entry > h
        fallback_used = False
        wait_round2 = False
        fb_h, fb_l = h, l
        
        if outside_pd:
            try:
                # ลองดึง swing ก่อนหน้าเพื่อทำ fallback
                prev_sh, prev_sl = _hs.get_prev_swing_hl_pts(tf_name)
                if signal == "BUY" and prev_sh is not None:
                    try_h = float(prev_sh["price"])
                    if try_h > fb_l:
                        fb_h = try_h
                        fallback_used = True
                elif signal == "SELL" and prev_sl is not None:
                    try_l = float(prev_sl["price"])
                    if fb_h > try_l:
                        fb_l = try_l
                        fallback_used = True
            except Exception:
                pass

        if fallback_used:
            fb_outside = entry < fb_l or entry > fb_h
            if fb_outside:
                # fallback แล้วยังนอกกรอบ -> รอรอบ 2 (ไม่ cancel ทันที)
                wait_round2 = True
                result = False
            else:
                fib_382 = fb_l + (fb_h - fb_l) * 0.382
                fib_618 = fb_l + (fb_h - fb_l) * 0.618
                if signal == "BUY":
                    result = entry < fib_382
                else:
                    result = entry > fib_618
        else:
            fib_382 = l + (h - l) * 0.382
            fib_618 = l + (h - l) * 0.618
            if signal == "BUY":
                result = entry < fib_382
            else:
                result = entry > fib_618

        # บันทึก state
        pending["pd_state"] = {
            "cur_h": h,
            "cur_l": l,
            "round1": 0 if wait_round2 else (1 if result else -1),
        }

        if wait_round2:
            return False, "wait"
        
        if not result:
            # รอบ 1 fail -> ยกเลิกทันที
            return True, "PD Zone Recheck: order อยู่นอก Premium/Discount zone (Round 1 Fail)"
        return False, ""

    else:
        # รอบที่ 2: รอ H/L เปลี่ยนครั้งแรก
        pd_state = pending["pd_state"]
        h_changed = abs(h - pd_state["cur_h"]) > 0.01
        l_changed = abs(l - pd_state["cur_l"]) > 0.01
        
        if h_changed or l_changed:
            fib_382 = l + (h - l) * 0.382
            fib_618 = l + (h - l) * 0.618
            if signal == "BUY":
                result = entry < fib_382
            else:
                result = entry > fib_618

            pd_state["cur_h"] = h
            pd_state["cur_l"] = l
            pending["pd_state"] = pd_state
            
            if result:
                pending["pd_pending_passed"] = True
                return False, ""
            else:
                return True, "PD Zone Recheck: order อยู่นอก Premium/Discount zone (Round 2 Fail)"

    return False, ""


def backtest_tf(tf_name: str, tf_val: int) -> list:
    global VOLUME, PRICE_TO_USD, CURRENT_SIM_TIME
    _PD_ENABLED = False  # S10 does not use PD Fibo Plus in live runtime.
    VOLUME = getattr(config, 'AUTO_VOLUME', 0.01)
    if getattr(config, 'SCALE_OUT_ENABLED', False):
        VOLUME = config.scale_out_total_volume()
    PRICE_TO_USD = 100 * VOLUME

    # ดึงแท่งราคา LTF
    rates = _copy_rates_covering_since(SYMBOL, tf_val, tf_name)
    if rates is None or len(rates) == 0:
        return []

    bars = [
        {'time': int(r['time']), 'open': float(r['open']),
         'high': float(r['high']), 'low': float(r['low']),
         'close': float(r['close'])}
        for r in rates
    ]

    # ดึงและเตรียมข้อมูลของ HTF ทุกตัวที่จับคู่กับ LTF นี้
    htf_list = _LTF_TO_HTFS.get(tf_name, [])
    htf_rates_all = {}
    for htf in htf_list:
        htf_val_const = mt5.TIMEFRAME_H4 if htf == 'H4' else (mt5.TIMEFRAME_D1 if htf == 'D1' else (mt5.TIMEFRAME_H12 if htf == 'H12' else (mt5.TIMEFRAME_H1 if htf == 'H1' else (mt5.TIMEFRAME_M30 if htf == 'M30' else mt5.TIMEFRAME_M15))))
        raw_htf = _copy_rates_covering_since(SYMBOL, htf_val_const, htf)
        if raw_htf is not None:
            htf_rates_all[htf] = [
                {'time': int(r['time']), 'open': float(r['open']),
                 'high': float(r['high']), 'low': float(r['low']),
                 'close': float(r['close'])}
                for r in raw_htf
            ]
        else:
            htf_rates_all[htf] = []

    since_ts = int(SINCE.timestamp())
    window_needed = 200 # สำหรับ LTF lookback

    # หาดัชนีเริ่มต้น
    start_idx = None
    for i, b in enumerate(bars):
        if b['time'] >= since_ts and i >= window_needed:
            start_idx = i
            break
    if start_idx is None:
        return []

    trades = []
    pending_orders = []   # วาง Pending Limit รอราคาเกี่ยว
    in_trades = []        # ออเดอร์ที่ถูก fill และถือครองอยู่
    sl_guard = SimSLGuard()
    guard_closed_tickets = set()
    ticket_counter = 100000
    
    # รีเซ็ตสถานะภายในโมดูล strategy10
    reset_mtf_state()
    
    # ติดตามเวลาของแท่ง HTF ล่าสุดที่สแกนไปแล้วเพื่อป้องกันสแกนซ้ำซ้อน
    last_scanned_htf_times = {htf: None for htf in htf_list}

    for i in range(start_idx, len(bars)):
        b = bars[i]
        CURRENT_SIM_TIME = int(b['time'])
        bt = to_bkk(b['time'])
        ltf_bars_so_far = bars[:i + 1]

        # 1. ทำการคำนวณและอัปเดตระดับสวิงราคา HHLL ปัจจุบัน
        _inject_hhll(tf_name, ltf_bars_so_far)
        sl_guard.check_unblock(tf_name, "BUY")
        sl_guard.check_unblock(tf_name, "SELL")

        def _cancel_guard_scope(side: str, reason: str, skip_ticket: int | None = None) -> None:
            nonlocal pending_orders, in_trades
            if not getattr(config, "SL_GUARD_CLOSE_ON_ACTIVATE", True):
                return
            kept_pending = []
            for p in pending_orders:
                if p.get("signal") == side:
                    trades.append({
                        **p,
                        'close_type': 'CANCEL',
                        'close_price': b['open'],
                        'close_time': bt,
                        'pnl': 0.0,
                        'cancel_reason': reason,
                    })
                    from strategy10 import handle_ticket_closed
                    handle_ticket_closed(p['s10_htf_tf'], p['ticket'], "cancel")
                else:
                    kept_pending.append(p)
            pending_orders = kept_pending

            kept_trades = []
            for t in in_trades:
                if skip_ticket is not None and t.get("ticket") == skip_ticket:
                    kept_trades.append(t)
                    continue
                if t.get("signal") == side:
                    close_px = float(b['close'])
                    pnl = profit(close_px - t['entry']) if side == 'BUY' else profit(t['entry'] - close_px)
                    trades.append({
                        **t,
                        'close_type': 'SL_GUARD_CLOSE',
                        'close_price': close_px,
                        'close_time': bt,
                        'pnl': pnl,
                        'cancel_reason': reason,
                    })
                    guard_closed_tickets.add(t.get("ticket"))
                    from strategy10 import handle_ticket_closed
                    handle_ticket_closed(t['s10_htf_tf'], t['ticket'], "cancel")
                else:
                    kept_trades.append(t)
            in_trades = kept_trades

        # 2. ตรวจสอบออเดอร์ที่ถูกเติม (Position ในตลาด)
        still_in_trades = []
        for in_trade in in_trades:
            if in_trade.get("ticket") in guard_closed_tickets:
                continue
            pd_closed = False
            # 2.1 PD Fibo Plus is skipped for S10.
            if _PD_ENABLED and in_trade.get('pd_result') == 'PASS':
                try:
                    sh_pt, sl_pt = _hs.get_swing_hl_pts(tf_name)
                    if sh_pt and sl_pt:
                        curr_h = float(sh_pt["price"])
                        curr_l = float(sl_pt["price"])
                        fill_h = in_trade.get('fill_h')
                        fill_l = in_trade.get('fill_l')
                        if fill_h is not None and fill_l is not None:
                            if abs(curr_h - fill_h) > 0.01 or abs(curr_l - fill_l) > 0.01:
                                fib_382 = curr_l + (curr_h - curr_l) * 0.382
                                fib_618 = curr_l + (curr_h - curr_l) * 0.618
                                r2_fibo_pct = ((in_trade['entry'] - curr_l) / (curr_h - curr_l)) * 100
                                r2_pass = False
                                if in_trade['signal'] == "BUY":
                                    r2_pass = in_trade['entry'] < fib_382
                                elif in_trade['signal'] == "SELL":
                                    r2_pass = in_trade['entry'] > fib_618
                                
                                in_trade['fill_h'] = curr_h
                                in_trade['fill_l'] = curr_l
                                in_trade['pd_h'] = curr_h
                                in_trade['pd_l'] = curr_l
                                in_trade['pd_h_time'] = int(sh_pt["time"])
                                in_trade['pd_l_time'] = int(sl_pt["time"])
                                in_trade['pd_fibo_pct'] = r2_fibo_pct
                                
                                if not r2_pass:
                                    pnl = profit(b['open'] - in_trade['entry']) if in_trade['signal'] == 'BUY' else profit(in_trade['entry'] - b['open'])
                                    trades.append({
                                        **in_trade, 'close_type': 'PD_FAIL',
                                        'close_price': b['open'], 'close_time': bt, 'pnl': pnl,
                                        'pd_result': 'FAIL', 'pd_round': 2,
                                        'pd_h': curr_h, 'pd_l': curr_l,
                                        'pd_h_time': int(sh_pt["time"]), 'pd_l_time': int(sl_pt["time"])
                                    })
                                    from strategy10 import handle_ticket_closed
                                    handle_ticket_closed(in_trade['s10_htf_tf'], in_trade['ticket'], "sl")
                                    pd_closed = True
                except Exception:
                    pass

            if pd_closed:
                continue

            # 2.2 ตรวจสอบเงื่อนไขตัดขาดทุน (SL) หรือ ทำกำไร (TP)
            h_val, l_val = b['high'], b['low']
            sig = in_trade['signal']
            trade_closed = False
            if sig == 'BUY':
                if l_val <= in_trade['sl']:
                    pnl = profit(in_trade['sl'] - in_trade['entry'])
                    trades.append({**in_trade, 'close_type': 'SL',
                                   'close_price': in_trade['sl'], 'close_time': bt, 'pnl': pnl})
                    if sl_guard.record_close(tf_name, sig, "SL", pnl):
                        _cancel_guard_scope(sig, "SL Guard activated after SL hit", in_trade.get("ticket"))
                    from strategy10 import handle_ticket_closed
                    handle_ticket_closed(in_trade['s10_htf_tf'], in_trade['ticket'], "sl")
                    trade_closed = True
                elif h_val >= in_trade['tp']:
                    pnl = profit(in_trade['tp'] - in_trade['entry'])
                    trades.append({**in_trade, 'close_type': 'TP',
                                   'close_price': in_trade['tp'], 'close_time': bt, 'pnl': pnl})
                    sl_guard.record_close(tf_name, sig, "TP", pnl)
                    from strategy10 import handle_ticket_closed
                    handle_ticket_closed(in_trade['s10_htf_tf'], in_trade['ticket'], "tp")
                    trade_closed = True
            else:  # SELL
                if h_val >= in_trade['sl']:
                    pnl = profit(in_trade['entry'] - in_trade['sl'])
                    trades.append({**in_trade, 'close_type': 'SL',
                                   'close_price': in_trade['sl'], 'close_time': bt, 'pnl': pnl})
                    if sl_guard.record_close(tf_name, sig, "SL", pnl):
                        _cancel_guard_scope(sig, "SL Guard activated after SL hit", in_trade.get("ticket"))
                    from strategy10 import handle_ticket_closed
                    handle_ticket_closed(in_trade['s10_htf_tf'], in_trade['ticket'], "sl")
                    trade_closed = True
                elif l_val <= in_trade['tp']:
                    pnl = profit(in_trade['entry'] - in_trade['tp'])
                    trades.append({**in_trade, 'close_type': 'TP',
                                   'close_price': in_trade['tp'], 'close_time': bt, 'pnl': pnl})
                    sl_guard.record_close(tf_name, sig, "TP", pnl)
                    from strategy10 import handle_ticket_closed
                    handle_ticket_closed(in_trade['s10_htf_tf'], in_trade['ticket'], "tp")
                    trade_closed = True

            if not trade_closed:
                still_in_trades.append(in_trade)
        in_trades = still_in_trades

        # 3. ตรวจสอบออเดอร์ที่ตั้งรอไว้ (Pending Limit)
        still_pending = []
        tickets_to_cancel = set()
        for pending in pending_orders:
            # Check if this ticket was marked for sibling cancellation in this same bar
            if pending["ticket"] in tickets_to_cancel:
                trades.append({
                    **pending,
                    'close_type': 'CANCEL',
                    'close_price': b['open'],
                    'close_time': bt,
                    'pnl': 0.0,
                    'cancel_reason': "S10 Sibling order filled"
                })
                from strategy10 import handle_ticket_closed
                handle_ticket_closed(pending['s10_htf_tf'], pending['ticket'], "cancel")
                continue
            # 3.1 ตรวจสอบเงื่อนไขการโดนยกเลิกออเดอร์ (Cancel Criteria)
            if sl_guard.near_blocked(tf_name, pending["signal"], pending["entry"], b):
                trades.append({
                    **pending,
                    'close_type': 'CANCEL',
                    'close_price': b['open'],
                    'close_time': bt,
                    'pnl': 0.0,
                    'cancel_reason': "SL Guard active near entry"
                })
                from strategy10 import handle_ticket_closed
                handle_ticket_closed(pending['s10_htf_tf'], pending['ticket'], "cancel")
                continue

            cancel_reason = check_pending_order_invalid(pending, b, ltf_bars_so_far, htf_rates_all[pending['s10_htf_tf']])
            if cancel_reason:
                trades.append({
                    **pending,
                    'close_type': 'CANCEL',
                    'close_price': b['open'],
                    'close_time': bt,
                    'pnl': 0.0,
                    'cancel_reason': cancel_reason
                })
                from strategy10 import handle_ticket_closed
                handle_ticket_closed(pending['s10_htf_tf'], pending['ticket'], "cancel")
                continue

            # 3.1.2 PD Fibo Plus is skipped for S10.
            if _PD_ENABLED:
                pd_cancel, pd_reason = check_pending_order_pd_cancel(pending, b, tf_name)
                if pd_cancel:
                    trades.append({
                        **pending,
                        'close_type': 'PD_FAIL',
                        'close_price': pending['entry'],
                        'close_time': bt,
                        'pnl': 0.0,
                        'cancel_reason': pd_reason
                    })
                    from strategy10 import handle_ticket_closed
                    handle_ticket_closed(pending['s10_htf_tf'], pending['ticket'], "cancel")
                    continue
                
            # 3.2 ตรวจสอบเงื่อนไขราคาเกี่ยวออเดอร์สำเร็จ (Fill Check)
            sig = pending['signal']
            entry_price = pending['entry']
            is_filled = False
            if sig == 'BUY' and b['low'] <= entry_price:
                is_filled = True
            elif sig == 'SELL' and b['high'] >= entry_price:
                is_filled = True
                
            if is_filled:
                in_trade_obj = {
                    **pending,
                    'entry_time': bt,
                    'entry_time_raw': int(b['time']),
                    'entry_idx': i
                }
                
                # PD Fibo Plus is skipped for S10.
                if _PD_ENABLED:
                    pd_pass, fibo_pct, fill_h, fill_l, fill_h_time, fill_l_time = _check_pd_fibo(
                        in_trade_obj['signal'], in_trade_obj['entry'], tf_name
                    )
                    in_trade_obj['pd_result'] = 'PASS' if pd_pass else 'FAIL'
                    in_trade_obj['pd_round'] = 1
                    if fibo_pct is not None:
                        in_trade_obj['pd_fibo_pct'] = fibo_pct
                    if fill_h is not None:
                        in_trade_obj['fill_h'] = fill_h
                        in_trade_obj['fill_l'] = fill_l
                        in_trade_obj['pd_h'] = fill_h
                        in_trade_obj['pd_l'] = fill_l
                        in_trade_obj['pd_h_time'] = fill_h_time
                        in_trade_obj['pd_l_time'] = fill_l_time
                        
                    if not pd_pass:
                        # ถูกปิดตัดสิทธิ์ทันที ณ ราคาเข้า (PnL = 0)
                        trades.append({**in_trade_obj, 'close_type': 'PD_FAIL',
                                       'close_price': in_trade_obj['entry'], 'close_time': bt, 'pnl': 0.0})
                        from strategy10 import handle_ticket_closed
                        handle_ticket_closed(in_trade_obj['s10_htf_tf'], in_trade_obj['ticket'], "cancel")
                        continue
                
                in_trades.append(in_trade_obj)
                
                # S10 sibling cancellation
                sibling_tickets = pending.get("s10_sibling_tickets") or []
                for sib in sibling_tickets:
                    if sib != pending["ticket"]:
                        tickets_to_cancel.add(sib)
                        # If the sibling has already been added to still_pending, cancel it
                        sibling_in_still = next((p for p in still_pending if p["ticket"] == sib), None)
                        if sibling_in_still:
                            trades.append({
                                **sibling_in_still,
                                'close_type': 'CANCEL',
                                'close_price': b['open'],
                                'close_time': bt,
                                'pnl': 0.0,
                                'cancel_reason': f"S10 Sibling order filled (ticket {pending['ticket']})"
                            })
                            from strategy10 import handle_ticket_closed
                            handle_ticket_closed(sibling_in_still['s10_htf_tf'], sibling_in_still['ticket'], "cancel")
                            still_pending = [p for p in still_pending if p["ticket"] != sib]
            else:
                still_pending.append(pending)
        pending_orders = still_pending

        # 4. สแกนหาสัญญาณเข้าใหม่
        # 4.1 ตรวจสอบการอัปเดตสัญญาณของฝั่ง HTF (Closed Bars)
        # รันเหมือน scanner คอยมอนิเตอร์แท่งปิด H4 เพื่อทำการ Arm
        for htf in htf_list:
            htf_rates = htf_rates_all[htf]
            htf_secs = TF_SECONDS[htf]
            
            # ดึงแท่ง H4 ที่ปิดสมบูรณ์แล้ว ณ เวลาปัจจุบันของ LTF
            closed_htf = [r for r in htf_rates if r["time"] + htf_secs <= b["time"]]
            if closed_htf:
                last_closed_t = closed_htf[-1]["time"]
                if last_scanned_htf_times[htf] is None or last_closed_t > last_scanned_htf_times[htf]:
                    # รันเช็คปิดแท่ง H4 เพื่อสร้าง arm state
                    strategy_10(closed_htf, htf)
                    last_scanned_htf_times[htf] = last_closed_t

        # 4.2 ตรวจสอบการทำ Pre-Sweep บน HTF (ยังไม่ปิดแท่ง)
        # (จะข้ามการทำตรงนี้ทั้งหมดหากเปิดใช้ Option CRT_WAIT_HTF_CLOSE = True)
        if not getattr(config, "CRT_WAIT_HTF_CLOSE", False):
            from strategy10 import _armed_states
            for htf in htf_list:
                if not _armed_states.get(htf):
                    # สร้างจำลอง H4 Rates ที่รวมแท่งปัจจุบันที่กำลังวิ่งอยู่
                    htf_rates_with_current = get_htf_rates_at_time(htf, b["time"], ltf_bars_so_far, htf_rates_all[htf])
                    try_pre_arm_htf(htf, htf_rates_with_current)

        # 4.3 สแกนหาจุดเข้าทางฝั่ง LTF (Model 1 & 2)
        # ส่งข้อมูลแท่ง M5 เข้าไปเพื่อหาจุดเข้าใน LTF
        r10 = strategy_10(ltf_bars_so_far, tf_name)
        if r10.get("signal") in ("BUY", "SELL") and r10.get("s10_model_orders"):
            if sl_guard.is_blocked(tf_name, r10["signal"]):
                trades.append({
                    "ticket": 0,
                    "signal": r10["signal"],
                    "entry": float(r10.get("entry", 0.0) or 0.0),
                    "sl": float(r10.get("sl", 0.0) or 0.0),
                    "tp": float(r10.get("tp", 0.0) or 0.0),
                    "pattern": r10.get("pattern", "S10"),
                    "entry_time": bt,
                    "entry_time_raw": int(b['time']),
                    "s10_htf_tf": r10.get("htf_tf") or (htf_list[0] if htf_list else ""),
                    "close_type": "BLOCK",
                    "close_price": float(r10.get("entry", 0.0) or 0.0),
                    "close_time": bt,
                    "pnl": 0.0,
                    "cancel_reason": "SL Guard blocked new LIMIT",
                })
                continue
            # ดึงข้อมูลการ Arm
            from strategy10 import _armed_states
            active_htf = r10.get("htf_tf") or (htf_list[0] if htf_list else "")
            state = _armed_states.get(active_htf)
            
            # ถอดข้อมูลการวางออเดอร์
            parent_high = 0.0
            parent_low = 0.0
            parent_time = 0
            sweep_time = 0
            bar_mode = "2bar"
            if state:
                parent_time = int(state.get("candles", [{}])[0].get("time", 0) or 0)
                sweep_time = int(state.get("armed_at", 0) or 0)
                parent_high = float(state.get("candles", [{}])[0].get("high", 0.0) or 0.0)
                parent_low = float(state.get("candles", [{}])[0].get("low", 0.0) or 0.0)
                bar_mode = state.get("s10_bar_mode", "2bar")
            
            specs_to_place = []
            for spec in r10["s10_model_orders"]:
                ticket_counter += 1
                specs_to_place.append((ticket_counter, spec))

            placed_pending = []
            placed_tickets = []
            for tkt, spec in specs_to_place:
                pending_order_obj = {
                    "ticket":           tkt,
                    "signal":           r10["signal"],
                    "entry":            float(spec["entry"]),
                    "sl":               float(r10["sl"]),
                    "tp":               float(r10["tp"]),
                    "pattern":          spec["pattern"],
                    "entry_time":       bt,
                    "entry_time_raw":   int(b['time']),
                    "s10_htf_tf":       active_htf,
                    "s10_parent_time":  parent_time,
                    "s10_sweep_time":   sweep_time,
                    "s10_parent_high":  parent_high,
                    "s10_parent_low":   parent_low,
                    "s10_bar_mode":     bar_mode,
                    "s10_sibling_tickets": [],
                    "s10_m1_price":     r10.get("s10_m1_price"),
                    "s10_m1_time":      r10.get("s10_m1_time"),
                    "s10_m2_price":     r10.get("s10_m2_price"),
                    "s10_m2_time":      r10.get("s10_m2_time"),
                    "s10_m3_price":     r10.get("s10_m3_price"),
                    "s10_m3_time":      r10.get("s10_m3_time"),
                }
                
                placed_pending.append(pending_order_obj)
                placed_tickets.append(tkt)

            if placed_tickets:
                from strategy10 import register_fired_tickets
                register_fired_tickets(active_htf, placed_tickets)
                for pending_order_obj in placed_pending:
                    pending_order_obj["s10_sibling_tickets"] = placed_tickets
                    pending_orders.append(pending_order_obj)

    # จัดการออเดอร์ที่ค้างอยู่ ณ สิ้นสุดการเทส
    if bars:
        lc  = bars[-1]['close']
        lt  = to_bkk(bars[-1]['time'])
        for in_trade in in_trades:
            sig = in_trade['signal']
            pnl = profit(lc - in_trade['entry']) if sig == 'BUY' else profit(in_trade['entry'] - lc)
            trades.append({**in_trade, 'close_type': 'OPEN', 'close_price': lc, 'close_time': lt, 'pnl': pnl})
            
        for pending in pending_orders:
            trades.append({**pending, 'close_type': 'OPEN_PENDING', 'close_price': pending['entry'], 'close_time': lt, 'pnl': 0.0})

    CURRENT_SIM_TIME = 0.0
    return trades


def main():
    if not mt5.initialize():
        print('MT5 init failed:', mt5.last_error())
        return

    # Load auto trade config state from bot_state.json
    config.restore_runtime_state()
    sync_strategy10_runtime_config()

    # Calculate actual volume for display
    display_vol = getattr(config, 'AUTO_VOLUME', 0.01)
    if getattr(config, 'SCALE_OUT_ENABLED', False):
        display_vol = config.scale_out_total_volume()

    print(f'Symbol : {SYMBOL}')
    print(f'Since  : {SINCE.strftime("%d-%m-%Y")}  Volume: {display_vol} lot')
    print(f'S10 Settings: active_strategies[10]={config.active_strategies.get(10, False)}')
    print(f'              CRT_BAR_MODE={getattr(config,"CRT_BAR_MODE","2bar")}  CRT_ENTRY_MODE={getattr(config,"CRT_ENTRY_MODE","htf")}')
    print(f'              CRT_WAIT_HTF_CLOSE={getattr(config,"CRT_WAIT_HTF_CLOSE",False)} | CRT_PARENT_MIN_BODY_PCT={getattr(config,"CRT_PARENT_MIN_BODY_PCT",0.50)} | PDFIBOPLUS_ENABLED={getattr(config,"PDFIBOPLUS_ENABLED",True)} | PD_SKIP_SIDS=9,10,13,14,15,16')
    print('=' * 65)

    if not config.active_strategies.get(10, False):
        print("❌ S10 is disabled (OFF) in config! Skip backtest.")
        mt5.shutdown()
        return

    grand_total = 0.0
    all_trades  = []

    for tf_name, tf_val in TF_MAP.items():
        trades = backtest_tf(tf_name, tf_val)
        all_trades.extend([(t.get("s10_htf_tf", tf_name), t) for t in trades])

        if not trades:
            print(f'\n{tf_name}: ไม่พบ signal')
            continue

        tp_cnt  = sum(1 for t in trades if t['close_type'] == 'TP')
        sl_cnt  = sum(1 for t in trades if t['close_type'] == 'SL')
        cc_cnt  = sum(1 for t in trades if t['close_type'] == 'CANCEL')
        pdf_cnt = sum(1 for t in trades if t['close_type'] == 'PD_FAIL')
        op_cnt  = sum(1 for t in trades if t['close_type'] == 'OPEN')
        total   = sum(t['pnl'] for t in trades)
        grand_total += total

        from collections import defaultdict
        htf_groups = defaultdict(list)
        for t in trades:
            htf_groups[t.get("s10_htf_tf", tf_name)].append(t)

        for htf_name, grp_trades in htf_groups.items():
            grp_tp  = sum(1 for t in grp_trades if t['close_type'] == 'TP')
            grp_sl  = sum(1 for t in grp_trades if t['close_type'] == 'SL')
            grp_cc  = sum(1 for t in grp_trades if t['close_type'] == 'CANCEL')
            grp_pdf = sum(1 for t in grp_trades if t['close_type'] == 'PD_FAIL')
            grp_op  = sum(1 for t in grp_trades if t['close_type'] == 'OPEN')
            grp_total = sum(t['pnl'] for t in grp_trades)
            grp_wr  = grp_tp / (grp_tp + grp_sl) * 100 if (grp_tp + grp_sl) > 0 else 0

            print(f'\n── {htf_name} ─────────────────────────────────────────')
            print(f'   trades={len(grp_trades)}  TP={grp_tp}  SL={grp_sl}  CANCEL={grp_cc}  PD_FAIL={grp_pdf}  OPEN={grp_op}  WR={grp_wr:.0f}%')
            print(f'   P&L total: {"+" if grp_total>=0 else ""}{grp_total:.2f} USD')

            # แสดงรายการเทรด
            for t in grp_trades:
                dt  = t['entry_time'].strftime('%d-%m %H:%M')
                ct  = t['close_time'].strftime('%H:%M') if t['close_type'] not in ('OPEN', 'OPEN_PENDING') else 'OPEN'
                pnl_s = f'{"+" if t["pnl"]>=0 else ""}{t["pnl"]:.2f}'
                cancel_str = f" [{t['cancel_reason']}]" if t.get('cancel_reason') else ""
                print(f'   {dt} {t["signal"]:<4} E={t["entry"]:.2f} SL={t["sl"]:.2f} TP={t["tp"]:.2f} '
                      f'→ {t["close_type"]:<6} @ {t.get("close_price", 0):.2f}{cancel_str} [{ct}]  {pnl_s} USD  [{t["pattern"]}]')

    print('\n' + '=' * 65)
    print(f'GRAND TOTAL: {"+" if grand_total>=0 else ""}{grand_total:.2f} USD  (ทุก TF รวมกัน, volume={VOLUME} lot each)')

    # ตารางสรุป
    print('\n── สรุปตาม TF ─────────────────────────────────────────────')
    print(f'{"TF":<10} {"Trades":>7} {"TP":>5} {"SL":>5} {"CANCEL":>7} {"PD_FAIL":>7} {"WR%":>6} {"P&L":>10}')
    print('-' * 64)
    HTF_LIST = ["M15", "M30", "H1", "H4", "H12", "D1"]
    HTF_TO_LTF_DISPLAY = {
        "M15": "M15 (M1)",
        "M30": "M30 (M1)",
        "H1":  "H1 (M1)",
        "H4":  "H4 (M5)",
        "H12": "H12 (M15)",
        "D1":  "D1 (M15)",
    }
    for tf_name in HTF_LIST:
        tf_trades = [t for n, t in all_trades if n == tf_name]
        disp_name = HTF_TO_LTF_DISPLAY.get(tf_name, tf_name)
        if not tf_trades:
            print(f'{disp_name:<10} {"0":>7}')
            continue
        tp = sum(1 for t in tf_trades if t['close_type'] == 'TP')
        sl = sum(1 for t in tf_trades if t['close_type'] == 'SL')
        cc = sum(1 for t in tf_trades if t['close_type'] == 'CANCEL')
        pdf = sum(1 for t in tf_trades if t['close_type'] == 'PD_FAIL')
        wr = tp / (tp + sl) * 100 if (tp + sl) > 0 else 0
        pnl = sum(t['pnl'] for t in tf_trades)
        print(f'{disp_name:<10} {len(tf_trades):>7} {tp:>5} {sl:>5} {cc:>7} {pdf:>7} {wr:>5.0f}% {pnl:>+10.2f}')
    print('-' * 64)
    print(f'{"TOTAL":<10} {len(all_trades):>7} '
          f'{sum(1 for _,t in all_trades if t["close_type"]=="TP"):>5} '
          f'{sum(1 for _,t in all_trades if t["close_type"]=="SL"):>5} '
          f'{sum(1 for _,t in all_trades if t["close_type"]=="CANCEL"):>7} '
          f'{sum(1 for _,t in all_trades if t["close_type"]=="PD_FAIL"):>7} '
          f'{"":>6} {grand_total:>+10.2f}')

    mt5.shutdown()

if __name__ == '__main__':
    main()
