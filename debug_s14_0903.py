import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import MetaTrader5 as mt5
from datetime import datetime, timezone, timedelta
import config
from strategy14 import strategy_14

# Parameters
SYMBOL = config.SYMBOL

# Define window in Bangkok time (UTC+7)
start_bkk = datetime(2026, 6, 5, 9, 0, tzinfo=timezone(timedelta(hours=7)))
end_bkk   = datetime(2026, 6, 5, 9, 10, tzinfo=timezone(timedelta(hours=7)))
# Convert to UTC for MT5
start_utc = start_bkk - timedelta(hours=7)
end_utc   = end_bkk   - timedelta(hours=7)

if not mt5.initialize():
    print('MT5 init failed:', mt5.last_error())
    sys.exit(1)

# Fetch M1 rates for the window (add extra bars for lookback)
lookback_extra = 100  # enough for S14 lookback
rates = mt5.copy_rates_range(SYMBOL, mt5.TIMEFRAME_M1, start_utc, end_utc)
if rates is None or len(rates) == 0:
    print('No rates fetched')
    mt5.shutdown()
    sys.exit(1)

# Convert to list of dicts for easier handling
bars = [ {'time':int(r['time']),'open':float(r['open']),'high':float(r['high']),'low':float(r['low']),'close':float(r['close'])} for r in rates ]

# We need a longer history for lookback, so fetch earlier data as well
extra_needed = 200  # enough for lookback + period
earlier = mt5.copy_rates_from_pos(SYMBOL, mt5.TIMEFRAME_M1, 0, extra_needed)
if earlier is None:
    earlier = []
else:
    earlier = [ {'time':int(r['time']),'open':float(r['open']),'high':float(r['high']),'low':float(r['low']),'close':float(r['close'])} for r in earlier ]
# Combine, ensuring chronological order (oldest first)
all_rates = earlier + bars

# Scan each bar as reject (i.e., treat each as the last bar of a window)
found = False
for i in range(len(all_rates)):
    window = all_rates[:i+1]  # rates up to current bar
    result = strategy_14(window, tf='M1')
    if result.get('signal') not in ('WAIT',):
        # Identify timestamp of reject bar
        reject_time = datetime.fromtimestamp(window[-1]['time'], tz=timezone.utc) + timedelta(hours=7)
        if start_bkk <= reject_time <= end_bkk:
            print('Found signal at', reject_time.strftime('%Y-%m-%d %H:%M'), result)
            found = True

mt5.shutdown()
if not found:
    print('No S14 signal in the 09:00-09:10 window')
