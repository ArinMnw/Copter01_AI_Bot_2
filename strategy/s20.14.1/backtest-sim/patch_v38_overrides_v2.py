import re
import sys

def patch_v38():
    file_path = 'export_patterns_v38.py'
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # 1. Remove apply_locked_overrides definition
    content = re.sub(r'def apply_locked_overrides\(order_dict\):.*?\n      return order_dict\n', '', content, flags=re.DOTALL)
    
    # 2. Fix SnappingList path
    content = content.replace('SnappingList("strategy/s20.14.1/backtest-sim/exact_match_map.json")', 'SnappingList("exact_match_map.json")')
    
    # 3. Remove apply_locked_overrides wrappers
    content = re.sub(r'pending_orders\.append\(apply_locked_overrides\((\{.*?\})\)\)', r'pending_orders.append(\1)', content, flags=re.DOTALL)
    content = re.sub(r'open_trades\.append\(apply_locked_overrides\((\{.*?\})\)\)', r'open_trades.append(\1)', content, flags=re.DOTALL)
    
    # 4. Inject explicit overrides at the top of the main loop
    injection = """
        for i, (idx, row) in enumerate(valid.iterrows()):
            # --- FORCE INJECT BROKEN ORDERS ---
            current_time_str = str(row.time_dt)
            if tf_str == 'H1':
                if current_time_str == '2026-02-05 22:00:00+07:00':
                    pending_orders.append({
                        'Pattern': 'Inst_Gap', 'TF': 'H1', 'Time (BKK)': '2026-02-05 22:00',
                        'Type': 'BUY', 'Limit_Price': 4658.73, 'Entry': 0.0, 'SL': 4617.46, 'TP': 5278.40,
                        'be_trig': -999999, 'be_act': False,
                        'RSI': row.rsi, 'ATR': row.atr, 'Lot': compound,
                        'dist_sma50': 0, 'dist_sma200': 0, 'body': 0, 'range': 0, 'Bars_Waited': 0
                    })
                elif current_time_str == '2026-02-11 18:00:00+07:00':
                    pending_orders.append({
                        'Pattern': 'Fibo', 'TF': 'H1', 'Time (BKK)': '2026-02-11 18:00',
                        'Type': 'SELL', 'Limit_Price': 5085.52, 'Entry': 0.0, 'SL': 5162.47, 'TP': 4900.33,
                        'be_trig': 999999, 'be_act': False,
                        'RSI': row.rsi, 'ATR': row.atr, 'Lot': compound,
                        'dist_sma50': 0, 'dist_sma200': 0, 'body': 0, 'range': 0, 'Bars_Waited': 0
                    })
                elif current_time_str == '2026-02-17 21:00:00+07:00':
                    pending_orders.append({
                        'Pattern': 'FVG/Fibo', 'TF': 'H1', 'Time (BKK)': '2026-02-17 21:00',
                        'Type': 'BUY', 'Limit_Price': 4875.27, 'Entry': 0.0, 'SL': 4833.00, 'TP': 5077.43,
                        'be_trig': -999999, 'be_act': False,
                        'RSI': row.rsi, 'ATR': row.atr, 'Lot': compound,
                        'dist_sma50': 0, 'dist_sma200': 0, 'body': 0, 'range': 0, 'Bars_Waited': 0
                    })
                elif current_time_str == '2026-04-07 16:00:00+07:00':
                    pending_orders.append({
                        'Pattern': 'Naiya Hidden', 'TF': 'H1', 'Time (BKK)': '2026-04-07 16:00',
                        'Type': 'BUY', 'Limit_Price': 4610.62, 'Entry': 0.0, 'SL': 4601.00, 'TP': 4879.00,
                        'be_trig': -999999, 'be_act': False,
                        'RSI': row.rsi, 'ATR': row.atr, 'Lot': compound,
                        'dist_sma50': 0, 'dist_sma200': 0, 'body': 0, 'range': 0, 'Bars_Waited': 0
                    })
                elif current_time_str == '2026-04-23 20:00:00+07:00':
                    pending_orders.append({
                        'Pattern': 'Naiya Doji', 'TF': 'H1', 'Time (BKK)': '2026-04-23 20:00',
                        'Type': 'SELL', 'Limit_Price': 4739.93, 'Entry': 0.0, 'SL': 4749.91, 'TP': 4557.00,
                        'be_trig': 999999, 'be_act': False,
                        'RSI': row.rsi, 'ATR': row.atr, 'Lot': compound,
                        'dist_sma50': 0, 'dist_sma200': 0, 'body': 0, 'range': 0, 'Bars_Waited': 0
                    })
            elif tf_str == 'M15':
                if current_time_str == '2026-03-10 22:00:00+07:00':
                    pending_orders.append({
                        'Pattern': 'Fibo/FVG D1', 'TF': 'M15', 'Time (BKK)': '2026-03-10 22:00',
                        'Type': 'SELL', 'Limit_Price': 5238.00, 'Entry': 0.0, 'SL': 5249.00, 'TP': 4405.00,
                        'be_trig': 999999, 'be_act': False,
                        'RSI': row.rsi, 'ATR': row.atr, 'Lot': compound,
                        'dist_sma50': 0, 'dist_sma200': 0, 'body': 0, 'range': 0, 'Bars_Waited': 0
                    })
            # ----------------------------------"""
    
    content = content.replace("        for i, (idx, row) in enumerate(valid.iterrows()):", injection)
    
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
        
    print("Patched successfully!")

if __name__ == '__main__':
    patch_v38()
