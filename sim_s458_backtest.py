from __future__ import annotations

from datetime import datetime, timezone, timedelta

import MetaTrader5 as mt5

import config
import hhll_swing
import sim_s1_backtest
import sim_s2_backtest
import sim_s3_backtest
import sim_s4_backtest
import sim_s5_backtest
import sim_s8_backtest
from strategy1 import strategy_1
from strategy2 import strategy_2
from strategy3 import strategy_3
from strategy4 import strategy_4
from strategy5 import strategy_5
from strategy8 import strategy_8
from sim_lifecycle import (
    fill_pdfiboplus_round1,
    fill_pdfiboplus_round2,
    fill_rsi_recheck,
    fill_trend_recheck_round1,
    fill_trend_recheck_round2,
    limit_guard_cancel,
    limit_sweep_followup_s8,
    opposite_order_apply,
    pd_cancel_event,
    pending_pdfiboplus_round1,
    pending_pdfiboplus_round2,
    pending_trend_check_round1,
    pending_trend_check_round2,
    s1_fill_rule_check,
    s1_pending_rule_check,
    s1_prepare_order,
    s1_rule_close_type,
    SimSLGuard,
    trail_sl_apply,
    trend_cancel_event,
)


SYMBOL = config.SYMBOL
UTC = timezone.utc
TZ_OFF = getattr(config, "TZ_OFFSET", 7)
SRV_TZ = getattr(config, "MT5_SERVER_TZ", 0)
VOLUME = 0.01
PRICE_TO_USD = 100 * VOLUME
S2_PARALLEL_LIFECYCLE_TF = False
S2_FILL_BEFORE_CANCEL_BARS = False

TF_MAP = sim_s8_backtest.TF_MAP
TF_EXTRA_BARS = {
    tf: max(
        sim_s1_backtest.TF_EXTRA_BARS.get(tf, 0),
        sim_s2_backtest.TF_EXTRA_BARS.get(tf, 0),
        sim_s3_backtest.TF_EXTRA_BARS.get(tf, 0),
        sim_s4_backtest.TF_EXTRA_BARS.get(tf, 0),
        sim_s5_backtest.TF_EXTRA_BARS.get(tf, 0),
        sim_s8_backtest.TF_EXTRA_BARS.get(tf, 0),
    )
    for tf in TF_MAP
}
SINCE = min(
    sim_s1_backtest.SINCE,
    sim_s2_backtest.SINCE,
    sim_s3_backtest.SINCE,
    sim_s4_backtest.SINCE,
    sim_s5_backtest.SINCE,
    sim_s8_backtest.SINCE,
)
TF_SECONDS = {
    "M1": 60,
    "M5": 300,
    "M15": 900,
    "M30": 1800,
    "H1": 3600,
    "H4": 14400,
    "D1": 86400,
}


def to_bkk(ts: int) -> datetime:
    return datetime.fromtimestamp(int(ts), tz=UTC) + timedelta(hours=TZ_OFF - SRV_TZ)


def profit(price_diff: float) -> float:
    return round(float(price_diff) * PRICE_TO_USD, 2)


def _as_records(rates) -> list[dict]:
    return sorted(
        [{name: r[name] for name in rates.dtype.names} for r in rates],
        key=lambda r: int(r["time"]),
    )


def _fetch_rates(tf_name: str, tf_val: int, range_end_utc: datetime | None = None):
    total = TF_EXTRA_BARS.get(tf_name, 500) + 8000
    if range_end_utc is None:
        return mt5.copy_rates_from_pos(SYMBOL, tf_val, 0, total)

    pad_bars = max(
        120,
        int(getattr(config, "HHLL_LOOKBACK", 500) or 500)
        + int(getattr(config, "HHLL_LEFT", 5) or 5)
        + int(getattr(config, "HHLL_RIGHT", 5) or 5)
        + int(getattr(config, "TF_LOOKBACK", {}).get(tf_name, getattr(config, "SWING_LOOKBACK", 20)) or 20)
        + 20,
    )
    start_utc = SINCE - timedelta(seconds=TF_SECONDS.get(tf_name, 60) * pad_bars)
    return mt5.copy_rates_range(SYMBOL, tf_val, start_utc, range_end_utc)


def _build_historical_hhll_data(rates: list[dict]) -> dict:
    return sim_s8_backtest._build_historical_hhll_data(rates)


def _call_with_hhll(tf_name: str, hist_data: dict, func, *args, **kwargs) -> dict:
    old_data = hhll_swing._hhll_data.get(tf_name)
    if hist_data:
        hhll_swing._hhll_data[tf_name] = hist_data
    try:
        return func(*args, **kwargs)
    finally:
        if old_data is None:
            hhll_swing._hhll_data.pop(tf_name, None)
        else:
            hhll_swing._hhll_data[tf_name] = old_data


def _pre_scan_hhll_needed(strategies: set[int]) -> bool:
    return bool(strategies & {4, 5, 8})


def _post_signal_hhll_needed(strategies: set[int], scan_results: list[tuple[int, dict]]) -> bool:
    if not scan_results:
        return False
    if strategies & {2, 3}:
        return True
    return bool(getattr(config, "TREND_FILTER_SCAN_BLOCK", False))


def _trend_scan_blocked(tf_name: str, hist_data: dict, sid: int, signal: str) -> tuple[bool, str]:
    if not getattr(config, "TREND_FILTER_SCAN_BLOCK", False):
        return False, ""
    if sid in (9, 10, 13, 14, 15, 16, 17, 18, 19):
        return False, ""
    if not hist_data:
        return False, ""

    try:
        import scanner as _scanner
    except Exception:
        return False, ""

    old_swing = getattr(_scanner, "_swing_data", {}).get(tf_name)
    old_hhll = hhll_swing._hhll_data.get(tf_name)
    try:
        _scanner._swing_data[tf_name] = hist_data
        hhll_swing._hhll_data[tf_name] = hist_data
        allowed, reason = _scanner.trend_allows_signal(tf_name, signal)
        return (not allowed), reason
    finally:
        if old_swing is None:
            _scanner._swing_data.pop(tf_name, None)
        else:
            _scanner._swing_data[tf_name] = old_swing
        if old_hhll is None:
            hhll_swing._hhll_data.pop(tf_name, None)
        else:
            hhll_swing._hhll_data[tf_name] = old_hhll


def _sweep_htf_name(tf_name: str) -> str:
    mapping = {
        "M1": "M5",
        "M5": "M15",
        "M15": "H1",
        "M30": "H4",
        "H1": "H4",
        "H4": "D1",
    }
    return mapping.get(tf_name, "M5")


def _entry_already_passed(result: dict, signal_bar: dict) -> bool:
    entry = float(result.get("entry", 0.0) or 0.0)
    close = float(signal_bar["close"])
    signal = result.get("signal")
    if signal == "BUY":
        return close <= entry
    if signal == "SELL":
        return close >= entry
    return False


