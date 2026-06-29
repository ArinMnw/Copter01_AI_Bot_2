import MetaTrader5 as mt5
import config
from strategy29 import S29_DEFAULTS
import sim_s29_backtest as sim

mt5.initialize()
cfg = dict(S29_DEFAULTS)
cfg["ENTRY_PATTERN"] = "engulfing"
cfg["ENGULF_MIN_RATIO"] = 1.6
cfg["SL_ATR_MULT"] = 0.5
cfg["TP_RR"] = 0.8
cfg["DD_CONTROL"] = "circuit_breaker"
cfg["CONSEC_LOSS_TRIGGER"] = 3
cfg["COOLDOWN_TRADES"] = 10
cfg["RISK_PCT"] = 1.0

entry_bars = sim.fetch_bars(config.SYMBOL, "M5", 15, extra_bars=500)
htf_bars = sim.fetch_bars(config.SYMBOL, "M15", 15, extra_bars=200)
htf_series = sim.build_htf_series(htf_bars, cfg)
raw = sim.replay(entry_bars, htf_series, 0.20, cfg)
trades, eq = sim.simulate_equity_v2(raw, cfg)

print(f"total raw signals: {len(raw)}, after DD-control: {len(trades)}")
print("-- first 10 trades --")
for t in trades[:10]:
    sig = t["signal"]
    e, s, tp = t["entry"], t["sl"], t["tp"]
    ok = (s < e < tp) if sig == "BUY" else (tp < e < s)
    print(f"{sig:4} entry={e:.2f} sl={s:.2f} tp={tp:.2f} outcome={t['outcome']:3} "
          f"risk_dist={t['risk_distance']:.3f} risk_pct_used={t['risk_pct_used']} order_ok={ok}")

mt5.shutdown()
