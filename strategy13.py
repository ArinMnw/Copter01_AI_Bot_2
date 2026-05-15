import config


def _true_range(cur, prev_close: float) -> float:
    high = float(cur["high"])
    low = float(cur["low"])
    return max(high - low, abs(high - prev_close), abs(low - prev_close))


def _atr_values(rates, period: int):
    n = len(rates)
    if n == 0:
        return []
    period = max(1, int(period))
    atr = [None] * n
    if n < period + 1:
        return atr

    trs = [0.0] * n
    for i in range(1, n):
        trs[i] = _true_range(rates[i], float(rates[i - 1]["close"]))

    seed = sum(trs[1:period + 1]) / period
    atr[period] = seed
    prev_atr = seed
    for i in range(period + 1, n):
        prev_atr = ((prev_atr * (period - 1)) + trs[i]) / period
        atr[i] = prev_atr
    return atr


def _supertrend_series(rates, factor: float, atr_len: int):
    n = len(rates)
    atr = _atr_values(rates, atr_len)
    supertrend = [None] * n
    direction = [None] * n
    upper_band = [None] * n
    lower_band = [None] * n

    for i in range(n):
        a = atr[i]
        if a is None:
            continue

        close_i = float(rates[i]["close"])
        upper = close_i + factor * a
        lower = close_i - factor * a

        if i > 0 and lower_band[i - 1] is not None:
            prev_lower = lower_band[i - 1]
            prev_upper = upper_band[i - 1]
            prev_close = float(rates[i - 1]["close"])
            lower = lower if (lower > prev_lower or prev_close < prev_lower) else prev_lower
            upper = upper if (upper < prev_upper or prev_close > prev_upper) else prev_upper

        lower_band[i] = lower
        upper_band[i] = upper

        if i == 0 or atr[i - 1] is None or supertrend[i - 1] is None:
            direction[i] = 1
        elif supertrend[i - 1] == upper_band[i - 1]:
            direction[i] = -1 if close_i > upper else 1
        else:
            direction[i] = 1 if close_i < lower else -1

        supertrend[i] = lower if direction[i] == -1 else upper

    return supertrend, direction


def _crossover(prev_a: float, prev_b: float, cur_a: float, cur_b: float) -> bool:
    return prev_a <= prev_b and cur_a > cur_b


def _crossunder(prev_a: float, prev_b: float, cur_a: float, cur_b: float) -> bool:
    return prev_a >= prev_b and cur_a < cur_b


def strategy_13(rates):
    """EzAlgo V5 core signal with market entry and 3 TP levels."""
    if rates is None or len(rates) < 40:
        return {"signal": "WAIT", "reason": "S13 data not enough"}

    closed = rates[:-1]
    if len(closed) < 30:
        return {"signal": "WAIT", "reason": "S13 closed bars not enough"}

    factor = float(getattr(config, "S13_SENSITIVITY", 2.0) or 2.0)
    st_atr_len = max(1, int(getattr(config, "S13_SUPERTREND_ATR", 11) or 11))
    stop_atr_len = max(1, int(getattr(config, "S13_STOP_ATR_LEN", 14) or 14))
    stop_atr_mult = float(getattr(config, "S13_STOP_ATR_MULT", 4.0) or 4.0)

    st, _ = _supertrend_series(closed, factor, st_atr_len)
    if len(st) < 2 or st[-1] is None or st[-2] is None:
        return {"signal": "WAIT", "reason": "S13 supertrend not ready"}

    stop_atr = _atr_values(closed, stop_atr_len)
    atr_stop = stop_atr[-1]
    if atr_stop is None:
        return {"signal": "WAIT", "reason": "S13 stop ATR not ready"}

    prev_close = float(closed[-2]["close"])
    cur_close = float(closed[-1]["close"])
    prev_st = float(st[-2])
    cur_st = float(st[-1])

    bull = _crossover(prev_close, prev_st, cur_close, cur_st)
    bear = _crossunder(prev_close, prev_st, cur_close, cur_st)
    if not bull and not bear:
        return {"signal": "WAIT", "reason": "No EzAlgo signal"}

    signal_bar = closed[-1]
    o = float(signal_bar["open"])
    h = float(signal_bar["high"])
    l = float(signal_bar["low"])
    c = float(signal_bar["close"])
    entry = round(c, 2)

    tp_rrs = [
        float(getattr(config, "S13_TP1_RR", 0.7) or 0.7),
        float(getattr(config, "S13_TP2_RR", 1.2) or 1.2),
        float(getattr(config, "S13_TP3_RR", 1.5) or 1.5),
    ]

    candles = [
        {"open": float(closed[-3]["open"]), "high": float(closed[-3]["high"]), "low": float(closed[-3]["low"]), "close": float(closed[-3]["close"])} ,
        {"open": float(closed[-2]["open"]), "high": float(closed[-2]["high"]), "low": float(closed[-2]["low"]), "close": float(closed[-2]["close"])} ,
        {"open": o, "high": h, "low": l, "close": c},
    ]

    if bull:
        sl = round(l - (atr_stop * stop_atr_mult), 2)
        risk = entry - sl
        if risk <= 0:
            return {"signal": "WAIT", "reason": "S13 BUY invalid risk"}
        tp_levels = [round(entry + (risk * rr), 2) for rr in tp_rrs]
        return {
            "signal": "BUY",
            "pattern": "S13 EzAlgo V5 BUY",
            "entry": entry,
            "sl": sl,
            "tp": tp_levels[0],
            "tp_levels": tp_levels,
            "order_mode": "market",
            "entry_label": "Market at",
            "reason": (
                f"Supertrend cross up | Close:{c:.2f} > ST:{cur_st:.2f}\n"
                f"Sensitivity:{factor:g} ATR(ST):{st_atr_len} StopATR:{stop_atr_len}x{stop_atr_mult:g}\n"
                f"Signal bar O:{o:.2f} H:{h:.2f} L:{l:.2f} C:{c:.2f}\n"
                f"Entry:{entry:.2f} SL:{sl:.2f} TP1:{tp_levels[0]:.2f} TP2:{tp_levels[1]:.2f} TP3:{tp_levels[2]:.2f}"
            ),
            "candles": candles,
        }

    sl = round(h + (atr_stop * stop_atr_mult), 2)
    risk = sl - entry
    if risk <= 0:
        return {"signal": "WAIT", "reason": "S13 SELL invalid risk"}
    tp_levels = [round(entry - (risk * rr), 2) for rr in tp_rrs]
    return {
        "signal": "SELL",
        "pattern": "S13 EzAlgo V5 SELL",
        "entry": entry,
        "sl": sl,
        "tp": tp_levels[0],
        "tp_levels": tp_levels,
        "order_mode": "market",
        "entry_label": "Market at",
        "reason": (
            f"Supertrend cross down | Close:{c:.2f} < ST:{cur_st:.2f}\n"
            f"Sensitivity:{factor:g} ATR(ST):{st_atr_len} StopATR:{stop_atr_len}x{stop_atr_mult:g}\n"
            f"Signal bar O:{o:.2f} H:{h:.2f} L:{l:.2f} C:{c:.2f}\n"
            f"Entry:{entry:.2f} SL:{sl:.2f} TP1:{tp_levels[0]:.2f} TP2:{tp_levels[1]:.2f} TP3:{tp_levels[2]:.2f}"
        ),
        "candles": candles,
    }
