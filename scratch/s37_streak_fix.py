import sys
sys.path.insert(0, ".")
import MetaTrader5 as mt5
import config
from strategy37 import S37_DEFAULTS
import sim_s30_backtest as s30sim
import sim_s31_backtest as s31sim
import sim_s37_backtest as sim

mt5.initialize()
base = dict(S37_DEFAULTS)
base.update(PIVOT_WING=3, MAX_LEVEL_AGE_BARS=60, TOUCH_ATR_MULT=0.3, REJECT_ATR_MULT=0.15,
            SL_ATR_MULT=0.8, TP_RR=1.5)

variants = {
    "baseline": dict(base),
    "adx_min15": {**base, "ADX_MIN_THRESHOLD": 15.0},
    "adx_min20": {**base, "ADX_MIN_THRESHOLD": 20.0},
    "circuit_tighter": {**base, "CONSEC_LOSS_TRIGGER": 2, "COOLDOWN_TRADES": 15},
    "reject_stricter": {**base, "REJECT_ATR_MULT": 0.25},
}

for days in [120, 150, 180]:
    print(f"--- {days}d ---")
    entry_bars = s30sim.fetch_bars(config.SYMBOL, base["ENTRY_TF"], days, extra_bars=base["MAX_LEVEL_AGE_BARS"] + 100)
    htf_bars = s30sim.fetch_bars(config.SYMBOL, base["HTF_TF"], days, extra_bars=max(base["HTF_EMA_PERIOD"], 28) + 60)
    for name, cfg in variants.items():
        raw = sim.run_single(entry_bars, htf_bars, cfg, days, 0.20)
        twp, eq = s31sim.simulate_equity_substream(raw, cfg, sim.START_EQUITY)
        if not twp:
            print(f"  {name:<16} no trades"); continue
        s = s30sim.summarize(twp, eq, cfg["RISK_PCT"], days)
        by_day = s31sim.daily_series_from_trades(twp)
        c = s31sim.consistency_metrics(by_day)
        print(f"  {name:<16} n={s['trades']:>5} WR={s['wr']:>5.1f} $/mo={s['avg_per_day_span']*30:>8.1f} "
              f"DD={s['max_dd_pct']:>5.1f} PF={s['profit_factor']:>4.2f} posDay={c['pct_pos_days']:>5.1f}% "
              f"streak={c['max_losing_day_streak']:>2}d sharpe={c['sharpe_like']:>6.3f}")
mt5.shutdown()
