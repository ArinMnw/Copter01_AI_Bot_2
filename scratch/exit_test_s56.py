import sys
sys.path.insert(0, ".")
import MetaTrader5 as mt5
import numpy as np
import config
from strategy56 import S56_DEFAULTS
import sim_s30_backtest as s30sim
import sim_s31_backtest as s31sim
import sim_s56_backtest as s56sim

mt5.initialize()

cfg = dict(S56_DEFAULTS)
cfg.update(TOUCH_ATR_MULT=0.8, REJECT_ATR_MULT=0.15, SL_ATR_MULT=1.0, TP_RR=1.5,
           CONFIRMATION_TYPE="none", SESSION_FILTER=False)


def gen_signals(bars, cfg, days):
    """คืน list ของ (fill_idx, sig, entry, sl, tp, atr) — เหมือน replay56 แต่เก็บ index + atr"""
    from strategy56 import detect_s56, _calc_atr
    win_size = 40
    all_dt = [config.mt5_ts_to_bkk(int(b["time"])) for b in bars]
    ws, whl = s56sim._build_week_levels(days)
    sigs = []
    last_fire = -10
    n = len(bars)
    for j in range(win_size + 5, n - 1):
        if j - last_fire < 1:
            continue
        entry_bar = bars[j + 1]
        ts = int(entry_bar["time"])
        live = {"time": ts, "open": float(entry_bar["open"]), "high": float(entry_bar["open"]),
                "low": float(entry_bar["open"]), "close": float(entry_bar["open"])}
        lo = max(0, j + 1 - win_size)
        window = list(bars[lo:j + 1]) + [live]
        pwhl = s56sim._prev_week_hl(ts, ws, whl)
        res = detect_s56(window, tf=cfg["ENTRY_TF"], dt_bkk=all_dt[j + 1], cfg=cfg, htf_ctx=None,
                         prev_week_hl=pwhl)
        if res.get("signal") not in ("BUY", "SELL"):
            continue
        last_fire = j
        atr = res["atr_at_signal"]
        sigs.append((j + 1, res["signal"], float(res["entry"]), float(res["sl"]), float(res["tp"]),
                     atr, ts))
    return sigs


def resolve(bars, sig, policy):
    """resolve trade ภายใต้ exit policy คืน (pnl_per_001lot, exit_ts). policy = dict"""
    fill_idx, direction, entry, sl, tp, atr, ts = sig
    n = len(bars)
    risk = abs(entry - sl)
    be_trig = policy.get("be_trigger")      # move SL->BE เมื่อกำไร >= be_trig*risk
    trail_atr = policy.get("trail_atr")     # trail SL ห่าง trail_atr*atr จาก best
    p_tp1 = policy.get("partial_tp1")       # TP1 ที่ p_tp1*risk (RR), ปิดครึ่ง
    cur_sl = sl
    half_closed = False
    half_pnl = 0.0
    best = entry
    for m in range(fill_idx, n):
        hi, lw = float(bars[m]["high"]), float(bars[m]["low"])
        if direction == "BUY":
            best = max(best, hi)
            # partial TP1
            if p_tp1 and not half_closed and hi >= entry + p_tp1 * risk:
                half_pnl = 0.5 * (p_tp1 * risk)
                half_closed = True
            # breakeven
            if be_trig and hi >= entry + be_trig * risk:
                cur_sl = max(cur_sl, entry)
            # trailing
            if trail_atr:
                cur_sl = max(cur_sl, best - trail_atr * atr)
            # exits
            if lw <= cur_sl:
                base = (cur_sl - entry)
                return (half_pnl + (0.5 if half_closed else 1.0) * base), int(bars[m]["time"])
            if hi >= tp:
                base = (tp - entry)
                return (half_pnl + (0.5 if half_closed else 1.0) * base), int(bars[m]["time"])
        else:
            best = min(best, lw)
            if p_tp1 and not half_closed and lw <= entry - p_tp1 * risk:
                half_pnl = 0.5 * (p_tp1 * risk)
                half_closed = True
            if be_trig and lw <= entry - be_trig * risk:
                cur_sl = min(cur_sl, entry)
            if trail_atr:
                cur_sl = min(cur_sl, best + trail_atr * atr)
            if hi >= cur_sl:
                base = (entry - cur_sl)
                return (half_pnl + (0.5 if half_closed else 1.0) * base), int(bars[m]["time"])
            if lw <= tp:
                base = (entry - tp)
                return (half_pnl + (0.5 if half_closed else 1.0) * base), int(bars[m]["time"])
    return None, None


def agg(bars, sigs, policy, spread, days):
    daily = {}
    n_tr = 0
    for sig in sigs:
        pnl, ex_ts = resolve(bars, sig, policy)
        if pnl is None:
            continue
        pnl -= spread
        d = config.mt5_ts_to_bkk(sig[6]).date().isoformat()
        daily[d] = daily.get(d, 0.0) + pnl
        n_tr += 1
    c = s31sim.consistency_metrics(daily)
    total = sum(daily.values())
    # PF
    return total / days * 30, c["sharpe_like"], c["max_losing_day_streak"], n_tr


policies = {
    "baseline":        {},
    "BE@0.5R":         {"be_trigger": 0.5},
    "BE@1.0R":         {"be_trigger": 1.0},
    "trail 2ATR":      {"trail_atr": 2.0},
    "trail 3ATR":      {"trail_atr": 3.0},
    "partialTP@1.0R":  {"partial_tp1": 1.0},
    "partial+BE@1R":   {"partial_tp1": 1.0, "be_trigger": 1.0},
}

for days in [90, 150, 180]:
    eb = s30sim.fetch_bars(config.SYMBOL, "M5", days, extra_bars=100)
    sigs = gen_signals(eb, cfg, days)
    print(f"\n=== {days}d (n_sig={len(sigs)}) ===")
    print(f"{'policy':<16} {'$/mo':>8} {'sharpe':>7} {'maxStrk':>7} {'nTr':>5}")
    for name, pol in policies.items():
        mo, sh, ms, nt = agg(eb, sigs, pol, 0.20, days)
        print(f"{name:<16} {mo:>8.0f} {sh:>7.3f} {ms:>7} {nt:>5}")
mt5.shutdown()
