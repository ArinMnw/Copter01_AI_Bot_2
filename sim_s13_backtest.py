from __future__ import annotations

from datetime import datetime, timezone, timedelta

import MetaTrader5 as mt5

import config
import hhll_swing as _hs
from strategy13 import strategy_13


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
    "M1": 2000,
    "M5": 600,
    "M15": 400,
    "M30": 250,
    "H1": 180,
    "H4": 100,
    "D1": 50,
}

_HHLL_LB = int(getattr(config, "HHLL_LEFT", 5) or 5)
_HHLL_RB = int(getattr(config, "HHLL_RIGHT", 5) or 5)
_HHLL_LBK = int(getattr(config, "HHLL_LOOKBACK", 500) or 500)


def to_bkk(ts: int) -> datetime:
    return datetime.fromtimestamp(int(ts), tz=UTC) + timedelta(hours=TZ_OFF - SRV_TZ)


def profit(price_diff: float) -> float:
    return round(float(price_diff) * PRICE_TO_USD, 2)


def s13_runtime_feature_coverage() -> list[dict]:
    return [
        {
            "name": "S13 EzAlgo detect",
            "config_on": bool(config.active_strategies.get(13, False)),
            "runtime": "apply",
            "replay": "apply",
            "note": "Replay calls shared strategy13.strategy_13()",
        },
        {
            "name": "S13 market/split TP",
            "config_on": True,
            "runtime": "apply",
            "replay": "partial",
            "note": "Replay opens TP split as market rows; live can mix market and limit depending tick vs entry",
        },
        {
            "name": "S13 opposite flip",
            "config_on": True,
            "runtime": "apply",
            "replay": "apply",
            "note": "Replay closes opposite S13 rows on the same TF before new signal",
        },
        {
            "name": "PD Fibo Plus",
            "config_on": getattr(config, "PDFIBOPLUS_ENABLED", False),
            "runtime": "skip_s13",
            "replay": "skip_s13",
            "note": "Runtime skips SIDs 9,10,13,14,15,16",
        },
        {
            "name": "Trend Recheck",
            "config_on": getattr(config, "LIMIT_TREND_RECHECK", False),
            "runtime": "apply",
            "replay": "partial",
            "note": "Replay applies fill trend recheck round1 with injected HHLL trend context",
        },
        {
            "name": "RSI Fill Recheck",
            "config_on": getattr(config, "PENDING_RSI_RECHECK_ENABLED", False),
            "runtime": "apply",
            "replay": "gap",
            "note": "Runtime RSI fill recheck applies to S13 when enabled",
        },
        {
            "name": "SL Guard",
            "config_on": bool(getattr(config, "SL_GUARD_GROUP_ENABLED", False)),
            "runtime": "apply",
            "replay": "partial",
            "note": "Central runner can apply SL Guard Group close-on-activate overlay with context TFs",
        },
        {
            "name": "Trail SL",
            "config_on": getattr(config, "TRAIL_SL_ENABLED", False),
            "runtime": "skip_s13",
            "replay": "skip_s13",
            "note": "Runtime Trail SL skips standalone S13",
        },
        {
            "name": "Opposite Order",
            "config_on": getattr(config, "OPPOSITE_ORDER_ENABLED", False),
            "runtime": "skip_s13",
            "replay": "skip_s13",
            "note": "Runtime opposite-order TP/protect filters S13",
        },
    ]


def s13_unreplayed_active_features() -> list[dict]:
    return [
        item for item in s13_runtime_feature_coverage()
        if item["config_on"] and item["replay"] == "gap"
    ]


def _tp_levels_for(result: dict, entry: float, signal: str) -> list[float]:
    tp_levels = [float(x) for x in (result.get("tp_levels") or []) if float(x) > 0]
    if not tp_levels and float(result.get("tp", 0.0) or 0.0) > 0:
        tp_levels = [float(result["tp"])]

    if getattr(config, "SCALE_OUT_ENABLED", False) and tp_levels:
        tp_max = tp_levels[-1]
        dist = (tp_max - entry) if signal == "BUY" else (entry - tp_max)
        steps = list(config.compute_tso_effective_steps(dist, sid=13))
        if steps:
            if signal == "BUY":
                return [round(entry + float(d), 2) for d in steps]
            return [round(entry - float(d), 2) for d in steps]
    return [round(x, 2) for x in tp_levels]


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


