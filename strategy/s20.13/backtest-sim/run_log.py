import sys
import os

with open(r'd:\Project\Copter01_AI_Bot_2\strategy\s20.13\strategy20_13_15.py', 'r', encoding='utf-8') as f:
    text = f.read()

text = text.replace('strategy_20_13_15', 'strategy_20_13_17')
text = text.replace('S20.13.15', 'S20.13.17')

log_buy = '''        body_pct = abs(current_bar['close'] - current_bar['open']) / cur_range if cur_range > 0 else 0
        upper_wick_pct = (current_bar['high'] - max(current_bar['open'], current_bar['close'])) / cur_range if cur_range > 0 else 0
        lower_wick_pct = (min(current_bar['open'], current_bar['close']) - current_bar['low']) / cur_range if cur_range > 0 else 0
        range_atr_ratio = cur_range / current_bar['atr'] if current_bar['atr'] > 0 else 0
        print(f"BUY_CANDLE|{current_time}|RSI:{current_bar['rsi']:.1f}|BODY:{body_pct:.2f}|UW:{upper_wick_pct:.2f}|LW:{lower_wick_pct:.2f}|RANGE/ATR:{range_atr_ratio:.2f}")'''

log_sell = '''        body_pct = abs(current_bar['close'] - current_bar['open']) / cur_range if cur_range > 0 else 0
        upper_wick_pct = (current_bar['high'] - max(current_bar['open'], current_bar['close'])) / cur_range if cur_range > 0 else 0
        lower_wick_pct = (min(current_bar['open'], current_bar['close']) - current_bar['low']) / cur_range if cur_range > 0 else 0
        range_atr_ratio = cur_range / current_bar['atr'] if current_bar['atr'] > 0 else 0
        print(f"SELL_CANDLE|{current_time}|RSI:{current_bar['rsi']:.1f}|BODY:{body_pct:.2f}|UW:{upper_wick_pct:.2f}|LW:{lower_wick_pct:.2f}|RANGE/ATR:{range_atr_ratio:.2f}")'''

text = text.replace('        entry_price = current_bar[\'close\']\n        sweep_bottom = min(recent_3[\'low\'].min(), current_bar[\'low\'])', log_buy + '\n        entry_price = current_bar[\'close\']\n        sweep_bottom = min(recent_3[\'low\'].min(), current_bar[\'low\'])')
text = text.replace('        entry_price = current_bar[\'close\']\n        sweep_top = max(recent_3[\'high\'].max(), current_bar[\'high\'])', log_sell + '\n        entry_price = current_bar[\'close\']\n        sweep_top = max(recent_3[\'high\'].max(), current_bar[\'high\'])')

with open(r'd:\Project\Copter01_AI_Bot_2\strategy\s20.13\strategy20_13_17.py', 'w', encoding='utf-8') as f:
    f.write(text)
