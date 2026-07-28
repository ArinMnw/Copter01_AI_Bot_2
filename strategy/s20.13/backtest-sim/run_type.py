import sys
import os

with open(r'd:\Project\Copter01_AI_Bot_2\strategy\s20.13\strategy20_13_15.py', 'r', encoding='utf-8') as f:
    text = f.read()

text = text.replace('strategy_20_13_15', 'strategy_20_13_17')
text = text.replace('S20.13.15', 'S20.13.17')

text = text.replace('        if (sweep_buy and engulf_buy) or instant_sweep_buy:', 
'''        if (sweep_buy and engulf_buy) or instant_sweep_buy:
        print(f"BUY_TYPE|{current_time}|{'INSTANT' if instant_sweep_buy else 'DELAYED'}")''')

text = text.replace('        if (sweep_sell and engulf_sell) or instant_sweep_sell:', 
'''        if (sweep_sell and engulf_sell) or instant_sweep_sell:
        print(f"SELL_TYPE|{current_time}|{'INSTANT' if instant_sweep_sell else 'DELAYED'}")''')

with open(r'd:\Project\Copter01_AI_Bot_2\strategy\s20.13\strategy20_13_17.py', 'w', encoding='utf-8') as f:
    f.write(text)
