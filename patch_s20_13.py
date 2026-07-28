import re
import os

PROJECT_DIR = r"d:\Project\Copter01_AI_Bot_2"

# 1. Update config.py
config_path = os.path.join(PROJECT_DIR, "config.py")
with open(config_path, "r", encoding="utf-8") as f:
    config_content = f.read()

# Replace 20.12, 21 with 20.12, 20.13, 21
config_content = config_content.replace("20.12, 21", "20.12, 20.13, 21")

# Add new variables if not present
if "S20_13_ENABLED" not in config_content:
    s20_13_vars = """
# S20.13 Quant Fuel (Quant Sniper Fuel)
S20_13_ENABLED = False
S20_13_TF_ENABLED = {"M1": True, "M5": True, "M15": True, "M30": True, "H1": True, "H4": True, "H12": True, "D1": True}
S20_13_COMPOUNDING_ENABLED = False
S20_13_RISK_PCT = 1.0
S20_13_MAX_LOT = 1.0
S20_13_FUEL_MULTIPLIER = 3.42
"""
    # Insert before active_strategies or at a safe place, maybe just append to the config.py before def save_runtime_state
    # Let's find save_runtime_state
    if "def save_runtime_state(" in config_content:
        config_content = config_content.replace("def save_runtime_state(", s20_13_vars + "\ndef save_runtime_state(")
    else:
        config_content += s20_13_vars

# Add to save_runtime_state
save_pattern = r'("S20_12_MAX_LOT": S20_12_MAX_LOT,)'
save_repl = r'\1\n        "S20_13_ENABLED": S20_13_ENABLED,\n        "S20_13_TF_ENABLED": S20_13_TF_ENABLED,\n        "S20_13_COMPOUNDING_ENABLED": S20_13_COMPOUNDING_ENABLED,\n        "S20_13_RISK_PCT": S20_13_RISK_PCT,\n        "S20_13_MAX_LOT": S20_13_MAX_LOT,\n        "S20_13_FUEL_MULTIPLIER": S20_13_FUEL_MULTIPLIER,'
config_content = re.sub(save_pattern, save_repl, config_content)

# Add to restore_runtime_state
restore_pattern = r'(global S20_12_ENABLED, S20_12_TF_ENABLED, S20_12_COMPOUNDING_ENABLED, S20_12_RISK_PCT, S20_12_MAX_LOT)'
restore_repl = r'\1, S20_13_ENABLED, S20_13_TF_ENABLED, S20_13_COMPOUNDING_ENABLED, S20_13_RISK_PCT, S20_13_MAX_LOT, S20_13_FUEL_MULTIPLIER'
config_content = re.sub(restore_pattern, restore_repl, config_content)

restore_assign_pattern = r'(S20_12_MAX_LOT = float\(state\.get\("S20_12_MAX_LOT", S20_12_MAX_LOT\)\))'
restore_assign_repl = r'\1\n        S20_13_ENABLED = bool(state.get("S20_13_ENABLED", S20_13_ENABLED))\n        S20_13_TF_ENABLED = state.get("S20_13_TF_ENABLED", S20_13_TF_ENABLED)\n        S20_13_COMPOUNDING_ENABLED = bool(state.get("S20_13_COMPOUNDING_ENABLED", S20_13_COMPOUNDING_ENABLED))\n        S20_13_RISK_PCT = float(state.get("S20_13_RISK_PCT", S20_13_RISK_PCT))\n        S20_13_MAX_LOT = float(state.get("S20_13_MAX_LOT", S20_13_MAX_LOT))\n        S20_13_FUEL_MULTIPLIER = float(state.get("S20_13_FUEL_MULTIPLIER", S20_13_FUEL_MULTIPLIER))'
config_content = re.sub(restore_assign_pattern, restore_assign_repl, config_content)

with open(config_path, "w", encoding="utf-8") as f:
    f.write(config_content)


# 2. Update scanner.py
scanner_path = os.path.join(PROJECT_DIR, "scanner.py")
with open(scanner_path, "r", encoding="utf-8") as f:
    scanner_content = f.read()

# Add import
if "from strategy20_13 import strategy_20_13" not in scanner_content:
    import_stmt = """sys.path.append(os.path.join(os.path.dirname(__file__), "strategy", "s20.13"))
try:
    from strategy20_13 import strategy_20_13
except ImportError:
    def strategy_20_13(*args, **kwargs):
        return {"signal": "WAIT", "reason": "S20_13 module not found"}
"""
    scanner_content = scanner_content.replace("from strategy20_12 import strategy_20_12", "from strategy20_12 import strategy_20_12\n" + import_stmt)

# Add logic
logic_stmt = """            if config.S20_13_ENABLED and config.S20_13_TF_ENABLED.get(tf_name, False):
                try:
                    r20_13 = strategy_20_13(rates, tf=tf_name)
                    if r20_13 and r20_13.get("signal") in ("BUY", "SELL"):
                        _results.append((20.13, r20_13))
                except Exception as e:
                    from bot_log import log_error
                    log_error("S20_13_SCAN_ERROR", str(e), tf=tf_name)
"""
if "strategy_20_13(" not in scanner_content:
    scanner_content = scanner_content.replace("if config.S20_12_ENABLED and config.S20_12_TF_ENABLED.get(tf_name, False):", logic_stmt + "\n            if config.S20_12_ENABLED and config.S20_12_TF_ENABLED.get(tf_name, False):")