def _order_touched_entry(order: dict, bar: dict) -> bool:
    entry = float(order.get("entry", 0.0) or 0.0)
    signal = str(order.get("signal") or order.get("side") or "").upper()
    if entry <= 0:
        return False
    if signal == "BUY":
        return float(bar.get("low", 0.0) or 0.0) <= entry
    if signal == "SELL":
        return float(bar.get("high", 0.0) or 0.0) >= entry
    return False


def _close_row(trade: dict, reason: str, price: float, close_time: datetime) -> dict:
    if trade["signal"] == "BUY":
        pnl = profit(float(price) - float(trade["entry"]))
    else:
        pnl = profit(float(trade["entry"]) - float(price))
    return {
        **trade,
        "close_time": close_time,
        "close_type": reason,
        "close_price": round(float(price), 2),
        "pnl": pnl,
        "profit": pnl,
        "reason": reason,
    }


def _green_break(cur_bar: dict, prev_bar: dict, level: float) -> bool:
    return (
        float(cur_bar["close"]) > float(cur_bar["open"])
        and float(prev_bar["close"]) > float(prev_bar["open"])
        and float(cur_bar["close"]) > float(level)
        and float(cur_bar["close"]) > float(prev_bar["high"])
    )


def _red_break(cur_bar: dict, prev_bar: dict, level: float) -> bool:
    return (
        float(cur_bar["close"]) < float(cur_bar["open"])
        and float(prev_bar["close"]) < float(prev_bar["open"])
        and float(cur_bar["close"]) < float(level)
        and float(cur_bar["close"]) < float(prev_bar["low"])
    )


def _limit_break_cancel_event(order: dict, tf_name: str, rates: list[dict], close_time: datetime) -> dict | None:
    sid = int(order.get("sid", 0) or 0)
    if sid == 10:
        return None
    if sid == 2 and str(order.get("c3_type") or "") in ("เขียวกลืนกิน", "แดงกลืนกิน"):
        return None
    if not getattr(config, "LIMIT_BREAK_CANCEL", False):
        return None
    if not getattr(config, "LIMIT_BREAK_CANCEL_TF", {}).get(tf_name, False):
        return None
    if len(rates) < 2:
        return None

    cur_bar = rates[-1]
    prev_bar = rates[-2]
    signal = str(order.get("signal") or "").upper()
    limit_tp = float(order.get("tp", 0.0) or 0.0)
    limit_sl = float(order.get("sl", 0.0) or order.get("intended_sl", 0.0) or 0.0)
    reason = ""
    if signal == "BUY":
        if limit_tp > 0 and _green_break(cur_bar, prev_bar, limit_tp):
            reason = "TP Break Cancel"
        elif limit_sl > 0 and _red_break(cur_bar, prev_bar, limit_sl):
            reason = "SL Break Cancel"
    elif signal == "SELL":
        if limit_tp > 0 and _red_break(cur_bar, prev_bar, limit_tp):
            reason = "TP Break Cancel"
        elif limit_sl > 0 and _green_break(cur_bar, prev_bar, limit_sl):
            reason = "SL Break Cancel"
    if not reason:
        return None
    return {
        **order,
        "entry_time": order["detect_time"],
        "entry_time_raw": order["detect_time_raw"],
        "close_time": close_time,
        "close_price": None,
        "close_type": "CANCEL",
        "pnl": 0.0,
        "profit": 0.0,
        "reason": f"{reason} [{tf_name}]",
        "cancel_reason": f"{reason} [{tf_name}]",
    }


def _cancel_pending_event(
    order: dict,
    close_time: datetime,
    reason: str,
    *,
    bar: dict | None = None,
    age_bars: int | None = None,
    cancel_bars: int | None = None,
) -> dict:
    entry = float(order.get("entry", 0.0) or 0.0)
    signal = str(order.get("signal") or order.get("side") or "").upper()
    bar_high = float(bar.get("high", 0.0) or 0.0) if bar else 0.0
    bar_low = float(bar.get("low", 0.0) or 0.0) if bar else 0.0
    touched_entry = False
    if entry > 0 and bar:
        if signal == "BUY":
            touched_entry = bar_low <= entry
        elif signal == "SELL":
            touched_entry = bar_high >= entry
    return {
        **order,
        "entry_time": order["detect_time"],
        "entry_time_raw": order["detect_time_raw"],
        "close_time": close_time,
        "close_price": None,
        "close_type": "CANCEL",
        "pnl": 0.0,
        "profit": 0.0,
        "reason": reason,
        "cancel_reason": reason,
        "cancel_age_bars": "" if age_bars is None else int(age_bars),
        "cancel_bars": "" if cancel_bars is None else int(cancel_bars),
        "cancel_bar_high": round(bar_high, 2) if bar else "",
        "cancel_bar_low": round(bar_low, 2) if bar else "",
        "cancel_bar_touched_entry": touched_entry if bar else "",
    }


def _pending_from_result(result: dict, tf_name: str, detect_bar: dict, sid: int) -> dict:
    if result.get("_prebuilt_order"):
        return dict(result["_prebuilt_order"])

    signal = result["signal"]
    row = {
        "sid": sid,
        "tf": tf_name,
        "signal": signal,
        "side": signal,
        "pattern": result.get("pattern", f"S{sid}"),
        "entry": round(float(result["entry"]), 2),
        "sl": round(float(result["sl"]), 2),
        "tp": round(float(result["tp"]), 2),
        "detect_time": to_bkk(detect_bar["time"]),
        "detect_time_raw": int(detect_bar["time"]),
    }
    if sid == 1:
        row.update({
            "cancel_bars": int(result.get("cancel_bars", 0) or 0),
            "s1_zone_meta": result.get("s1_zone_meta") or {},
        })
        s1_prepare_order(row)
    if sid == 2:
        row.update({
            "gap_bot": round(float(result.get("gap_bot", 0.0) or 0.0), 2),
            "gap_top": round(float(result.get("gap_top", 0.0) or 0.0), 2),
            "final_gap_bot": round(float(result.get("gap_bot", 0.0) or 0.0), 2),
            "final_gap_top": round(float(result.get("gap_top", 0.0) or 0.0), 2),
            "c3_type": result.get("c3_type", ""),
            "_s2_confirm_ok": bool(result.get("_s2_confirm_ok", False)),
            "cancel_bars": 1 if result.get("c3_type") == "ปฏิเสธราคา" else 0,
        })
    if sid == 3 and result.get("source_candle_time"):
        row.update({
            "source_candle_time": int(result.get("source_candle_time", 0) or 0),
            "marubozu_source": result.get("marubozu_source", "marubozu"),
        })
    if sid == 8:
        row.update({
            "intended_sl": row["sl"],
            "sl_armed": False,
            "swing_price": float(result.get("swing_price", 0.0) or 0.0),
            "swing_bar_time": int(result.get("swing_bar_time", 0) or 0),
        })
    return row


def _fill_trade(order: dict, bar: dict) -> dict:
    row = {
        **order,
        "entry_time": to_bkk(bar["time"]),
        "entry_time_raw": int(bar["time"]),
        "close_type": "OPEN",
    }
    if int(order.get("sid", 0) or 0) == 8:
        sl_armed = bool(order.get("sl_armed"))
        if not sl_armed and getattr(config, "DELAY_SL_MODE", "off") == "off":
            sl_armed = True
        row["sl_armed"] = sl_armed
    return row


