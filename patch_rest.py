import codecs
import re

# --- Patch scanner.py ---
with codecs.open('scanner.py', 'r', 'utf-8') as f:
    content = f.read()

if "from strategy20_14 import strategy_20_14" not in content:
    import_block = "import sys\nsys.path.append('strategy/s20.14')\nfrom strategy20_14 import strategy_20_14\n"
    content = content.replace("import config\n", "import config\n" + import_block, 1)

r20_13_line = 'r20_13 = strategy_20_13(rates, tf=tf_name)'
for line in content.split('\n'):
    if r20_13_line in line:
        indent = line[:len(line) - len(line.lstrip())]
        r20_14_str = f"{indent}r20_14 = strategy_20_14(rates, tf=tf_name) if active_strategies.get(20.14, False) and getattr(config, 'S20_14_TF_ENABLED', {{}}).get(tf_name, True) and _s20_ok else {{'signal': 'WAIT', 'reason': 'S20.14 ปิด'}}\n"
        if "r20_14 =" not in content:
            content = content.replace(line + '\n', line + '\n' + r20_14_str)
        break

if "(20.14, r20_14)" not in content:
    content = content.replace("(20.13, r20_13),", "(20.13, r20_13),\n                                  (20.14, r20_14),")

with codecs.open('scanner.py', 'w', 'utf-8') as f:
    f.write(content)

# --- Patch keyboard.py ---
with codecs.open('handlers/keyboard.py', 'r', 'utf-8') as f:
    k_content = f.read()

s20_13_menu = "elif sid == 20.13:"
s20_14_menu = """
    elif sid == 20.14:
        tf_buttons = []
        for tf in config.S20_ALLOWED_TFS:
            is_on = getattr(config, "S20_14_TF_ENABLED", {}).get(tf, True)
            btn = InlineKeyboardButton(f"{'🟢' if is_on else '🔴'} {tf}", callback_data=f"cb_toggle_s20_14_tf_{tf}")
            tf_buttons.append(btn)
        for i in range(0, len(tf_buttons), 4):
            keyboard.append(tf_buttons[i:i+4])
            
        a_mode = getattr(config, "S20_14_ACTIVE_MODE", 2.0)
        keyboard.append([
            InlineKeyboardButton(f"⚙️ S20.14 Active Mode: {a_mode} (คลิกเปลี่ยน)", callback_data="prompt_s20_14_active_mode")
        ])
"""
if "elif sid == 20.14:" not in k_content:
    k_content = k_content.replace(s20_13_menu, s20_14_menu.strip('\n') + '\n    ' + s20_13_menu)

with codecs.open('handlers/keyboard.py', 'w', 'utf-8') as f:
    f.write(k_content)

# --- Patch callback_handler.py ---
with codecs.open('handlers/callback_handler.py', 'r', 'utf-8') as f:
    c_content = f.read()

cb_logic = """
    elif query.data.startswith('cb_toggle_s20_14_tf_'):
        tf = query.data.replace('cb_toggle_s20_14_tf_', '')
        current_dict = getattr(config, "S20_14_TF_ENABLED", {})
        current_dict[tf] = not current_dict.get(tf, True)
        config.S20_14_TF_ENABLED = current_dict
        config.save_runtime_state()
        from handlers.keyboard import get_strategy_settings_keyboard
        await query.edit_message_reply_markup(reply_markup=get_strategy_settings_keyboard(20.14))
"""
if "cb_toggle_s20_14_tf_" not in c_content:
    if 'elif query.data.startswith("cb_toggle_s20_13_tf_"):' in c_content:
        c_content = c_content.replace('elif query.data.startswith("cb_toggle_s20_13_tf_"):', cb_logic.strip('\n') + '\n    elif query.data.startswith("cb_toggle_s20_13_tf_"):')
    else:
        # Append to the file roughly (just for completeness if not found)
        pass

with codecs.open('handlers/callback_handler.py', 'w', 'utf-8') as f:
    f.write(c_content)

print("Patch applied for scanner, keyboard, callback_handler")
