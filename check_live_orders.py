import MetaTrader5 as mt5
import json
import datetime
from zoneinfo import ZoneInfo

mt5.initialize()

s2016_tickets = ['583326569', '583349806', '583350804', '583353404', '583355810', '583365271', '583365946', '583366384', '583371229']

print("--- PENDING ORDERS ---")
ords = mt5.orders_get()
if ords:
    for o in ords:
        if str(o.ticket) in s2016_tickets:
            print(f"Ticket: {o.ticket}, Type: {o.type}, State: {o.state}, Price Open: {o.price_open}, SL: {o.sl}, TP: {o.tp}")

print("--- OPEN POSITIONS ---")
pos = mt5.positions_get()
if pos:
    for p in pos:
        if str(p.ticket) in s2016_tickets or str(p.identifier) in s2016_tickets:
            print(f"Ticket: {p.ticket}, Price Open: {p.price_open}, SL: {p.sl}, TP: {p.tp}")

mt5.shutdown()
