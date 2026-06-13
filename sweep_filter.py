# sweep_filter.py
# ──────────────────────────────────────────────────────────────────────
# Sweep Low / Sweep High Filter
#   SWEEP_LOW  → Block SELL, Unblock BUY  (ราคา sweep low แล้ว bounce ขึ้น)
#   SWEEP_HIGH → Block BUY,  Unblock SELL (ราคา sweep high แล้ว reject ลง)
#
# Aligned with S14 (strategy14.py):
#   - Pattern A matches S14 Sweep Swing (no HTF check, 1 green/red confirm)
#   - Pattern B matches S14 Engulf Swing (HTF closing color check, secondary HTF check)
#   - Swing Reference selection and Close Invalidation match S14
# ──────────────────────────────────────────────────────────────────────

import MetaTrader5 as mt5
from datetime import datetime, timedelta, timezone

try:
    from config import TF_OPTIONS, SYMBOL
    from mt5_utils import connect_mt5
    import config as _cfg_mod
except ImportError:
    TF_OPTIONS = {}
    SYMBOL = ""
    _cfg_mod = None
    def connect_mt5(): return False

# ── State per TF ──────────────────────────────────────────────────────
_sweep_state:      dict[str, str]   = {}  # "SWEEP_LOW" | "SWEEP_HIGH"
_sweep_price:      dict[str, float] = {}  # ราคา swing ที่เป็น reference
_sweep_at:         dict[str, str]   = {}  # เวลา detect (BKK string)
_sweep_ts:         dict[str, int]   = {}  # เวลา detect (unix ของ trigger bar) — ใช้เช็ค expiry
_prev_trend:       dict[str, str]   = {}  # track trend เพื่อ detect change
_prev_last_label:  dict[str, str]   = {}  # track last swing label เพื่อ detect change

_BKK = timezone(timedelta(hours=7))

TF_SECONDS = {
    "M1": 60, "M5": 300, "M15": 900, "M30": 1800,
    "H1": 3600, "H4": 14400, "H12": 43200, "D1": 86400,
}

TRADING_TFS = ["M1", "M5", "M15", "M30", "H1"]

HIGH_TYPES = ("HH", "LH")
LOW_TYPES  = ("LL", "HL")


# ── Public API ────────────────────────────────────────────────────────

def is_enabled() -> bool:
    if _cfg_mod is None:
        return False
    return bool(getattr(_cfg_mod, "SWEEP_FILTER_ENABLED", False))


def get_sweep_state(tf: str) -> str | None:
    """คืน 'SWEEP_LOW' | 'SWEEP_HIGH' | None"""
    if not is_enabled():
        return None
    # หมดอายุ → reset แล้วคืน None
    if _sweep_state.get(tf) and _is_expired(tf):
        reset_sweep(tf, reason="expired")
        return None
    return _sweep_state.get(tf)


def get_sweep_info(tf: str) -> dict:
    return {
        "state": _sweep_state.get(tf),
        "price": _sweep_price.get(tf),
        "time":  _sweep_at.get(tf, ""),
    }


def reset_sweep(tf: str, reason: str = "") -> None:
    prev = _sweep_state.get(tf)
    if prev:
        try:
            from bot_log import log_event as _log
            _log("SWEEP_RESET", prev, tf=tf, reason=reason or "-")
        except Exception:
            pass
    _sweep_state.pop(tf, None)
    _sweep_price.pop(tf, None)
    _sweep_at.pop(tf, None)
    _sweep_ts.pop(tf, None)


def reset_all() -> None:
    _sweep_state.clear()
    _sweep_price.clear()
    _sweep_at.clear()
    _sweep_ts.clear()


def update_trend_and_check_reset(tf: str, current_trend: str,
                                  last_label: str = "") -> bool:
    """
    เรียกทุก scan cycle: reset sweep state เมื่อ trend หรือ last swing label เปลี่ยน
    """
    prev_trend  = _prev_trend.get(tf)
    prev_label  = _prev_last_label.get(tf, "")

    _prev_trend[tf] = current_trend
    if last_label:
        _prev_last_label[tf] = last_label

    trend_changed = (prev_trend is not None and prev_trend != current_trend)
    label_changed = (
        current_trend == "SIDEWAY"
        and bool(last_label) and bool(prev_label)
        and prev_label != last_label
    )

    if trend_changed or label_changed:
        reason = f"trend_changed:{prev_trend}→{current_trend}" if trend_changed else f"label_changed:{prev_label}→{last_label}"
        reset_sweep(tf, reason=reason)
        return True
    return False


