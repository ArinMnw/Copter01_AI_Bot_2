from __future__ import annotations

from datetime import datetime, time, timezone, timedelta

import MetaTrader5 as mt5

import config
from mt5_utils import calc_atr
from strategy16 import find_bearish_fvgs_in_range, find_bullish_fvgs_in_range


SYMBOL = config.SYMBOL
SINCE = datetime(2026, 5, 24, 0, 0, 0, tzinfo=timezone.utc)
VOLUME = 0.01
PRICE_TO_USD = 100 * VOLUME

UTC = timezone.utc
TZ_OFF = getattr(config, "TZ_OFFSET", 7)
SRV_TZ = getattr(config, "MT5_SERVER_TZ", 0)

TF_MAP = {
    "M1": mt5.TIMEFRAME_M1,
    "M5": mt5.TIMEFRAME_M5,
    "M15": mt5.TIMEFRAME_M15,
    "M30": mt5.TIMEFRAME_M30,
    "H1": mt5.TIMEFRAME_H1,
    "H4": mt5.TIMEFRAME_H4,
    "D1": mt5.TIMEFRAME_D1,
}

TF_EXTRA_BARS = {
    "M1": 3500,
    "M5": 1200,
    "M15": 700,
    "M30": 400,
    "H1": 250,
    "H4": 140,
    "D1": 80,
}


def to_bkk(ts: int) -> datetime:
    return datetime.fromtimestamp(int(ts), tz=UTC) + timedelta(hours=TZ_OFF - SRV_TZ)


def profit(price_diff: float) -> float:
    return round(float(price_diff) * PRICE_TO_USD, 2)


def s16_runtime_feature_coverage() -> list[dict]:
    return [
        {
            "name": "S16 AMD/iFVG detect",
            "config_on": bool(config.active_strategies.get(16, False)),
            "runtime": "apply",
            "replay": "apply",
            "note": "Replay injects simulated BKK time and Asian range instead of using config.now_bkk()",
        },
        {
            "name": "S16 limit lifecycle",
            "config_on": True,
            "runtime": "apply",
            "replay": "partial",
            "note": "Replay models pending limit fill then fixed SL/TP; broker tick ordering can drift",
        },
        {
            "name": "PD Fibo Plus",
            "config_on": getattr(config, "PDFIBOPLUS_ENABLED", False),
            "runtime": "skip_s16",
            "replay": "skip_s16",
            "note": "Runtime skips SIDs 9,10,13,14,15,16",
        },
        {
            "name": "Trend Recheck",
            "config_on": getattr(config, "LIMIT_TREND_RECHECK", False),
            "runtime": "skip_s16",
            "replay": "skip_s16",
            "note": "Runtime skips S16 fill trend recheck",
        },
        {
            "name": "SL Guard",
            "config_on": bool(getattr(config, "SL_GUARD_GROUP_ENABLED", False)),
            "runtime": "apply",
            "replay": "partial",
            "note": "Central runner can apply SL Guard Group close-on-activate overlay with context TFs",
        },
        {
            "name": "Trail/Opposite",
            "config_on": getattr(config, "TRAIL_SL_ENABLED", False) or getattr(config, "OPPOSITE_ORDER_ENABLED", False),
            "runtime": "skip_s16",
            "replay": "skip_s16",
            "note": "Runtime filters standalone S16 from Trail SL and Opposite Order",
        },
    ]


def s16_unreplayed_active_features() -> list[dict]:
    return [
        item for item in s16_runtime_feature_coverage()
        if item["config_on"] and item["replay"] == "gap"
    ]


def _as_records(rates) -> list[dict]:
    return sorted(
        [{name: r[name] for name in rates.dtype.names} for r in rates],
        key=lambda r: int(r["time"]),
    )


def _parse_hhmm(value: str) -> time:
    hh, mm = map(int, value.split(":"))
    return time(hh, mm)


def _in_killzone(dt_bkk: datetime) -> tuple[bool, datetime | None]:
    current_time = dt_bkk.time()
    for start_str, end_str in getattr(config, "S16_KILLZONES", [("14:00", "17:00"), ("19:00", "22:00")]):
        start_t = _parse_hhmm(start_str)
        end_t = _parse_hhmm(end_str)
        if start_t <= current_time < end_t:
            return True, dt_bkk.replace(hour=start_t.hour, minute=start_t.minute, second=0, microsecond=0)
    return False, None


