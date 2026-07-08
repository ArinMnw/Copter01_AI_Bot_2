import re

with open('mt5_utils.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_lines = []
for i in range(len(lines)):
    line = lines[i]
    new_lines.append(line)
    if 'prob = ml_scoring.predict_success_probability(features)' in line:
        indent = line.split('prob =')[0]
        
        dyn_lot = f"""
{indent}# Dynamic Lot Sizing based on ML Prob and ATR
{indent}atr_val = features[1] if isinstance(features, (list, tuple)) and len(features) > 1 else 20.0
{indent}if isinstance(features, dict):
{indent}    atr_val = features.get('atr', 20.0)
{indent}
{indent}if getattr(config, "ML_LOT_SCALING_ENABLED", True):
{indent}    mult = 1.0
{indent}    if prob >= 0.75:
{indent}        mult *= 1.5
{indent}    elif prob < 0.50:
{indent}        mult *= 0.5
{indent}    if atr_val > 35:
{indent}        mult *= 0.7
{indent}    elif atr_val < 15:
{indent}        mult *= 1.2
{indent}    if mult != 1.0:
{indent}        volume = volume * mult
{indent}        info = mt5.symbol_info(SYMBOL)
{indent}        if info:
{indent}            v_step = info.volume_step
{indent}            volume = round(volume / v_step) * v_step
{indent}            volume = max(info.volume_min, min(volume, info.volume_max))
{indent}        print(f"[{{time_bkk.strftime('%H:%M:%S')}}] ⚖️ [Dynamic Lot] Adjusted volume to {{volume}} (Prob: {{prob:.2f}}, ATR: {{atr_val:.1f}}, Mult: {{mult:.2f}})")
"""
        new_lines.append(dyn_lot)

with open('mt5_utils.py', 'w', encoding='utf-8') as f:
    f.writelines(new_lines)
print('mt5_utils.py patched with Dynamic Lot Sizing successfully!')
