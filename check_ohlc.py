import MetaTrader5 as mt5
from datetime import datetime, timedelta, timezone

mt5.initialize()
BKK = timezone(timedelta(hours=7))
start = datetime(2026,6,16,20,0,tzinfo=BKK)
end = datetime(2026,6,16,21,30,tzinfo=BKK)
rates = mt5.copy_rates_range('XAUUSD.iux', mt5.TIMEFRAME_M1, start, end)
with open('ohlc_dump.txt','w') as f:
    if rates is not None:
        for r in rates:
            t_bkk = datetime.fromtimestamp(r['time'], tz=timezone.utc).astimezone(BKK)
            f.write(f"{t_bkk.strftime('%H:%M')} | O: {r['open']} | H: {r['high']} | L: {r['low']} | C: {r['close']}\n")
mt5.shutdown()
