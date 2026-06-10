from __future__ import annotations

from datetime import datetime, timezone, timedelta

import MetaTrader5 as mt5

import config
from strategy12 import s12_get_tp, s12_get_zone_levels, s12_get_swing_context


SYMBOL = config.SYMBOL
SINCE = datetime(2026, 5, 24, 0, 0, 0, tzinfo=timezone.utc)
VOLUME = 0.01
PRICE_TO_USD = 100 * VOLUME

UTC = timezone.utc
TZ_OFF = getattr(config, "TZ_OFFSET", 7)
SRV_TZ = getattr(config, "MT5_SERVER_TZ", 0)

TF_MAP = {"M5": mt5.TIMEFRAME_M5}
M15_TF = mt5.TIMEFRAME_M15


def to_bkk(ts: int) -> datetime:
    return datetime.fromtimestamp(int(ts), tz=UTC) + timedelta(hours=TZ_OFF - SRV_TZ)


def profit(price_diff: float) -> float:
    return round(float(price_diff) * PRICE_TO_USD, 2)


def s12_runtime_feature_coverage() -> list[dict]:
    return [
        {
            "name": "S12 M5 range zone scan",
            "config_on": bool(config.active_strategies.get(12, False)),
            "runtime": "apply",
            "replay": "apply",
            "note": "Replay uses strategy12 zone helpers on M5 bars",
        },
        {
            "name": "S12 market lifecycle",
            "config_on": True,
            "runtime": "apply",
            "replay": "partial",
            "note": "Replay approximates entry/close with M5 bar close instead of live bid/ask tick",
        },
        {
            "name": "S12 order count / side state",
            "config_on": True,
            "runtime": "apply",
            "replay": "apply",
            "note": "Replay tracks side, order count, and last entry price",
        },
        {
            "name": "S12 breakout / flip close-all",
            "config_on": True,
            "runtime": "apply",
            "replay": "partial",
            "note": "Replay closes open S12 rows on breakout/flip using M5 close",
        },
        {
            "name": "S12 SL cooldown",
            "config_on": getattr(config, "S12_COOLDOWN_SECONDS", 0) > 0,
            "runtime": "apply",
            "replay": "gap",
            "note": "Replay does not yet enforce wall-time cooldown after SL",
        },
        {
            "name": "PD/Trend/Limit Guard",
            "config_on": getattr(config, "PDFIBOPLUS_ENABLED", False) or getattr(config, "LIMIT_TREND_RECHECK", False) or getattr(config, "LIMIT_GUARD", False),
            "runtime": "skip_s12_or_market",
            "replay": "skip_s12_or_market",
            "note": "S12 is market/standalone and runtime skips normal pending limit guard path",
        },
    ]


def s12_unreplayed_active_features() -> list[dict]:
    return [
        item for item in s12_runtime_feature_coverage()
        if item["config_on"] and item["replay"] == "gap"
    ]


def _as_records(rates) -> list[dict]:
    return sorted(
        [{name: r[name] for name in rates.dtype.names} for r in rates],
        key=lambda r: int(r["time"]),
    )


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


def _close_all(open_trades: list[dict], reason: str, price: float, close_time: datetime, trades: list[dict]) -> None:
    for trade in list(open_trades):
        trades.append(_close_row(trade, reason, price, close_time))
    open_trades.clear()


def _m15_slice(m15_bars: list[dict], time_raw: int) -> list[dict]:
    return [r for r in m15_bars if int(r["time"]) <= int(time_raw)]


