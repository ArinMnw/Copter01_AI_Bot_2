import MetaTrader5 as mt5
import config
from datetime import datetime, timedelta, timezone

config.mt5_initialize(mt5)
BKK = timezone(timedelta(hours=7))
start = datetime(2026,6,15,20,0,tzinfo=BKK)
end = datetime(2026,6,15,21,30,tzinfo=BKK)
rates = mt5.copy_rates_range(config.SYMBOL, mt5.TIMEFRAME_M1, start, end)
with open('ohlc_dump_15.txt','w') as f:
    if rates is not None:
        for r in rates:
            t_bkk = datetime.fromtimestamp(r['time'], tz=timezone.utc).astimezone(BKK)
            f.write(f"{t_bkk.strftime('%H:%M')} | O: {r['open']} | H: {r['high']} | L: {r['low']} | C: {r['close']}\n")
mt5.shutdown()
