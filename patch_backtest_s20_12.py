import sys
import os

filepath = r"strategy\s20.12\backtest-sim\backtest_S20_12_runner_mt5.py"
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

# Insert sim_trades list
if 'sim_trades = []' not in content:
    target1 = 'results = []'
    replacement1 = 'results = []\n        sim_trades = []'
    content = content.replace(target1, replacement1)
    
# Import config's time converter
if 'from config import mt5_ts_to_bkk' not in content:
    target_import = 'import config'
    replacement_import = 'import config\nfrom config import mt5_ts_to_bkk'
    content = content.replace(target_import, replacement_import)

# Insert sim_trades append logic
target2 = '''                    if trade_result:
                        skip_until_index = j
                        trades += 1
                        balance += trade_pnl
                        net_pl += trade_pnl
                        patterns[pattern] = patterns.get(pattern, 0) + 1
                        
                        if trade_result == "WIN":
                            wins += 1
                        else:
                            losses += 1'''

replacement2 = '''                    if trade_result:
                        skip_until_index = j
                        trades += 1
                        balance += trade_pnl
                        net_pl += trade_pnl
                        patterns[pattern] = patterns.get(pattern, 0) + 1
                        
                        dt_bkk = mt5_ts_to_bkk(rates[i]['time'])
                        close_time = mt5_ts_to_bkk(c['time'])
                        sim_trades.append({
                            "Time (BKK)": dt_bkk.strftime('%Y-%m-%d %H:%M:%S'),
                            "Close Time": close_time.strftime('%Y-%m-%d %H:%M:%S') if close_time else "",
                            "TF": tf_name,
                            "Type": sig,
                            "Entry": f"{entry:.2f}",
                            "SL": f"{sl:.2f}",
                            "TP": f"{tp:.2f}",
                            "P&L": f"{trade_pnl:.2f}",
                            "Reason": "TP" if trade_result == "WIN" else "SL"
                        })
                        
                        if trade_result == "WIN":
                            wins += 1
                        else:
                            losses += 1'''

if 'sim_trades.append(' not in content:
    content = content.replace(target2, replacement2)

# Insert CSV saving logic
target3 = '''        print(f"| **สรุปรวมทุก TF** | {total_trades} | {total_wins} | {total_losses} | {total_wr:.1f}% | - | {total_net:,.2f} |")'''

replacement3 = '''        print(f"| **สรุปรวมทุก TF** | {total_trades} | {total_wins} | {total_losses} | {total_wr:.1f}% | - | {total_net:,.2f} |")
        
        # Save SIM trades to CSV
        if sim_trades:
            import pandas as pd
            df_sim = pd.DataFrame(sim_trades)
            out_csv = os.path.join(os.path.dirname(__file__), "..", "excel", "s20_12_sim_trades.csv")
            os.makedirs(os.path.dirname(out_csv), exist_ok=True)
            df_sim.to_csv(out_csv, index=False)
            print(f"💾 บันทึกประวัติออเดอร์จำลองไว้ที่: {out_csv}")'''

if 'df_sim.to_csv(' not in content:
    content = content.replace(target3, replacement3)

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(content)

print("backtest_S20_12_runner_mt5.py patched for CSV export successfully")
