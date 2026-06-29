import sys
sys.path.insert(0, ".")
import MetaTrader5 as mt5
import config
from strategy37 import S37_DEFAULTS
import sim_s30_backtest as s30sim
import sim_s37_backtest as sim

mt5.initialize()
days = 60
cfg = dict(S37_DEFAULTS)
entry_bars = s30sim.fetch_bars(config.SYMBOL, cfg["ENTRY_TF"], days, extra_bars=cfg["MAX_LEVEL_AGE_BARS"] + 100)
htf_bars = s30sim.fetch_bars(config.SYMBOL, cfg["HTF_TF"], days, extra_bars=max(cfg["HTF_EMA_PERIOD"], 28) + 60)

raw = sim.run_single(entry_bars, htf_bars, cfg, days, 0.20)
print(f"n={len(raw)}")
for t in raw[:15]:
    ok = (t["sl"] < t["entry"] < t["tp"]) if t["signal"] == "BUY" else (t["tp"] < t["entry"] < t["sl"])
    print(f"  {t['signal']:<4} entry={t['entry']:<9} sl={t['sl']:<9} tp={t['tp']:<9} "
          f"outcome={t['outcome']:<3} risk={t['risk_distance']:.3f} OK={ok}")

bad = [t for t in raw if not ((t["sl"] < t["entry"] < t["tp"]) if t["signal"] == "BUY" else (t["tp"] < t["entry"] < t["sl"]))]
print(f"bad trades: {len(bad)}")
mt5.shutdown()
