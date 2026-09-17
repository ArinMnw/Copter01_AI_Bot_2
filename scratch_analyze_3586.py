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
# ดูย้อนหลัง 24 ชม หรือตั้งแต่เริ่มรันเมื่อวาน
since = now - timedelta(days=2)

acc = mt5.account_info()
print(f"=== Account {acc.login} ===")
print(f"Balance: ${acc.balance:.2f} | Equity: ${acc.equity:.2f} | Profit: ${acc.profit:+.2f}")

deals = mt5.history_deals_get(since, now)
if deals:
    out_deals = [d for d in deals if d.entry == mt5.DEAL_ENTRY_OUT]
    # filter out balance deposit/withdrawal
    out_deals = [d for d in out_deals if d.symbol != ""]
    
    print(f"\n--- Closed Trades in last 48h: {len(out_deals)} trades ---")
    wins = [d for d in out_deals if d.profit > 0]
    losses = [d for d in out_deals if d.profit < 0]
    be = [d for d in out_deals if d.profit == 0]
    
    total_win_amt = sum(d.profit for d in wins)
    total_loss_amt = sum(d.profit for d in losses)
    net_pnl = total_win_amt + total_loss_amt
    
    print(f"Wins: {len(wins)} (Sum: +${total_win_amt:.2f}, Avg: +${(total_win_amt/len(wins) if wins else 0):.2f})")
    print(f"Losses: {len(losses)} (Sum: -${abs(total_loss_amt):.2f}, Avg: -${(abs(total_loss_amt)/len(losses) if losses else 0):.2f})")
    print(f"Breakeven: {len(be)}")
    print(f"Win Rate: {len(wins)/len(out_deals)*100:.1f}%")
    print(f"Profit Factor: {total_win_amt/abs(total_loss_amt):.2f}" if total_loss_amt != 0 else "PF: inf")
    print(f"Net P/L: ${net_pnl:+.2f}")
    
    print("\n--- Breakdown by Strategy / Comment (last 48h) ---")
    by_strat = {}
    for d in out_deals:
        comm = d.comment or "unknown"
        # parse prefix
        prefix = comm.split()[0] if comm else "unknown"
        if prefix not in by_strat:
            by_strat[prefix] = {"w": 0, "l": 0, "be": 0, "profit": 0.0}
        if d.profit > 0:
            by_strat[prefix]["w"] += 1
        elif d.profit < 0:
            by_strat[prefix]["l"] += 1
        else:
            by_strat[prefix]["be"] += 1
        by_strat[prefix]["profit"] += d.profit
        
    for k, v in sorted(by_strat.items(), key=lambda x: x[1]["profit"], reverse=True):
        total_k = v["w"] + v["l"] + v["be"]
        wr = (v["w"] / total_k * 100) if total_k > 0 else 0
        print(f"{k:25s} | Trades: {total_k:3d} | W: {v['w']:2d} L: {v['l']:2d} BE: {v['be']:2d} | WR: {wr:4.1f}% | Net: ${v['profit']:+7.2f}")

    print("\n--- Last 20 Closed Trades Details ---")
    for d in out_deals[-20:]:
        t_str = datetime.fromtimestamp(d.time, tz=BKK).strftime('%d/%m %H:%M:%S')
        print(f"{t_str} | Ticket: {d.order} | {d.symbol:7s} | P/L: ${d.profit:+6.2f} | Comm: {d.comment}")

# Check current open positions
positions = mt5.positions_get()
print(f"\n--- Open Positions: {len(positions) if positions else 0} ---")
if positions:
    for p in positions:
        t_str = datetime.fromtimestamp(p.time, tz=BKK).strftime('%d/%m %H:%M:%S')
        side = "BUY" if p.type == 0 else "SELL"
        print(f"{t_str} | #{p.ticket} | {p.symbol} {side} {p.volume} @ {p.price_open:.2f} -> {p.price_current:.2f} | SL: {p.sl:.2f} TP: {p.tp:.2f} | P/L: ${p.profit:+.2f} | {p.comment}")

mt5.shutdown()