with open(scanner_path, "w", encoding="utf-8") as f:
    f.write(scanner_content)


# 3. Update keyboard.py
keyboard_path = os.path.join(PROJECT_DIR, "handlers", "keyboard.py")
with open(keyboard_path, "r", encoding="utf-8") as f:
    keyboard_content = f.read()

# Add S20_13 button
kb_stmt = """        [
            InlineKeyboardButton(f"[{'ON' if config.S20_13_ENABLED else 'OFF'}] S20.13: Quant Fuel", callback_data='toggle_s20_13'),
            InlineKeyboardButton("⚙️ ตั้งค่า", callback_data='settings_s20_13')
        ],"""
if "toggle_s20_13" not in keyboard_content:
    keyboard_content = keyboard_content.replace("[InlineKeyboardButton(f\"[{'ON' if getattr(config, 'S20_12_ENABLED', False) else 'OFF'}] S20.12: FVG Flow Setup\", callback_data='toggle_s20_12'),", kb_stmt + "\n        [InlineKeyboardButton(f\"[{'ON' if getattr(config, 'S20_12_ENABLED', False) else 'OFF'}] S20.12: FVG Flow Setup\", callback_data='toggle_s20_12'),")
    
# Add S20_13 settings menu
if "def get_s20_13_settings_keyboard()" not in keyboard_content:
    settings_menu = """
def get_s20_13_settings_keyboard():
    tfs = ["M1", "M5", "M15", "M30", "H1", "H4", "H12", "D1"]
    keyboard = []
    
    row = []
    for tf in tfs[:4]:
        state = "🟢" if config.S20_13_TF_ENABLED.get(tf) else "🔴"
        row.append(InlineKeyboardButton(f"{state} {tf}", callback_data=f"toggle_s20_13_tf_{tf}"))
    keyboard.append(row)
    
    row2 = []
    for tf in tfs[4:]:
        state = "🟢" if config.S20_13_TF_ENABLED.get(tf) else "🔴"
        row2.append(InlineKeyboardButton(f"{state} {tf}", callback_data=f"toggle_s20_13_tf_{tf}"))
    keyboard.append(row2)

    comp_state = "🟢 ON" if config.S20_13_COMPOUNDING_ENABLED else "🔴 OFF"
    keyboard.append([InlineKeyboardButton(f"Compounding: {comp_state}", callback_data="toggle_s20_13_compound")])
    keyboard.append([
        InlineKeyboardButton(f"Risk: {config.S20_13_RISK_PCT}%", callback_data="set_s20_13_risk"),
        InlineKeyboardButton(f"Max Lot: {config.S20_13_MAX_LOT}", callback_data="set_s20_13_max_lot")
    ])
    keyboard.append([InlineKeyboardButton("🔙 กลับ", callback_data='menu_strategy')])
    return InlineKeyboardMarkup(keyboard)
"""
    keyboard_content += settings_menu

with open(keyboard_path, "w", encoding="utf-8") as f:
    f.write(keyboard_content)


# 4. Update callback_handler.py
callback_path = os.path.join(PROJECT_DIR, "handlers", "callback_handler.py")
with open(callback_path, "r", encoding="utf-8") as f:
    callback_content = f.read()

# Add logic for toggle_s20_13
cb_logic = """
    elif data == 'toggle_s20_13':
        config.S20_13_ENABLED = not config.S20_13_ENABLED
        config.save_runtime_state()
        from handlers.keyboard import get_strategy_keyboard
        await query.edit_message_reply_markup(reply_markup=get_strategy_keyboard())
    elif data == 'settings_s20_13':
        from handlers.keyboard import get_s20_13_settings_keyboard
        await query.edit_message_text("⚙️ **ตั้งค่า S20.13 Quant Fuel**\\nเลือกเปิด/ปิด TF และตั้งค่า MM:", reply_markup=get_s20_13_settings_keyboard(), parse_mode='Markdown')
    elif data.startswith('toggle_s20_13_tf_'):
        tf = data.replace('toggle_s20_13_tf_', '')
        config.S20_13_TF_ENABLED[tf] = not config.S20_13_TF_ENABLED.get(tf, False)
        config.save_runtime_state()
        from handlers.keyboard import get_s20_13_settings_keyboard
        await query.edit_message_reply_markup(reply_markup=get_s20_13_settings_keyboard())
    elif data == 'toggle_s20_13_compound':
        config.S20_13_COMPOUNDING_ENABLED = not config.S20_13_COMPOUNDING_ENABLED
        config.save_runtime_state()
        from handlers.keyboard import get_s20_13_settings_keyboard
        await query.edit_message_reply_markup(reply_markup=get_s20_13_settings_keyboard())
"""
if "toggle_s20_13" not in callback_content:
    callback_content = callback_content.replace("elif data == 'toggle_s20_12':", cb_logic.strip() + "\n    elif data == 'toggle_s20_12':")

with open(callback_path, "w", encoding="utf-8") as f:
    f.write(callback_content)

print("Patch applied successfully.")
