# -*- coding: utf-8 -*-
"""Confluence-scoring backtest: does agreement between independent strategy
detectors at the same price zone predict better trade quality than any single
detector alone?

Each pool strategy is an independent "concept detector" (liquidity sweep,
structural break, Kalman-fade, distribution-shift, rollover-clock breakout...).
When several fire the same side within a short time window AND their entry
prices cluster within a tolerance, that is empirical confluence — conceptually
the same idea as ICT point-scoring (FVG+OB+BOS all agreeing), except the
"concepts" here are whole validated/candidate strategies rather than hand-coded
tags, because the reason/pattern strings in this codebase are free text with no
structured concept field to parse reliably.

Mechanism (fully causal — every detector only sees bars strictly before the
bar it is asked to act on, exactly like the standard harness):
  1. Fetch one shared M5 price set.
  2. At every bar, run every pool strategy's own detector with its own
     validated default cfg (no re-tuning here — confluence is evaluated on
     top of each strategy's already-decided entry).
  3. Maintain a rolling buffer of recent same-side signals. A new signal joins
     a "cluster" with any buffered signal (within --window-bars) whose entry
     price is within --tolerance-atr of the new one.
  4. Cluster score = sum of per-strategy weights (default 1.0 each, or set via
     --pool "id:weight,id:weight,...").
  5. If score >= --min-score, the newest signal's own entry/SL/TP is taken as
     the composite trade (SL/TP untouched — confluence is a *filter*, not a
     re-pricer, to avoid changing each strategy's already-validated payoff).
  6. Backtest the confluence trades with the same conservative fill/exit rules
     as sim_strategy_backtest.py (market fill next-bar-open equivalent is not
     used here since these entries are decided on close; SL-first same-bar
     rule; one trade at a time via next_free cooldown).

Example:
    python confluence_scan.py --months 6 --end 2026-07-18T00:00:00+07:00 \
        --pool 99,100,101,105,111,206,258,294 --min-score 2
"""

from __future__ import annotations

import argparse
import importlib
import json
from datetime import datetime

from sim_strategy_backtest import BKK, parse_bkk, prepare_rates, validate_signal
from strategy119 import _atr


def _load_pool(spec):
    """Parse '99,100:2.0,206' into [(id, weight), ...], default weight 1.0."""
    pool = []
    for token in spec.split(","):
        token = token.strip()
        if not token:
            continue
        if ":" in token:
            sid, w = token.split(":")
            pool.append((int(sid), float(w)))
        else:
            pool.append((int(token), 1.0))
    return pool


def _detector(strategy_id):
    module = importlib.import_module(f"strategy{strategy_id}")
    return getattr(module, f"detect_s{strategy_id}")


