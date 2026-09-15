import os
import pandas as pd
import MetaTrader5 as mt5
from datetime import datetime, timedelta, timezone

def generate_mt5_reports(df_trades, group_id, out_dir, symbol="XAUUSD.iux"):
    if df_trades.empty:
        return
        
    # We will search for S20.14{group_id} in MT5 comments
    target_comment_part = f"S20.14{group_id}"
    
    # 1. Determine the date range
    try:
        start_time_bkk = pd.to_datetime(df_trades['Time (BKK)'].min())
        end_time_bkk = pd.to_datetime(df_trades['Time (BKK)'].max()) + timedelta(days=2) # Pad end
    except:
        return
        
    import pytz
    bkk_tz = pytz.timezone("Asia/Bangkok")
    try:
        start_dt = bkk_tz.localize(start_time_bkk).astimezone(timezone.utc) - timedelta(days=5) # padding for old pending orders
        end_dt = bkk_tz.localize(end_time_bkk).astimezone(timezone.utc)
    except Exception as e:
        print(f"Timezone error: {e}")
        return

    # 2. Fetch MT5 Orders and Deals to find our group
    if not mt5.initialize():
        print("MT5 initialization failed in matcher")
        return
        
    orders = mt5.history_orders_get(start_dt, end_dt)
    deals = mt5.history_deals_get(start_dt, end_dt)
    mt5.shutdown() # shutdown after we fetch
    
    if not orders:
        orders = []
    if not deals:
        deals = []
        
    # Map deals by position_id to get profit and volume
    deal_profit_map = {}
    deal_volume_map = {}
    for d in deals:
        pid = d.position_id
        if pid:
            deal_profit_map[pid] = deal_profit_map.get(pid, 0.0) + d.profit
            if d.entry == 0: # DEAL_ENTRY_IN
                deal_volume_map[pid] = deal_volume_map.get(pid, 0.0) + d.volume
        
    mt5_entries = []
    # type: 0 = BUY, 1 = SELL (for deals/positions)
    # in orders: type 0=BUY, 1=SELL, 2=BUY_LIMIT, 3=SELL_LIMIT, etc
    for o in orders:
        if o.symbol != symbol: continue
        if target_comment_part not in (o.comment or ""): continue
        if o.state != 4: continue # ORDER_STATE_FILLED=4. We only care about filled orders. Wait, ORDER_STATE_FILLED is 4. Let's not filter by state strictly yet, just check if it's filled or position is opened. Actually, it's easier to use deals!
        
        # We need the entry time (BKK)
        # BKK is UTC+7
        o_time_bkk = datetime.fromtimestamp(o.time_setup, tz=timezone.utc).astimezone(bkk_tz)
        o_fill_time_bkk = datetime.fromtimestamp(o.time_done, tz=timezone.utc).astimezone(bkk_tz) if o.time_done else o_time_bkk
        
        sig_type = "BUY" if o.type in (0, 2, 4) else "SELL"
        
        mt5_entries.append({
            "mt5_ticket": o.ticket,
            "mt5_time": o_fill_time_bkk,
            "mt5_type": sig_type,
            "mt5_entry": o.price_open, # For limits, price_open is requested. For markets, it's price.
            "mt5_sl": o.sl,
            "mt5_tp": o.tp,
            "comment": o.comment,
            "position_id": o.position_id,
            "matched": False
        })
        
    # 3. Match df_trades against mt5_entries
    match_rows = []
    bt_unmatched = []
    
    for i, bt in df_trades.iterrows():
        try:
            bt_time = pd.to_datetime(bt['Time (BKK)'])
        except:
            continue
            
        bt_type = str(bt['Type']).upper()
        
        # Find best MT5 match (same type, time within 48 hours)
        best_match = None
        min_diff = timedelta(hours=48)
        
        for mt in mt5_entries:
            if mt['matched']: continue
            if mt['mt5_type'] != bt_type: continue
            
            diff = abs(mt['mt5_time'].replace(tzinfo=None) - bt_time)
            # Match only if the entry price is close enough (since limits fill exactly, and markets fill closely)
            price_diff = abs(mt['mt5_entry'] - float(bt['Entry']))
            
            if diff <= min_diff and (price_diff < 50.0 or mt['mt5_entry'] == 0.0):
                best_match = mt
                min_diff = diff
                
        if best_match:
            best_match['matched'] = True
            row = bt.to_dict()
            row['MT5_Ticket'] = best_match['mt5_ticket']
            row['MT5_Time'] = best_match['mt5_time'].strftime("%Y-%m-%d %H:%M")
            row['MT5_Entry'] = best_match['mt5_entry']
            row['MT5_Comment'] = best_match['comment']
            match_rows.append(row)
        else:
            bt_unmatched.append(bt.to_dict())
            
    # MT5 unmatched
    mt5_unmatched = [m for m in mt5_entries if not m['matched']]
    
    # 4. Save files
    os.makedirs(out_dir, exist_ok=True)
    
    if match_rows:
        pd.DataFrame(match_rows).to_csv(os.path.join(out_dir, "match_order.csv"), index=False)
        print(f"Saved: match_order.csv ({len(match_rows)} matched rows)")
    else:
        pd.DataFrame(columns=list(df_trades.columns) + ['MT5_Ticket', 'MT5_Time', 'MT5_Entry', 'MT5_Comment']).to_csv(os.path.join(out_dir, "match_order.csv"), index=False)
        
    if bt_unmatched:
        pd.DataFrame(bt_unmatched).to_csv(os.path.join(out_dir, "backtest_not_match.csv"), index=False)
        print(f"Saved: backtest_not_match.csv ({len(bt_unmatched)} rows)")
    else:
        pd.DataFrame(columns=df_trades.columns).to_csv(os.path.join(out_dir, "backtest_not_match.csv"), index=False)
        
    if mt5_unmatched:
        mt5_df = pd.DataFrame(mt5_unmatched)
        mt5_df['mt5_time'] = mt5_df['mt5_time'].apply(lambda x: x.strftime("%Y-%m-%d %H:%M") if pd.notnull(x) else "")
        mt5_df.drop(columns=['matched'], inplace=True)
        mt5_df.to_csv(os.path.join(out_dir, "mt5_not_match.csv"), index=False)
        print(f"Saved: mt5_not_match.csv ({len(mt5_unmatched)} rows)")
    else:
        pd.DataFrame(columns=['mt5_ticket', 'mt5_time', 'mt5_type', 'mt5_entry', 'mt5_sl', 'mt5_tp', 'comment']).to_csv(os.path.join(out_dir, "mt5_not_match.csv"), index=False)

    # Legacy file for dashboard compatibility (populate with all fetched MT5 orders)
    mt5_real_data = []
    for m in mt5_entries:
        pid = m['position_id']
        profit = deal_profit_map.get(pid, 0.0) if pid else 0.0
        volume = deal_volume_map.get(pid, 0.0) if pid else 0.0
        
        mt5_real_data.append({
            'Time': m['mt5_time'].strftime("%Y-%m-%d %H:%M") if pd.notnull(m['mt5_time']) else "",
            'Ticket': m['mt5_ticket'],
            'Type': m['mt5_type'],
            'Volume': volume,
            'Price': m['mt5_entry'],
            'S / L': m['mt5_sl'] if 'mt5_sl' in m else 0.0,
            'T / P': m['mt5_tp'] if 'mt5_tp' in m else 0.0,
            'Profit': profit
        })
    pd.DataFrame(mt5_real_data, columns=['Time', 'Ticket', 'Type', 'Volume', 'Price', 'S / L', 'T / P', 'Profit']).to_csv(os.path.join(out_dir, "mt5_real.csv"), index=False)
    print("Saved: mt5_real.csv")
