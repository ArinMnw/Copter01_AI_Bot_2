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

orders = mt5.history_orders_get(since, now)
deals = mt5.history_deals_get(since, now)

# Map order ticket to original order comment and magic
order_info = {}
if orders:
    for o in orders:
        order_info[o.ticket] = {
            'magic': o.magic,
            'comment': o.comment,
            'symbol': o.symbol,
            'time_setup': o.time_setup,
            'volume': o.volume_initial
        }

# Process closed deals
out_deals = [d for d in deals if d.entry == mt5.DEAL_ENTRY_OUT and d.symbol != ""] if deals else []

print(f"Total out deals: {len(out_deals)}")

# Breakdown by Magic / Original Comment / Symbol / TF
strat_stats = {}
symbol_stats = {}
tf_stats = {}

for d in out_deals:
    orig = order_info.get(d.order, {})
    magic = orig.get('magic', d.magic)
    orig_comm = orig.get('comment', '')
    sym = d.symbol
    
    # parse timeframe from comment or magic
    # S20.301-304 magic: 990301-990304 or similar, comment often like S20.301_M5 or similar
    strat_key = orig_comm if orig_comm else f"magic_{magic}"
    
    if strat_key not in strat_stats:
        strat_stats[strat_key] = {'wins': 0, 'losses': 0, 'be': 0, 'profit': 0.0}
    if sym not in symbol_stats:
        symbol_stats[sym] = {'wins': 0, 'losses': 0, 'be': 0, 'profit': 0.0}
        
    p = d.profit
    if p > 0.01:
        strat_stats[strat_key]['wins'] += 1
        symbol_stats[sym]['wins'] += 1
    elif p < -0.01:
        strat_stats[strat_key]['losses'] += 1
        symbol_stats[sym]['losses'] += 1
    else:
        strat_stats[strat_key]['be'] += 1
        symbol_stats[sym]['be'] += 1
        
    strat_stats[strat_key]['profit'] += p
    symbol_stats[sym]['profit'] += p

print("\n=== Profit / Loss by Symbol (last 48h) ===")
for sym, v in sorted(symbol_stats.items(), key=lambda x: x[1]['profit'], reverse=True):
    tot = v['wins'] + v['losses'] + v['be']
    wr = (v['wins'] / tot * 100) if tot else 0
    print(f"{sym:12s} | Trades: {tot:4d} | W: {v['wins']:3d} | L: {v['losses']:3d} | BE: {v['be']:2d} | WR: {wr:4.1f}% | Net: ${v['profit']:+7.2f}")

print("\n=== Top 20 Strategies / Comments (last 48h) ===")
for k, v in sorted(strat_stats.items(), key=lambda x: x[1]['profit']):
    tot = v['wins'] + v['losses'] + v['be']
    wr = (v['wins'] / tot * 100) if tot else 0
    print(f"{k:35s} | Trades: {tot:4d} | W: {v['wins']:3d} | L: {v['losses']:3d} | BE: {v['be']:2d} | WR: {wr:4.1f}% | Net: ${v['profit']:+7.2f}")

# Look at distribution of losses
loss_amounts = [d.profit for d in out_deals if d.profit < -0.01]
win_amounts = [d.profit for d in out_deals if d.profit > 0.01]

if loss_amounts:
    print(f"\nLoss summary: count={len(loss_amounts)}, min={min(loss_amounts):.2f}, max={max(loss_amounts):.2f}, avg={sum(loss_amounts)/len(loss_amounts):.2f}")
if win_amounts:
    print(f"Win summary: count={len(win_amounts)}, min={min(win_amounts):.2f}, max={max(win_amounts):.2f}, avg={sum(win_amounts)/len(win_amounts):.2f}")

mt5.shutdown()
