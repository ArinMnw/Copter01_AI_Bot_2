import MetaTrader5 as mt5
from datetime import datetime, timedelta, timezone
import pytz

mt5.initialize()
bkk_tz = pytz.timezone('Asia/Bangkok')
end_dt = bkk_tz.localize(datetime.now()).astimezone(timezone.utc)
start_dt = end_dt - timedelta(days=3)
orders = mt5.history_orders_get(start_dt, end_dt)

if orders:
    for o in orders[-50:]:
        time_str = datetime.fromtimestamp(o.time_done, tz=timezone.utc).astimezone(bkk_tz).strftime('%Y-%m-%d %H:%M:%S') if o.time_done else 'Not Done'
        print(f"{o.ticket} | {o.symbol} | {o.comment} | {time_str} | {o.price_open}")
else:
    print('no orders')
