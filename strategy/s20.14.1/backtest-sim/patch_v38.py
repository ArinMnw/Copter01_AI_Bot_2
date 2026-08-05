import os

with open('export_patterns_v34.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Fix FVG
old_fvg_sell = """if tf_str in target_tfs["FVG"] and row.bear_fvg_10 and row.fvg_sell_ml == 1:
                if 23.0 <= row.rsi <= 77.0 and row.atr >= 10.0:
                    # PD Fibo Zone Check (Must be in Premium > 61.8%)
                    if row.recent_high > fibo_61_8:
                        patterns_sell.append("FVG")"""
new_fvg_sell = """if tf_str in target_tfs["FVG"] and row.bear_fvg_10:
                if row.fvg_sell_ml == 1 or row.rsi < 30: # Momentum bypass
                    if 10.0 <= row.rsi <= 77.0 and row.atr >= 10.0:
                        if row.recent_high > fibo_61_8 or row.rsi < 30:
                            patterns_sell.append("FVG")"""
content = content.replace(old_fvg_sell, new_fvg_sell)

# Fix Fibo
old_fibo_sell = """if s11_res and s11_res.get('signal') == 'SELL':
                patterns_sell.append("Fibo")"""
new_fibo_sell = """if s11_res and s11_res.get('signal') == 'SELL':
                patterns_sell.append("Fibo")
            if tf_str in target_tfs["Fibo"]:
                for b in range(2, 20):
                    b_bar = df.iloc[i-b]
                    if b_bar['close'] < b_bar['open']:
                        rng = b_bar['high'] - b_bar['low']
                        if rng > 0:
                            krh3 = b_bar['low'] + rng * 5.165
                            if abs(row.high - krh3) < 2.0 and row.close < row.open:
                                patterns_sell.append("Fibo")
                                break"""
content = content.replace(old_fibo_sell, new_fibo_sell)

with open('export_patterns_v38.py', 'w', encoding='utf-8') as f:
    f.write(content)
