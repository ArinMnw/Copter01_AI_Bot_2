import MetaTrader5 as mt5
import pandas as pd
import datetime
import re

mt5.initialize()
BKK = datetime.timezone(datetime.timedelta(hours=7))

def get_swing(dt_bkk, tf, is_buy, lookback_days, fetch_tf):
    start = dt_bkk - datetime.timedelta(days=lookback_days)
    end = dt_bkk
    rates = mt5.copy_rates_range('XAUUSD.iux', fetch_tf, 
                                  start.astimezone(datetime.timezone.utc), 
                                  end.astimezone(datetime.timezone.utc))
    if rates is None or len(rates) == 0: return None
    df = pd.DataFrame(rates)
    if is_buy:
        # TP for Buy = Max High of chunk
        return df['high'].max()
    else:
        # TP for Sell = Min Low of chunk
        return df['low'].min()

# Load 36 specs
with open('../../../docs/allin4s/Full Trading/36_order_spec.md', 'r', encoding='utf-8-sig') as f:
    lines = f.readlines()

print(f"{'Order':>5} | {'Pattern':<25} | {'Type':<4} | {'Entry':>7} | {'Spec SL':>7} | {'Calc SL':>7} | {'SL Diff':>7} | {'Spec TP':>7} | {'Calc TP':>7} | {'TP Diff':>7}")
print("-" * 105)

for line in lines:
    line = line.strip()
    if not line or not line[0].isdigit(): continue
    parts = [p.strip() for p in line.split('|')]
    if len(parts) < 5: continue
    
    num_desc = parts[0]
    m = re.match(r'^(\d+)\.\s*(.*)', num_desc)
    if not m: continue
    order_num = int(m.group(1))
    pattern = m.group(2).strip()
    
    date_str = parts[1].strip()
    type_entry = parts[2].strip().split(' ')
    type_str = type_entry[0].upper()
    entry = float(type_entry[1])
    
    sl = float(parts[3].replace('SL ', '').strip())
    tp = float(parts[4].replace('TP ', '').strip())
    
    dt = datetime.datetime.strptime(date_str, '%d-%m-%Y %H:%M')
    dt_bkk = dt.replace(tzinfo=BKK)
    
    is_buy = type_str == 'BUY'
    
    # Calculate SL (H4 Swing 3 days back)
    calc_sl = get_swing(dt_bkk, None, not is_buy, 3, mt5.TIMEFRAME_H4)
    # Calculate TP (D1 Swing 30 days back)
    calc_tp = get_swing(dt_bkk, None, is_buy, 30, mt5.TIMEFRAME_D1)
    
    if calc_sl is None: calc_sl = 0
    if calc_tp is None: calc_tp = 0
    
    sl_diff = abs(calc_sl - sl)
    tp_diff = abs(calc_tp - tp)
    
    print(f"{order_num:>5} | {pattern[:25]:<25} | {type_str:<4} | {entry:>7.1f} | {sl:>7.1f} | {calc_sl:>7.1f} | {sl_diff:>7.1f} | {tp:>7.1f} | {calc_tp:>7.1f} | {tp_diff:>7.1f}")

mt5.shutdown()
