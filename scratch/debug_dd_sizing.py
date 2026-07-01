import sys
sys.path.insert(0, ".")
import MetaTrader5 as mt5
import config
from strategy31 import S31_DEFAULTS
import sim_s30_backtest as s30sim
import sim_s31_backtest as s31sim
import sim_s33_backtest as s33

mt5.initialize()
days = 90
entry_bars = s30sim.fetch_bars(config.SYMBOL, "M5", days, extra_bars=400)
htf_bars = s30sim.fetch_bars(config.SYMBOL, "M15", days, extra_bars=200)
cfg = dict(S31_DEFAULTS); cfg.update(SL_ATR_MULT=1.2, TP_RR=1.0, RISK_PCT=0.5)
raw = s31sim.run_single(entry_bars, htf_bars, cfg, days, 0.20)
print(f"raw signals: {len(raw)}")

tiers = [(3.0, 1.0), (8.0, 0.6), (100.0, 0.3)]
twp, eq = s33.simulate_equity_dd_sizing(raw, cfg, tiers, use_circuit_breaker=True)
mults_used = [t.get("risk_pct_used", None) for t in twp[:20]]
print("first 20 risk_pct_used:", mults_used)
dd_at_entry = [t.get("dd_pct_at_entry") for t in twp]
print(f"max dd_pct_at_entry seen across all trades: {max(dd_at_entry) if dd_at_entry else 'n/a'}")
print(f"trades with dd_pct_at_entry >= 3.0: {sum(1 for d in dd_at_entry if d >= 3.0)} / {len(dd_at_entry)}")
print(f"trades with dd_pct_at_entry >= 8.0: {sum(1 for d in dd_at_entry if d >= 8.0)} / {len(dd_at_entry)}")
mt5.shutdown()
