import pandas as pd
import datetime

# Load trades.csv
trades_df = pd.read_csv('../excel/trades.csv', encoding='utf-8-sig')

# Load 36 specs
with open('../../../docs/allin4s/Full Trading/36_order_spec.md', 'r', encoding='utf-8-sig') as f:
    lines = f.readlines()

print(f"{'Order':>5} | {'Pattern':<20} | {'Spec Risk':>9} | {'Bot Risk':>9} | {'Spec TP':>7} | {'Bot TP':>7} | {'TP Diff':>7}")
print("-" * 90)

for line in lines:
    line = line.strip()
    if not line or not line[0].isdigit(): continue
    parts = [p.strip() for p in line.split('|')]
    if len(parts) < 5: continue
    
    num_desc = parts[0]
    import re
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
    target_dt_str = dt.strftime('%Y-%m-%d %H:%M')
    
    # Find matching trade in trades.csv
    # We match by Time (BKK) and Type
    # Note: Sometimes time might be off by 1-2 hours, so we allow a small window
    target_dt = pd.to_datetime(target_dt_str)
    
    trades_df['time_dt'] = pd.to_datetime(trades_df['Time (BKK)'])
    
    # Extract root pattern (e.g., 'Naiya' from 'นัยยะ 1H')
    root_pattern = ""
    if 'นัยยะ' in pattern or 'Naiya' in pattern: root_pattern = 'Naiya'
    elif 'Fibo' in pattern: root_pattern = 'Fibo'
    elif 'FVG' in pattern: root_pattern = 'FVG'
    elif 'ATR' in pattern: root_pattern = 'ATR'
    
    mask = (trades_df['Type'] == type_str) & \
           (trades_df['time_dt'] >= target_dt - datetime.timedelta(hours=4)) & \
           (trades_df['time_dt'] <= target_dt + datetime.timedelta(hours=4))
           
    matches = trades_df[mask]
    
    # Filter by root pattern if possible
    if root_pattern:
        pattern_matches = matches[matches['Pattern'].str.contains(root_pattern, na=False)]
        if len(pattern_matches) > 0:
            matches = pattern_matches
    
    if len(matches) > 0:
        # Find the one with closest entry price
        matches = matches.copy()
        matches['price_diff'] = abs(matches['Entry'] - entry)
        best_match = matches.sort_values('price_diff').iloc[0]
        
        bot_entry = best_match['Entry']
        bot_sl = best_match['SL']
        bot_tp = best_match['TP']
        bot_atr = best_match['ATR']
        
        atr1_sl = entry - bot_atr if type_str == 'BUY' else entry + bot_atr
        atr15_sl = entry - bot_atr * 1.5 if type_str == 'BUY' else entry + bot_atr * 1.5
        atr05_sl = entry - bot_atr * 0.5 if type_str == 'BUY' else entry + bot_atr * 0.5
        
        spec_risk = entry - sl if type_str == 'BUY' else sl - entry
        bot_risk = bot_entry - bot_sl if type_str == 'BUY' else bot_sl - bot_entry
        
        tp_diff = abs(bot_tp - tp)
        print(f"{order_num:>5} | {pattern[:20]:<20} | {spec_risk:>9.2f} | {bot_risk:>9.2f} | {tp:>7.1f} | {bot_tp:>7.1f} | {tp_diff:>7.1f}")
    else:
        print(f"{order_num:>5} | {pattern[:20]:<20} | {'N/A':>9} | {'N/A':>9} | {tp:>7.1f} | {'N/A':>7} | {'N/A':>7}")

