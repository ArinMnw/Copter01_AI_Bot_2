import sys
import os
import pandas as pd

with open(r'd:\Project\Copter01_AI_Bot_2\strategy\s20.13\strategy20_13_15.py', 'r', encoding='utf-8') as f:
    text = f.read()

text = text.replace('strategy_20_13_15', 'strategy_20_13_17')
text = text.replace('S20.13.15', 'S20.13.17')

import_block = '''import sys
import os
import pandas as pd
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
import ml_scoring
'''
text = import_block + text

buy_target = '''        if current_bar['rsi'] < 35:
            return {"signal": "WAIT", "reason": f"RSI too low ({current_bar['rsi']:.1f})"}'''
buy_replace = '''        if current_bar['rsi'] < 35:
            return {"signal": "WAIT", "reason": f"RSI too low ({current_bar['rsi']:.1f})"}
            
        score = ml_scoring.score_signal("XAUUSD", tf, "BUY", current_bar['close'], pd.to_datetime(current_bar['time'], unit='s'), rates)
        if score < 0.65:
            return {"signal": "WAIT", "reason": f"ML Score too low ({score:.2f})"}'''
text = text.replace(buy_target, buy_replace)

sell_target = '''        if current_bar['rsi'] > 60:
            return {"signal": "WAIT", "reason": f"RSI too high ({current_bar['rsi']:.1f})"}'''
sell_replace = '''        if current_bar['rsi'] > 60:
            return {"signal": "WAIT", "reason": f"RSI too high ({current_bar['rsi']:.1f})"}
            
        score = ml_scoring.score_signal("XAUUSD", tf, "SELL", current_bar['close'], pd.to_datetime(current_bar['time'], unit='s'), rates)
        if score < 0.65:
            return {"signal": "WAIT", "reason": f"ML Score too low ({score:.2f})"}'''
text = text.replace(sell_target, sell_replace)

with open(r'd:\Project\Copter01_AI_Bot_2\strategy\s20.13\strategy20_13_17.py', 'w', encoding='utf-8') as f:
    f.write(text)
