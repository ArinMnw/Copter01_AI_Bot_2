"""
_diag_order.py  — ดึงข้อมูล order/deal จาก MT5 history
"""
import sys
sys.path.insert(0, "D:/Project/Copter01_AI_Bot_2")

import MetaTrader5 as mt5
from datetime import datetime, timedelta, timezone

BKK = timezone(timedelta(hours=7))

def chart_t(ts):
    return datetime.fromtimestamp(int(ts), tz=BKK) - timedelta(hours=1)

ticket = int(sys.argv[1]) if len(sys.argv) > 1 else 532198427

if not mt5.initialize():
    print("MT5 init failed:", mt5.last_error())
    sys.exit(1)

# ดึง deal history (30 วัน)
from_dt = datetime(2026, 5, 1, tzinfo=BKK)
to_dt   = datetime(2026, 6, 1, tzinfo=BKK)
deals = mt5.history_deals_get(from_dt, to_dt)

# ดึง order history
orders = mt5.history_orders_get(from_dt, to_dt)

mt5.shutdown()

# หา deals ที่ position_id == ticket หรือ ticket == ticket
matched_deals = []
if deals:
    for d in deals:
        if d.position_id == ticket or d.ticket == ticket or d.order == ticket:
            matched_deals.append(d)

matched_orders = []
if orders:
    for o in orders:
        if o.ticket == ticket or o.position_id == ticket:
            matched_orders.append(o)

print(f"\n=== Order/Deal info: ticket={ticket} ===")

if matched_orders:
    for o in matched_orders:
        ct_open = chart_t(o.time_setup).strftime("%d/%m %H:%M") if o.time_setup else "-"
        ct_done = chart_t(o.time_done).strftime("%d/%m %H:%M") if o.time_done else "-"
        print(f"\n[Order #{o.ticket}]")
        print(f"  symbol     : {o.symbol}")
        print(f"  type       : {o.type}  ({['BUY','SELL','BUY_LIMIT','SELL_LIMIT','BUY_STOP','SELL_STOP','BUY_STOP_LIMIT','SELL_STOP_LIMIT'][o.type] if o.type < 8 else o.type})")
        print(f"  state      : {o.state}")
        print(f"  volume     : {o.volume_initial}")
        print(f"  price_open : {o.price_open}")
        print(f"  sl / tp    : {o.sl} / {o.tp}")
        print(f"  time_setup : {ct_open}  (chart)")
        print(f"  time_done  : {ct_done}  (chart)")
        print(f"  comment    : {o.comment}")
        print(f"  position_id: {o.position_id}")
else:
    print("  [no orders found]")

if matched_deals:
    for d in matched_deals:
        ct = chart_t(d.time).strftime("%d/%m %H:%M") if d.time else "-"
        print(f"\n[Deal #{d.ticket}]")
        print(f"  symbol     : {d.symbol}")
        print(f"  type       : {d.type}  ({['BUY','SELL','BALANCE','CREDIT','CHARGE','CORRECTION','BONUS','COMMISSION','COMMISSION_DAILY','COMMISSION_MONTHLY','COMMISSION_AGENT_DAILY','COMMISSION_AGENT_MONTHLY','INTEREST','BUY_CANCELED','SELL_CANCELED','DIVIDEND','DIVIDEND_FRANKED','TAX'][d.type] if d.type < 18 else d.type})")
        print(f"  entry      : {d.entry}  ({['IN','OUT','INOUT','OUT_BY'][d.entry] if d.entry < 4 else d.entry})")
        print(f"  volume     : {d.volume}")
        print(f"  price      : {d.price}")
        print(f"  sl / tp    : {getattr(d,'sl','-')} / {getattr(d,'tp','-')}")
        print(f"  profit     : {d.profit}")
        print(f"  time       : {ct}  (chart)")
        print(f"  comment    : {d.comment}")
        print(f"  order      : {d.order}")
        print(f"  position_id: {d.position_id}")
else:
    print("  [no deals found]")
