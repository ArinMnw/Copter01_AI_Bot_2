import os, re

PROJECT_DIR = r"d:\Project\Copter01_AI_Bot_2"
config_path = os.path.join(PROJECT_DIR, "config.py")

with open(config_path, "r", encoding="utf-8") as f:
    config_content = f.read()

if "S20_13_ACTIVE_MODE" not in config_content:
    config_content = config_content.replace(
        "S20_13_FUEL_MULTIPLIER = 3.42",
        "S20_13_FUEL_MULTIPLIER = 3.42\nS20_13_ACTIVE_MODE = 2.6"
    )
    
    config_content = config_content.replace(
        '"S20_13_FUEL_MULTIPLIER": S20_13_FUEL_MULTIPLIER,',
        '"S20_13_FUEL_MULTIPLIER": S20_13_FUEL_MULTIPLIER,\n        "S20_13_ACTIVE_MODE": S20_13_ACTIVE_MODE,'
    )
    
    config_content = config_content.replace(
        'S20_13_MAX_LOT, S20_13_FUEL_MULTIPLIER',
        'S20_13_MAX_LOT, S20_13_FUEL_MULTIPLIER, S20_13_ACTIVE_MODE'
    )
    
    config_content = config_content.replace(
        'S20_13_FUEL_MULTIPLIER = float(state.get("S20_13_FUEL_MULTIPLIER", S20_13_FUEL_MULTIPLIER))',
        'S20_13_FUEL_MULTIPLIER = float(state.get("S20_13_FUEL_MULTIPLIER", S20_13_FUEL_MULTIPLIER))\n        S20_13_ACTIVE_MODE = float(state.get("S20_13_ACTIVE_MODE", 2.6))'
    )

with open(config_path, "w", encoding="utf-8") as f:
    f.write(config_content)

strat_path = os.path.join(PROJECT_DIR, "strategy", "s20.13", "strategy20_13.py")
with open(strat_path, "r", encoding="utf-8") as f:
    strat = f.read()

strat = strat.replace(
    'fuel = current_bar[\'atr\'] * fuel_multiplier',
    'active_mode = getattr(config, "S20_13_ACTIVE_MODE", 2.6)\n        fuel = current_bar[\'atr\'] * active_mode * fuel_multiplier'
)

with open(strat_path, "w", encoding="utf-8") as f:
    f.write(strat)

print("Patched.")
