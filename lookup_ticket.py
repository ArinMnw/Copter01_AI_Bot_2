import sys; sys.path.insert(0, ".")
import MetaTrader5 as mt5, config

TICKET = 541881814
mt5.initialize()

print("=== history_deals_get(ticket) ===")
deals = mt5.history_deals_get(ticket=TICKET)
if deals:
    for d in deals:
        print(f"  deal  ticket={d.ticket} order={d.order} symbol={d.symbol} type={d.type} entry={d.entry}"
              f" vol={d.volume} price={d.price} profit={d.profit} comment={d.comment!r}"
              f" time={config.mt5_ts_to_bkk(d.time)}")
else:
    print("  (none)")

print("=== history_orders_get(ticket) ===")
orders = mt5.history_orders_get(ticket=TICKET)
if orders:
    for o in orders:
        print(f"  order ticket={o.ticket} symbol={o.symbol} type={o.type} vol={o.volume_initial}"
              f" open={o.price_open} sl={o.sl} tp={o.tp} comment={o.comment!r}"
              f" setup={config.mt5_ts_to_bkk(o.time_setup)} done={config.mt5_ts_to_bkk(o.time_done)}")
else:
    print("  (none)")

print("=== history_deals_get(position) ===")
pos_deals = mt5.history_deals_get(position=TICKET)
if pos_deals:
    for d in pos_deals:
        print(f"  deal  ticket={d.ticket} entry={d.entry} price={d.price} profit={d.profit}"
              f" comment={d.comment!r} time={config.mt5_ts_to_bkk(d.time)}")
else:
    print("  (none)")

mt5.shutdown()
