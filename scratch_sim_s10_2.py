import MetaTrader5 as mt5
import datetime
import config
from strategy10 import _strategy_10_mtf, reset_mtf_state

mt5.initialize()

start_time = datetime.datetime.strptime("2026-06-16 08:00", "%Y-%m-%d %H:%M").replace(tzinfo=datetime.timezone(datetime.timedelta(hours=7)))
end_time = datetime.datetime.strptime("2026-06-16 10:10", "%Y-%m-%d %H:%M").replace(tzinfo=datetime.timezone(datetime.timedelta(hours=7)))

rates_ltf = mt5.copy_rates_range(config.SYMBOL, mt5.TIMEFRAME_M1, start_time, end_time)
rates_htf = mt5.copy_rates_range(config.SYMBOL, mt5.TIMEFRAME_H1, start_time - datetime.timedelta(hours=24), end_time)

bars_ltf = [{'time': int(r['time']), 'open': float(r['open']), 'high': float(r['high']), 'low': float(r['low']), 'close': float(r['close'])} for r in rates_ltf]
bars_htf = [{'time': int(r['time']), 'open': float(r['open']), 'high': float(r['high']), 'low': float(r['low']), 'close': float(r['close'])} for r in rates_htf]

reset_mtf_state()
for i in range(len(bars_htf)):
    if bars_htf[i]['time'] > end_time.timestamp(): break
    _strategy_10_mtf(bars_htf[:i+1], "H1")

for i in range(10, len(bars_ltf)):
    t_str = datetime.datetime.fromtimestamp(bars_ltf[i]['time'], tz=datetime.timezone(datetime.timedelta(hours=7))).strftime('%H:%M')
    if t_str >= "09:55":
        res = _strategy_10_mtf(bars_ltf[:i+1], "M1")
        print(f"Time {t_str}: {res}")

mt5.shutdown()
