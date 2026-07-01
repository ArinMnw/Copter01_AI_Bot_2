import os
import re

def update_config():
    with open('config.py', 'r', encoding='utf-8') as f:
        data = f.read()

    if 'S20_11_ENABLED' not in data:
        # 1. active_strategies
        data = data.replace(
            "20.10: False, # ท่าที่ 20.10: Allin4s_2 (Reversal Trap)",
            "20.10: False, # ท่าที่ 20.10: Allin4s_2 (Reversal Trap)\n    20.11: False, # ท่าที่ 20.11: Candle Strength"
        )
        
        # 2. STRATEGY_NAMES
        data = data.replace(
            '20.10: "S20.10: Wick Purge",',
            '20.10: "S20.10: Wick Purge",\n    20.11: "S20.11: Candle Strength",'
        )
        
        # 3. config variables
        vars_inject = """S20_11_ENABLED        = False
S20_11_TF_ENABLED     = {"M1": True, "M5": True, "M15": True, "M30": True, "H1": True, "H4": True, "H12": True, "D1": True}
S20_11_COMPOUNDING_ENABLED = False
S20_11_RISK_PCT       = 2.0
S20_11_MAX_LOT        = 50.0
"""
        data = data.replace(
            "S20_10_USE_PSYCHOLOGICAL_NUMBERS = True",
            "S20_10_USE_PSYCHOLOGICAL_NUMBERS = True\n" + vars_inject
        )
        
        # 4. _RUNTIME_DEFAULTS
        defaults_inject = """    "s20_10_use_psychological_numbers": S20_10_USE_PSYCHOLOGICAL_NUMBERS,
    "s20_11_enabled": S20_11_ENABLED,
    "s20_11_tf_enabled": S20_11_TF_ENABLED,
    "s20_11_compounding_enabled": S20_11_COMPOUNDING_ENABLED,
    "s20_11_risk_pct": S20_11_RISK_PCT,
    "s20_11_max_lot": S20_11_MAX_LOT,"""
        data = data.replace(
            '    "s20_10_use_psychological_numbers": S20_10_USE_PSYCHOLOGICAL_NUMBERS,',
            defaults_inject
        )
        
        # 5. save_runtime_state() -> packing
        state_inject = """            "s20_10_max_lot": S20_10_MAX_LOT,
            "s20_10_use_psychological_numbers": S20_10_USE_PSYCHOLOGICAL_NUMBERS,
            "s20_11_enabled": S20_11_ENABLED,
            "s20_11_tf_enabled": S20_11_TF_ENABLED,
            "s20_11_compounding_enabled": S20_11_COMPOUNDING_ENABLED,
            "s20_11_risk_pct": S20_11_RISK_PCT,
            "s20_11_max_lot": S20_11_MAX_LOT,"""
        data = data.replace(
            '            "s20_10_max_lot": S20_10_MAX_LOT,\n            "s20_10_use_psychological_numbers": S20_10_USE_PSYCHOLOGICAL_NUMBERS,',
            state_inject
        )
        
        # 6. restore_runtime_state() -> unpacking
        data = re.sub(
            r'(global .*)\n(\s+S20_10_ENABLED = state\.get\("s20_10_enabled", S20_10_ENABLED\))',
            r'\1, S20_11_ENABLED, S20_11_TF_ENABLED, S20_11_COMPOUNDING_ENABLED, S20_11_RISK_PCT, S20_11_MAX_LOT\n\2\n\2'.replace("S20_10", "S20_11"),
            data
        )
        
        data = re.sub(
            r'(S20_10_MAX_LOT\s*=.*\n)(\s+S20_10_USE_PSYCHOLOGICAL_NUMBERS\s*=.*\n)',
            r'\1\2        S20_11_ENABLED = state.get("s20_11_enabled", S20_11_ENABLED)\n        S20_11_TF_ENABLED = state.get("s20_11_tf_enabled", S20_11_TF_ENABLED)\n        S20_11_COMPOUNDING_ENABLED = state.get("s20_11_compounding_enabled", S20_11_COMPOUNDING_ENABLED)\n        S20_11_RISK_PCT = state.get("s20_11_risk_pct", S20_11_RISK_PCT)\n        S20_11_MAX_LOT = state.get("s20_11_max_lot", S20_11_MAX_LOT)\n',
            data
        )
        # Skip rules
        data = data.replace('20.10, 21}', '20.10, 20.11, 21}')

        with open('config.py', 'w', encoding='utf-8') as f:
            f.write(data)

