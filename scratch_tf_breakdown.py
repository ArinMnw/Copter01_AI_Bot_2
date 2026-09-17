import sys
import os
import re
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

# Breakdown by (Strategy, Timeframe) and Symbol
by_tf = {}
by_strat = {}
by_sym = {}

for d in out_deals:
    in_info = pos_map.get(d.position_id, {})
    comm = in_info.get('comment', 'unknown')
    sym = d.symbol.replace('.iux', '')
    
    # Parse TF and Strategy from comment like "M1_S20.301" or "[M5]_S20.304" or similar
    # Format: {TF}_{STRAT}
    parts = comm.split('_')
    tf = parts[0] if len(parts) > 0 else "unknown"
    strat = parts[1] if len(parts) > 1 else comm
    
    # Clean up
    tf = tf.strip('[]')
    strat = strat.strip()
    
    p = d.profit
    
    # TF bucket
    if tf not in by_tf:
        by_tf[tf] = {'trades': 0, 'w': 0, 'l': 0, 'be': 0, 'net': 0.0}
    by_tf[tf]['trades'] += 1
    if p > 0.01:
        by_tf[tf]['w'] += 1
    elif p < -0.01:
        by_tf[tf]['l'] += 1
    else:
        by_tf[tf]['be'] += 1
    by_tf[tf]['net'] += p

    # Strat bucket
    if strat not in by_strat:
        by_strat[strat] = {'trades': 0, 'w': 0, 'l': 0, 'be': 0, 'net': 0.0}
    by_strat[strat]['trades'] += 1
    if p > 0.01:
        by_strat[strat]['w'] += 1
    elif p < -0.01:
        by_strat[strat]['l'] += 1
    else:
        by_strat[strat]['be'] += 1
    by_strat[strat]['net'] += p

    # Sym bucket
    if sym not in by_sym:
        by_sym[sym] = {'trades': 0, 'w': 0, 'l': 0, 'be': 0, 'net': 0.0}
    by_sym[sym]['trades'] += 1
    if p > 0.01:
        by_sym[sym]['w'] += 1
    elif p < -0.01:
        by_sym[sym]['l'] += 1
    else:
        by_sym[sym]['be'] += 1
    by_sym[sym]['net'] += p

print("=== Breakdown by Timeframe (48h) ===")
for tf, v in sorted(by_tf.items(), key=lambda x: x[1]['net']):
    wr = (v['w'] / v['trades'] * 100) if v['trades'] else 0
    print(f"TF: {tf:<8s} | Trades: {v['trades']:4d} | W: {v['w']:3d} | L: {v['l']:3d} | BE: {v['be']:2d} | WR: {wr:4.1f}% | Net: ${v['net']:+7.2f}")

print("\n=== Breakdown by Strategy Variant (48h) ===")
for st, v in sorted(by_strat.items(), key=lambda x: x[1]['net']):
    wr = (v['w'] / v['trades'] * 100) if v['trades'] else 0
    print(f"Strat: {st:<12s} | Trades: {v['trades']:4d} | W: {v['w']:3d} | L: {v['l']:3d} | BE: {v['be']:2d} | WR: {wr:4.1f}% | Net: ${v['net']:+7.2f}")

print("\n=== Breakdown by Symbol (48h) ===")
for sym, v in sorted(by_sym.items(), key=lambda x: x[1]['net']):
    wr = (v['w'] / v['trades'] * 100) if v['trades'] else 0
    print(f"Symbol: {sym:<8s} | Trades: {v['trades']:4d} | W: {v['w']:3d} | L: {v['l']:3d} | BE: {v['be']:2d} | WR: {wr:4.1f}% | Net: ${v['net']:+7.2f}")

mt5.shutdown()
