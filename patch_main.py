with open('main.py', 'r', encoding='utf-8') as f:
    content = f.read()
    
# Import new functions
content = content.replace(
    'from trailing import (check_entry_candle_quality, check_engulf_trail_sl,',
    'from trailing import (check_smart_cutloss, check_atr_trailing, check_entry_candle_quality, check_engulf_trail_sl,'
)

# Add calls to run_position_check
content = content.replace(
    'await check_limit_fill_notify(app); _lap("limit_fill_notify")',
    'await check_limit_fill_notify(app); _lap("limit_fill_notify")\n            await check_smart_cutloss(app); _lap("smart_cutloss")\n            await check_atr_trailing(app); _lap("atr_trailing")'
)

with open('main.py', 'w', encoding='utf-8') as f:
    f.write(content)
print('main.py patched')
