import re

with open('handlers/callback_handler.py', 'r', encoding='utf-8') as f:
    content = f.read()

toggle_s20_5 = '''
    elif data == "toggle_s20_5_enabled":
        config.S20_5_ENABLED = not getattr(config, "S20_5_ENABLED", False)
        save_runtime_state()
        await _show_strategy_detail(query, 20.5)
'''

if 'toggle_s20_5_enabled' not in content:
    content = content.replace(
        'elif data == "toggle_s20_enabled":',
        toggle_s20_5 + '\n    elif data == "toggle_s20_enabled":'
    )
    with open('handlers/callback_handler.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print("callback_handler.py toggle updated.")