def _asian_ranges(m5_bars: list[dict]) -> dict[str, dict]:
    start_t = _parse_hhmm(getattr(config, "S16_ASIAN_START_BKK", "08:00"))
    end_t = _parse_hhmm(getattr(config, "S16_ASIAN_END_BKK", "12:00"))
    by_date: dict[str, list[dict]] = {}
    for bar in m5_bars:
        bt = to_bkk(bar["time"])
        if start_t <= bt.time() < end_t:
            by_date.setdefault(bt.strftime("%Y-%m-%d"), []).append(bar)
    return {
        day: {
            "asian_high": max(float(b["high"]) for b in bars),
            "asian_low": min(float(b["low"]) for b in bars),
        }
        for day, bars in by_date.items()
        if bars
    }


def _strategy_16_at(rates: list[dict], tf_name: str, dt_bkk: datetime, asian: dict | None) -> dict:
    if not asian:
        return {"signal": "WAIT", "reason": "รอตีกรอบเอเชียหลังเวลา 12:00 BKK"}

    in_kz, kz_start_bkk = _in_killzone(dt_bkk)
    if not in_kz or kz_start_bkk is None:
        return {"signal": "WAIT", "reason": "อยู่นอกเวลา Killzones"}

    a_high = float(asian["asian_high"])
    a_low = float(asian["asian_low"])
    kz_start_ts = int((kz_start_bkk - timedelta(hours=TZ_OFF - SRV_TZ)).replace(tzinfo=UTC).timestamp())
    kz_indices = [idx for idx, bar in enumerate(rates) if int(bar["time"]) >= kz_start_ts]
    min_bars = 5 if tf_name in ("M1", "M5") else 3
    if len(kz_indices) < min_bars:
        return {"signal": "WAIT", "reason": f"ข้อมูลบาร์ {tf_name} ใน Killzone ปัจจุบันยังมีไม่พอ"}

    kz_start_idx = kz_indices[0]
    n_rates = len(rates)
    kz_low_price = min(float(rates[idx]["low"]) for idx in kz_indices)
    kz_low_idx = next(idx for idx in kz_indices if float(rates[idx]["low"]) == kz_low_price)
    kz_high_price = max(float(rates[idx]["high"]) for idx in kz_indices)
    kz_high_idx = next(idx for idx in kz_indices if float(rates[idx]["high"]) == kz_high_price)

    atr = calc_atr(rates, 14) or 1.0
    # mirror runtime strategy16.py: SL buffer ของ S16 เอง + risk cap (11/06/2026)
    _slb = getattr(config, "S16_SL_ATR_BUFFER", None)
    sl_buf = (atr * float(_slb)) if _slb is not None else config.SL_BUFFER(atr)
    max_risk = atr * float(getattr(config, "S16_MAX_RISK_ATR_MULT", 0) or 0)
    min_rr = float(getattr(config, "S16_MIN_RR", 1.5))
    entry_mode = getattr(config, "S16_ENTRY_MODE", "boundary")

    if kz_low_price < a_low:
        highest_before_sweep = max(float(rates[idx]["high"]) for idx in range(kz_start_idx, kz_low_idx + 1))
        manip_start_idx = next(idx for idx in range(kz_start_idx, kz_low_idx + 1) if float(rates[idx]["high"]) == highest_before_sweep)
        bearish_fvgs = find_bearish_fvgs_in_range(rates, manip_start_idx, kz_low_idx)
        inverted = []
        for fvg in bearish_fvgs:
            for j in range(kz_low_idx + 1, n_rates):
                if float(rates[j]["close"]) > float(fvg["upper_boundary"]):
                    inverted.append({
                        "fvg_idx": fvg["idx"],
                        "upper": float(fvg["upper_boundary"]),
                        "lower": float(fvg["lower_boundary"]),
                        "time": int(fvg["time"]),
                    })
                    break
        if inverted:
            target = max(inverted, key=lambda f: f["fvg_idx"])
            entry = ((target["upper"] + target["lower"]) / 2.0) if entry_mode == "midline" else target["upper"]
            sl = kz_low_price - sl_buf
            tp = a_high
            risk = entry - sl
            if risk > 0 and (max_risk <= 0 or risk <= max_risk) and float(rates[-1]["close"]) > entry:
                if (tp - entry) / risk < min_rr:
                    tp = entry + (risk * min_rr)
                return {
                    "signal": "BUY",
                    "entry": round(entry, 2),
                    "sl": round(sl, 2),
                    "tp": round(tp, 2),
                    "pattern": "ท่าที่ 16 AMD x iFVG 🟢 BUY",
                    "reason": f"Asian Range: {a_low:.2f} – {a_high:.2f}\nSweep Low: {kz_low_price:.2f}",
                    "order_mode": "limit",
                    "entry_label": "BUY LIMIT (iFVG Inversion)",
                    "asian_high": a_high,
                    "asian_low": a_low,
                    "sweep_price": kz_low_price,
                    "ifvg_time": target["time"],
                    "kz_start_ts": kz_start_ts,
                }

    if kz_high_price > a_high:
        lowest_before_sweep = min(float(rates[idx]["low"]) for idx in range(kz_start_idx, kz_high_idx + 1))
        manip_start_idx = next(idx for idx in range(kz_start_idx, kz_high_idx + 1) if float(rates[idx]["low"]) == lowest_before_sweep)
        bullish_fvgs = find_bullish_fvgs_in_range(rates, manip_start_idx, kz_high_idx)
        inverted = []
        for fvg in bullish_fvgs:
            for j in range(kz_high_idx + 1, n_rates):
                if float(rates[j]["close"]) < float(fvg["lower_boundary"]):
                    inverted.append({
                        "fvg_idx": fvg["idx"],
                        "lower": float(fvg["lower_boundary"]),
                        "upper": float(fvg["upper_boundary"]),
                        "time": int(fvg["time"]),
                    })
                    break
        if inverted:
            target = max(inverted, key=lambda f: f["fvg_idx"])
            entry = ((target["upper"] + target["lower"]) / 2.0) if entry_mode == "midline" else target["lower"]
            sl = kz_high_price + sl_buf
            tp = a_low
            risk = sl - entry
            if risk > 0 and (max_risk <= 0 or risk <= max_risk) and float(rates[-1]["close"]) < entry:
                if (entry - tp) / risk < min_rr:
                    tp = entry - (risk * min_rr)
                return {
                    "signal": "SELL",
                    "entry": round(entry, 2),
                    "sl": round(sl, 2),
                    "tp": round(tp, 2),
                    "pattern": "ท่าที่ 16 AMD x iFVG 🔴 SELL",
                    "reason": f"Asian Range: {a_low:.2f} – {a_high:.2f}\nSweep High: {kz_high_price:.2f}",
                    "order_mode": "limit",
                    "entry_label": "SELL LIMIT (iFVG Inversion)",
                    "asian_high": a_high,
                    "asian_low": a_low,
                    "sweep_price": kz_high_price,
                    "ifvg_time": target["time"],
                    "kz_start_ts": kz_start_ts,
                }

    return {"signal": "WAIT", "reason": "S16: ยังไม่พบ sweep+iFVG"}


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


