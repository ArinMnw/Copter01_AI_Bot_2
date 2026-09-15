import os
import subprocess
import glob
import pandas as pd
import time
import re
import sys

base_dir = r"d:\Project\Copter01_AI_Bot_2\strategy\s20.14.1"
scripts_dir = os.path.join(base_dir, "backtest-sim")
scripts = glob.glob(os.path.join(scripts_dir, "v38_standalone_group*.py"))
scripts.sort(key=lambda x: (len(x), x)) # Sort intuitively

results = []
print(f"Found {len(scripts)} scripts to check.")

for script in scripts:
    filename = os.path.basename(script)
    # Extract group id, e.g. v38_standalone_group13.1.py -> 13.1
    m = re.search(r'group([\d\.]+)\.py', filename)
    if not m:
        continue
    group_id = m.group(1)
    
    print(f"Running {filename}...")
    try:
        # Run script
        subprocess.run([sys.executable, script, "--day", "3", "--compare"], cwd=scripts_dir, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except subprocess.CalledProcessError as e:
        print(f"Error running {filename}")
        results.append({"Group": group_id, "Matched": "ERROR", "BT_Unmatched": "ERROR", "MT5_Unmatched": "ERROR"})
        continue
        
    # Read output files
    excel_dir = os.path.join(base_dir, f"excel_group{group_id}")
    match_file = os.path.join(excel_dir, "match_order.csv")
    bt_not_match = os.path.join(excel_dir, "backtest_not_match.csv")
    mt5_not_match = os.path.join(excel_dir, "mt5_not_match.csv")
    
    matched = 0
    bt_un = 0
    mt5_un = 0
    
    if os.path.exists(match_file):
        try:
            df = pd.read_csv(match_file)
            matched = len(df)
        except pd.errors.EmptyDataError:
            pass
            
    if os.path.exists(bt_not_match):
        try:
            df = pd.read_csv(bt_not_match)
            bt_un = len(df)
        except pd.errors.EmptyDataError:
            pass
            
    if os.path.exists(mt5_not_match):
        try:
            df = pd.read_csv(mt5_not_match)
            mt5_un = len(df)
        except pd.errors.EmptyDataError:
            pass
            
    results.append({"Group": group_id, "Matched": matched, "BT_Unmatched": bt_un, "MT5_Unmatched": mt5_un})

print("\n--- SUMMARY ---")
summary_df = pd.DataFrame(results)
print(summary_df.to_string(index=False))
summary_df.to_csv(os.path.join(base_dir, "matching_summary.csv"), index=False)
