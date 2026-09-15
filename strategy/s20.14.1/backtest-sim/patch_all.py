import os
import glob
import re

directory = r"d:\Project\Copter01_AI_Bot_2\strategy\s20.14.1\backtest-sim"

# Pattern to find the start of the main block
main_pattern = r"if __name__ == '__main__':\n\s*days = 365"

argparse_code = """if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--day', type=int, default=365)
    parser.add_argument('--start', type=str, default=None, help='Start date (YYYY-MM-DD)')
    parser.add_argument('--end', type=str, default=None, help='End date (YYYY-MM-DD)')
    args = parser.parse_args()

    days = args.day
    
    start_dt = None
    end_dt = None
    if args.start and args.end:
        import pandas as pd
        from datetime import timedelta
        import pytz
        bkk_tz = pytz.timezone('Asia/Bangkok')
        start_dt = pd.to_datetime(args.start).tz_localize(bkk_tz)
        end_dt = pd.to_datetime(args.end).tz_localize(bkk_tz)
        
        # Override days for internal logic
        days_diff = (end_dt - start_dt).days
        if days_diff > 0:
            days = days_diff"""

# The fetch replacement
fetch_original = """        limit = ((days * 24 * 60) // mins) + 150
        if limit > 500000: limit = 500000
            
        rates = mt5.copy_rates_from_pos(symbol, tf, 0, limit)"""

fetch_replacement = """        limit = ((days * 24 * 60) // mins) + 150
        if limit > 500000: limit = 500000
            
        if start_dt and end_dt:
            # Pad the start date to give indicators enough history
            start_pad = start_dt - timedelta(days=30)
            rates = mt5.copy_rates_range(symbol, tf, start_pad.astimezone(pytz.utc).replace(tzinfo=None), end_dt.astimezone(pytz.utc).replace(tzinfo=None))
        else:
            rates = mt5.copy_rates_from_pos(symbol, tf, 0, limit)"""


def patch_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # Skip if already patched
    if "parser.add_argument('--day'" in content:
        return False

    # 1. Inject argparse
    content = re.sub(main_pattern, argparse_code, content)

    # 2. Inject fetch replacement
    content = content.replace(fetch_original, fetch_replacement)

    # 3. Remove hardcoded overriding of days
    # (e.g. `if target_tf == 'D1': days = 365`)
    # We will just comment them out or remove them using regex
    content = re.sub(r"\s+if target_tf == 'D1': days = 365", "", content)
    content = re.sub(r"\s+elif target_tf == 'H12': days = 365", "", content)
    content = re.sub(r"\s+elif target_tf == 'H4': days = 365", "", content)
    content = re.sub(r"\s+elif target_tf == 'H1': days = 365", "", content)
    content = re.sub(r"\s+elif target_tf == 'M30': days = 365", "", content)
    content = re.sub(r"\s+else: days = 365", "", content)

    # Also fix the global_dfs limit, maybe make it dynamic?
    # Actually, global_dfs is used for Swing structure on higher TFs. It fetches 50000 or 10000 bars.
    # It doesn't use `days`, so it's fine.

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    return True

if __name__ == '__main__':
    files = glob.glob(os.path.join(directory, "v38_standalone_group*.py"))
    for file in files:
        if patch_file(file):
            print(f"Patched: {os.path.basename(file)}")
    print("Done patching.")
