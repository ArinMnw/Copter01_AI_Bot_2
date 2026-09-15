import MetaTrader5 as mt5
import json
from datetime import datetime, timedelta

mt5.initialize()

# Load bot_state.json to get S20.16 tickets
try:
    with open('bot_state.json', encoding='utf-8') as f:
        d = json.load(f)
    live_tickets = [t for t, v in d.get('position_sid', {}).items() if str(v) == '20.16']
except:
    live_tickets = []

print(f"--- LIVE S20.16 ORDERS ({len(live_tickets)}) ---")
pos = mt5.positions_get()
for p in pos:
    if str(p.ticket) in live_tickets or str(p.identifier) in live_tickets:
        print(f"Ticket: {p.ticket}, Type: {'BUY' if p.type == 0 else 'SELL'}, Open: {p.price_open}, Current: {p.price_current}, SL: {p.sl}, TP: {p.tp}, Profit: {p.profit}")

print("\n--- CLOSED S20.16 ORDERS (Since Yesterday) ---")
today = datetime.now()
start = today - timedelta(days=1)
deals = mt5.history_deals_get(start, today)

closed_profit = 0
closed_count = 0
win_count = 0
loss_count = 0

if deals:
    for d in deals:
        # Check if this deal corresponds to our S20.16 by checking magic number or comment
        # We know S20.16 comment usually starts with S20.16 or something. Let's just find magic or comment if possible.
        # But wait, MT5 deals have comments. Let's just look at comments containing 20.16
        if d.comment and '20.16' in str(d.comment):
            if d.entry == 1: # DEAL_ENTRY_OUT (closing deal)
                closed_profit += d.profit
                closed_count += 1
                if d.profit > 0: win_count += 1
                elif d.profit < 0: loss_count += 1

print(f"Total Closed: {closed_count}")
print(f"Wins: {win_count}, Losses: {loss_count}")
print(f"Net Profit: ${closed_profit:.2f}")

mt5.shutdown()
