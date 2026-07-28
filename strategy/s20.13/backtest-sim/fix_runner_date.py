with open('d:\\Project\\Copter01_AI_Bot_2\\strategy\\s20.13\\backtest-sim\\backtest_s20_13_17_runner.py', 'r', encoding='utf-8') as f:
    text = f.read()

text = text.replace('end = datetime(2026, 7, 24, 12, 40, 0)', 'end = datetime.now()')

with open('d:\\Project\\Copter01_AI_Bot_2\\strategy\\s20.13\\backtest-sim\\backtest_s20_13_17_runner.py', 'w', encoding='utf-8') as f:
    f.write(text)
print("Updated end to datetime.now()")
