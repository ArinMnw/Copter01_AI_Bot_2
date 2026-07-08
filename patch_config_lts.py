import re

with open('config.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Add to active_strategies
if '"LTS10K": False' not in content and '"LTS10K": True' not in content:
    content = content.replace('"LTS890": False,', '"LTS890": False,\n    "LTS10K": True,')
    content = content.replace('"LTS890": True,', '"LTS890": True,\n    "LTS10K": True,')
    
# Add to DEMO_PORTFOLIO_WEIGHT_ENABLED
if '"LTS10K":' not in content.split('DEMO_PORTFOLIO_WEIGHT_ENABLED = {')[1].split('}')[0]:
    content = content.replace('"LTS890": False', '"LTS890": False, "LTS10K": False')
    content = content.replace('"LTS890": True', '"LTS890": True, "LTS10K": False')

# Add to DEMO_PORTFOLIO_WEIGHT_SCALE
if '"LTS10K":' not in content.split('DEMO_PORTFOLIO_WEIGHT_SCALE = {')[1].split('}')[0]:
    content = content.replace('"LTS890": 1.0', '"LTS890": 1.0, "LTS10K": 1.0')

with open('config.py', 'w', encoding='utf-8') as f:
    f.write(content)
print('config.py updated for LTS10K')
