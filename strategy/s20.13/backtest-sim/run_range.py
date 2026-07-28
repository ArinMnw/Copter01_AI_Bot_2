import sys
import os

with open(r'd:\Project\Copter01_AI_Bot_2\strategy\s20.13\strategy20_13_15.py', 'r', encoding='utf-8') as f:
    text = f.read()

text = text.replace('strategy_20_13_15', 'strategy_20_13_17')
text = text.replace('S20.13.15', 'S20.13.17')

text = text.replace('cur_range >= (0.8 * current_bar[\'atr\'])', 'cur_range >= (1.2 * current_bar[\'atr\'])')
text = text.replace('cur_range >= 0.8 * current_bar[\'atr\']', 'cur_range >= (1.2 * current_bar[\'atr\'])')

with open(r'd:\Project\Copter01_AI_Bot_2\strategy\s20.13\strategy20_13_17.py', 'w', encoding='utf-8') as f:
    f.write(text)