def _inject_hhll_for_trend(tf_name: str, bars_slice: list[dict]) -> bool:
    max_bars = _HHLL_LBK + _HHLL_LB + _HHLL_RB + 5
    rates = bars_slice[-max_bars:] if len(bars_slice) > max_bars else bars_slice
    if len(rates) < _HHLL_LB + _HHLL_RB + 10:
        return False
    zz = _hs._build_zz(rates, _HHLL_LB, _HHLL_RB)
    if len(zz) < 5:
        return False
    buckets = {"HH": None, "HL": None, "LH": None, "LL": None}
    prev_buckets = {"HH": None, "HL": None, "LH": None, "LL": None}
    structure = []
    for k in range(len(zz)):
        lbl = _hs._classify_pt(zz, k)
        if not lbl:
            continue
        pt = {"price": zz[k]["price"], "time": zz[k]["time"], "label": lbl}
        prev_buckets[lbl] = buckets[lbl]
        buckets[lbl] = pt
        structure.append(lbl)
    _hs._hhll_data[tf_name] = {
        "hh": buckets["HH"],
        "hl": buckets["HL"],
        "lh": buckets["LH"],
        "ll": buckets["LL"],
        "prev_hh": prev_buckets["HH"],
        "prev_hl": prev_buckets["HL"],
        "prev_lh": prev_buckets["LH"],
        "prev_ll": prev_buckets["LL"],
        "last_label": structure[-1] if structure else "",
        "structure": list(reversed(structure[-6:])),
    }
    try:
        import scanner as _scanner

        trend = _hs.get_trend_from_structure(tf_name) or {}
        _scanner._swing_data[tf_name] = {
            "trend": trend,
            "breakout": {},
            "asof_time": int(rates[-1]["time"]),
            "last_bar": {
                "time": int(rates[-1]["time"]),
                "open": float(rates[-1]["open"]),
                "high": float(rates[-1]["high"]),
                "low": float(rates[-1]["low"]),
                "close": float(rates[-1]["close"]),
            },
        }
    except Exception:
        return False
    return True


def _fill_trend_allows(tf_name: str, signal: str, bars_slice: list[dict]) -> tuple[bool, str]:
    if not getattr(config, "LIMIT_TREND_RECHECK", False):
        return True, ""
    if not _inject_hhll_for_trend(tf_name, bars_slice):
        return True, "trend_data_unavailable"
    try:
        import scanner as _scanner

        return _scanner.trend_allows_signal(tf_name, signal)
    except Exception as exc:
        return True, f"trend_check_error:{type(exc).__name__}"


def _open_trade(result: dict, tf_name: str, bars: list, entry_idx: int, tp: float, order_index: int) -> dict:
    fill_bar = bars[entry_idx]
    signal = result["signal"]
    entry = round(float(fill_bar["open"]), 2)
    sl = round(float(result["sl"]), 2)
    return {
        "sid": 13,
        "tf": tf_name,
        "signal": signal,
        "side": signal,
        "pattern": f"{result.get('pattern', 'S13')} TP{order_index}",
        "entry": entry,
        "strategy_entry": round(float(result.get("entry", entry)), 2),
        "sl": sl,
        "tp": round(float(tp), 2),
        "entry_time": to_bkk(fill_bar["time"]),
        "entry_time_raw": int(fill_bar["time"]),
        "entry_idx": entry_idx,
        "order_index": order_index,
        "tp_levels": result.get("tp_levels", []),
        "close_type": "OPEN",
    }


def backtest_tf(tf_name: str, tf_val: int) -> list[dict]:
    extra = TF_EXTRA_BARS.get(tf_name, 300)
    rates = mt5.copy_rates_from_pos(SYMBOL, tf_val, 0, extra + 6000)
    if rates is None or len(rates) < 80:
        return []
    bars = sorted(
        [{name: r[name] for name in rates.dtype.names} for r in rates],
        key=lambda r: int(r["time"]),
    )
    since_ts = int(SINCE.timestamp())
    start_idx = max(40, next((i for i, r in enumerate(bars) if int(r["time"]) >= since_ts), 40))

    trades: list[dict] = []
    open_trades: list[dict] = []

    def _close_exits(bar: dict) -> None:
        nonlocal open_trades
        still = []
        bt = to_bkk(bar["time"])
        h = float(bar["high"])
        l = float(bar["low"])
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
            still.append(trade)
        open_trades = still

    for i in range(start_idx, len(bars)):
        bar = bars[i]
        _close_exits(bar)

        result = strategy_13(bars[:i + 1])
        signal = result.get("signal", "WAIT")
        if signal not in ("BUY", "SELL"):
            continue

        if any(t.get("signal") == signal for t in open_trades):
            continue

        entry_ref = round(float(result.get("entry", 0.0) or 0.0), 2)
        tp_levels = _tp_levels_for(result, entry_ref, signal)
        if not tp_levels:
            continue

        kept = []
        for trade in open_trades:
            if trade.get("signal") != signal:
                trades.append(_close_row(trade, "S13_FLIP", float(bar["open"]), to_bkk(bar["time"])))
            else:
                kept.append(trade)
        open_trades = kept

        trend_ok, trend_why = _fill_trend_allows(tf_name, signal, bars[:i + 1])
        for idx, tp in enumerate(tp_levels, start=1):
            trade = _open_trade(result, tf_name, bars, i, tp, idx)
            if not trend_ok:
                row = _close_row(trade, "TREND_RECHECK", trade["entry"], to_bkk(bar["time"]))
                row["trend_recheck_why"] = trend_why
                trades.append(row)
                continue
            open_trades.append(trade)

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
