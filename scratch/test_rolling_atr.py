import MetaTrader5 as mt5
import pandas as pd
import numpy as np
import sys

if not mt5.initialize():
    print("MT5 init failed")
    sys.exit()

sym = "XAUUSD.iux"
rates = mt5.copy_rates_from_pos(sym, mt5.TIMEFRAME_H1, 0, 500)
df = pd.DataFrame(rates)

# Standard H1 ATR
high_low = df['high'] - df['low']
high_close = np.abs(df['high'] - df['close'].shift())
low_close = np.abs(df['low'] - df['close'].shift())
tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
atr_h1 = tr.rolling(14).mean().iloc[-1]

# Dynamic H12 ATR from H1 data
# A 12-hour bar consists of 12 H1 bars.
# Since we don't care about precise 00:00 - 12:00 alignment for volatility,
# a rolling 12-bar window's TR gives us a smoothed 12H volatility.
roll_high = df['high'].rolling(12).max()
roll_low = df['low'].rolling(12).min()
# close shifted by 12 bars represents the previous 12H close
prev_close = df['close'].shift(12)

tr12_1 = roll_high - roll_low
tr12_2 = np.abs(roll_high - prev_close)
tr12_3 = np.abs(roll_low - prev_close)
tr_12 = pd.concat([tr12_1, tr12_2, tr12_3], axis=1).max(axis=1)

# Now take the average of this 12H TR. 
# But wait, 14 periods of 12H bars would span 14*12 = 168 bars.
# So if we average the 12H TR over the last 168 H1 bars:
atr_h12_dynamic = tr_12.rolling(168).mean().iloc[-1]

# Let's compare to actual H12 ATR from MT5
rates12 = mt5.copy_rates_from_pos(sym, mt5.TIMEFRAME_H12, 0, 100)
df12 = pd.DataFrame(rates12)
hl12 = df12['high'] - df12['low']
hc12 = np.abs(df12['high'] - df12['close'].shift())
lc12 = np.abs(df12['low'] - df12['close'].shift())
tr_12_mt5 = pd.concat([hl12, hc12, lc12], axis=1).max(axis=1)
atr_h12_mt5 = tr_12_mt5.rolling(14).mean().iloc[-1]

print(f"H1 ATR: {atr_h1:.3f}")
print(f"Dynamic H12 ATR (Rolling): {atr_h12_dynamic:.3f}")
print(f"MT5 H12 ATR: {atr_h12_mt5:.3f}")
print(f"Implied Multiplier (Dynamic): {atr_h12_dynamic / atr_h1:.3f}")
print(f"Implied Multiplier (MT5): {atr_h12_mt5 / atr_h1:.3f}")

mt5.shutdown()
