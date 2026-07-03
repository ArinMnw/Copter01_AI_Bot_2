"""
strategy87.py - S87 HTF D1/H12 closed-bar bias filter.

RESEARCH/BACKTEST-ONLY. Not wired into the live bot.

The filter converts completed D1/H12 candle behavior into a directional bias.
It is designed to validate raw intraday generators such as S86 without using
any unfinished higher-timeframe bar.
"""

import bisect


TF_SECONDS = {
    "H12": 12 * 60 * 60,
    "D1": 24 * 60 * 60,
}


def _bar_color(bar):
    o = float(bar["open"])
    c = float(bar["close"])
    if c > o:
        return "UP"
    if c < o:
        return "DOWN"
    return "FLAT"


def build_closed_series(bars, tf_name):
    """Return bars indexed by their close time, not open time."""
    seconds = TF_SECONDS[tf_name]
    close_times = [int(b["time"]) + seconds for b in bars]
    colors = [_bar_color(b) for b in bars]
    return {
        "tf": tf_name,
        "close_times": close_times,
        "bars": bars,
        "colors": colors,
    }


def _last_closed(series, ts, offset=0):
    idx = bisect.bisect_right(series["close_times"], int(ts)) - 1 - offset
    if idx < 0:
        return None
    return {
        "idx": idx,
        "bar": series["bars"][idx],
        "color": series["colors"][idx],
        "close_time": series["close_times"][idx],
    }


def bias_at(ts, d1_series, h12_series, mode):
    """Return BUY/SELL/NEUTRAL using only HTF bars fully closed by ts."""
    d1 = _last_closed(d1_series, ts, 0)
    h0 = _last_closed(h12_series, ts, 0)
    h1 = _last_closed(h12_series, ts, 1)
    if d1 is None or h0 is None:
        return "NEUTRAL"

    d1_color = d1["color"]
    h0_color = h0["color"]
    h1_color = h1["color"] if h1 else "FLAT"

    if mode == "D1_LAST":
        return "BUY" if d1_color == "UP" else "SELL" if d1_color == "DOWN" else "NEUTRAL"
    if mode == "H12_LAST":
        return "BUY" if h0_color == "UP" else "SELL" if h0_color == "DOWN" else "NEUTRAL"
    if mode == "D1_AND_H12":
        if d1_color == "UP" and h0_color == "UP":
            return "BUY"
        if d1_color == "DOWN" and h0_color == "DOWN":
            return "SELL"
        return "NEUTRAL"
    if mode == "H12_TURN":
        if h1_color == "DOWN" and h0_color == "UP":
            return "BUY"
        if h1_color == "UP" and h0_color == "DOWN":
            return "SELL"
        return "NEUTRAL"
    if mode == "D1_H12_TURN":
        if d1_color == "DOWN" and h1_color == "DOWN" and h0_color == "UP":
            return "BUY"
        if d1_color == "UP" and h1_color == "UP" and h0_color == "DOWN":
            return "SELL"
        return "NEUTRAL"
    if mode == "D1_OR_H12_TURN":
        turn = bias_at(ts, d1_series, h12_series, "H12_TURN")
        if turn != "NEUTRAL":
            return turn
        return bias_at(ts, d1_series, h12_series, "D1_LAST")
    if mode == "D1_THEN_H12_REVERSAL":
        if d1_color == "DOWN" and h0_color == "UP":
            return "BUY"
        if d1_color == "UP" and h0_color == "DOWN":
            return "SELL"
        return "NEUTRAL"
    raise ValueError(f"unknown S87 mode: {mode}")


def filter_trades(raw_trades, d1_series, h12_series, mode, relation="follow"):
    kept = []
    for t in raw_trades:
        bias = bias_at(int(t["fill_time_ts"]), d1_series, h12_series, mode)
        sig = t.get("signal")
        if relation == "follow":
            ok = bias == sig
        elif relation == "inverse":
            ok = (bias == "BUY" and sig == "SELL") or (bias == "SELL" and sig == "BUY")
        elif relation == "exclude_neutral":
            ok = bias != "NEUTRAL"
        else:
            raise ValueError(f"unknown relation: {relation}")
        if ok:
            x = dict(t)
            x["s87_bias"] = bias
            x["s87_mode"] = mode
            x["s87_relation"] = relation
            kept.append(x)
    return kept
