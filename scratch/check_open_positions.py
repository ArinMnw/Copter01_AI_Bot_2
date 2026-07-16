import MetaTrader5 as mt5
import os
import sys

sys_path = r"d:\Project\Copter01_AI_Bot_2\profiles\demo\demo-exness-416010472\mt5\terminal64.exe"

if not mt5.initialize(path=sys_path, portable=True):
    print("MT5 Initialization FAILED")
    sys.exit(1)
    
print("Connected to Exness account:", mt5.account_info().login)

open_positions = mt5.positions_get(symbol="XAUUSD")
print(f"Total open positions on XAUUSD: {len(open_positions) if open_positions else 0}")

if open_positions:
    for i, p in enumerate(open_positions):
        print(f"{i+1}. Ticket: {p.ticket} | Type: {p.type} | Volume: {p.volume} | Price: {p.price_open} | Profit: {p.profit} | Magic: {p.magic} | Comment: {p.comment}")

mt5.shutdown()
