import MetaTrader5 as mt5
import sys
import os

if not mt5.initialize():
    print("MT5 init failed")
    sys.exit()

symbols = mt5.symbols_get()
names = [s.name for s in symbols if "BTC" in s.name or "ETH" in s.name or "XAU" in s.name]
print("Found symbols:", names[:20])
mt5.shutdown()
