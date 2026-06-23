import re

with open('config.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Add 20.5 to active_strategies
content = re.sub(
    r'(20: False,.*?)(\n\})',
    r'\1\n    20.5: True, # S20.5: Fibo Standalone\2',
    content,
    flags=re.DOTALL
)

# Add 20.5 to STRATEGY_NAMES
content = re.sub(
    r'(20: ".*?",?)(\n\})',
    r'\1\n    20.5: "S20.5: Fibo Standalone",\2',
    content,
    flags=re.DOTALL
)

if "S20_5_ENABLED" not in content:
    content = content.replace("S20_HTF_FVG_FILTER = False", "S20_HTF_FVG_FILTER = False\nS20_5_ENABLED = True")

with open('config.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("Config updated.")
