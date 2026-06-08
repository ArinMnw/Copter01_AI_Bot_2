import config
import MetaTrader5 as mt5
from datetime import datetime, timezone, timedelta

SYMBOL = config.SYMBOL

# Bangkok timezone (UTC+7)
BKK_TZ = timezone(timedelta(hours=config.TZ_OFFSET))

now_bkk = datetime.now(BKK_TZ)
# Build start at today 08:55 BKK
start_dt = now_bkk.replace(hour=8, minute=55, second=0, microsecond=0)
end_dt = start_dt + timedelta(minutes=8)  # up to 09:03 inclusive

if not mt5.initialize():
    print("Failed to initialize MT5")
    mt5.shutdown()
    raise SystemExit

# Convert BKK start/end to MT5 server timezone (UTC+6)
server_offset = timedelta(hours=-1)  # BKK is UTC+7, server UTC+6
start_dt_server = start_dt + server_offset
end_dt_server = end_dt + server_offset
rates = mt5.copy_rates_range(SYMBOL, mt5.TIMEFRAME_M1, start_dt_server, end_dt_server)

if rates is None or len(rates) == 0:
    print("No M1 bars found for the specified range.")
else:
    print(f"Fetched {len(rates)} M1 bars from {start_dt} to {end_dt} (BKK)")
    for r in rates:
        ts = datetime.fromtimestamp(r[0], tz=timezone.utc).astimezone(BKK_TZ)
        print(f"Time: {ts.strftime('%H:%M')}, O:{r[1]:.2f}, H:{r[2]:.2f}, L:{r[3]:.2f}, C:{r[4]:.2f}, Vol:{r[5]}")

mt5.shutdown()
