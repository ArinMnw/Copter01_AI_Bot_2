import os
import subprocess
import re

with open(r'd:\Project\Copter01_AI_Bot_2\strategy\s20.13\strategy20_13_15.py', 'r', encoding='utf-8') as f:
    base_text = f.read()

best_pl = 0
best_params = None

for sl in [0.5, 0.8, 1.0, 1.2, 1.5, 2.0]:
    for am in [2.2, 2.4, 2.6, 2.8, 3.0, 3.5]:
        text = base_text.replace('strategy_20_13_15', 'strategy_20_13_17')
        text = text.replace('S20.13.15', 'S20.13.17')
        text = re.sub(r'active_mode = [\d\.]+', f'active_mode = {am}', text)
        
        text = text.replace("config.SL_BUFFER(current_bar['atr'])", f"(current_bar['atr'] * {sl})")
        
        with open(r'd:\Project\Copter01_AI_Bot_2\strategy\s20.13\strategy20_13_17.py', 'w', encoding='utf-8') as f:
            f.write(text)
            
        result = subprocess.run(['python', 'backtest_s20_13_17_runner.py'], capture_output=True, text=True)
        
        if 'SNIPER RULE PASSED!' in result.stdout:
            pl = 0
            wr = 0
            for l in result.stdout.split('\n'):
                if '**H1**' in l:
                    parts = [p.strip() for p in l.split('|')]
                    try:
                        wr = float(parts[5].replace('%', ''))
                        pl = float(parts[7].replace('$', '').replace(',', ''))
                    except:
                        pass
            print(f"SL:{sl}, AM:{am} -> WR:{wr}%, PL:${pl}")
            if pl > best_pl:
                best_pl = pl
                best_params = (sl, am)

if best_params:
    print(f"Best: SL={best_params[0]}, AM={best_params[1]}, PL=${best_pl}")
else:
    print("No combination passed the Sniper Rule.")
