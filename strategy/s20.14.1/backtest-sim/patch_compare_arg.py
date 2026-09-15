import os
import glob
import re

directory = r"d:\Project\Copter01_AI_Bot_2\strategy\s20.14.1\backtest-sim"

# Pattern to find argparse block
argparse_pattern = r"(parser\.add_argument\('--end', type=str, default=None, help='End date \(YYYY-MM-DD\)'\))"
argparse_replacement = r"\1\n    parser.add_argument('--compare', action='store_true', help='Run MT5 history matching')"

# Pattern to find MT5 matching call
matching_pattern = r"(    # 6\. MT5 History Matching\n    try:\n        import mt5_matcher\n        mt5_matcher\.generate_mt5_reports\(df_trades, group_id, out_dir, symbol\)\n    except Exception as e:\n        print\(f\"Error generating MT5 match reports: \{e\}\"\))"
matching_replacement = """    # 6. MT5 History Matching
    if args.compare:
        try:
            import mt5_matcher
            mt5_matcher.generate_mt5_reports(df_trades, group_id, out_dir, symbol)
        except Exception as e:
            print(f"Error generating MT5 match reports: {e}")"""

def patch_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # Skip if already patched
    if "parser.add_argument('--compare'" in content:
        return False

    # 1. Inject --compare argument
    content = re.sub(argparse_pattern, argparse_replacement, content)

    # 2. Inject condition for matching
    content = re.sub(matching_pattern, matching_replacement, content, flags=re.DOTALL)

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
