with open('trailing.py', 'a', encoding='utf-8') as f:
    f.write('''
async def check_momentum_stall_exit(app):
    """
    Phase 4: Momentum Stall Exit (ล็อกกำไรเมื่อกราฟหมดแรง).
    ถ้าราคาพุ่งไปในทิศทางกำไร (In Profit) เกิน X จุด แต่เกิดอาการยึกยัก
    ไม่สามารถทำ High/Low ใหม่ได้ติดต่อกันเกิน 5 แท่ง (M15) บอทจะปิดเก็บกำไรทันที
    """
    import mt5_worker as mt5
    import pandas as pd
    import config
    from bot_log import log_event
    from notifications import tg
    
    if not getattr(config, "MOMENTUM_STALL_EXIT_ENABLED", True):
        return
        
    positions = mt5.positions_get(symbol=config.SYMBOL)
    if not positions:
        return
        
    rates = mt5.copy_rates_from_pos(config.SYMBOL, mt5.TIMEFRAME_M15, 0, 10)
    if rates is None or len(rates) < 5:
        return
        
    df = pd.DataFrame(rates)
    
    # 5 แท่งล่าสุดไม่รวมแท่งปัจจุบันที่ยังไม่จบ (หรือรวมก็ได้)
    recent_highs = df['high'].iloc[-6:-1]
    recent_lows = df['low'].iloc[-6:-1]
    
    for pos in positions:
        ticket = pos.ticket
        is_buy = pos.type == mt5.ORDER_TYPE_BUY
        pos_type = "BUY" if is_buy else "SELL"
        
        # ต้องอยู่ในสถานะกำไรเกิน 150 จุด ถึงจะพิจารณา (ป้องกันการปิดตอนยังไม่ได้อะไร)
        # คูณ 10**5 สำหรับคู่เงินที่มี 5 ทศนิยม หรือใช้ _get_point_multiplier
        mult = 100000 if "USD" in config.SYMBOL or "EUR" in config.SYMBOL or "GBP" in config.SYMBOL else 1000
        if config.SYMBOL == "XAUUSD":
            mult = 100
            
        profit_points = (pos.price_current - pos.price_open) * mult
        if not is_buy:
            profit_points = -profit_points
            
        if profit_points < 150:
            continue
            
        should_close = False
        reason = ""
        
        if is_buy:
            # ถ้าเป็น BUY และราคาเริ่มสร้าง Lower High 3 แท่งติด
            last_3_highs = list(recent_highs.iloc[-3:])
            if last_3_highs[0] >= last_3_highs[1] >= last_3_highs[2]:
                should_close = True
                reason = "กราฟหมดแรง (สร้าง Lower High 3 แท่งติดขณะมีกำไร)"
        else:
            # ถ้าเป็น SELL
            last_3_lows = list(recent_lows.iloc[-3:])
            if last_3_lows[0] <= last_3_lows[1] <= last_3_lows[2]:
                should_close = True
                reason = "กราฟหมดแรง (สร้าง Higher Low 3 แท่งติดขณะมีกำไร)"
                
        if should_close:
            ok, cp = _close_position(pos, pos_type, "Momentum Stall Exit")
            if ok:
                log_event("MOMENTUM_STALL", f"Closed {pos_type} {ticket} due to {reason} at profit {profit_points:.0f} pts", ticket=ticket)
                await tg(app, f"🛑 *Momentum Stall Exit (หนีทำกำไร)*\\nTicket: `{ticket}` ({pos_type})\\nเหตุผล: {reason}\\nเก็บกำไรเข้ากระเป๋าเรียบร้อย 💸")
''')
