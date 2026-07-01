import config as _config

_last_trigger = {}

def strategy_20_8(rates, tf="M1", tf_name=None, config=None) -> dict:
    if config is None:
        config = _config
    
    """
    ท่าไม้ตายอออิน4วิ 2 (Small 2L/2H & Wick Rejection Sniper) S20.8
    เล่น TF เล็ก (M1-M30) จับโครงสร้าง 2L/2H ที่รายใหญ่กวาด Liquidity แบบไม่ทะลุฐานเดิม
    """
    if not getattr(config, "S20_8_ENABLED", False):
        return {"signal": "WAIT", "reason": "S20.8 disabled", "pattern": "S20.8", "sid": 20.8}
        
    if rates is None or len(rates) < 15:
        return {"signal": "WAIT", "reason": "Not enough rates", "pattern": "S20.8", "sid": 20.8}
        
    # กันยิงเบิ้ลในแท่งเดียวกัน (Race condition)
    current_time = int(rates[-1]["time"])
    last_trig = _last_trigger.get(tf_name, 0)
    if current_time == last_trig:
        return {"signal": "WAIT", "reason": "Already triggered in this candle", "pattern": "S20.8", "sid": 20.8}
        
    # เช็กระยะความผันผวนของ TF (ห้ามเข้าถ้าไส้วิ่งแรงเกิน 2000 จุด)
    for r in rates[-15:]:
        if (float(r["high"]) - float(r["low"])) > 20.00: 
            return {"signal": "WAIT", "reason": "High volatility > 2000 pts", "pattern": "S20.8", "sid": 20.8}
    
    current_bar = rates[-1]
    _open = float(current_bar["open"])
    _close = float(current_bar["close"])
    _high = float(current_bar["high"])
    _low = float(current_bar["low"])
    
    range_total = max(abs(_high - _low), 0.0001)
    body = abs(_close - _open)
    body_pct = body / range_total
    
    is_green = _close > _open
    is_red = _close < _open
    
    upper_wick = _high - max(_open, _close)
    lower_wick = min(_open, _close) - _low
    
    upper_wick_pct = upper_wick / range_total
    lower_wick_pct = lower_wick / range_total
    
    signal = "WAIT"
    entry = 0.0
    sl = 0.0
    tp = 0.0
    
    pt_mult = getattr(config, "S20_8_POINTS_MULTIPLIER", 0.01)
    
    # Calculate Dynamic ATR
    tr_list = []
    for i in range(1, min(15, len(rates))):
        c0 = rates[-i]
        c1 = rates[-(i+1)]
        hl = float(c0["high"]) - float(c0["low"])
        hc = abs(float(c0["high"]) - float(c1["close"]))
        lc = abs(float(c0["low"]) - float(c1["close"]))
        tr_list.append(max(hl, hc, lc))
    atr_price = sum(tr_list) / len(tr_list) if tr_list else range_total
    atr_pts = atr_price / pt_mult
    
    # 🔥 Dynamic Risk Management for Consistent 1:1.5 RR Growth
    # ปรับใช้ ATR เพื่อให้ยืดหยุ่นตามสภาวะตลาด
    buffer_pts = max(100.0, atr_pts * 0.3) 
    sl_pts = max(150.0, atr_pts * 1.0)
    tp_pts = sl_pts * 1.5 # RR 1:1.5

    # 🛡️ Institutional Momentum & Trend Filter
    prev_candle = rates[-2]
    prev_body = abs(float(prev_candle["close"]) - float(prev_candle["open"]))
    if prev_body > (atr_price * 1.5):
        return {"signal": "WAIT", "reason": "Institutional Displacement Block", "pattern": "S20.8", "sid": 20.8}
        
    sma50 = sum(float(r["close"]) for r in rates[-min(50, len(rates)):]) / min(50, len(rates))

    # ⚖️ Macro Premium / Discount Zone Filter (Lookback 120)
    lookback_120 = rates[-min(120, len(rates)):]
    highs_120 = [float(r["high"]) for r in lookback_120]
    lows_120 = [float(r["low"]) for r in lookback_120]
    max_120 = max(highs_120) if highs_120 else _high
    min_120 = min(lows_120) if lows_120 else _low
    mid_120 = (max_120 + min_120) / 2
    is_macro_discount = _close <= mid_120
    is_macro_premium = _close >= mid_120

    # 📊 RSI (14) Momentum Filter
    rsi_14 = 50.0
    if len(rates) >= 15:
        gains = []
        losses = []
        for i in range(-15, -1):
            change = float(rates[i+1]["close"]) - float(rates[i]["close"])
            if change > 0:
                gains.append(change)
                losses.append(0)
            else:
                gains.append(0)
                losses.append(abs(change))
        avg_gain = sum(gains) / 14
        avg_loss = sum(losses) / 14
        if avg_loss > 0:
            rs = avg_gain / avg_loss
            rsi_14 = 100.0 - (100.0 / (1.0 + rs))
        else:
            rsi_14 = 100.0 if avg_gain > 0 else 50.0

    # 🔬 เงื่อนไข 2L/2H Liquidity Sweep (กวาดสภาพคล่องระดับ 15 แท่ง)
    recent_lows = [float(r["low"]) for r in rates[-16:-1]]
    recent_highs = [float(r["high"]) for r in rates[-16:-1]]
    min_recent_low = min(recent_lows) if recent_lows else _low
    max_recent_high = max(recent_highs) if recent_highs else _high
    
    is_buy_sweep = (_low < min_recent_low) and (_close > min_recent_low)
    is_sell_sweep = (_high > max_recent_high) and (_close < max_recent_high)

    # 📈 Bollinger Bands (20, 2.0) Filter for Exhaustion Extremes
    sma20 = sum(float(r["close"]) for r in rates[-min(20, len(rates)):]) / min(20, len(rates))
    variance = sum((float(r["close"]) - sma20)**2 for r in rates[-min(20, len(rates)):]) / min(20, len(rates))
    stddev = variance ** 0.5
    lower_bb = sma20 - (2.0 * stddev)
    upper_bb = sma20 + (2.0 * stddev)
    
    pierced_lower_bb = _low < lower_bb
    pierced_upper_bb = _high > upper_bb

    # 🔬 เงื่อนไข Rejection & Sweep Confirmation (เข้มข้นขึ้นเพื่อเพิ่ม WR)
    valid_buy_rejection = (
        ((lower_wick_pct >= 0.45) or (is_green and body_pct >= 0.60 and lower_wick_pct >= 0.30)) 
        and (_close > sma50) 
        and is_buy_sweep
        and is_macro_discount
        and pierced_lower_bb
        and (rsi_14 < 55)
    )
    
    valid_sell_rejection = (
        ((upper_wick_pct >= 0.45) or (is_red and body_pct >= 0.60 and upper_wick_pct >= 0.30)) 
        and (_close < sma50) 
        and is_sell_sweep
        and is_macro_premium
        and pierced_upper_bb
        and (rsi_14 > 45)
    )
    
    signal_to_return = "WAIT"
    entry = 0.0
    sl = 0.0
    tp = 0.0
    
    if valid_buy_rejection:
        buy_sl = _low - (sl_pts * pt_mult)
        actual_risk = _close - buy_sl
        buy_tp = _close + (actual_risk * 1.0) # RR 1:1
        
        signal_to_return = "BUY"
        entry = _close
        sl = buy_sl
        tp = buy_tp

    elif valid_sell_rejection:
        sell_sl = _high + (sl_pts * pt_mult)
        actual_risk = sell_sl - _close
        sell_tp = _close - (actual_risk * 1.0) # RR 1:1
        
        signal_to_return = "SELL"
        entry = _close
        sl = sell_sl
        tp = sell_tp

    if signal_to_return != "WAIT":
        lot_multiplier = 1.0
        if getattr(config, "S20_8_COMPOUNDING_ENABLED", False):
            try:
                import mt5_worker as mt5
                acc = mt5.account_info()
                if acc is not None:
                    balance = acc.balance
                    risk_pct = getattr(config, "S20_8_RISK_PCT", 2.0)
                    max_lot = getattr(config, "S20_8_MAX_LOT", 50.0)
                    sl_dist = abs(entry - sl)
                    
                    if sl_dist > 0:
                        symbol_info = mt5.symbol_info(getattr(config, "SYMBOL", "XAUUSD"))
                        contract_size = symbol_info.trade_contract_size if symbol_info else 100.0
                        
                        risk_usd = balance * (risk_pct / 100.0)
                        calculated_lot = risk_usd / (sl_dist * contract_size)
                        target_lot = round(calculated_lot, 2)
                        target_lot = max(0.01, min(target_lot, max_lot))
                        
                        base_lot = config.get_volume()
                        if base_lot > 0:
                            lot_multiplier = target_lot / base_lot
            except Exception as e:
                pass

        _last_trigger[tf_name] = current_time
        return {
            "signal": signal_to_return,
            "entry": entry,
            "sl": sl,
            "tp": tp,
            "order_mode": "market",
            "pattern": f"S20.8 Small2L2H",
            "sid": 20.8,
            "quant_lot_multiplier": lot_multiplier
        }
        
    return {"signal": "WAIT", "reason": "S20.8 No valid small 2L/2H structure", "pattern": "S20.8", "sid": 20.8}
