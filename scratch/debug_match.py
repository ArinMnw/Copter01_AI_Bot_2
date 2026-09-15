import pandas as pd
import MetaTrader5 as mt5
from datetime import datetime, timedelta, timezone
import pytz

df_trades = pd.read_csv('d:/Project/Copter01_AI_Bot_2/strategy/s20.14.1/excel_group9/trades.csv')
mt5.initialize()
bkk_tz = pytz.timezone('Asia/Bangkok')
start_dt = datetime.now(timezone.utc) - timedelta(days=5)
end_dt = datetime.now(timezone.utc)
orders = mt5.history_orders_get(start_dt, end_dt)

mt5_entries = []
for o in orders:
    if 'S20.149' not in (o.comment or ""): continue
    o_time_bkk = datetime.fromtimestamp(o.time_setup, tz=timezone.utc).astimezone(bkk_tz)
    o_fill_time_bkk = datetime.fromtimestamp(o.time_done, tz=timezone.utc).astimezone(bkk_tz) if o.time_done else o_time_bkk
    sig_type = "BUY" if o.type in (0, 2, 4) else "SELL"
    mt5_entries.append({
        "mt5_ticket": o.ticket,
        "mt5_time": o_fill_time_bkk,
        "mt5_type": sig_type,
        "mt5_entry": o.price_open,
        "comment": o.comment,
        "matched": False
    })

for i, bt in df_trades.iterrows():
    try:
        bt_time = pd.to_datetime(bt['Time (BKK)'])
    except:
        continue
    bt_type = str(bt['Type']).upper()
    best_match = None
    min_diff = timedelta(hours=48)
    
    for mt in mt5_entries:
        if mt['matched']: continue
        if mt['mt5_type'] != bt_type: continue
        diff = abs(mt['mt5_time'].replace(tzinfo=None) - bt_time)
        price_diff = abs(mt['mt5_entry'] - float(bt['Entry']))
        
        if diff <= min_diff:
            print(f"Candidate for {bt_time}: MT5 {mt['mt5_time']} diff {diff} price diff {price_diff}")
            if price_diff < 10.0:
                best_match = mt
                min_diff = diff
    
    if best_match:
        best_match['matched'] = True
        print(f"MATCHED: BT {bt_time} -> MT5 {best_match['mt5_time']}")

mt5_unmatched = [m for m in mt5_entries if not m['matched']]
print(f"MT5 Unmatched: {len(mt5_unmatched)}")
