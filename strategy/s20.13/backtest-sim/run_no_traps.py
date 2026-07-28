import sys
import os

with open(r'd:\Project\Copter01_AI_Bot_2\strategy\s20.13\strategy20_13_15.py', 'r', encoding='utf-8') as f:
    text = f.read()

text = text.replace('strategy_20_13_15', 'strategy_20_13_17')
text = text.replace('S20.13.15', 'S20.13.17')

# Remove Time Traps!
traps = [
    '        if is_ny_pre_open:\n            return {"signal": "WAIT", "reason": "NY Pre-Open Trap"}\n',
    '        if is_sydney_open:\n            return {"signal": "WAIT", "reason": "Sydney Open Trap"}\n',
    '        if is_tokyo_buy:\n            return {"signal": "WAIT", "reason": "Tokyo Trap (BUY)"}\n',
    '        if is_late_ny_buy:\n            return {"signal": "WAIT", "reason": "Late NY Trap (BUY)"}\n',
    '        if is_midnight_buy:\n            return {"signal": "WAIT", "reason": "Midnight Trap (BUY)"}\n',
    '        if is_london_open:\n            return {"signal": "WAIT", "reason": "London Open Trap (BUY)"}\n',
    '        if is_london_fake:\n            return {"signal": "WAIT", "reason": "London Fake Trap (BUY)"}\n',
    '        if is_tokyo_sell:\n            return {"signal": "WAIT", "reason": "Tokyo Trap (SELL)"}\n',
    '        if is_late_ny_sell:\n            return {"signal": "WAIT", "reason": "Late NY Trap (SELL)"}\n',
    '        if is_midnight_sell:\n            return {"signal": "WAIT", "reason": "Midnight Trap (SELL)"}\n',
    '        if is_london_open:\n            return {"signal": "WAIT", "reason": "London Open Trap (SELL)"}\n',
    '        if is_london_fake:\n            return {"signal": "WAIT", "reason": "London Fake Trap (SELL)"}\n'
]

for trap in traps:
    text = text.replace(trap, '')

buy_target = '''        if current_bar['rsi'] < 35:
            return {"signal": "WAIT", "reason": f"RSI too low ({current_bar['rsi']:.1f})"}'''
buy_replace = '''        if current_bar['rsi'] < 40:
            return {"signal": "WAIT", "reason": f"RSI too low ({current_bar['rsi']:.1f})"}'''
text = text.replace(buy_target, buy_replace)

sell_target = '''        if current_bar['rsi'] > 60:
            return {"signal": "WAIT", "reason": f"RSI too high ({current_bar['rsi']:.1f})"}'''
sell_replace = '''        if current_bar['rsi'] > 60:
            return {"signal": "WAIT", "reason": f"RSI too high ({current_bar['rsi']:.1f})"}'''
text = text.replace(sell_target, sell_replace)

with open(r'd:\Project\Copter01_AI_Bot_2\strategy\s20.13\strategy20_13_17.py', 'w', encoding='utf-8') as f:
    f.write(text)
