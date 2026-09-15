import MetaTrader5 as mt5
import json
import datetime
from zoneinfo import ZoneInfo

mt5.initialize()

s2016_tickets = ['583326569', '583349806', '583350804', '583353404', '583355810', '583365271', '583365946', '583366384', '583371229']

print("--- HISTORY ORDERS ---")
today = datetime.datetime.now()
start = today - datetime.timedelta(days=2)
h_ords = mt5.history_orders_get(start, today)
if h_ords:
    for o in h_ords:
        if str(o.ticket) in s2016_tickets:
            print(f"Ticket: {o.ticket}, Time: {o.time_setup}, State: {o.state}, Price Open: {o.price_open}, SL: {o.sl}, TP: {o.tp}")

mt5.shutdown()