def backtest_tf(tf_name: str, tf_val: int) -> list[dict]:
    if tf_name != "M5":
        return []
    rates_m5 = mt5.copy_rates_from_pos(SYMBOL, tf_val, 0, 12000)
    rates_m15 = mt5.copy_rates_from_pos(SYMBOL, M15_TF, 0, 5000)
    if rates_m5 is None or len(rates_m5) < config.S12_LOOKBACK + 10:
        return []
    if rates_m15 is None or len(rates_m15) < 80:
        return []

    bars = _as_records(rates_m5)
    m15_bars = _as_records(rates_m15)
    since_ts = int(SINCE.timestamp())
    start_idx = max(config.S12_LOOKBACK + 5, next((i for i, r in enumerate(bars) if int(r["time"]) >= since_ts), config.S12_LOOKBACK + 5))

    pt = 0.01
    scale = config.points_scale()
    zone_dist = config.S12_ZONE_POINTS * pt * scale
    sl_dist = config.S12_SL_POINTS * pt * scale

    state = {"side": None, "order_count": 0, "last_entry_price": None}
    trades: list[dict] = []
    open_trades: list[dict] = []

    for i in range(start_idx, len(bars)):
        bar = bars[i]
        bt = to_bkk(bar["time"])
        high = float(bar["high"])
        low = float(bar["low"])
        close = float(bar["close"])

        still_open = []
        for trade in open_trades:
            if trade["signal"] == "BUY":
                if low <= float(trade["sl"]):
                    trades.append(_close_row(trade, "SL", trade["sl"], bt))
                    continue
                if high >= float(trade["tp"]):
                    trades.append(_close_row(trade, "TP", trade["tp"], bt))
                    continue
            else:
                if high >= float(trade["sl"]):
                    trades.append(_close_row(trade, "SL", trade["sl"], bt))
                    continue
                if low <= float(trade["tp"]):
                    trades.append(_close_row(trade, "TP", trade["tp"], bt))
                    continue
            still_open.append(trade)
        open_trades = still_open
        if not open_trades:
            state["side"] = None
            state["order_count"] = 0
            state["last_entry_price"] = None

        scan_m5 = bars[max(0, i - config.S12_LOOKBACK - 4):i + 1]
        if len(scan_m5) < config.S12_LOOKBACK:
            continue

        if open_trades:
            context = s12_get_swing_context(scan_m5, config.S12_LOOKBACK)
            if context:
                swing_high = context["pivot_swing_high"]
                swing_low = context["pivot_swing_low"]
                side = state["side"]
                if side == "BUY" and close > swing_high:
                    _close_all(open_trades, "S12_BREAKOUT_UP", close, bt, trades)
                    state.update({"side": None, "order_count": 0, "last_entry_price": None})
                    continue
                if side == "SELL" and close < swing_low:
                    _close_all(open_trades, "S12_BREAKOUT_DOWN", close, bt, trades)
                    state.update({"side": None, "order_count": 0, "last_entry_price": None})
                    continue
                if side == "SELL" and close <= swing_low + zone_dist:
                    _close_all(open_trades, "S12_FLIP_BUY", close, bt, trades)
                    state.update({"side": "BUY", "order_count": 0, "last_entry_price": None})
                elif side == "BUY" and close >= swing_high - zone_dist:
                    _close_all(open_trades, "S12_FLIP_SELL", close, bt, trades)
                    state.update({"side": "SELL", "order_count": 0, "last_entry_price": None})

        levels = s12_get_zone_levels(scan_m5, config.S12_LOOKBACK, zone_dist)
        if not levels:
            continue
        swing_high = levels["swing_high"]
        swing_low = levels["swing_low"]
        side = state["side"]
        count = int(state["order_count"] or 0)
        last_price = state["last_entry_price"]

        in_buy_zone = swing_low <= close <= swing_low + zone_dist
        in_sell_zone = swing_high - zone_dist <= close <= swing_high
        should_buy = in_buy_zone and (side is None or side == "BUY") and count < config.S12_ORDER_COUNT and (last_price is None or close < last_price)
        should_sell = in_sell_zone and (side is None or side == "SELL") and count < config.S12_ORDER_COUNT and (last_price is None or close > last_price)
        if not should_buy and not should_sell:
            continue

        direction = "BUY" if should_buy else "SELL"
        mb = int(getattr(config, "S12_MOMENTUM_BARS", 0) or 0)
        if mb > 0 and len(scan_m5) >= mb + 1:
            recent = scan_m5[-(mb + 1):-1]
            all_bull = all(float(r["close"]) > float(r["open"]) for r in recent)
            all_bear = all(float(r["close"]) < float(r["open"]) for r in recent)
            if direction == "SELL" and all_bull:
                continue
            if direction == "BUY" and all_bear:
                continue

        entry = round(close, 2)
        sl = round(entry - sl_dist, 2) if direction == "BUY" else round(entry + sl_dist, 2)
        tp_raw = s12_get_tp(_m15_slice(m15_bars, int(bar["time"])), direction)
        if tp_raw is not None and ((direction == "BUY" and float(tp_raw) > entry) or (direction == "SELL" and float(tp_raw) < entry)):
            tp = round(float(tp_raw), 2)
        else:
            tp = round(entry + sl_dist, 2) if direction == "BUY" else round(entry - sl_dist, 2)

        new_count = count + 1
        open_trades.append({
            "sid": 12,
            "tf": "M5",
            "signal": direction,
            "side": direction,
            "pattern": f"ท่าที่ 12 Range Trading {direction} #{new_count}",
            "entry": entry,
            "sl": sl,
            "tp": tp,
            "entry_time": bt,
            "entry_time_raw": int(bar["time"]),
            "close_type": "OPEN",
            "s12_count": new_count,
            "swing_high": round(float(swing_high), 2),
            "swing_low": round(float(swing_low), 2),
        })
        state["side"] = direction
        state["order_count"] = new_count
        state["last_entry_price"] = entry

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
