import MetaTrader5 as mt5
import datetime
import config

mt5.initialize()
start = datetime.datetime(2026, 6, 16, 1, 50, 0, tzinfo=datetime.timezone(datetime.timedelta(hours=7)))
end = start + datetime.timedelta(minutes=15)
rates = mt5.copy_rates_range(config.SYMBOL, mt5.TIMEFRAME_M1, start, end)
if rates is not None:
    for r in rates:
        t = datetime.datetime.fromtimestamp(r['time'], tz=datetime.timezone(datetime.timedelta(hours=7))).strftime('%H:%M')
        print(f"{t} O:{r['open']} H:{r['high']} L:{r['low']} C:{r['close']}")
mt5.shutdown()
