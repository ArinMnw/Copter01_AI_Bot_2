import subprocess

tp_values = [300, 500, 600, 700, 800]
sl_values = [50, 75, 100, 150]

best_pnl = 0
best_params = None

print("Starting Quant Optimization for S20.8 on 30 Days (M1 only for speed)...")

# We will modify strategy20_8.py for each run
with open("strategy20_8.py", "r", encoding="utf-8") as f:
    orig_code = f.read()

try:
    for sl in sl_values:
        for tp in tp_values:
            # Replace SL and TP
            mod_code = orig_code.replace('sl_pts = getattr(config, "S20_8_SL_POINTS", 100.0)', f'sl_pts = {float(sl)}')
            mod_code = mod_code.replace('tp_pts = 700.0 # Hardcode TP to test optimization logic directly', f'tp_pts = {float(tp)}')

            
            with open("strategy20_8.py", "w", encoding="utf-8") as f:
                f.write(mod_code)
                
            res = subprocess.run(["python", "backtest_S20_8_runner_mt5.py", "--days", "30", "--tf", "M1"], capture_output=True, text=True)
            
            # Parse PnL
            lines = res.stdout.split('\n')
            pnl = 0
            for line in lines:
                if "M1 " in line and "$" in line:
                    parts = line.split("$")
                    if len(parts) > 1:
                        val = parts[1].split("|")[0].strip()
                        pnl = float(val.replace(',', ''))
            
            print(f"SL: {sl}, TP: {tp} => PnL: ${pnl}")
            if pnl > best_pnl:
                best_pnl = pnl
                best_params = (sl, tp)

finally:
    # Restore original code
    with open("strategy20_8.py", "w", encoding="utf-8") as f:
        f.write(orig_code)

print(f"\nOptimization Complete! Best PnL: ${best_pnl} with SL: {best_params[0]}, TP: {best_params[1]}")
