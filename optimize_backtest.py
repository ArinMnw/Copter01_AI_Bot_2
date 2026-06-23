import re

with open('backtest_runner_mt5.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Replace current_slice = rates[:i] with current_slice = rates[max(0, i-100):i]
content = content.replace(
    'current_slice = rates[:i]',
    'current_slice = rates[max(0, i-100):i]'
)

with open('backtest_runner_mt5.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("backtest_runner_mt5.py optimized.")
