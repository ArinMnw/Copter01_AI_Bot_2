import os
import re

md_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', 'docs', 'allin4s', 'Full Trading', 'full_trading.md'))
with open(md_path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

output = """Order 1 [SELL] 2026-05-12 01:00 E:4769.61 | TIME MATCH ONLY in trades.csv (Bot E:4671.96 SL:4697.7 TP:4646.67)
Order 2 [SELL] 2026-05-12 02:00 E:4773.49 | TIME MATCH ONLY in trades.csv (Bot E:4690.6 SL:4723.82 TP:4662.14)
Order 3 [SELL] 2026-05-19 02:00 E:4589.28 | TIME MATCH ONLY in trades.csv (Bot E:4546.68 SL:4594.71 TP:4515.0)
Order 4 [SELL] 2026-05-19 02:00 E:4589.28 | TIME MATCH ONLY in trades.csv (Bot E:4546.68 SL:4594.71 TP:4515.0)
Order 5 [SELL] 2026-05-29 17:00 E:4595.29 | TIME MATCH ONLY in trades.csv (Bot E:4531.07 SL:4561.85 TP:4508.76)
Order 6 [SELL] 2026-06-02 09:00 E:4541.48 | TIME MATCH ONLY in trades.csv (Bot E:4485.39 SL:4502.54 TP:4471.09)
Order 7 [BUY] 2026-06-08 02:00 E:4339.72 | TIME MATCH ONLY in trades.csv (Bot E:4343.94 SL:4304.59 TP:4372.37)
Order 8 [SELL] 2026-06-15 16:00 E:4369.3 | TIME MATCH ONLY in trades.csv (Bot E:4329.65 SL:4370.9 TP:4294.24)
Order 9 [SELL] 2026-06-18 09:00 E:4309.44 | TIME MATCH ONLY in trades.csv (Bot E:4227.45 SL:4353.06 TP:4169.78)
Order 10 [BUY] 2026-06-30 03:00 E:3942.68 | TIME MATCH ONLY in trades.csv (Bot E:4047.26 SL:4024.9 TP:4065.86)
Order 11 [SELL] 2026-07-01 03:00 E:3999.81 | TIME MATCH ONLY in trades.csv (Bot E:4023.78 SL:4058.89 TP:3998.21)
Order 12 [SELL] 2026-07-01 17:00 E:4094.59 | TIME MATCH ONLY in trades.csv (Bot E:3981.41 SL:4008.25 TP:3960.27)
Order 13 [BUY] 2026-07-01 09:00 E:3960.16 | TIME MATCH ONLY in trades.csv (Bot E:4021.18 SL:3994.89 TP:4047.47)
Order 14 [BUY] 2026-07-01 09:00 E:3960.16 | TIME MATCH ONLY in trades.csv (Bot E:4021.18 SL:3994.89 TP:4047.47)
Order 15 [SELL] 2026-07-07 20:00 E:4145.2 | EXACT MATCH in trades.csv (Bot E:4143.13 SL:4165.38 TP:4122.83)
Order 16 [SELL] 2026-07-08 00:00 E:4106.04 | TIME MATCH ONLY in trades.csv (Bot E:4137.45 SL:4159.9 TP:4116.53)
Order 17 [BUY] 2026-07-08 17:00 E:4021.78 | TIME MATCH ONLY in trades.csv (Bot E:4129.95 SL:4089.0 TP:4155.48)
Order 18 [SELL] 2026-07-06 01:00 E:4201.83 | TIME MATCH ONLY in trades.csv (Bot E:4188.19 SL:4313.79 TP:4065.94)
Order 19 [BUY] 2026-07-08 17:00 E:4021.78 | TIME MATCH ONLY in trades.csv (Bot E:4129.95 SL:4089.0 TP:4155.48)
Order 20 [SELL] 2026-07-09 18:00 E:4138.08 | TIME MATCH ONLY in trades.csv (Bot E:4060.58 SL:4081.63 TP:4043.46)
Order 21 [SELL] 2026-07-14 14:00 E:4102.97 | TIME MATCH ONLY in trades.csv (Bot E:4016.78 SL:4037.1 TP:3997.55)
Order 22 [SELL] 2026-07-14 14:00 E:4102.97 | TIME MATCH ONLY in trades.csv (Bot E:4016.78 SL:4037.1 TP:3997.55)
Order 23 [BUY] 2026-07-17 15:00 E:3959.72 | TIME MATCH ONLY in trades.csv (Bot E:3991.17 SL:3971.29 TP:4007.22)
Order 24 [BUY] 2026-07-17 15:00 E:3959.72 | TIME MATCH ONLY in trades.csv (Bot E:3991.17 SL:3971.29 TP:4007.22)
Order 25 [BUY] 2026-07-17 13:00 E:3990.0 | EXACT MATCH in trades.csv (Bot E:3991.17 SL:3971.29 TP:4007.22)
Order 26 [SELL] 2026-07-14 14:00 E:4102.97 | TIME MATCH ONLY in trades.csv (Bot E:4016.78 SL:4037.1 TP:3997.55)
Order 27 [SELL] 2026-07-15 20:00 E:4081.19 | TIME MATCH ONLY in trades.csv (Bot E:4026.14 SL:4055.67 TP:4005.98)
Order 28 [BUY] 2026-07-17 15:00 E:3959.72 | TIME MATCH ONLY in trades.csv (Bot E:3991.17 SL:3971.29 TP:4007.22)
Order 29 [SELL] 2026-07-22 05:00 E:4141.71 | TIME MATCH ONLY in trades.csv (Bot E:4076.83 SL:4099.23 TP:4056.73)
Order 30 [SELL] 2026-07-22 17:00 E:4165.99 | TIME MATCH ONLY in trades.csv (Bot E:4127.02 SL:4148.55 TP:4107.63)
Order 31 [SELL] 2026-07-23 03:00 E:4141.06 | EXACT MATCH in trades.csv (Bot E:4136.7 SL:4158.3 TP:4116.26)
Order 32 [SELL] 2026-07-23 03:00 E:4141.06 | EXACT MATCH in trades.csv (Bot E:4136.7 SL:4158.3 TP:4116.26)
Order 33 [BUY] 2026-07-24 05:00 E:4023.2 | TIME MATCH ONLY in trades.csv (Bot E:4048.73 SL:4015.52 TP:4075.61)
Order 34 [BUY] 2026-07-24 05:00 E:4023.2 | TIME MATCH ONLY in trades.csv (Bot E:4048.73 SL:4015.52 TP:4075.61)
Order 35 [BUY] 2026-07-24 14:00 E:4051.71 | EXACT MATCH in trades.csv (Bot E:4055.28 SL:4042.32 TP:4067.99)"""

matches = {}
for line in output.strip().split('\n'):
    m = re.match(r'^Order (\d+) .*?\| (.*)$', line)
    if m:
        matches[int(m.group(1))] = m.group(2)

new_lines = []
for line in lines:
    m = re.match(r'^(\d+)\.\s+\*\*Order', line)
    if m:
        num = int(m.group(1))
        if num in matches:
            # clean up previous MATCHED tags
            clean_line = re.sub(r'\s*\|\s*✅\s*\*\*MATCHED\*\*.*$', '', line.rstrip())
            exact = "🔥 **EXACT MATCH**" if "EXACT MATCH" in matches[num] else "✅ **MATCHED**"
            new_lines.append(clean_line + f" | {exact} ({matches[num]})\n")
            continue
    new_lines.append(line)

with open(md_path, 'w', encoding='utf-8') as f:
    f.writelines(new_lines)

print("Updated full_trading.md with all 35 matches!")
