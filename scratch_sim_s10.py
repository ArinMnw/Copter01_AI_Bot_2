import MetaTrader5 as mt5
import datetime
import config
from strategy10 import _strategy_10_mtf, reset_mtf_state

mt5.initialize()

# Simulate S10 from 00:00 BKK to 03:00 BKK on June 16, 2026
start_time = datetime.datetime(2026, 6, 16, 0, 0, 0, tzinfo=datetime.timezone(datetime.timedelta(hours=7)))
end_time = datetime.datetime(2026, 6, 16, 3, 0, 0, tzinfo=datetime.timezone(datetime.timedelta(hours=7)))

rates_m1 = mt5.copy_rates_range(config.SYMBOL, mt5.TIMEFRAME_M1, start_time, end_time)
rates_h1 = mt5.copy_rates_range(config.SYMBOL, mt5.TIMEFRAME_H1, start_time - datetime.timedelta(hours=24), end_time)

bars_m1 = [{'time': int(r['time']), 'open': float(r['open']), 'high': float(r['high']), 'low': float(r['low']), 'close': float(r['close'])} for r in rates_m1]
bars_h1 = [{'time': int(r['time']), 'open': float(r['open']), 'high': float(r['high']), 'low': float(r['low']), 'close': float(r['close'])} for r in rates_h1]

reset_mtf_state()

for i in range(len(bars_h1)):
    if bars_h1[i]['time'] > end_time.timestamp(): break
    res = _strategy_10_mtf(bars_h1[:i+1], "H1")
    if res and res.get("signal") in ("BUY", "SELL"):
        print(f"H1 Armed at {datetime.datetime.fromtimestamp(bars_h1[i]['time']).strftime('%H:%M')}: {res}")

for i in range(10, len(bars_m1)):
    res = _strategy_10_mtf(bars_m1[:i+1], "M1")
    if res and res.get("signal") in ("BUY", "SELL"):
        print(f"M1 Trigger at {datetime.datetime.fromtimestamp(bars_m1[i]['time']).strftime('%H:%M')}:")
        print(res['reason'])
        print(f"Entry: {res['entry']}, SL: {res['sl']}, TP: {res['tp']}")
        break
    # elif res: print(res.get('reason'))

print("Simulation finished.")
mt5.shutdown()
