import re

with open('trailing.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Replace sid tuples to include 20.5
content = content.replace(
    'if sid in (1, 9, 11, 14, 15, 16, 17, 18, 19, 20):',
    'if sid in (1, 9, 11, 14, 15, 16, 17, 18, 19, 20, 20.5):'
)

content = content.replace(
    'if sid in (1, 2, 3, 9, 10, 11, 14, 15, 16, 17, 18, 19, 20):',
    'if sid in (1, 2, 3, 9, 10, 11, 14, 15, 16, 17, 18, 19, 20, 20.5):'
)

content = content.replace(
    'if sid in (1, 2, 3, 9, 10, 11, 14, 15, 17, 18, 19, 20):',
    'if sid in (1, 2, 3, 9, 10, 11, 14, 15, 17, 18, 19, 20, 20.5):'
)

content = content.replace(
    'if sid in (10, 12, 13, 15, 16, 17, 18, 19, 20):',
    'if sid in (10, 12, 13, 15, 16, 17, 18, 19, 20, 20.5):'
)

# Also check for PDFIBOPLUS_SKIP_SIDS. That's in config, let's update it in config.py
with open('trailing.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("trailing.py updated.")

with open('config.py', 'r', encoding='utf-8') as f:
    config_content = f.read()
    
config_content = re.sub(
    r'(PDFIBOPLUS_SKIP_SIDS = \[)(.*?)(\])',
    lambda m: m.group(1) + m.group(2) + (', 20.5' if '20.5' not in m.group(2) else '') + m.group(3),
    config_content
)

with open('config.py', 'w', encoding='utf-8') as f:
    f.write(config_content)
print("config.py PDFIBOPLUS_SKIP_SIDS updated.")
