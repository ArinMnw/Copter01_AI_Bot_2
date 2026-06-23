import re

with open('handlers/callback_handler.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Replace sid = int(data.replace("open_strategy_detail_", ""))
content = content.replace(
    'sid = int(data.replace("open_strategy_detail_", ""))',
    '_sid_val = float(data.replace("open_strategy_detail_", "")); sid = int(_sid_val) if _sid_val.is_integer() else _sid_val'
)

# Replace sid = int(data.split("_")[-1]) under 	oggle_strategy_
content = content.replace(
    'sid = int(data.split("_")[-1])',
    '_sid_val = float(data.split("_")[-1]); sid = int(_sid_val) if _sid_val.is_integer() else _sid_val'
)

with open('handlers/callback_handler.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("callback_handler.py updated.")