def update_keyboard():
    with open('handlers/keyboard.py', 'r', encoding='utf-8') as f:
        data = f.read()
    
    if 'cb_toggle_S20_11' not in data:
        btn_s20_11 = """
        [
            InlineKeyboardButton(f"S20.10: Wick Purge {'🟢' if getattr(config, 'S20_10_ENABLED', False) else '🔴'}", callback_data='cb_toggle_S20_10'),
            InlineKeyboardButton(f"S20.11: Candle Str {'🟢' if getattr(config, 'S20_11_ENABLED', False) else '🔴'}", callback_data='cb_toggle_S20_11')
        ],"""
        data = re.sub(r'\[\s*InlineKeyboardButton\(f"S20\.10:.*cb_toggle_S20_10\'\)\s*\],', btn_s20_11, data)
        with open('handlers/keyboard.py', 'w', encoding='utf-8') as f:
            f.write(data)

def update_callback():
    with open('handlers/callback_handler.py', 'r', encoding='utf-8') as f:
        data = f.read()
        
    if "cb_toggle_S20_11" not in data:
        s20_11_logic = """
    elif query.data == 'cb_toggle_S20_11':
        config.S20_11_ENABLED = not getattr(config, 'S20_11_ENABLED', False)
        config.active_strategies[20.11] = config.S20_11_ENABLED
        config.save_runtime_state()
        await query.edit_message_reply_markup(reply_markup=keyboard.get_strategy_menu())"""
        
        data = data.replace(
            "config.save_runtime_state()\n        await query.edit_message_reply_markup(reply_markup=keyboard.get_strategy_menu())",
            "config.save_runtime_state()\n        await query.edit_message_reply_markup(reply_markup=keyboard.get_strategy_menu())" + s20_11_logic,
            1
        )
        with open('handlers/callback_handler.py', 'w', encoding='utf-8') as f:
            f.write(data)

def update_scanner():
    with open('scanner.py', 'r', encoding='utf-8') as f:
        data = f.read()
        
    if 'strategy20_11' not in data:
        data = data.replace(
            'from strategy.s20_10.strategy20_10 import strategy_20_10',
            'from strategy.s20_10.strategy20_10 import strategy_20_10\nfrom strategy.s20_11.strategy20_11 import strategy_20_11'
        )
        
        s20_11_call = """
        if config.active_strategies.get(20.11, False) and getattr(config, 'S20_11_ENABLED', False):
            s20_11_res = strategy_20_11(rates, tf)
            if s20_11_res and s20_11_res.get("signal") in ("BUY", "SELL"):
                best_signal = s20_11_res"""
                
        data = data.replace(
            "if best_signal is None and getattr(config, 'S20_10_ENABLED', False):",
            s20_11_call + "\n\n        if best_signal is None and getattr(config, 'S20_10_ENABLED', False):"
        )
        
        # If replace didn't work (structure might be different), let's fallback:
        if 's20_11_res' not in data:
            data = data.replace(
                "best_signal = s20_10_res",
                "best_signal = s20_10_res\n" + s20_11_call
            )
            
        with open('scanner.py', 'w', encoding='utf-8') as f:
            f.write(data)

os.makedirs('strategy/s20.11', exist_ok=True)
with open('strategy/s20.11/__init__.py', 'w') as f: pass

update_config()
update_keyboard()
update_callback()
update_scanner()
print("Setup script finished.")
