"""Sanity check: print 10 sample trades from best config to verify logic correctness"""
import MetaTrader5 as mt5
import config
from strategy28 import S28_DEFAULTS
import sim_s28_backtest as sim

if not mt5.initialize():
    print(f"MT5 init failed: {mt5.last_error()}")
    exit()

cfg = dict(S28_DEFAULTS)
cfg["SWEEP_MIN_ATR"] = 0.02
cfg["BODY_REVERSAL_PCT"] = 0.2
cfg["SL_ATR_MULT"] = 0.2
cfg["TP_RR"] = 1.5
cfg["ENTRY_TF"] = "M1"

bars = sim.fetch_bars(config.SYMBOL, "M1", 30, extra_bars=1500)
mt5.shutdown()

print(f"Bars: {len(bars)}")
raw = sim.replay(bars, 0.20, cfg)
print(f"Total raw trades: {len(raw)}")

# Print first 10 trades
print("\n=== Sample Trades (first 10) ===")
for i, t in enumerate(raw[:10]):
    dt_sig = sim.to_bkk(t["signal_time_ts"])
    dt_fill = sim.to_bkk(t["fill_time_ts"])
    dt_exit = sim.to_bkk(t["exit_time_ts"])
    print(f"\nTrade #{i+1}:")
    print(f"  Signal: {t['signal']} | Outcome: {t['outcome']}")
    print(f"  Signal time: {dt_sig.strftime('%Y-%m-%d %H:%M')}")
    print(f"  Fill time:   {dt_fill.strftime('%Y-%m-%d %H:%M')}")
    print(f"  Exit time:   {dt_exit.strftime('%Y-%m-%d %H:%M')}")
    print(f"  Entry: {t['entry']:.2f} | SL: {t['sl']:.2f} | TP: {t['tp']:.2f}")
    print(f"  Exit price: {t['exit_price']:.2f}")
    print(f"  Risk distance: {t['risk_distance']:.4f}")
    print(f"  Asian H: {t['asian_high']:.2f} | Asian L: {t['asian_low']:.2f}")
    print(f"  Diff/0.01lot: {t['diff_usd_per_001lot']:.4f}")
    
    # Verify SL/TP placement
    if t['signal'] == "BUY":
        risk = t['entry'] - t['sl']
        reward = t['tp'] - t['entry']
        correct_sl = t['sl'] < t['entry']
        correct_tp = t['tp'] > t['entry']
        sl_below_asian_low = t['sl'] <= t['asian_low']
    else:
        risk = t['sl'] - t['entry']
        reward = t['entry'] - t['tp']
        correct_sl = t['sl'] > t['entry']
        correct_tp = t['tp'] < t['entry']
        sl_below_asian_low = False
    
    rr_actual = reward / risk if risk > 0 else 0
    print(f"  Risk: {risk:.2f} | Reward: {reward:.2f} | RR: {rr_actual:.2f}")
    print(f"  SL correct side: {correct_sl} | TP correct side: {correct_tp}")
    
    if not correct_sl or not correct_tp:
        print(f"  ⚠️ BUG: SL or TP on wrong side!")

# Verify P&L direction
print("\n=== P&L Sanity ===")
for i, t in enumerate(raw[:10]):
    if t['signal'] == "BUY":
        expected_pnl = t['exit_price'] - t['entry']
    else:
        expected_pnl = t['entry'] - t['exit_price']
    match = abs(expected_pnl - t['diff_usd_per_001lot']) < 0.01
    status = "✓" if match else "✗"
    print(f"  Trade #{i+1}: expected={expected_pnl:.4f} actual={t['diff_usd_per_001lot']:.4f} {status}")