def _duplicate_pending(pending: list[dict], order: dict) -> bool:
    for p in pending:
        if int(p.get("sid", 0) or 0) != int(order.get("sid", 0) or 0):
            continue
        if p.get("signal") != order.get("signal"):
            continue
        if abs(float(p.get("entry", 0.0) or 0.0) - float(order.get("entry", 0.0) or 0.0)) > 0.01:
            continue
        if abs(float(p.get("sl", 0.0) or 0.0) - float(order.get("sl", 0.0) or 0.0)) > 0.01:
            continue
        if abs(float(p.get("tp", 0.0) or 0.0) - float(order.get("tp", 0.0) or 0.0)) > 0.01:
            continue
        return True
    return False


def _has_active_sid_tf(pending: list[dict], open_trades: list[dict], tf_name: str, sid: int) -> bool:
    for row in pending + open_trades:
        if str(row.get("tf") or "") == tf_name and int(row.get("sid", 0) or 0) == int(sid):
            return True
    return False


def _pattern_allows_adjacent_order(sid: int, pattern: str) -> bool:
    if int(sid or 0) != 1:
        return False
    pattern = str(pattern or "")
    return ("Pattern กลืนกิน 2 แดง" in pattern) or ("Pattern กลืนกิน 2 เขียว" in pattern)


def _adjacent_sid_blocked_sim(
    last_sid_tf: dict,
    pending: list[dict],
    open_trades: list[dict],
    tf_name: str,
    sid: int,
    candle_time: int,
    tf_secs: int,
) -> bool:
    prev = (last_sid_tf.get(tf_name) or {}).get(int(sid))
    if not prev or tf_secs <= 0 or (int(candle_time) - int(prev)) != int(tf_secs):
        return False
    if _has_active_sid_tf(pending, open_trades, tf_name, sid):
        return True
    tf_map = last_sid_tf.get(tf_name)
    if isinstance(tf_map, dict) and tf_map.get(int(sid)) == prev:
        tf_map.pop(int(sid), None)
        if not tf_map:
            last_sid_tf.pop(tf_name, None)
    return False


def _sweep_scan_state(
    tf_name: str,
    hist_data: dict,
    full_rates: list[dict],
    htf_rates: list[dict] | None = None,
) -> str | None:
    try:
        import sweep_filter
        if not sweep_filter.is_enabled():
            return None
        state = None
        if hist_data:
            sweep_rates = list(full_rates[-150:])
            state = sweep_filter._detect_both(tf_name, hist_data, sweep_rates, htf_rates, htf_rates)
        if not state:
            state = getattr(sweep_filter, "_sweep_state", {}).get(tf_name)
        if state:
            info = _sweep_filter_info(tf_name)
            sweep_ts = int(info.get("ts", 0) or 0)
            if sweep_ts <= 0:
                return None
            expiry_min = int(info.get("expiry_min", 0) or 0)
            current_ts = int(full_rates[-1]["time"]) if full_rates else 0
            if sweep_ts and expiry_min > 0 and current_ts - sweep_ts > expiry_min * 60:
                sweep_filter.reset_sweep(tf_name, reason="historical_expired")
                return None
        return state
    except Exception:
        return None


def _sweep_scan_blocked(sweep_state: str | None, sid: int, signal: str) -> bool:
    if int(sid or 0) in (9, 10, 13, 14, 15, 16, 17, 18, 19):
        return False
    return (sweep_state == "SWEEP_LOW" and signal == "SELL") or (sweep_state == "SWEEP_HIGH" and signal == "BUY")


def _sweep_filter_info(tf_name: str) -> dict:
    try:
        import sweep_filter
        info = dict(sweep_filter.get_sweep_info(tf_name) or {})
        expiry_cfg = getattr(config, "SWEEP_FILTER_EXPIRY_MIN", 0)
        if isinstance(expiry_cfg, dict):
            expiry_min = int(expiry_cfg.get(tf_name, 0) or 0)
        else:
            expiry_min = int(expiry_cfg or 0)
        info["ts"] = getattr(sweep_filter, "_sweep_ts", {}).get(tf_name, 0)
        info["expiry_min"] = expiry_min
        return info
    except Exception:
        return {}


def _sweep_scan_meta(tf_name: str, order: dict) -> dict:
    info = _sweep_filter_info(tf_name)
    sweep_ts = int(info.get("ts", 0) or 0)
    detect_ts = int(order.get("detect_time_raw", 0) or 0)
    age_min = round((detect_ts - sweep_ts) / 60.0, 2) if sweep_ts and detect_ts else ""
    return {
        "sweep_scan_price": info.get("price", ""),
        "sweep_scan_time": info.get("time", ""),
        "sweep_scan_ts": sweep_ts or "",
        "sweep_scan_age_min": age_min,
        "sweep_scan_expiry_min": info.get("expiry_min", ""),
    }


def _tf_sort_key(tf_name: str) -> int:
    return int(TF_SECONDS.get(tf_name, 999999))


def _s2_group_candidates(tf_name: str, active_tfs: set[str]) -> list[list[str]]:
    groups = []
    for group in getattr(config, "FVG_PARALLEL_GROUPS", []) or []:
        if tf_name not in group:
            continue
        if not all(tf in active_tfs for tf in group):
            continue
        if any(tf != tf_name for tf in group):
            groups.append(list(group))
    return groups


def _s2_lifecycle_tf(order: dict) -> str:
    if int(order.get("sid", 0) or 0) != 2:
        return str(order.get("tf") or "")
    parallel_tfs = [str(tf) for tf in (order.get("parallel_tfs") or []) if tf]
    if len(parallel_tfs) < 2:
        return str(order.get("tf") or "")
    return min(parallel_tfs, key=_tf_sort_key)