def _stats(profits):
    if not profits:
        return {"trades": 0, "win_rate": None, "net": 0.0, "pf": None, "max_dd": 0.0}
    net = sum(profits)
    wins = sum(p > 0.0 for p in profits)
    gw = sum(p for p in profits if p > 0.0)
    gl = -sum(p for p in profits if p < 0.0)
    eq = pk = dd = 0.0
    for p in profits:
        eq += p
        pk = max(pk, eq)
        dd = max(dd, pk - eq)
    return {
        "trades": len(profits),
        "win_rate": round(wins / len(profits) * 100.0, 1),
        "net": round(net, 2),
        "pf": round(gw / gl, 2) if gl else None,
        "max_dd": round(dd, 2),
        "ratio": round(net / dd, 1) if dd > 0 else None,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pool", required=True,
                        help="comma list of strategy ids, optional :weight, e.g. 99,100:2,206")
    parser.add_argument("--months", type=int, default=6)
    parser.add_argument("--end", default="2026-07-18T00:00:00+07:00")
    parser.add_argument("--lookback", type=int, default=620)
    parser.add_argument("--spread", type=float, default=0.20)
    parser.add_argument("--lot", type=float, default=0.01)
    parser.add_argument("--tolerance-atr", type=float, default=0.50,
                        help="max distance between two signals' entries, in ATR, to cluster")
    parser.add_argument("--window-bars", type=int, default=12,
                        help="how many bars a signal stays eligible to join a cluster")
    parser.add_argument("--min-score", type=float, default=2.0,
                        help="minimum cluster score to take the confluence trade")
    parser.add_argument("--csv")
    args = parser.parse_args()

    pool = _load_pool(args.pool)
    detectors = {sid: _detector(sid) for sid, _ in pool}
    weights = dict(pool)

    end = parse_bkk(args.end)
    bars, _, start_index = prepare_rates(args.months, "M5", end, args.lookback)

    # per-strategy standalone trade logs (for comparison) + the raw signal stream
    solo_profits = {sid: [] for sid, _ in pool}
    solo_next_free = {sid: start_index for sid, _ in pool}
    buffer = []  # list of dicts: {sid, side, entry, bar_index}
    confluence_events = []  # (bar_index, side, entry, sl, tp, score, members)
    next_free_conf = start_index

    total_bars = len(bars) - 1 - start_index
    report_every = max(1, total_bars // 20)
    import sys, time
    t_start = time.time()
    for scan_pos, index in enumerate(range(start_index, len(bars) - 1)):
        if scan_pos % report_every == 0:
            elapsed = time.time() - t_start
            print(f"# progress {scan_pos}/{total_bars} "
                  f"({scan_pos / total_bars * 100:.0f}%) events={len(confluence_events)} "
                  f"elapsed={elapsed:.0f}s", file=sys.stderr, flush=True)
        window = bars[index - args.lookback + 1:index + 1]
        dt_bkk = datetime.fromtimestamp(int(bars[index]["time"]), tz=BKK)
        atr = _atr([{"high": b["high"], "low": b["low"], "close": b["close"]}
                    for b in window[:-1]], 14)
        if atr <= 0.0:
            continue
        tol = atr * args.tolerance_atr

        # drop stale buffer entries
        buffer = [s for s in buffer if index - s["bar_index"] <= args.window_bars]

        fired_here = []
        for sid, detect in detectors.items():
            try:
                sig = detect(window, tf="M5", dt_bkk=dt_bkk, cfg={})
            except Exception:
                continue
            if sig.get("signal") not in ("BUY", "SELL"):
                continue
            try:
                validate_signal(sig, sid)
            except AssertionError:
                continue
            side = 1 if sig["signal"] == "BUY" else -1
            entry = float(sig["entry"])
            sl = float(sig["sl"])
            tp = float(sig["tp"])

            # standalone bookkeeping (one trade at a time per strategy, like the
            # harness) purely to report each pool member's own baseline
            if index >= solo_next_free[sid]:
                risk = side * (entry - sl)
                if risk > 0:
                    outcome_idx, exit_price = _simulate(bars, index + 1, side, sl, tp)
                    if outcome_idx is not None:
                        pnl = (side * (exit_price - entry) - args.spread) * 100.0 * args.lot
                        solo_profits[sid].append(pnl)
                        solo_next_free[sid] = outcome_idx + 1

            fired_here.append({"sid": sid, "side": side, "entry": entry, "sl": sl,
                               "tp": tp, "bar_index": index})

        for new_sig in fired_here:
            members = [new_sig]
            for old in buffer:
                if old["side"] != new_sig["side"]:
                    continue
                if old["sid"] == new_sig["sid"]:
                    continue
                if abs(old["entry"] - new_sig["entry"]) <= tol:
                    members.append(old)
            score = sum(weights[m["sid"]] for m in members)
            if score >= args.min_score and index >= next_free_conf:
                side = new_sig["side"]
                risk = side * (new_sig["entry"] - new_sig["sl"])
                if risk > 0:
                    outcome_idx, exit_price = _simulate(
                        bars, index + 1, side, new_sig["sl"], new_sig["tp"])
                    if outcome_idx is not None:
                        pnl = (side * (exit_price - new_sig["entry"]) - args.spread) * 100.0 * args.lot
                        confluence_events.append({
                            "bar_index": index,
                            "signal_time": dt_bkk.isoformat(),
                            "side": "BUY" if side > 0 else "SELL",
                            "entry": new_sig["entry"], "sl": new_sig["sl"], "tp": new_sig["tp"],
                            "score": score,
                            "members": sorted(set(m["sid"] for m in members)),
                            "profit": round(pnl, 2),
                        })
                        next_free_conf = outcome_idx + 1

        buffer.extend(fired_here)

    print("=== per-strategy standalone (for reference) ===")
    for sid, _ in pool:
        s = _stats(solo_profits[sid])
        print(json.dumps({"strategy": sid, **s}))

    print("\n=== confluence-gated composite ===")
    conf_profits = [e["profit"] for e in confluence_events]
    print(json.dumps({"min_score": args.min_score, **_stats(conf_profits)}))

    if confluence_events:
        by_score = {}
        for e in confluence_events:
            by_score.setdefault(int(e["score"]), []).append(e["profit"])
        print("\n=== breakdown by score bucket ===")
        for score in sorted(by_score):
            print(json.dumps({"score>=": score, **_stats(by_score[score])}))

    if args.csv and confluence_events:
        import csv
        with open(args.csv, "w", newline="", encoding="utf-8") as h:
            w = csv.DictWriter(h, fieldnames=list(confluence_events[0].keys()))
            w.writeheader()
            for e in confluence_events:
                row = dict(e)
                row["members"] = ";".join(str(m) for m in row["members"])
                w.writerow(row)


def _simulate(bars, fill_index, side, sl, tp):
    """SL-first-on-tie exit simulation, market fill assumed at the signal bar's
    own close (the entries here already come from each detector's own quoted
    entry, which for market-order strategies equals the signal bar's close)."""
    for cursor in range(fill_index, len(bars)):
        low, high = float(bars[cursor]["low"]), float(bars[cursor]["high"])
        if side > 0:
            if low <= sl:
                return cursor, sl
            if high >= tp:
                return cursor, tp
        else:
            if high >= sl:
                return cursor, sl
            if low <= tp:
                return cursor, tp
    return None, None


if __name__ == "__main__":
    main()
