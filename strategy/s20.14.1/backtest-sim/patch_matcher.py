import os
import glob
import re

directory = r"d:\Project\Copter01_AI_Bot_2\strategy\s20.14.1\backtest-sim"

old_snippet = """    # 6. mt5_real.csv
    mt5_real = pd.DataFrame(columns=['Time', 'Ticket', 'Type', 'Volume', 'Price', 'S / L', 'T / P', 'Profit'])
    mt5_real.to_csv(os.path.join(out_dir, "mt5_real.csv"), index=False)
    print("Saved: mt5_real.csv")"""

new_snippet = """    # 6. MT5 History Matching
    try:
        import mt5_matcher
        mt5_matcher.generate_mt5_reports(df_trades, group_id, out_dir, symbol)
    except Exception as e:
        print(f"Error generating MT5 match reports: {e}")"""

def patch_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
        
    if "MT5 History Matching" in content:
        return False
        
    if old_snippet in content:
        content = content.replace(old_snippet, new_snippet)
    else:
        # If it doesn't strictly match the old snippet due to formatting, try regex
        pattern = r"    # 6\. mt5_real\.csv.*?print\(\"Saved: mt5_real\.csv\"\)"
        content = re.sub(pattern, new_snippet, content, flags=re.DOTALL)
        
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
        
    return True

if __name__ == '__main__':
    files = glob.glob(os.path.join(directory, "v38_standalone_group*.py"))
    count = 0
    for file in files:
        if patch_file(file):
            count += 1
            print(f"Patched: {os.path.basename(file)}")
    print(f"Done patching {count} files.")
