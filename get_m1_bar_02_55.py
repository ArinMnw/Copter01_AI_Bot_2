import config
import MetaTrader5 as mt5
from datetime import datetime, timezone, timedelta

SYMBOL = config.SYMBOL  # assume defined in config

# Define BKK timezone
BKK_TZ = timezone(timedelta(hours=config.TZ_OFFSET))

# Build start and end datetime for today 02:55 – 03:03 BKK
now_bkk = datetime.now(BKK_TZ)
start_dt = now_bkk.replace(hour=2, minute=55, second=0, microsecond=0)
end_dt = start_dt + timedelta(minutes=8)  # 02:55 to 03:03 inclusive

if not mt5.initialize():
    print("Failed to initialize MT5")
    mt5.shutdown()
    raise SystemExit

rates = mt5.copy_rates_range(SYMBOL, mt5.TIMEFRAME_M1, start_dt, end_dt)
if rates is None or len(rates) == 0:
    print("No M1 bars found for the specified range.")
else:
    print(f"Fetched {len(rates)} M1 bars from {start_dt} to {end_dt} (BKK)")
    for r in rates:
        ts = datetime.fromtimestamp(r[0], tz=timezone.utc) + timedelta(hours=config.TZ_OFFSET - config.MT5_SERVER_TZ)
        print(f"Time: {ts.strftime('%H:%M')}, O:{r[1]:.2f}, H:{r[2]:.2f}, L:{r[3]:.2f}, C:{r[4]:.2f}, Vol:{r[5]}")

mt5.shutdown()
