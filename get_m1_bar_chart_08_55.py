import config
import MetaTrader5 as mt5
from datetime import datetime, timezone, timedelta

# Use MT5 server timezone (UTC+6) as chart time
SERVER_TZ = timezone(timedelta(hours=config.TZ_OFFSET - 1))  # BKK +7 -> server +6

SYMBOL = config.SYMBOL

now_server = datetime.now(SERVER_TZ)
# Build start at today 08:55 (chart time, i.e., server time)
start_dt = now_server.replace(hour=8, minute=55, second=0, microsecond=0)
end_dt = start_dt + timedelta(minutes=8)  # up to 09:03 inclusive

if not mt5.initialize():
    print("Failed to initialize MT5")
    mt5.shutdown()
    raise SystemExit

rates = mt5.copy_rates_range(SYMBOL, mt5.TIMEFRAME_M1, start_dt, end_dt)
if rates is None or len(rates) == 0:
    print("No M1 bars found for the specified range.")
else:
    print(f"Fetched {len(rates)} M1 bars from {start_dt} to {end_dt} (Server TZ UTC+6)")
    for r in rates:
        # Convert timestamp to server timezone for display
        ts = datetime.fromtimestamp(r[0], tz=timezone.utc).astimezone(SERVER_TZ)
        print(f"Time: {ts.strftime('%H:%M')}, O:{r[1]:.2f}, H:{r[2]:.2f}, L:{r[3]:.2f}, C:{r[4]:.2f}, Vol:{r[5]}")

mt5.shutdown()
