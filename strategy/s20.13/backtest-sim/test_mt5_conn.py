import MetaTrader5 as mt5
from datetime import datetime, timedelta

path = r'd:\Project\Copter01_AI_Bot_2\profiles\demo\demo-iux-2101114448\mt5\terminal64.exe'
mt5.initialize(path=path)

for n in [1000, 2000, 3000, 3600, 5000, 10000]:
    r = mt5.copy_rates_from_pos('XAUUSD.iux', mt5.TIMEFRAME_H1, 0, n)
    print(f"from_pos({n}): {len(r) if r is not None else 0}")

end = datetime.now()
start = end - timedelta(days=150)
r_range = mt5.copy_rates_range('XAUUSD.iux', mt5.TIMEFRAME_H1, start, end)
print(f"copy_rates_range(150 days): {len(r_range) if r_range is not None else 0}")

mt5.shutdown()
