import os

with open(r'd:\Project\Copter01_AI_Bot_2\strategy\s20.13\strategy20_13_22.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Replace file docstring / name references
content = content.replace('strategy20_13_22', 'strategy20_13_23')
content = content.replace('strategy_20_13_22', 'strategy_20_13_23')
content = content.replace('S20.13.22', 'S20.13.23')
content = content.replace('v22 Evolution', 'v22 Evolution') # keep existing comments

# Insert v23 BUY filter
buy_target = "if current_bar['rsi'] < 48.0 and current_bar['di_diff'] > 0.0:\n            return {\"signal\": \"WAIT\", \"reason\": f\"BUY Bull Trap Exhaustion Divergence Block (RSI={current_bar['rsi']:.1f}, DI_Diff={current_bar['di_diff']:.1f})\"}"
buy_replacement = buy_target + "\n\n        # v23 Evolution BUY Filters (Precision Loss Trap Block)\n        if current_bar['rsi'] < 40.0 and current_bar['adx'] > 42.0:\n            return {\"signal\": \"WAIT\", \"reason\": f\"BUY Oversold High ADX Momentum Trap Block (RSI={current_bar['rsi']:.1f}, ADX={current_bar['adx']:.1f})\"}"

if buy_target not in content:
    print("Error finding BUY target!")
else:
    content = content.replace(buy_target, buy_replacement)

# Insert v23 SELL filter
sell_target = "if current_bar['z_score'] < -1.50 and current_bar['upper_wick_pct'] > 0.30:\n            return {\"signal\": \"WAIT\", \"reason\": f\"SELL Lower BB Whipsaw Rejection Block (Z={current_bar['z_score']:.2f}, uWick%={current_bar['upper_wick_pct']:.2f})\"}"
sell_replacement = sell_target + "\n\n        # v23 Evolution SELL Filters (Precision Loss Trap Block)\n        if current_bar['body_pct'] > 0.70 and current_bar['atr_pct'] < 0.30:\n            return {\"signal\": \"WAIT\", \"reason\": f\"SELL Large Body Low Volatility Exhaustion Block (Body%={current_bar['body_pct']:.2f}, ATR%={current_bar['atr_pct']:.2f}%)\"}\n        if current_bar['rsi'] < 52.0 and current_bar['z_score'] > 0.0:\n            return {\"signal\": \"WAIT\", \"reason\": f\"SELL RSI/Z-Score Discrepancy Trap Block (RSI={current_bar['rsi']:.1f}, Z={current_bar['z_score']:.2f})\"}\n        if current_bar['rsi_7'] < 55.0 and current_bar['body_pct'] > 0.90:\n            return {\"signal\": \"WAIT\", \"reason\": f\"SELL Marubozu Momentum Trap Block (RSI7={current_bar['rsi_7']:.1f}, Body%={current_bar['body_pct']:.2f})\"}"

if sell_target not in content:
    print("Error finding SELL target!")
else:
    content = content.replace(sell_target, sell_replacement)

with open(r'd:\Project\Copter01_AI_Bot_2\strategy\s20.13\strategy20_13_23.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Successfully generated strategy20_13_23.py!")
