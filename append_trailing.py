with open('trailing.py', 'a', encoding='utf-8') as f:
    f.write('''
async def check_smart_cutloss(app):
    """
    Phase 4: Smart Cut-loss (Dynamic Cut-loss).
    If price aggressively crosses Fast EMA (e.g., EMA 20 or 50) against the position,
    cut loss early to preserve capital before hitting the static SL.
    """
    import mt5_worker as mt5
    import pandas as pd
    import numpy as np
    import config
    from bot_log import log_event
    from notifications import tg
    
    if not getattr(config, "SMART_CUTLOSS_ENABLED", True):
        return
        
    positions = mt5.positions_get(symbol=config.SYMBOL)
    if not positions:
        return
        
    rates = mt5.copy_rates_from_pos(config.SYMBOL, mt5.TIMEFRAME_M15, 0, 60)
    if rates is None or len(rates) < 50:
        return
        
    df = pd.DataFrame(rates)
    df['ema20'] = df['close'].ewm(span=20, adjust=False).mean()
    df['ema50'] = df['close'].ewm(span=50, adjust=False).mean()
    
    current_price = df['close'].iloc[-1]
    ema20 = df['ema20'].iloc[-1]
    ema50 = df['ema50'].iloc[-1]
    
    for pos in positions:
        ticket = pos.ticket
        is_buy = pos.type == mt5.ORDER_TYPE_BUY
        pos_type = "BUY" if is_buy else "SELL"
        
        # Condition: If we are long, but price drops significantly below EMA 50
        # and EMA 20 crosses below EMA 50 (strong momentum shift against us)
        should_cut = False
        reason = ""
        
        if is_buy:
            if current_price < ema50 and ema20 < ema50:
                should_cut = True
                reason = "ราคาหลุด EMA50 และเกิด Death Cross (Momentum Reversal)"
        else:
            if current_price > ema50 and ema20 > ema50:
                should_cut = True
                reason = "ราคาทะลุ EMA50 และเกิด Golden Cross (Momentum Reversal)"
                
        if should_cut:
            ok, cp = _close_position(pos, pos_type, "Smart Cut-loss (EMA)")
            if ok:
                log_event("SMART_CUTLOSS", f"Closed {pos_type} {ticket} due to {reason}", ticket=ticket)
                await tg(app, f"🛡️ *Smart Cut-loss ทำงาน*\nTicket: `{ticket}` ({pos_type})\nเหตุผล: {reason}\nเพื่อรักษาทุนก่อนชน SL")


async def check_atr_trailing(app):
    """
    Phase 4: ATR Trailing Stop (Dynamic Take-profit / Trailing).
    Moves the SL to follow the price dynamically based on ATR.
    """
    import mt5_worker as mt5
    import pandas as pd
    import numpy as np
    import config
    from bot_log import log_event
    
    if not getattr(config, "ATR_TRAILING_ENABLED", True):
        return
        
    positions = mt5.positions_get(symbol=config.SYMBOL)
    if not positions:
        return
        
    rates = mt5.copy_rates_from_pos(config.SYMBOL, mt5.TIMEFRAME_M15, 0, 50)
    if rates is None or len(rates) < 20:
        return
        
    df = pd.DataFrame(rates)
    high_low = df['high'] - df['low']
    high_close = np.abs(df['high'] - df['close'].shift())
    low_close = np.abs(df['low'] - df['close'].shift())
    true_range = np.max(pd.concat([high_low, high_close, low_close], axis=1), axis=1)
    df['atr'] = true_range.rolling(14).mean()
    df.bfill(inplace=True)
    
    atr_val = df['atr'].iloc[-1]
    multiplier = getattr(config, "ATR_TRAILING_MULT", 2.0)
    trail_dist = atr_val * multiplier
    
    for pos in positions:
        ticket = pos.ticket
        is_buy = pos.type == mt5.ORDER_TYPE_BUY
        pos_type = "BUY" if is_buy else "SELL"
        current_price = _get_current_price(pos_type)
        current_sl = pos.sl
        
        new_sl = current_sl
        
        if is_buy:
            proposed_sl = current_price - trail_dist
            if proposed_sl > current_sl and proposed_sl > pos.price_open:
                new_sl = proposed_sl
        else:
            proposed_sl = current_price + trail_dist
            if proposed_sl < current_sl and (current_sl == 0.0 or proposed_sl < pos.price_open):
                new_sl = proposed_sl
                
        if new_sl != current_sl and _price_differs(new_sl, current_sl):
            if _modify_sl(pos, new_sl):
                log_event("ATR_TRAILING", f"Ticket {ticket} updated SL to {new_sl:.2f} (ATR dist {trail_dist:.2f})", ticket=ticket)

''')