def _s2_parallel_prepare(
    order: dict,
    pending: list[dict],
    trades: list[dict],
    bt: datetime,
    *,
    active_tfs: set[str],
) -> dict | None:
    if int(order.get("sid", 0) or 0) != 2:
        return order

    normal_confirm_ok = bool(order.pop("_s2_confirm_ok", False))
    if not getattr(config, "FVG_NORMAL", False) and not getattr(config, "FVG_PARALLEL", False):
        return None

    tf_name = str(order.get("tf") or "")
    signal = str(order.get("signal") or "")
    gap_bot = float(order.get("gap_bot", 0.0) or 0.0)
    gap_top = float(order.get("gap_top", 0.0) or 0.0)
    parallel_tfs = [tf_name]
    parallel_patterns = [str(order.get("pattern", ""))]
    cancel_ids: set[int] = set()
    int_bot = None
    int_top = None

    if getattr(config, "FVG_PARALLEL", False):
        groups = _s2_group_candidates(tf_name, active_tfs)
        gaps = [{"tf": tf_name, "bot": gap_bot, "top": gap_top, "pattern": str(order.get("pattern", "")), "order": None}]
        for old in pending:
            if int(old.get("sid", 0) or 0) != 2:
                continue
            if old.get("signal") != signal:
                continue
            old_tf = str(old.get("tf") or "")
            if old_tf == tf_name:
                continue
            if not any(old_tf in group and tf_name in group for group in groups):
                continue
            old_bot = float(old.get("gap_bot", old.get("entry", 0.0)) or 0.0)
            old_top = float(old.get("gap_top", old.get("entry", 0.0)) or 0.0)
            if gap_top < old_bot or gap_bot > old_top:
                continue
            gaps.append({
                "tf": old_tf,
                "bot": old_bot,
                "top": old_top,
                "pattern": str(old.get("pattern", "")),
                "order": old,
            })

        if len(gaps) > 1:
            candidate_bot = max(g["bot"] for g in gaps)
            candidate_top = min(g["top"] for g in gaps)
            if candidate_top > candidate_bot and candidate_top - candidate_bot >= 0.5:
                int_bot = candidate_bot
                int_top = candidate_top
                gaps.sort(key=lambda g: _tf_sort_key(str(g["tf"])))
                seen = set()
                parallel_tfs = []
                parallel_patterns = []
                for gap in gaps:
                    gap_tf = str(gap["tf"])
                    if gap_tf in seen:
                        continue
                    seen.add(gap_tf)
                    parallel_tfs.append(gap_tf)
                    parallel_patterns.append(str(gap.get("pattern", "")))
                    old_order = gap.get("order")
                    if old_order is not None:
                        cancel_ids.add(id(old_order))

    if int_bot is None or int_top is None:
        if getattr(config, "FVG_PARALLEL", False) and not getattr(config, "FVG_NORMAL", False):
            return None
        if not normal_confirm_ok:
            return None
        return order

    gap_size = int_top - int_bot
    if signal == "BUY":
        order["entry"] = round(int_bot + gap_size * 0.98, 2)
    else:
        order["entry"] = round(int_top - gap_size * 0.98, 2)
    order["final_gap_bot"] = round(float(int_bot), 2)
    order["final_gap_top"] = round(float(int_top), 2)
    order["parallel_tfs"] = list(parallel_tfs)
    order["parallel_patterns"] = list(parallel_patterns)
    if S2_PARALLEL_LIFECYCLE_TF:
        order["lifecycle_tf"] = _s2_lifecycle_tf(order)
    order["pattern"] = f"{order.get('pattern', 'S2 FVG')} [{'+'.join(parallel_tfs)}]"

    if cancel_ids:
        kept = []
        for old in pending:
            if id(old) in cancel_ids:
                trades.append(trend_cancel_event(old, bt, "S2 FVG Parallel replaced by intersection"))
            else:
                kept.append(old)
        pending[:] = kept
    return order


def _scan_signals(
    strategies: set[int],
    scan_rates: list[dict],
    full_rates: list[dict],
    hist_data: dict,
    tf_name: str,
    bt: datetime,
    bar: dict,
    tf_secs: int,
    fallback_start: dict,
    maru_pending: dict,
) -> list[tuple[int, dict]]:
    signals: list[tuple[int, dict]] = []
    if 1 in strategies:
        r1 = strategy_1(full_rates, tf=tf_name)
        if r1.get("signal") in ("BUY", "SELL"):
            signals.append((1, r1))
    if 2 in strategies:
        r2 = strategy_2(scan_rates, tf=tf_name)
        if r2.get("signal") == "FVG_DETECTED":
            fvg = r2.get("fvg") or {}
            signal = fvg.get("signal")
            if signal in ("BUY", "SELL"):
                s2_confirm_ok = sim_s2_backtest._s2_confirm_ok(
                    full_rates, signal, tf_name, tf_secs, int(bar["time"]), fallback_start
                )
                tp = sim_s2_backtest._calc_tp(full_rates, signal, float(fvg["entry"]), float(fvg["sl"]), tf_name)
                signals.append((2, {
                    "signal": signal,
                    "pattern": fvg.get("pattern", "S2 FVG"),
                    "entry": fvg.get("entry"),
                    "sl": fvg.get("sl"),
                    "tp": tp,
                    "gap_bot": fvg.get("gap_bot", 0.0),
                    "gap_top": fvg.get("gap_top", 0.0),
                    "c3_type": fvg.get("c3_type", ""),
                    "_s2_confirm_ok": s2_confirm_ok,
                }))
    if 3 in strategies:
        for key, mp in list(maru_pending.items()):
            if int(bar["time"]) <= int(mp.get("candle_time", 0) or 0):
                continue
            bull_next = float(bar["close"]) > float(bar["open"])
            direction = mp.get("direction")
            color_ok = (direction == "BUY" and bull_next) or (direction == "SELL" and not bull_next)
            if color_ok and sim_s3_backtest._confirm_ok(full_rates, direction, tf_name, tf_secs, int(bar["time"]), fallback_start):
                signals.append((3, {"_prebuilt_order": sim_s3_backtest._pending_from_maru(mp, tf_name, bar)}))
            maru_pending.pop(key, None)

        r3 = strategy_3(full_rates)
        mp = r3.get("marubozu_pending")
        if mp:
            key = f"{tf_name}_{mp['candle_time']}_s3maru"
            if key not in maru_pending:
                maru_pending[key] = mp
        if r3.get("signal") in ("BUY", "SELL") and sim_s3_backtest._confirm_ok(
            full_rates, r3.get("signal"), tf_name, tf_secs, int(bar["time"]), fallback_start
        ):
            signals.append((3, r3))
    if 4 in strategies:
        r4 = _call_with_hhll(tf_name, hist_data, strategy_4, scan_rates, tf=tf_name if hist_data else "")
        if r4.get("signal") in ("BUY", "SELL"):
            signals.append((4, r4))
    if 5 in strategies:
        r5 = _call_with_hhll(tf_name, hist_data, strategy_5, scan_rates, tf=tf_name if hist_data else "", signal_time=bt)
        if r5.get("signal") in ("BUY", "SELL"):
            signals.append((5, r5))
    if 8 in strategies:
        r8 = _call_with_hhll(tf_name, hist_data, strategy_8, scan_rates, tf=tf_name if hist_data else "")
        if r8.get("signal") == "MULTI":
            for order in r8.get("orders", []) or []:
                if order.get("signal") in ("BUY", "SELL"):
                    signals.append((8, order))
    return signals


