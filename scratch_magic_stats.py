import sys
import os
from datetime import datetime, timedelta, timezone
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'strategy'))
from s20_compare_engine import connect_profile_mt5
import MetaTrader5 as mt5

if not connect_profile_mt5('demo-iux-2101183586'):
    print('Failed to connect to 3586')
    sys.exit(1)

BKK = timezone(timedelta(hours=7))
now = datetime.now(BKK)
since = now - timedelta(days=2)

deals = mt5.history_deals_get(since, now)

# Get in deals to map position_id -> magic, comment, symbol
pos_map = {}
if deals:
    for d in deals:
        if d.entry == mt5.DEAL_ENTRY_IN:
            pos_map[d.position_id] = {
                'magic': d.magic,
                'comment': d.comment,
                'symbol': d.symbol,
                'price': d.price,
                'time': d.time
            }

out_deals = [d for d in deals if d.entry == mt5.DEAL_ENTRY_OUT and d.symbol != ""] if deals else []

# Group by magic / parsed strategy
magic_stats = {}
for d in out_deals:
    in_info = pos_map.get(d.position_id, {})
    magic = in_info.get('magic', d.magic)
    comm = in_info.get('comment', d.comment)
    
    # Identify strategy name
    # 990301 -> S20.301, 990302 -> S20.302, etc.
    # or other magic numbers
    label = f"Magic {magic} ({comm})"
    if magic not in magic_stats:
        magic_stats[magic] = {'name': comm, 'wins': 0, 'losses': 0, 'be': 0, 'profit': 0.0, 'symbols': set()}
        
    p = d.profit
    if p > 0.01:
        magic_stats[magic]['wins'] += 1
    elif p < -0.01:
        magic_stats[magic]['losses'] += 1
    else:
        magic_stats[magic]['be'] += 1
    magic_stats[magic]['profit'] += p
    magic_stats[magic]['symbols'].add(d.symbol)

print("\n=== Profit / Loss by Magic Number (last 48h) ===")
for m, v in sorted(magic_stats.items(), key=lambda x: x[1]['profit']):
    tot = v['wins'] + v['losses'] + v['be']
    wr = (v['wins'] / tot * 100) if tot else 0
    syms = ", ".join(list(v['symbols'])[:3])
    print(f"Magic {m:<8d} | Comm: {v['name']:<20s} | Trades: {tot:4d} | W: {v['wins']:3d} | L: {v['losses']:3d} | BE: {v['be']:2d} | WR: {wr:4.1f}% | Net: ${v['profit']:+7.2f} | {syms}")

mt5.shutdown()
