import os
import glob

target_dir = r'strategy\s20.14.1\backtest-sim'
files = glob.glob(os.path.join(target_dir, 'v38_standalone_group*.py'))

# The replacement targets
argparse_old = "parser.add_argument('--compare', action='store_true', help='Run MT5 history matching')"
argparse_new = "parser.add_argument('--compare', action='store_true', help='Run MT5 history matching')\n    parser.add_argument('--compare-profile', type=str, default=None, help='MT5 profile directory name to use')"

matcher_old = "mt5_matcher.generate_mt5_reports(df_trades, group_id, out_dir, symbol)"
matcher_new = "mt5_matcher.generate_mt5_reports(df_trades, group_id, out_dir, symbol, profile=args.compare_profile)"

patched_count = 0

for file_path in files:
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
        
    modified = False
    
    # 1. Patch argparse
    if argparse_old in content and '--compare-profile' not in content:
        content = content.replace(argparse_old, argparse_new)
        modified = True
        
    # 2. Patch matcher call
    if matcher_old in content and 'profile=args.compare_profile' not in content:
        content = content.replace(matcher_old, matcher_new)
        modified = True
        
    # 3. Patch mt5 initialize block
    # Note: Because the hardcoded path might differ, we find the mt5.initialize line.
    import re
    # We look for something like: mt5.initialize(r'D:\Project\...\terminal64.exe')
    # and the lines after it.
    
    # Simple regex to find mt5.initialize(...) followed by symbol = ...
    # Instead of regex, we know it's usually:
    # mt5.initialize(...)
    # symbol = "..."
    # info = mt5.symbol_info(symbol)
    
    # Or we can just find 'mt5.initialize(' and if it doesn't have args.compare_profile handling near it, replace it.
    if 'args.compare_profile' not in content and 'mt5.initialize(' in content:
        # We will use regex to find the initialize line
        match = re.search(r'(mt5\.initialize\([^)]+\))\s*\n\s*(symbol\s*=\s*"[^"]+")', content)
        if match:
            init_line = match.group(1)
            symbol_line = match.group(2)
            
            # Extract the path from init_line if possible, else just use a generic one
            path_match = re.search(r"r'([^']+)'", init_line)
            default_path = f"r'{path_match.group(1)}'" if path_match else "r'D:\\Project\\Copter01_AI_Bot_2\\profiles\\demo\\demo-iux-2101114448\\mt5\\terminal64.exe'"
            
            replacement = f'''mt5_path = {default_path}
    {symbol_line}
    if args.compare_profile:
        import os
        profile_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..', 'profiles', 'demo', args.compare_profile)
        if not os.path.exists(profile_path):
            profile_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..', 'profiles', 'real', args.compare_profile)
        mt5_path = os.path.join(profile_path, 'mt5', 'terminal64.exe')
        if 'exness' in args.compare_profile.lower():
            symbol = "XAUUSDm"
    
    mt5.initialize(mt5_path)'''
            
            content = content.replace(f"{init_line}\n    {symbol_line}", replacement)
            modified = True
        else:
            print(f"Could not automatically patch initialization in {file_path}")
            
    if modified:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        patched_count += 1
        print(f"Patched: {os.path.basename(file_path)}")

print(f"Successfully patched {patched_count} files.")
