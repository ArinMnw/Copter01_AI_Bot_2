import config
import MetaTrader5 as mt5
from datetime import datetime, timezone, timedelta

# Use MT5 server timezone (UTC+6)
SERVER_TZ = timezone(timedelta(hours=config.TZ_OFFSET - 1))  # BKK+7 -> server+6

SYMBOL = config.SYMBOL

# Current time in server timezone
now_server = datetime.now(SERVER_TZ)
# Define the range 08:55 to 09:03 server time (which corresponds to the chart range the user mentions)
start_dt = now_server.replace(hour=8, minute=55, second=0, microsecond=0)
end_dt = start_dt + timedelta(minutes=8)  # inclusive up to 09:03

if not mt5.initialize():
    print("Failed to initialize MT5")
    mt5.shutdown()
    raise SystemExit

rates = mt5.copy_rates_range(SYMBOL, mt5.TIMEFRAME_M1, start_dt, end_dt)
if rates is None or len(rates) == 0:
    print("No M1 bars found for the specified range.")
    mt5.shutdown()
    raise SystemExit

# Extract high values for the first and last bar
first_bar = rates[0]
last_bar = rates[-1]
first_high = float(first_bar[2])
last_high = float(last_bar[2])

print(f"First bar (08:55)  High: {first_high:.2f}")
print(f"Last bar  (09:03)  High: {last_high:.2f}")

if last_high > first_high:
    print("Sweep HH detected: High at 09:03 is higher than High at 08:55")
else:
    print("❌ No Sweep HH: High at 09:03 is not higher than High at 08:55")

mt5.shutdown()
