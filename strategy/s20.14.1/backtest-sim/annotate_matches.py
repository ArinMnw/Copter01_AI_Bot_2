import os
import re

md_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', 'docs', 'allin4s', 'Full Trading', 'full_trading.md'))
with open(md_path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

# The 18 matches from my script output:
matches = {
    1: "Fibo_M15.csv (Bot E:4700.19 SL:4720.09 TP:4685.44)",
    2: "Fibo_M15.csv (Bot E:4700.19 SL:4720.09 TP:4685.44)",
    3: "MA12_H1.csv (Bot E:4537.22 SL:4581.75 TP:4502.61)",
    4: "MA12_H1.csv (Bot E:4537.22 SL:4581.75 TP:4502.61)",
    6: "Fibo_M15.csv (Bot E:4479.86 SL:4505.9 TP:4463.49)",
    10: "ATR_H1.csv (Bot E:3987.25 SL:3947.71 TP:4019.51)",
    13: "FVG_H1.csv (Bot E:4022.81 SL:3986.6 TP:4055.82)",
    14: "FVG_H1.csv (Bot E:4022.81 SL:3986.6 TP:4055.82)",
    15: "FVG_M30.csv (Bot E:4127.01 SL:4168.07 TP:4101.54)",
    16: "Fibo_M30.csv (Bot E:4088.89 SL:4147.46 TP:4062.8)",
    20: "Fibo_M15.csv (Bot E:4121.68 SL:4138.1 TP:4111.23)",
    23: "Div_H1.csv (Bot E:3966.16 SL:3933.21 TP:3997.07)",
    24: "Div_H1.csv (Bot E:3966.16 SL:3933.21 TP:3997.07)",
    25: "Div_H1.csv (Bot E:3966.16 SL:3933.21 TP:3997.07)",
    28: "Div_H1.csv (Bot E:3966.16 SL:3933.21 TP:3997.07)",
    31: "MA12_H1.csv (Bot E:4118.62 SL:4153.63 TP:4093.23)",
    32: "MA12_H1.csv (Bot E:4118.62 SL:4153.63 TP:4093.23)",
    35: "Fibo_H1.csv (Bot E:4052.4 SL:4026.78 TP:4077.28)"
}

new_lines = []
for line in lines:
    m = re.match(r'^(\d+)\.\s+\*\*Order', line)
    if m:
        num = int(m.group(1))
        if num in matches:
            line = line.rstrip() + f" | ✅ **MATCHED** ({matches[num]})\n"
    new_lines.append(line)

with open(md_path, 'w', encoding='utf-8') as f:
    f.writelines(new_lines)

print("Updated full_trading.md")
