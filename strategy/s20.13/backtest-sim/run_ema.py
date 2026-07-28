import sys
import os

with open(r'd:\Project\Copter01_AI_Bot_2\strategy\s20.13\strategy20_13_15.py', 'r', encoding='utf-8') as f:
    text = f.read()

text = text.replace('strategy_20_13_15', 'strategy_20_13_17')
text = text.replace('S20.13.15', 'S20.13.17')

ema_calc = '''    is_strong_range = cur_range >= 0.8 * current_bar['atr']
    ema_50 = df['close'].ewm(span=50, adjust=False).mean().iloc[-2]'''
text = text.replace("    is_strong_range = cur_range >= 0.8 * current_bar['atr']", ema_calc)

buy_target = '''        if current_bar['rsi'] < 35:
            return {"signal": "WAIT", "reason": f"RSI too low ({current_bar['rsi']:.1f})"}'''
buy_replace = '''        if current_bar['rsi'] < 35:
            return {"signal": "WAIT", "reason": f"RSI too low ({current_bar['rsi']:.1f})"}
        if current_bar['close'] < ema_50:
            return {"signal": "WAIT", "reason": "Counter Trend (BUY)"}'''
text = text.replace(buy_target, buy_replace)

sell_target = '''        if current_bar['rsi'] > 60:
            return {"signal": "WAIT", "reason": f"RSI too high ({current_bar['rsi']:.1f})"}'''
sell_replace = '''        if current_bar['rsi'] > 60:
            return {"signal": "WAIT", "reason": f"RSI too high ({current_bar['rsi']:.1f})"}
        if current_bar['close'] > ema_50:
            return {"signal": "WAIT", "reason": "Counter Trend (SELL)"}'''
text = text.replace(sell_target, sell_replace)

with open(r'd:\Project\Copter01_AI_Bot_2\strategy\s20.13\strategy20_13_17.py', 'w', encoding='utf-8') as f:
    f.write(text)
