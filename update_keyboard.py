import re

with open('handlers/keyboard.py', 'r', encoding='utf-8') as f:
    content = f.read()

s20_5_block = '''
    elif sid == 20.5:
        s20_5_en = getattr(config, "S20_5_ENABLED", False)
        rows.append([
            InlineKeyboardButton(
                f"{'🟢' if s20_5_en else '🔴'} Fibo Standalone",
                callback_data="toggle_s20_5_enabled"
            )
        ])
'''

if 'elif sid == 20.5:' not in content:
    content = content.replace(
        'elif sid == 20:',
        s20_5_block + '\n    elif sid == 20:'
    )

    with open('handlers/keyboard.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print("keyboard.py updated.")