def _pending_from_order(order: dict, tf_name: str, detect_bar: dict) -> dict:
    return {
        "sid": 16,
        "tf": tf_name,
        "signal": order["signal"],
        "side": order["signal"],
        "pattern": order.get("pattern", "S16"),
        "entry": round(float(order["entry"]), 2),
        "sl": round(float(order["sl"]), 2),
        "tp": round(float(order["tp"]), 2),
        "detect_time": to_bkk(detect_bar["time"]),
        "detect_time_raw": int(detect_bar["time"]),
        "asian_high": order.get("asian_high"),
        "asian_low": order.get("asian_low"),
        "sweep_price": order.get("sweep_price"),
        "ifvg_time": order.get("ifvg_time"),
    }


def _fill_trade(order: dict, bar: dict) -> dict:
    return {
        **order,
        "entry_time": to_bkk(bar["time"]),
        "entry_time_raw": int(bar["time"]),
        "close_type": "OPEN",
    }


def backtest_tf(tf_name: str, tf_val: int) -> list[dict]:
    _since = SINCE if SINCE.tzinfo is not None else SINCE.replace(tzinfo=timezone.utc)
    days = max(30, (datetime.now(timezone.utc) - _since).days + 3)
    bars_per_day = {"M1": 1440, "M5": 288, "M15": 96, "M30": 48, "H1": 24, "H4": 6, "D1": 1}.get(tf_name, 100)
    count = min(TF_EXTRA_BARS.get(tf_name, 500) + days * bars_per_day, 90000)  # cap ~90k
    rates = mt5.copy_rates_from_pos(SYMBOL, tf_val, 0, count)
    m5_days_bars = min(days * 288 + 500, 90000)
    m5_rates = mt5.copy_rates_from_pos(SYMBOL, mt5.TIMEFRAME_M5, 0, m5_days_bars)
    if rates is None or len(rates) < 100 or m5_rates is None or len(m5_rates) < 100:
        return []

    bars = _as_records(rates)
    asian_by_date = _asian_ranges(_as_records(m5_rates))
    since_ts = int(SINCE.timestamp())
    start_idx = max(50, next((i for i, r in enumerate(bars) if int(r["time"]) >= since_ts), 50))

    trades: list[dict] = []
    pending: list[dict] = []
    open_trades: list[dict] = []
    fired_keys: set[tuple] = set()
    # _strategy_16_at ใช้ absolute timestamp filter (kz_start_ts) ไม่ใช่ relative index
    # → window ต้องครอบ kz_start_ts เสมอ (killzone อยู่ใน "วันนี้" เสมอ) ใช้ ~33h เผื่อ
    # (เดิม bars[:i+1] copy ทั้ง list ทุกแท่ง = O(n^2), ค้างที่ >10k แท่ง)
    _WIN_BARS = {"M1": 2000, "M5": 400, "M15": 200, "M30": 100, "H1": 60, "H4": 30, "D1": 10}
    win_size = _WIN_BARS.get(tf_name, 500)

    for i in range(start_idx, len(bars)):
        bar = bars[i]
        bt = to_bkk(bar["time"])
        h = float(bar["high"])
        l = float(bar["low"])

        still_pending = []
        for order in pending:
            if order["signal"] == "BUY" and l <= float(order["entry"]):
                open_trades.append(_fill_trade(order, bar))
            elif order["signal"] == "SELL" and h >= float(order["entry"]):
                open_trades.append(_fill_trade(order, bar))
            else:
                still_pending.append(order)
        pending = still_pending

        still_open = []
        for trade in open_trades:
            if trade["signal"] == "BUY":
                if l <= float(trade["sl"]):
                    trades.append(_close_row(trade, "SL", trade["sl"], bt))
                    continue
                if h >= float(trade["tp"]):
                    trades.append(_close_row(trade, "TP", trade["tp"], bt))
                    continue
            else:
                if h >= float(trade["sl"]):
                    trades.append(_close_row(trade, "SL", trade["sl"], bt))
                    continue
                if l <= float(trade["tp"]):
                    trades.append(_close_row(trade, "TP", trade["tp"], bt))
                    continue
            still_open.append(trade)
        open_trades = still_open

        day = bt.strftime("%Y-%m-%d")
        window = bars[max(0, i + 1 - win_size):i + 1]
        result = _strategy_16_at(window, tf_name, bt, asian_by_date.get(day))
        if result.get("signal") in ("BUY", "SELL") and result.get("order_mode") == "limit":
            # mirror runtime one-shot dedup: 1 order ต่อ (side, killzone window)
            # (เดิม key ละเอียดระดับ iFVG → live เกิด pending สะสม fill พร้อมกัน 13 ไม้ 09/06/2026)
            if bool(getattr(config, "S16_KZ_ONE_SHOT", True)):
                key = (result.get("signal"), int(result.get("kz_start_ts", 0) or 0))
            else:
                key = (
                    day,
                    result.get("signal"),
                    round(float(result.get("entry", 0.0) or 0.0), 2),
                    result.get("ifvg_time"),
                )
            if key not in fired_keys:
                fired_keys.add(key)
                pending.append(_pending_from_order(result, tf_name, bar))

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
