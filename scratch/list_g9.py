import MetaTrader5 as mt5
import pytz
from datetime import datetime, timedelta, timezone

mt5.initialize()
bkk_tz = pytz.timezone('Asia/Bangkok')
start_dt = datetime.now(timezone.utc) - timedelta(days=10)
end_dt = datetime.now(timezone.utc)

orders = mt5.history_orders_get(start_dt, end_dt)
matching = [o for o in (orders or []) if 'S20.149' in (o.comment or '')]

for o in matching:
    time_str = datetime.fromtimestamp(o.time_done, tz=timezone.utc).astimezone(bkk_tz).strftime('%Y-%m-%d %H:%M:%S') if o.time_done else 'Not Done'
    print(f"{o.ticket} | {time_str} | {o.price_open}")