def backtest_tf(
    tf_name: str,
    tf_val: int,
    strategies: set[int],
    range_end_utc: datetime | None = None,
    scan_until_utc: datetime | None = None,
    progress_cb=None,
) -> list[dict]:
    try:
        import sweep_filter
        sweep_filter.reset_all()
    except Exception:
        pass
    rates = _fetch_rates(tf_name, tf_val, range_end_utc=range_end_utc)
    if rates is None or len(rates) < 120:
        return []

    symbol_info = mt5.symbol_info(SYMBOL)
    point = float(getattr(symbol_info, "point", 0.01) or 0.01)
    spread = float(getattr(symbol_info, "spread", 0) or 0) * point
    bars = _as_records(rates)
    trail_rates_by_tf = {}
    for trail_tf in list(getattr(config, "TRAIL_GROUPS", {}).get(tf_name, [tf_name])):
        trail_val = TF_MAP.get(trail_tf)
        if trail_val is None:
            continue
        raw_trail = _fetch_rates(trail_tf, trail_val, range_end_utc=range_end_utc)
        if raw_trail is not None:
            trail_rates_by_tf[trail_tf] = _as_records(raw_trail)
    sweep_htf_rates = None
    sweep_htf = _sweep_htf_name(tf_name)
    sweep_htf_val = TF_MAP.get(sweep_htf)
    if sweep_htf_val is not None:
        raw_sweep_htf = _fetch_rates(sweep_htf, sweep_htf_val, range_end_utc=range_end_utc)
        if raw_sweep_htf is not None:
            sweep_htf_rates = _as_records(raw_sweep_htf)

    since_ts = int(SINCE.timestamp())
    start_idx = max(80, next((i for i, r in enumerate(bars) if int(r["time"]) >= since_ts), 80))
    strategy_window = max(
        80,
        int(getattr(config, "TF_LOOKBACK", {}).get(tf_name, getattr(config, "SWING_LOOKBACK", 20)) or 20) + 6,
    )

    trades: list[dict] = []
    pending: list[dict] = []
    open_trades: list[dict] = []
    fired: set[tuple] = set()
    sl_guard = SimSLGuard(point)
    trail_focus_state: dict = {}
    last_sid_tf: dict = {}
    fallback_start: dict = {}
    maru_pending: dict = {}
    tf_secs = TF_SECONDS.get(tf_name, 60)

    progress_every = max(1, (len(bars) - start_idx) // 20)
    for event_no, i in enumerate(range(start_idx, len(bars)), start=1):
        if progress_cb is not None and (event_no == 1 or event_no % progress_every == 0 or i == len(bars) - 1):
            try:
                total_events = max(1, len(bars) - start_idx)
                progress_cb(f"Unified {tf_name} replay progress {event_no}/{total_events} bar(s) ({event_no * 100 // total_events}%)")
            except Exception:
                pass
        bar = bars[i]
        bt = to_bkk(bar["time"])
        scan_allowed = scan_until_utc is None or bt <= scan_until_utc
        if not scan_allowed and not pending and not open_trades:
            continue
        h = float(bar["high"])
        l = float(bar["low"])
        full_rates = bars[:i + 1]
        hist_data = _build_historical_hhll_data(full_rates) if _pre_scan_hhll_needed(strategies) else {}
        scan_rates = bars[max(0, i - strategy_window + 1):i + 1]
        s8_scan = (
            _call_with_hhll(tf_name, hist_data, strategy_8, scan_rates, tf=tf_name if hist_data else "")
            if 8 in strategies else {"signal": "WAIT"}
        )

        still_pending = []
        for order in pending:
            sid = int(order.get("sid", 0) or 0)
            age_bars = (int(bar["time"]) - int(order.get("detect_time_raw", bar["time"]))) // max(1, int(tf_secs))
            cancel_bars = int(order.get("cancel_bars", 0) or 0)
            cancel_expired = (
                cancel_bars
                and ((sid == 1 and age_bars > cancel_bars) or (sid != 1 and age_bars >= cancel_bars))
            )
            if cancel_expired and S2_FILL_BEFORE_CANCEL_BARS and _order_touched_entry(order, bar):
                cancel_expired = False
            if cancel_expired:
                trades.append(_cancel_pending_event(
                    order,
                    bt,
                    "cancel_bars",
                    bar=bar,
                    age_bars=age_bars,
                    cancel_bars=cancel_bars,
                ))
                continue
            if sid == 8 and sim_s8_backtest._cancelled_by_swing_change(order, s8_scan):
                trades.append({
                    **order,
                    "entry_time": order["detect_time"],
                    "entry_time_raw": order["detect_time_raw"],
                    "close_time": bt,
                    "close_price": None,
                    "close_type": "CANCEL",
                    "pnl": 0.0,
                    "profit": 0.0,
                    "reason": "S8 swing changed",
                    "cancel_reason": "S8 swing changed",
                })
                continue
            break_cancel = _limit_break_cancel_event(order, tf_name, full_rates, bt)
            if break_cancel is not None:
                trades.append(break_cancel)
                continue
            if sl_guard.near_blocked(tf_name, order["signal"], float(order["entry"]), bar, full_rates):
                trades.append(trend_cancel_event(order, bt, "SL Guard active near entry"))
                continue
            s1_rule = s1_pending_rule_check(order, full_rates)
            if s1_rule.get("status") == "fail":
                trades.append(trend_cancel_event(order, bt, s1_rule.get("reason", "S1 rule cancel")))
                continue
            lg = limit_guard_cancel(order, open_trades, bar, point)
            if lg.get("status") == "fail":
                trades.append(trend_cancel_event(order, bt, lg.get("reason", "Limit Guard cancel")))
                continue
            pd_pending2 = pending_pdfiboplus_round2(order, full_rates)
            if pd_pending2.get("status") == "fail":
                trades.append(pd_cancel_event(order, bt))
                continue
            tr_pending2 = pending_trend_check_round2(order, full_rates)
            if tr_pending2.get("status") == "fail":
                trades.append(trend_cancel_event(order, bt, tr_pending2.get("reason", "Pending Trend Check round2 fail")))
                continue
            tr_pending = pending_trend_check_round1(order, full_rates, bar, point)
            if tr_pending.get("status") == "fail":
                trades.append(trend_cancel_event(order, bt, tr_pending.get("reason", "Pending Trend Check round1 fail")))
                continue
            if sid == 8:
                sim_s8_backtest._arm_pending_if_ready(order, bar)

            filled = (
                (order["signal"] == "BUY" and l <= float(order["entry"]))
                or (order["signal"] == "SELL" and h >= float(order["entry"]))
            )
            if not filled:
                still_pending.append(order)
                continue

            trade = _fill_trade(order, bar)
            pd = fill_pdfiboplus_round1(trade, full_rates)
            if pd.get("status") == "fail":
                trades.append(_close_row(trade, "PD_FILL_FAIL", float(bar["close"]), bt))
                continue
            rsi = fill_rsi_recheck(trade, full_rates)
            if rsi.get("status") == "fail":
                trades.append(_close_row(trade, "RSI_FAIL", float(bar["close"]), bt))
                continue
            tr = fill_trend_recheck_round1(trade, full_rates)
            if tr.get("status") == "fail":
                trades.append(_close_row(trade, "TREND_FAIL", float(bar["close"]), bt))
                continue
            open_trades.append(trade)
        pending = still_pending

        opposite_closes = opposite_order_apply(open_trades, pending, bar, spread)
        opposite_close_ids = {id(trade) for trade, _ in opposite_closes}
        guard_activated_sides = []
        still_open = []
        for trade in open_trades:
            sid = int(trade.get("sid", 0) or 0)
            if id(trade) in opposite_close_ids:
                trades.append(_close_row(trade, "OPPOSITE_CLOSE", float(bar["close"]), bt))
                continue
            s1_rule = s1_fill_rule_check(trade, full_rates, float(bar["close"]))
            if s1_rule.get("status") == "fail":
                row = _close_row(trade, s1_rule_close_type(s1_rule), float(bar["close"]), bt)
                trades.append(row)
                if sl_guard.record_close(tf_name, trade["signal"], row["close_type"], row["pnl"], full_rates):
                    guard_activated_sides.append(trade["signal"])
                continue
            sweep = limit_sweep_followup_s8(trade, full_rates, pending, bar, bars[i - 1] if i > 0 else None, tf_name)
            if sweep.get("status") == "close":
                row = _close_row(trade, "LIMIT_SWEEP", float(bar["close"]), bt)
                trades.append(row)
                if sl_guard.record_close(tf_name, trade["signal"], row["close_type"], row["pnl"], full_rates):
                    guard_activated_sides.append(trade["signal"])
                new_order = sweep.get("new_order")
                if new_order:
                    new_order["detect_time"] = to_bkk(new_order["detect_time_raw"])
                    pending.append(new_order)
                continue
            pd2 = fill_pdfiboplus_round2(trade, full_rates)
            if pd2.get("status") == "fail":
                trades.append(_close_row(trade, "PD_FILL_FAIL", float(bar["close"]), bt))
                continue
            tr2 = fill_trend_recheck_round2(trade, full_rates)
            if tr2.get("status") == "fail":
                trades.append(_close_row(trade, "TREND_FAIL", float(bar["close"]), bt))
                continue
            trail_sl_apply(
                trade, trail_rates_by_tf, int(bar["time"]), tf_name,
                open_trades=open_trades, pending=pending, bar=bar,
                point=point, spread=spread, focus_state=trail_focus_state,
            )
            sl_active = bool(trade.get("sl_armed", True)) if sid == 8 else True
            if trade["signal"] == "BUY":
                if sl_active and l <= float(trade["sl"]):
                    row = _close_row(trade, "SL", trade["sl"], bt)
                    trades.append(row)
                    if sl_guard.record_close(tf_name, trade["signal"], row["close_type"], row["pnl"], full_rates):
                        guard_activated_sides.append(trade["signal"])
                    continue
                if h >= float(trade["tp"]):
                    row = _close_row(trade, "TP", trade["tp"], bt)
                    trades.append(row)
                    sl_guard.record_close(tf_name, trade["signal"], row["close_type"], row["pnl"], full_rates)
                    continue
            else:
                if sl_active and h >= float(trade["sl"]):
                    row = _close_row(trade, "SL", trade["sl"], bt)
                    trades.append(row)
                    if sl_guard.record_close(tf_name, trade["signal"], row["close_type"], row["pnl"], full_rates):
                        guard_activated_sides.append(trade["signal"])
                    continue
                if l <= float(trade["tp"]):
                    row = _close_row(trade, "TP", trade["tp"], bt)
                    trades.append(row)
                    sl_guard.record_close(tf_name, trade["signal"], row["close_type"], row["pnl"], full_rates)
                    continue
            still_open.append(trade)

        if guard_activated_sides and getattr(config, "SL_GUARD_CLOSE_ON_ACTIVATE", True):
            active_sides = set(guard_activated_sides)
            kept_open = []
            for trade in still_open:
                if trade["signal"] in active_sides:
                    trades.append(_close_row(trade, "SL_GUARD_CLOSE", float(bar["close"]), bt))
                else:
                    kept_open.append(trade)
            still_open = kept_open
            kept_pending = []
            for order in pending:
                if order["signal"] in active_sides:
                    trades.append(trend_cancel_event(order, bt, "SL Guard activated"))
                else:
                    kept_pending.append(order)
            pending = kept_pending
        open_trades = still_open

        for retry_order in sl_guard.pop_retry_orders(tf_name, full_rates, bar):
            retry_order["detect_time"] = to_bkk(retry_order["detect_time_raw"])
            if not _duplicate_pending(pending, retry_order):
                pending.append(retry_order)

        scan_results = []
        if scan_allowed:
            scan_results = _scan_signals(
                strategies, scan_rates, full_rates, hist_data, tf_name, bt, bar, tf_secs, fallback_start, maru_pending
            )
        if not hist_data and _post_signal_hhll_needed(strategies, scan_results):
            hist_data = _build_historical_hhll_data(full_rates)
        sweep_state = _sweep_scan_state(tf_name, hist_data, full_rates, sweep_htf_rates) if scan_results else None
        for sid, result in scan_results:
            order = _pending_from_result(result, tf_name, bar, sid)
            order = _s2_parallel_prepare(order, pending, trades, bt, active_tfs={tf_name})
            if order is None:
                continue
            if _entry_already_passed(order, bar):
                continue
            key = (
                int(bar["time"]),
                sid,
                order.get("signal"),
                round(float(order.get("entry", 0.0) or 0.0), 2),
                round(float(order.get("sl", 0.0) or 0.0), 2),
                round(float(order.get("tp", 0.0) or 0.0), 2),
                str(order.get("pattern", "")),
            )
            if key in fired:
                continue
            fired.add(key)
            if _duplicate_pending(pending, order):
                continue
            if _sweep_scan_blocked(sweep_state, sid, order["signal"]):
                event = trend_cancel_event(order, order["detect_time"], "Sweep Filter scan block")
                event["sweep_scan_state"] = sweep_state or ""
                event["sweep_scan_tf"] = tf_name
                event.update(_sweep_scan_meta(tf_name, order))
                trades.append(event)
                continue
            trend_blocked, trend_reason = _trend_scan_blocked(tf_name, hist_data, sid, order["signal"])
            if trend_blocked:
                trades.append(trend_cancel_event(order, order["detect_time"], f"Trend Filter scan block: {trend_reason}"))
                continue
            if sid != 8 and not _pattern_allows_adjacent_order(sid, str(order.get("pattern", ""))):
                if _adjacent_sid_blocked_sim(last_sid_tf, pending, open_trades, tf_name, sid, int(bar["time"]), tf_secs):
                    trades.append(trend_cancel_event(order, order["detect_time"], "Adjacent same-sid order blocked"))
                    continue
            if sl_guard.is_blocked(tf_name, order["signal"], full_rates):
                guard_meta = sl_guard.block_reason_meta(tf_name, order["signal"])
                sl_guard.record_blocked_order(tf_name, order, int(bar["time"]))
                event = trend_cancel_event(order, order["detect_time"], "SL Guard blocked new LIMIT")
                event.update(guard_meta)
                trades.append(event)
                continue
            if sid == 4:
                pd = sim_s4_backtest._pd_precreate_check(order, scan_rates, tf_name)
            else:
                pd = pending_pdfiboplus_round1(order, full_rates)
            if pd.get("status") == "fail":
                trades.append(pd_cancel_event(order, order["detect_time"]))
                continue
            pending.append(order)
            last_sid_tf.setdefault(tf_name, {})[sid] = int(bar["time"])

    for order in pending:
        trades.append({
            **order,
            "entry_time": order["detect_time"],
            "entry_time_raw": order["detect_time_raw"],
            "close_time": None,
            "close_price": None,
            "close_type": "OPEN_PENDING",
            "pnl": 0.0,
            "profit": 0.0,
        })
    for trade in open_trades:
        trades.append({
            **trade,
            "close_time": None,
            "close_price": None,
            "close_type": "OPEN",
            "pnl": 0.0,
            "profit": 0.0,
        })
    return trades


def backtest_multi_tf(
    tf_map: dict[str, int],
    strategies: set[int],
    range_end_utc: datetime | None = None,
    scan_until_utc: datetime | None = None,
    progress_cb=None,
) -> list[dict]:
    if not tf_map:
        return []
    try:
        import sweep_filter
        sweep_filter.reset_all()
    except Exception:
        pass

    symbol_info = mt5.symbol_info(SYMBOL)
    point = float(getattr(symbol_info, "point", 0.01) or 0.01)
    spread = float(getattr(symbol_info, "spread", 0) or 0) * point

    states: dict[str, dict] = {}
    events: list[tuple[int, int, str, int]] = []
    since_ts = int(SINCE.timestamp())
    for tf_name, tf_val in tf_map.items():
        rates = _fetch_rates(tf_name, tf_val, range_end_utc=range_end_utc)
        if rates is None or len(rates) < 120:
            continue
        bars = _as_records(rates)
        start_idx = max(80, next((i for i, r in enumerate(bars) if int(r["time"]) >= since_ts), 80))
        strategy_window = max(
            80,
            int(getattr(config, "TF_LOOKBACK", {}).get(tf_name, getattr(config, "SWING_LOOKBACK", 20)) or 20) + 6,
        )
        states[tf_name] = {
            "bars": bars,
            "start_idx": start_idx,
            "strategy_window": strategy_window,
            "tf_secs": TF_SECONDS.get(tf_name, 60),
            "fallback_start": {},
            "maru_pending": {},
            "sweep_htf_rates": None,
        }
        sweep_htf = _sweep_htf_name(tf_name)
        sweep_htf_val = TF_MAP.get(sweep_htf)
        if sweep_htf_val is not None:
            raw_sweep_htf = _fetch_rates(sweep_htf, sweep_htf_val, range_end_utc=range_end_utc)
            if raw_sweep_htf is not None:
                states[tf_name]["sweep_htf_rates"] = _as_records(raw_sweep_htf)
        for idx in range(start_idx, len(bars)):
            events.append((int(bars[idx]["time"]), _tf_sort_key(tf_name), tf_name, idx))

    if not states:
        return []

    events.sort()
    active_tfs = set(states)
    trail_rates_by_tf = {tf_name: state["bars"] for tf_name, state in states.items()}
    trades: list[dict] = []
    pending: list[dict] = []
    open_trades: list[dict] = []
    fired: set[tuple] = set()
    sl_guard = SimSLGuard(point)
    trail_focus_state: dict = {}
    last_sid_tf: dict = {}

    progress_every = max(1, len(events) // 20)
    for event_no, (event_time, _, tf_name, idx) in enumerate(events, start=1):
        if progress_cb is not None and (event_no == 1 or event_no % progress_every == 0 or event_no == len(events)):
            try:
                progress_cb(f"S2 multi-TF replay progress {event_no}/{len(events)} event(s) ({event_no * 100 // max(1, len(events))}%)")
            except Exception:
                pass
        state = states[tf_name]
        bars = state["bars"]
        bar = bars[idx]
        bt = to_bkk(bar["time"])
        scan_allowed = scan_until_utc is None or bt <= scan_until_utc
        if not scan_allowed:
            has_active_tf = any(
                str(row.get("tf") or "") == tf_name
                or str(row.get("lifecycle_tf") or "") == tf_name
                for row in pending
            )
            has_active_tf = has_active_tf or any(
                str(row.get("tf") or "") == tf_name
                or str(row.get("lifecycle_tf") or "") == tf_name
                for row in open_trades
            )
            if not has_active_tf:
                continue
        h = float(bar["high"])
        l = float(bar["low"])
        full_rates = bars[:idx + 1]
        hist_data = _build_historical_hhll_data(full_rates) if _pre_scan_hhll_needed(strategies) else {}
        scan_rates = bars[max(0, idx - int(state["strategy_window"]) + 1):idx + 1]
        tf_secs = int(state["tf_secs"])
        s8_scan = {"signal": "WAIT"}

        still_pending = []
        for order in pending:
            order_tf = str(order.get("tf") or tf_name)
            lifecycle_tf = str(order.get("lifecycle_tf") or order_tf)
            if order_tf != tf_name and lifecycle_tf != tf_name:
                still_pending.append(order)
                continue
            sid = int(order.get("sid", 0) or 0)
            age_bars = (int(bar["time"]) - int(order.get("detect_time_raw", bar["time"]))) // max(1, int(tf_secs))
            cancel_bars = int(order.get("cancel_bars", 0) or 0)
            cancel_expired = (
                cancel_bars
                and ((sid == 1 and age_bars > cancel_bars) or (sid != 1 and age_bars >= cancel_bars))
            )
            if cancel_expired and S2_FILL_BEFORE_CANCEL_BARS and _order_touched_entry(order, bar):
                cancel_expired = False
            if order_tf == tf_name and cancel_expired:
                trades.append(_cancel_pending_event(
                    order,
                    bt,
                    "cancel_bars",
                    bar=bar,
                    age_bars=age_bars,
                    cancel_bars=cancel_bars,
                ))
                continue
            if sid == 8 and sim_s8_backtest._cancelled_by_swing_change(order, s8_scan):
                trades.append({
                    **order,
                    "entry_time": order["detect_time"],
                    "entry_time_raw": order["detect_time_raw"],
                    "close_time": bt,
                    "close_price": None,
                    "close_type": "CANCEL",
                    "pnl": 0.0,
                    "profit": 0.0,
                    "reason": "S8 swing changed",
                    "cancel_reason": "S8 swing changed",
                })
                continue
            break_cancel = _limit_break_cancel_event(order, tf_name, full_rates, bt) if order_tf == tf_name else None
            if break_cancel is not None:
                trades.append(break_cancel)
                continue
            if sl_guard.near_blocked(tf_name, order["signal"], float(order["entry"]), bar, full_rates):
                trades.append(trend_cancel_event(order, bt, "SL Guard active near entry"))
                continue
            lg = limit_guard_cancel(order, open_trades, bar, point)
            if lg.get("status") == "fail":
                trades.append(trend_cancel_event(order, bt, lg.get("reason", "Limit Guard cancel")))
                continue
            if lifecycle_tf != tf_name:
                still_pending.append(order)
                continue

            filled = (
                (order["signal"] == "BUY" and l <= float(order["entry"]))
                or (order["signal"] == "SELL" and h >= float(order["entry"]))
            )
            if not filled:
                still_pending.append(order)
                continue

            trade = _fill_trade(order, bar)
            rsi = fill_rsi_recheck(trade, full_rates)
            if rsi.get("status") == "fail":
                trades.append(_close_row(trade, "RSI_FAIL", float(bar["close"]), bt))
                continue
            open_trades.append(trade)
        pending = still_pending

        opposite_closes = opposite_order_apply(open_trades, pending, bar, spread)
        opposite_close_ids = {id(trade) for trade, _ in opposite_closes}
        guard_activated_sides = []
        still_open = []
        for trade in open_trades:
            trade_tf = str(trade.get("lifecycle_tf") or trade.get("tf") or tf_name)
            if trade_tf != tf_name:
                still_open.append(trade)
                continue
            sid = int(trade.get("sid", 0) or 0)
            if id(trade) in opposite_close_ids:
                trades.append(_close_row(trade, "OPPOSITE_CLOSE", float(bar["close"]), bt))
                continue
            trail_sl_apply(
                trade, trail_rates_by_tf, int(bar["time"]), tf_name,
                open_trades=open_trades, pending=pending, bar=bar,
                point=point, spread=spread, focus_state=trail_focus_state,
            )
            sl_active = bool(trade.get("sl_armed", True)) if sid == 8 else True
            if trade["signal"] == "BUY":
                if sl_active and l <= float(trade["sl"]):
                    row = _close_row(trade, "SL", trade["sl"], bt)
                    trades.append(row)
                    if sl_guard.record_close(tf_name, trade["signal"], row["close_type"], row["pnl"], full_rates):
                        guard_activated_sides.append(trade["signal"])
                    continue
                if h >= float(trade["tp"]):
                    row = _close_row(trade, "TP", trade["tp"], bt)
                    trades.append(row)
                    sl_guard.record_close(tf_name, trade["signal"], row["close_type"], row["pnl"], full_rates)
                    continue
            else:
                if sl_active and h >= float(trade["sl"]):
                    row = _close_row(trade, "SL", trade["sl"], bt)
                    trades.append(row)
                    if sl_guard.record_close(tf_name, trade["signal"], row["close_type"], row["pnl"], full_rates):
                        guard_activated_sides.append(trade["signal"])
                    continue
                if l <= float(trade["tp"]):
                    row = _close_row(trade, "TP", trade["tp"], bt)
                    trades.append(row)
                    sl_guard.record_close(tf_name, trade["signal"], row["close_type"], row["pnl"], full_rates)
                    continue
            still_open.append(trade)

        if guard_activated_sides and getattr(config, "SL_GUARD_CLOSE_ON_ACTIVATE", True):
            active_sides = set(guard_activated_sides)
            kept_open = []
            for trade in still_open:
                if trade["signal"] in active_sides:
                    trades.append(_close_row(trade, "SL_GUARD_CLOSE", float(bar["close"]), bt))
                else:
                    kept_open.append(trade)
            still_open = kept_open
            kept_pending = []
            for order in pending:
                if order["signal"] in active_sides:
                    trades.append(trend_cancel_event(order, bt, "SL Guard activated"))
                else:
                    kept_pending.append(order)
            pending = kept_pending
        open_trades = still_open

        for retry_order in sl_guard.pop_retry_orders(tf_name, full_rates, bar):
            retry_order["detect_time"] = to_bkk(retry_order["detect_time_raw"])
            if not _duplicate_pending(pending, retry_order):
                pending.append(retry_order)

        scan_results = []
        if scan_allowed:
            scan_results = _scan_signals(
                strategies,
                scan_rates,
                full_rates,
                hist_data,
                tf_name,
                bt,
                bar,
                tf_secs,
                state["fallback_start"],
                state["maru_pending"],
            )
        if not hist_data and _post_signal_hhll_needed(strategies, scan_results):
            hist_data = _build_historical_hhll_data(full_rates)
        sweep_state = (
            _sweep_scan_state(tf_name, hist_data, full_rates, state.get("sweep_htf_rates"))
            if scan_results and bool(strategies & {2, 3}) else None
        )
        for sid, result in scan_results:
            order = _pending_from_result(result, tf_name, bar, sid)
            order = _s2_parallel_prepare(order, pending, trades, bt, active_tfs=active_tfs)
            if order is None:
                continue
            if _entry_already_passed(order, bar):
                continue
            key = (
                int(bar["time"]),
                sid,
                order.get("signal"),
                round(float(order.get("entry", 0.0) or 0.0), 2),
                round(float(order.get("sl", 0.0) or 0.0), 2),
                round(float(order.get("tp", 0.0) or 0.0), 2),
                str(order.get("pattern", "")),
            )
            if key in fired:
                continue
            fired.add(key)
            if _duplicate_pending(pending, order):
                continue
            if _sweep_scan_blocked(sweep_state, sid, order["signal"]):
                event = trend_cancel_event(order, order["detect_time"], "Sweep Filter scan block")
                event["sweep_scan_state"] = sweep_state or ""
                event["sweep_scan_tf"] = tf_name
                event.update(_sweep_scan_meta(tf_name, order))
                trades.append(event)
                continue
            trend_blocked, trend_reason = _trend_scan_blocked(tf_name, hist_data, sid, order["signal"])
            if trend_blocked:
                trades.append(trend_cancel_event(order, order["detect_time"], f"Trend Filter scan block: {trend_reason}"))
                continue
            if sid != 8 and not _pattern_allows_adjacent_order(sid, str(order.get("pattern", ""))):
                if _adjacent_sid_blocked_sim(last_sid_tf, pending, open_trades, tf_name, sid, int(bar["time"]), tf_secs):
                    trades.append(trend_cancel_event(order, order["detect_time"], "Adjacent same-sid order blocked"))
                    continue
            if sl_guard.is_blocked(tf_name, order["signal"], full_rates):
                guard_meta = sl_guard.block_reason_meta(tf_name, order["signal"])
                sl_guard.record_blocked_order(tf_name, order, int(bar["time"]))
                event = trend_cancel_event(order, order["detect_time"], "SL Guard blocked new LIMIT")
                event.update(guard_meta)
                trades.append(event)
                continue
            pd = pending_pdfiboplus_round1(order, full_rates)
            if pd.get("status") == "fail":
                trades.append(pd_cancel_event(order, order["detect_time"]))
                continue
            pending.append(order)
            last_sid_tf.setdefault(tf_name, {})[sid] = int(bar["time"])

    for order in pending:
        trades.append({
            **order,
            "entry_time": order["detect_time"],
            "entry_time_raw": order["detect_time_raw"],
            "close_time": None,
            "close_price": None,
            "close_type": "OPEN_PENDING",
            "pnl": 0.0,
            "profit": 0.0,
        })
    for trade in open_trades:
        trades.append({
            **trade,
            "close_time": None,
            "close_price": None,
            "close_type": "OPEN",
            "pnl": 0.0,
            "profit": 0.0,
        })
    return trades
