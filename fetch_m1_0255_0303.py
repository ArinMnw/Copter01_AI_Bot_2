import MetaTrader5 as mt5
import datetime
from datetime import timezone, timedelta

# Initialize MT5 connection
if not mt5.initialize():
    print("initialize() failed, error code =", mt5.last_error())
    quit()

# Define BKK timezone
BKK = timezone(timedelta(hours=7))

# Get today's date in BKK
now = datetime.datetime.now(BKK)
# Set start and end times for the desired range 02:55 to 03:03 BKK
start_dt = datetime.datetime(now.year, now.month, now.day, 2, 55, tzinfo=BKK)
end_dt = datetime.datetime(now.year, now.month, now.day, 3, 3, tzinfo=BKK)

# Choose symbol (use first active symbol from config)
from config import SYMBOL_CONFIG
SYMBOL = next(iter(SYMBOL_CONFIG))

# Fetch M1 rates
rates = mt5.copy_rates_range(SYMBOL, mt5.TIMEFRAME_M1, start_dt, end_dt)
if rates is None:
    print("No rates returned, error:", mt5.last_error())
else:
    print(f"Fetched {len(rates)} bars for {SYMBOL} from {start_dt.time()} to {end_dt.time()}")
    for r in rates:
        t = datetime.datetime.fromtimestamp(r['time'], tz=BKK)
        print(f"{t.strftime('%H:%M')} O:{r['open']:.5f} H:{r['high']:.5f} L:{r['low']:.5f} C:{r['close']:.5f}")
        # Simple sweep HH check: if this bar's high > previous bar's high
        # (we will compute after the loop)

# Simple sweep detection
if rates is not None and len(rates) > 1:
    prev_high = rates[0]['high']
    for idx in range(1, len(rates)):
        cur = rates[idx]
        if cur['high'] > prev_high:
            t = datetime.datetime.fromtimestamp(cur['time'], tz=BKK)
            print(f"Sweep HH detected at {t.strftime('%H:%M')} (high {cur['high']:.5f} > previous high {prev_high:.5f})")
        prev_high = max(prev_high, cur['high'])

mt5.shutdown()