# ── S14-Aligned Helper Functions ───────────────────────────────────────

def _get_s14_htf(tf_name: str) -> str:
    mapping = {
        "M1": "M5",
        "M5": "M15",
        "M15": "H1",
        "M30": "H4",
        "H1": "H4",
        "H4": "D1"
    }
    return mapping.get(tf_name, "M5")


def _get_next_std_tf(tf_name: str) -> str:
    tfs = ["M1", "M5", "M15", "M30", "H1", "H4", "H12", "D1"]
    try:
        idx = tfs.index(tf_name)
        if idx < len(tfs) - 1:
            return tfs[idx + 1]
    except ValueError:
        pass
    return "M5"


def _is_sec_htf_currently_sweep(rates, tf_name: str, sec_htf_name: str, ref_level: float, is_buy: bool) -> bool:
    tf_secs = TF_SECONDS.get(tf_name, 60)
    sec_htf_secs = TF_SECONDS.get(sec_htf_name, 1800)
    next_bar_time = int(rates[-1]["time"]) + tf_secs
    sec_htf_start_time = ((next_bar_time - 1) // sec_htf_secs) * sec_htf_secs
    sub_rates = [r for r in rates if int(r["time"]) >= sec_htf_start_time]
    if not sub_rates:
        return False
    if is_buy:
        lowest_low = min(float(r["low"]) for r in sub_rates)
        return lowest_low < ref_level
    else:
        highest_high = max(float(r["high"]) for r in sub_rates)
        return highest_high > ref_level


def _get_htf_bar(tf_name: str, target_time: int, htf_rates_lookup: dict = None):
    if htf_rates_lookup is not None:
        return htf_rates_lookup.get(target_time)

    # Live bot case:
    try:
        import MetaTrader5 as mt5
        htf = _get_s14_htf(tf_name)
        htf_const = getattr(mt5, f"TIMEFRAME_{htf.upper()}")
        rates_raw = mt5.copy_rates_range(SYMBOL, htf_const, target_time, target_time + 10)
        if rates_raw is not None and len(rates_raw) > 0:
            r = rates_raw[0]
            return {
                "time": int(r["time"]),
                "open": float(r["open"]),
                "high": float(r["high"]),
                "low": float(r["low"]),
                "close": float(r["close"])
            }
    except Exception:
        pass
    return None


def _pivot_rsi_buy(rates, rsi_vals, idx):
    for j in range(idx, max(idx - 3, -1), -1):
        if j >= 0 and float(rates[j]["close"]) < float(rates[j]["open"]):
            return rsi_vals[j]
    return rsi_vals[idx]


def _pivot_rsi_sell(rates, rsi_vals, idx):
    for j in range(idx, max(idx - 3, -1), -1):
        if j >= 0 and float(rates[j]["close"]) > float(rates[j]["open"]):
            return rsi_vals[j]
    return rsi_vals[idx]


# ── Keep compatibility helpers for old scripts ──────────────────────────

def _get_latest_high_swing(d: dict) -> tuple[str, float, int] | None:
    candidates = []
    for lbl in ("HH", "LH"):
        pt = d.get(lbl.lower())
        if pt and pt.get("time") and pt.get("price"):
            candidates.append((lbl, float(pt["price"]), int(pt["time"])))
    if not candidates:
        return None
    return max(candidates, key=lambda x: x[2])


def _get_latest_low_swing(d: dict) -> tuple[str, float, int] | None:
    candidates = []
    for lbl in ("HL", "LL"):
        pt = d.get(lbl.lower())
        if pt and pt.get("time") and pt.get("price"):
            candidates.append((lbl, float(pt["price"]), int(pt["time"])))
    if not candidates:
        return None
    return max(candidates, key=lambda x: x[2])


def _get_latest_swing(d: dict) -> tuple[str, float, int] | None:
    candidates = []
    for lbl in ("HH", "HL", "LH", "LL"):
        pt = d.get(lbl.lower())
        if pt and pt.get("time") and pt.get("price"):
            candidates.append((lbl, float(pt["price"]), int(pt["time"])))
    if not candidates:
        return None
    return max(candidates, key=lambda x: x[2])


# ── Core S14-Aligned Detection ─────────────────────────────────────────

def _detect_both(
    tf: str,
    d: dict,
    rates: list,
    htf_rates_high=None,
    htf_rates_low=None,
) -> str | None:
    if len(rates) < 6:
        return None

    # Calculate RSI values
    period = 14
    applied = "close"
    try:
        from strategy9 import _calc_rsi_values
        rsi_vals = _calc_rsi_values(rates, period=period, applied_price=applied)
    except Exception:
        return None

    htf_rates_lookup = None
    if htf_rates_high is not None:
        htf_rates_lookup = {int(r["time"]): r for r in htf_rates_high}

    want_engulf_swing = True
    tf_secs = TF_SECONDS.get(tf, 60)
    htf = _get_s14_htf(tf)
    htf_secs = TF_SECONDS.get(htf, 300)

    # ── Reference list loaders ──
    def get_ref_low_list(setup_idx):
        candidates = []
        pts = []
        for k in ["hl", "ll", "prev_hl", "prev_ll"]:
            pt = d.get(k)
            if pt and pt.get("time") and pt.get("price"):
                pts.append(pt)
        for pt in pts:
            pt_time = int(pt["time"])
            for idx in range(len(rates)):
                if idx < setup_idx - 1 and int(rates[idx]["time"]) == pt_time:
                    candidates.append({
                        "idx":    idx,
                        "time":   pt_time,
                        "low":    float(pt["price"]),
                        "source": pt.get("label", "hl" if "hl" in k else "ll"),
                    })
                    break
        if not candidates:
            return []
        newest = max(candidates, key=lambda c: c["time"])
        active_refs = [newest]
        newest_src = str(newest["source"]).upper()
        if newest_src != "LL":
            ll_cands = [c for c in candidates if str(c["source"]).upper() == "LL"]
            if ll_cands:
                latest_ll = max(ll_cands, key=lambda c: c["time"])
                if latest_ll["time"] != newest["time"]:
                    active_refs.append(latest_ll)
        return active_refs

    def get_ref_high_list(setup_idx):
        candidates = []
        pts = []
        for k in ["hh", "lh", "prev_hh", "prev_lh"]:
            pt = d.get(k)
            if pt and pt.get("time") and pt.get("price"):
                pts.append(pt)
        for pt in pts:
            pt_time = int(pt["time"])
            for idx in range(len(rates)):
                if idx < setup_idx - 1 and int(rates[idx]["time"]) == pt_time:
                    candidates.append({
                        "idx":    idx,
                        "time":   pt_time,
                        "high":   float(pt["price"]),
                        "source": pt.get("label", "hh" if "hh" in k else "lh"),
                    })
                    break
        if not candidates:
            return []
        newest = max(candidates, key=lambda c: c["time"])
        active_refs = [newest]
        newest_src = str(newest["source"]).upper()
        if newest_src != "HH":
            hh_cands = [c for c in candidates if str(c["source"]).upper() == "HH"]
            if hh_cands:
                latest_hh = max(hh_cands, key=lambda c: c["time"])
                if latest_hh["time"] != newest["time"]:
                    active_refs.append(latest_hh)
        return active_refs

    result_low = None
    result_high = None

    # ── Loop to find any historical trigger in the rates window ──
    for setup_idx in range(len(rates)):
        # 1. Check SWEEP_LOW (BUY)
        if not result_low:
            # 1.1 Sweep Swing (Pattern A for BUY)
            if setup_idx >= 1:
                confirm_idx = setup_idx
                sweep_idx   = setup_idx - 1
                confirm_bar = rates[confirm_idx]
                sweep_bar   = rates[sweep_idx]
                co, cc = float(confirm_bar["open"]), float(confirm_bar["close"])

                if cc > co:  # confirm bar green
                    ref_list = get_ref_low_list(sweep_idx)
                    for ref in ref_list:
                        ref_idx = ref["idx"]
                        ref_low = ref["low"]
                        
                        # Close invalidation check
                        if any(float(r["close"]) < ref_low for r in rates[ref_idx + 1:sweep_idx]):
                            continue
                            
                        s_low   = float(sweep_bar["low"])
                        s_open  = float(sweep_bar["open"])
                        s_close = float(sweep_bar["close"])
                        
                        if s_low < ref_low and s_open > ref_low and s_close > ref_low:
                            passed_rsi = True
                            if getattr(_cfg_mod, "SWEEP_FILTER_RSI_DIV_ENABLED", False):
                                ref_rsi = _pivot_rsi_buy(rates, rsi_vals, ref_idx)
                                s_rsi = _pivot_rsi_buy(rates, rsi_vals, sweep_idx)
                                _rsi_min_diff = float(getattr(_cfg_mod, "S14_RSI_MIN_DIFF", 1.0))
                                if ref_rsi is not None and s_rsi is not None and s_rsi < 50.0 and (s_rsi - ref_rsi) > _rsi_min_diff:
                                    passed_rsi = True
                                else:
                                    passed_rsi = False
                            
                            if passed_rsi:
                                _activate("SWEEP_LOW", tf, ref_low, int(sweep_bar["time"]), confirm_ts=int(confirm_bar["time"]))
                                result_low = "SWEEP_LOW"
                                break

            # 1.2 Engulf Swing (Pattern B for BUY - with confirmations)
            if not result_low and want_engulf_swing and setup_idx >= 2:
                c2_bar = rates[setup_idx]
                c1_bar = rates[setup_idx - 1]
                e_bar  = rates[setup_idx - 2]
                c2_time = int(c2_bar["time"])
                c2_next_bar_time = c2_time + tf_secs

                if c2_next_bar_time % htf_secs == 0:
                    htf_bar_time = c2_next_bar_time - htf_secs
                    htf_bar = _get_htf_bar(tf, htf_bar_time, htf_rates_lookup)
                    if htf_bar:
                        ho = float(htf_bar["open"])
                        hc = float(htf_bar["close"])
                        
                        if hc < ho:  # HTF bar closed RED
                            ref_list = get_ref_low_list(setup_idx - 2)
                            for ref in ref_list:
                                ref_idx = ref["idx"]
                                ref_low = ref["low"]
                                
                                # Close invalidation check
                                if any(float(r["close"]) < ref_low for r in rates[ref_idx + 1:setup_idx - 2]):
                                    continue
                                    
                                e_low = float(e_bar["low"])
                                e_close = float(e_bar["close"])
                                
                                if e_low < ref_low and e_close < ref_low:
                                    c1_open, c1_close = float(c1_bar["open"]), float(c1_bar["close"])
                                    c2_open, c2_close = float(c2_bar["open"]), float(c2_bar["close"])
                                    
                                    if c1_close > c1_open and c2_close > c2_open:
                                        passed_rsi = True
                                        if getattr(_cfg_mod, "SWEEP_FILTER_RSI_DIV_ENABLED", False):
                                            ref_rsi = _pivot_rsi_buy(rates, rsi_vals, ref_idx)
                                            e_rsi = _pivot_rsi_buy(rates, rsi_vals, setup_idx - 2)
                                            _rsi_min_diff = float(getattr(_cfg_mod, "S14_RSI_MIN_DIFF", 1.0))
                                            if ref_rsi is not None and e_rsi is not None and e_rsi < 50.0 and (e_rsi - ref_rsi) > _rsi_min_diff:
                                                passed_rsi = True
                                            else:
                                                passed_rsi = False
                                                
                                        if passed_rsi:
                                            passed_htf_check = False
                                            if hc >= ref_low:
                                                passed_htf_check = True
                                            else:
                                                sec_htf = _get_next_std_tf(htf)
                                                if _is_sec_htf_currently_sweep(rates[:setup_idx + 1], tf, sec_htf, ref_low, is_buy=True):
                                                    passed_htf_check = True
                                                    
                                            if passed_htf_check:
                                                _activate("SWEEP_LOW", tf, ref_low, int(e_bar["time"]), confirm_ts=int(c2_bar["time"]))
                                                result_low = "SWEEP_LOW"
                                                break

            # 1.3 Direct Engulf Swing (Pattern B for BUY - no confirmations)
            if not result_low and want_engulf_swing and setup_idx >= 0:
                e_bar = rates[setup_idx]
                e_time = int(e_bar["time"])
                e_next_bar_time = e_time + tf_secs

                if e_next_bar_time % htf_secs == 0:
                    htf_bar_time = e_next_bar_time - htf_secs
                    htf_bar = _get_htf_bar(tf, htf_bar_time, htf_rates_lookup)
                    if htf_bar:
                        ho = float(htf_bar["open"])
                        hc = float(htf_bar["close"])
                        
                        if hc < ho:  # HTF bar closed RED
                            ref_list = get_ref_low_list(setup_idx)
                            for ref in ref_list:
                                ref_idx = ref["idx"]
                                ref_low = ref["low"]
                                
                                # Close invalidation check
                                if any(float(r["close"]) < ref_low for r in rates[ref_idx + 1:setup_idx]):
                                    continue
                                    
                                e_low = float(e_bar["low"])
                                e_close = float(e_bar["close"])
                                
                                if e_low < ref_low and e_close < ref_low:
                                    passed_rsi = True
                                    if getattr(_cfg_mod, "SWEEP_FILTER_RSI_DIV_ENABLED", False):
                                        ref_rsi = _pivot_rsi_buy(rates, rsi_vals, ref_idx)
                                        e_rsi = _pivot_rsi_buy(rates, rsi_vals, setup_idx)
                                        _rsi_min_diff = float(getattr(_cfg_mod, "S14_RSI_MIN_DIFF", 1.0))
                                        if ref_rsi is not None and e_rsi is not None and e_rsi < 50.0 and (e_rsi - ref_rsi) > _rsi_min_diff:
                                            passed_rsi = True
                                        else:
                                            passed_rsi = False
                                            
                                    if passed_rsi:
                                        if hc < ref_low:
                                            sec_htf = _get_next_std_tf(htf)
                                            if _is_sec_htf_currently_sweep(rates[:setup_idx + 1], tf, sec_htf, ref_low, is_buy=True):
                                                _activate("SWEEP_LOW", tf, ref_low, int(e_bar["time"]), confirm_ts=int(e_bar["time"]))
                                                result_low = "SWEEP_LOW"
                                                break

        # 2. Check SWEEP_HIGH (SELL)
        if not result_high:
            # 2.1 Sweep Swing (Pattern A for SELL)
            if setup_idx >= 1:
                confirm_idx = setup_idx
                sweep_idx   = setup_idx - 1
                confirm_bar = rates[confirm_idx]
                sweep_bar   = rates[sweep_idx]
                co, cc = float(confirm_bar["open"]), float(confirm_bar["close"])

                if cc < co:  # confirm bar red
                    ref_list = get_ref_high_list(sweep_idx)
                    for ref in ref_list:
                        ref_idx = ref["idx"]
                        ref_high = ref["high"]
                        
                        # Close invalidation check
                        if any(float(r["close"]) > ref_high for r in rates[ref_idx + 1:sweep_idx]):
                            continue
                            
                        s_high  = float(sweep_bar["high"])
                        s_open  = float(sweep_bar["open"])
                        s_close = float(sweep_bar["close"])
                        
                        if s_high > ref_high and s_open < ref_high and s_close < ref_high:
                            passed_rsi = True
                            if getattr(_cfg_mod, "SWEEP_FILTER_RSI_DIV_ENABLED", False):
                                ref_rsi = _pivot_rsi_sell(rates, rsi_vals, ref_idx)
                                s_rsi = _pivot_rsi_sell(rates, rsi_vals, sweep_idx)
                                _rsi_min_diff = float(getattr(_cfg_mod, "S14_RSI_MIN_DIFF", 1.0))
                                if ref_rsi is not None and s_rsi is not None and s_rsi > 50.0 and (ref_rsi - s_rsi) > _rsi_min_diff:
                                    passed_rsi = True
                                else:
                                    passed_rsi = False
                            
                            if passed_rsi:
                                _activate("SWEEP_HIGH", tf, ref_high, int(sweep_bar["time"]), confirm_ts=int(confirm_bar["time"]))
                                result_high = "SWEEP_HIGH"
                                break

            # 2.2 Engulf Swing (Pattern B for SELL - with confirmations)
            if not result_high and want_engulf_swing and setup_idx >= 2:
                c2_bar = rates[setup_idx]
                c1_bar = rates[setup_idx - 1]
                e_bar  = rates[setup_idx - 2]
                c2_time = int(c2_bar["time"])
                c2_next_bar_time = c2_time + tf_secs

                if c2_next_bar_time % htf_secs == 0:
                    htf_bar_time = c2_next_bar_time - htf_secs
                    htf_bar = _get_htf_bar(tf, htf_bar_time, htf_rates_lookup)
                    if htf_bar:
                        ho = float(htf_bar["open"])
                        hc = float(htf_bar["close"])
                        
                        if hc > ho:  # HTF bar closed GREEN
                            ref_list = get_ref_high_list(setup_idx - 2)
                            for ref in ref_list:
                                ref_idx = ref["idx"]
                                ref_high = ref["high"]
                                
                                # Close invalidation check
                                if any(float(r["close"]) > ref_high for r in rates[ref_idx + 1:setup_idx - 2]):
                                    continue
                                    
                                e_high = float(e_bar["high"])
                                e_close = float(e_bar["close"])
                                
                                if e_high > ref_high and e_close > ref_high:
                                    c1_open, c1_close = float(c1_bar["open"]), float(c1_bar["close"])
                                    c2_open, c2_close = float(c2_bar["open"]), float(c2_bar["close"])
                                    
                                    if c1_close < c1_open and c2_close < c2_open:
                                        passed_rsi = True
                                        if getattr(_cfg_mod, "SWEEP_FILTER_RSI_DIV_ENABLED", False):
                                            ref_rsi = _pivot_rsi_sell(rates, rsi_vals, ref_idx)
                                            e_rsi = _pivot_rsi_sell(rates, rsi_vals, setup_idx - 2)
                                            _rsi_min_diff = float(getattr(_cfg_mod, "S14_RSI_MIN_DIFF", 1.0))
                                            if ref_rsi is not None and e_rsi is not None and e_rsi > 50.0 and (ref_rsi - e_rsi) > _rsi_min_diff:
                                                passed_rsi = True
                                            else:
                                                passed_rsi = False
                                                
                                        if passed_rsi:
                                            passed_htf_check = False
                                            if hc <= ref_high:
                                                passed_htf_check = True
                                            else:
                                                sec_htf = _get_next_std_tf(htf)
                                                if _is_sec_htf_currently_sweep(rates[:setup_idx + 1], tf, sec_htf, ref_high, is_buy=False):
                                                    passed_htf_check = True
                                                    
                                            if passed_htf_check:
                                                _activate("SWEEP_HIGH", tf, ref_high, int(e_bar["time"]), confirm_ts=int(c2_bar["time"]))
                                                result_high = "SWEEP_HIGH"
                                                break

            # 2.3 Direct Engulf Swing (Pattern B for SELL - no confirmations)
            if not result_high and want_engulf_swing and setup_idx >= 0:
                e_bar = rates[setup_idx]
                e_time = int(e_bar["time"])
                e_next_bar_time = e_time + tf_secs

                if e_next_bar_time % htf_secs == 0:
                    htf_bar_time = e_next_bar_time - htf_secs
                    htf_bar = _get_htf_bar(tf, htf_bar_time, htf_rates_lookup)
                    if htf_bar:
                        ho = float(htf_bar["open"])
                        hc = float(htf_bar["close"])
                        
                        if hc > ho:  # HTF bar closed GREEN
                            ref_list = get_ref_high_list(setup_idx)
                            for ref in ref_list:
                                ref_idx = ref["idx"]
                                ref_high = ref["high"]
                                
                                # Close invalidation check
                                if any(float(r["close"]) > ref_high for r in rates[ref_idx + 1:setup_idx]):
                                    continue
                                    
                                e_high = float(e_bar["high"])
                                e_close = float(e_bar["close"])
                                
                                if e_high > ref_high and e_close > ref_high:
                                    passed_rsi = True
                                    if getattr(_cfg_mod, "SWEEP_FILTER_RSI_DIV_ENABLED", False):
                                        ref_rsi = _pivot_rsi_sell(rates, rsi_vals, ref_idx)
                                        e_rsi = _pivot_rsi_sell(rates, rsi_vals, setup_idx)
                                        _rsi_min_diff = float(getattr(_cfg_mod, "S14_RSI_MIN_DIFF", 1.0))
                                        if ref_rsi is not None and e_rsi is not None and e_rsi > 50.0 and (ref_rsi - e_rsi) > _rsi_min_diff:
                                            passed_rsi = True
                                        else:
                                            passed_rsi = False
                                            
                                    if passed_rsi:
                                        if hc > ref_high:
                                            sec_htf = _get_next_std_tf(htf)
                                            if _is_sec_htf_currently_sweep(rates[:setup_idx + 1], tf, sec_htf, ref_high, is_buy=False):
                                                _activate("SWEEP_HIGH", tf, ref_high, int(e_bar["time"]), confirm_ts=int(e_bar["time"]))
                                                result_high = "SWEEP_HIGH"
                                                break

    # Select latest
    if not result_high and not result_low:
        return None
    if result_high and not result_low:
        return result_high
    if result_low and not result_high:
        return result_low
        
    high_ts = _sweep_ts.get(tf + "_high_ts", 0)
    low_ts  = _sweep_ts.get(tf + "_low_ts",  0)
    return result_high if high_ts >= low_ts else result_low


def _activate(state: str, tf: str, price: float, bar_ts: int, confirm_ts: int = 0) -> None:
    _sweep_state[tf] = state
    _sweep_price[tf] = price
    _sweep_ts[tf]    = int(bar_ts)
    if state == "SWEEP_HIGH":
        _sweep_ts[tf + "_high_ts"] = int(bar_ts)
    else:
        _sweep_ts[tf + "_low_ts"] = int(bar_ts)
    bar_str = datetime.fromtimestamp(bar_ts, tz=_BKK).strftime("%H:%M %d-%b-%Y")
    _sweep_at[tf]    = bar_str
    try:
        from bot_log import log_event as _log
        conf_str = datetime.fromtimestamp(confirm_ts, tz=_BKK).strftime("%H:%M %d-%b-%Y") if confirm_ts else "-"
        _log("SWEEP_ACTIVATE", state,
             tf=tf, ref_price=f"{price:.2f}",
             sweep_bar=bar_str, confirm_bar=conf_str)
    except Exception:
        pass


def _is_expired(tf: str) -> bool:
    if _cfg_mod is None:
        return False
    expiry_cfg = getattr(_cfg_mod, "SWEEP_FILTER_EXPIRY_MIN", 0)
    if isinstance(expiry_cfg, dict):
        expiry_min = int(expiry_cfg.get(tf, 0) or 0)
    else:
        expiry_min = int(expiry_cfg or 0)

    if expiry_min <= 0:
        return False
    trig_ts = _sweep_ts.get(tf, 0)
    if trig_ts <= 0:
        return False
    import time as _t
    age_sec = _t.time() - trig_ts
    return age_sec > expiry_min * 60


def _get_closed_rates(tf: str, n: int = 80):
    tf_id = TF_OPTIONS.get(tf)
    if not tf_id or not connect_mt5():
        return None
    return mt5.copy_rates_from_pos(SYMBOL, tf_id, 1, n)




def check_and_update(tf: str) -> str | None:
    if not is_enabled():
        return None

    # ถ้า sweep active อยู่แล้ว → คงสถานะ
    if _sweep_state.get(tf):
        if _is_expired(tf):
            reset_sweep(tf, reason="expired")
        else:
            return _sweep_state[tf]

    try:
        import hhll_swing as _hs
        d = _hs.get_hhll_data(tf) or {}
    except Exception:
        return None

    if not d:
        return None

    num_bars = 150
    rates = _get_closed_rates(tf, num_bars)
    if rates is None or len(rates) < 6:
        return None

    return _detect_both(tf, d, list(rates))


# ── Simulation Helper (historical replay) ────────────────────────────

def check_sweep_at_time(
    tf: str,
    end_dt,           # datetime (raw +1h) ของเวลาที่ต้องการตรวจ
    swings: dict,     # {"hh":..., "hl":..., "lh":..., "ll":..., "prev_hh":...}
) -> str | None:
    if not connect_mt5():
        return None
    tf_id = TF_OPTIONS.get(tf)
    if not tf_id:
        return None

    if _sweep_state.get(tf):
        return _sweep_state[tf]

    tf_secs = {"M1": 60, "M5": 300, "M15": 900, "M30": 1800, "H1": 3600, "H4": 14400, "D1": 86400}
    secs = tf_secs.get(tf, 60)
    end_adj = end_dt - timedelta(seconds=secs) # exclude forming bar
    
    # Fetch exactly 150 bars, just like check_and_update
    start_dt = end_adj - timedelta(seconds=secs * 150)
    
    rates = mt5.copy_rates_range(SYMBOL, tf_id, start_dt, end_adj)
    if rates is None or len(rates) < 6:
        return None

    # Get HTF rates
    htf_rates = None
    htf = _get_s14_htf(tf)
    htf_id = TF_OPTIONS.get(htf)
    if htf_id:
        htf_start = start_dt - timedelta(hours=4)
        htf_r = mt5.copy_rates_range(SYMBOL, htf_id, htf_start, end_adj)
        if htf_r is not None:
            htf_rates = htf_r

    return _detect_both(tf, swings, list(rates), htf_rates, htf_rates)
