# -*- coding: utf-8 -*-
"""engine.py — Backtest engine กลางของแคมเปญ S20.140–S20.299 (ออกแบบตาม docs/quant_strategy_verification_checklist.md)

ใช้งาน:
    python strategy/s20_gen/engine.py --strategy S20.140 --days 365
    python strategy/s20_gen/engine.py --strategy S20.140 --start 2025-10-01 --end 2026-09-29 --tfs H1,H4
    python strategy/s20_gen/engine.py --strategy S20.140 --days 365 --compare --compare-profile demo-exness-434237129

สัญญากับ strategy module (strategy/s20.<N>/strategy20_<N>.py):
    META = {"sid": "20.140", "name": ..., "concept": ..., "sl_atr": 1.5, "rr": 2.0, "max_hold": 48, "be_r": 0.0}
    def generate(df, tf) -> np.ndarray[int8]  (+1 BUY / -1 SELL / 0) ตัดสินใจ ณ แท่ง i ที่ "ปิดแล้ว"
      หรือคืน dict {"sig": arr, "sl_dist": arr(optional, ระยะ SL เป็นราคา)}

การ execute (checklist):
  #1/#3  indicator causal ล้วน + automated truncation test (ตัดข้อมูลอนาคตทิ้งแล้วสัญญาณต้องเหมือนเดิม)
  #2     เข้าไม้ที่ open ของแท่งถัดไปหลังแท่งสัญญาณปิด (setup_time = bar_open + tf_sec); แท่งล่าสุดที่ยังไม่ปิดถูกตัดทิ้ง
  #4     ในแท่ง path เดียวกันถ้าแตะทั้ง SL และ TP → นับ SL ก่อน; path = M1 (สัญญาณ M1) / M5 (TF อื่น)
  #5     fill ที่ open ของแท่ง path → high/low ทั้งแท่งเกิดหลัง fill จริง; BE ขยับได้ตั้งแต่แท่งถัดไปเท่านั้น
  #6     market order (ไม่มี magic fill ของ limit) → #7/#10/#13 ไม่เกี่ยว
  #8     BUY เข้า Ask(=Bid+spread) ออก Bid; SELL เข้า Bid ออก Ask; spread=max(spread แท่งนั้น, --spread);
         swap จาก symbol_info (Wed x3), commission ตั้งได้
  #9     SL slippage 0.10 + SL ที่โดน gap ข้ามถูก fill ที่ open (แย่กว่า SL)
  #11    outcome แยก FULL_TP / BE / SL / TIME / WEEKEND (engine นี้ไม่มี trailing → Trail TP = 0)
  #12    ล็อก 1 position ต่อ TF → ทำ Monte-Carlo order-drop 15% x 300 รอบ
  #14    พารามิเตอร์ fixed ตาม market logic ไม่มี auto-tune + null-distribution test (สุ่มจุดเข้า 200 ชุด
         จำนวนไม้/สัดส่วน BUY เท่ากลยุทธ์ + ล็อกคิวเหมือนกัน) ต้อง p<0.05 ถึงนับ PASS
  #15    แบ่ง In-Sample 70% / Out-of-Sample 30% ตามเวลา
  #17    ปิดทุกไม้ก่อน weekend gap (แท่ง path สุดท้ายก่อนตลาดปิดวันศุกร์)
"""
import os
import sys
import json
import argparse
import importlib.util
import numpy as np
import pandas as pd
from datetime import datetime, timezone, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)

import data as D
import ind as I

ALL_TFS = ["M1", "M5", "M15", "M30", "H1", "H4", "D1"]
BKK = timezone(timedelta(hours=7))
SL_SLIP = 0.10
MC_RUNS = 300
MC_DROP = 0.15
SWING_TFS = ("H4", "D1")  # checklist #17: TF อื่นบังคับปิดก่อน weekend


def sid_parts(name):
    s = name.upper().replace("S", "").replace("_", ".")
    if not s.startswith("20."):
        s = "20." + s
    return s, s.split(".")[1]


def load_strategy(name):
    sid, n = sid_parts(name)
    path = os.path.join(ROOT, "strategy", f"s20.{n}", f"strategy20_{n}.py")
    spec = importlib.util.spec_from_file_location(f"strategy20_{n}", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return sid, n, mod


def bars_df(tf, meta):
    a = D.load_bars(tf)
    df = pd.DataFrame({k: a[k] for k in ("time", "open", "high", "low", "close", "tick_volume", "spread")})
    df["time"] = df["time"].astype(np.int64)
    fetched = int(datetime.strptime(meta["fetched_utc"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc).timestamp())
    df = df[df["time"] + D.TF_SEC[tf] <= fetched].reset_index(drop=True)  # checklist #2: ตัดแท่งที่ยังไม่ปิด
    df["volume"] = df["tick_volume"].astype(float)
    return df


def run_generate(mod, df, tf):
    out = mod.generate(df.copy(), tf)
    if isinstance(out, dict):
        sig = np.asarray(out["sig"], dtype=np.int8)
        sl = out.get("sl_dist")
        sl = None if sl is None else np.asarray(sl, dtype=float)
    else:
        sig, sl = np.asarray(out, dtype=np.int8), None
    return sig, sl


def lookahead_audit(mod, df, tf, sig_full, n_cuts=12, seed=7):
    """checklist #1/#3: ตัดข้อมูลที่แท่ง k แล้วรัน generate ใหม่ — สัญญาณที่แท่ง k-? ต้องเท่าเดิมทุกจุด"""
    rng = np.random.default_rng(seed)
    n = len(df)
    lo = max(300, int(n * 0.5))
    if n - lo < 20:
        return {"cuts": 0, "mismatch": 0}
    nz = np.flatnonzero(sig_full[lo:]) + lo
    cuts = list(rng.choice(np.arange(lo, n), size=min(n_cuts // 2, n - lo), replace=False))
    if len(nz):
        cuts += list(rng.choice(nz, size=min(n_cuts - len(cuts), len(nz)), replace=False))
    mism = 0
    for k in cuts:
        s2, _ = run_generate(mod, df.iloc[: k + 1].reset_index(drop=True), tf)
        tail = slice(max(0, k - 5), k + 1)
        if not np.array_equal(s2[tail], sig_full[tail]):
            mism += 1
    return {"cuts": len(cuts), "mismatch": int(mism)}


class Path:
    def __init__(self, tf, meta, spread_floor):
        a = D.load_bars(tf)
        self.t = a["time"].astype(np.int64)
        self.o = a["open"].astype(float)
        self.h = a["high"].astype(float)
        self.l = a["low"].astype(float)
        self.c = a["close"].astype(float)
        self.spr = np.maximum(a["spread"].astype(float) * meta["point"], spread_floor)
        gap = np.diff(self.t) > 2 * 86400  # แท่งสุดท้ายก่อน weekend
        self.wk_idx = np.flatnonzero(np.append(gap, False))
        self.n = len(self.t)


def simulate(cands, path, tf, meta, lot, commission):
    """จำลองทุก candidate แบบอิสระ (ยังไม่ล็อกคิว) คืน list ของ trade dict"""
    tf_sec = D.TF_SEC[tf]
    cs = meta["contract_size"]
    pt = meta["point"]
    swap_l = meta["swap_long"] * pt * cs * lot
    swap_s = meta["swap_short"] * pt * cs * lot
    out = []
    for c in cands:
        e = int(np.searchsorted(path.t, c["t_entry"], side="left"))
        if e >= path.n or path.t[e] - c["t_entry"] > 3 * 86400:
            continue
        lim = int(np.searchsorted(path.t, c["t_entry"] + c["max_hold"] * tf_sec, side="left")) - 1
        w = np.searchsorted(path.wk_idx, e, side="left")
        wk = int(path.wk_idx[w]) if w < len(path.wk_idx) else path.n - 1
        if tf in SWING_TFS:  # H4/D1 ถือข้ามสัปดาห์ได้ แต่ SL ที่โดน gap ถูก fill ที่ open (worst-case gap ถูกคิดจริง)
            wk = path.n - 1
        end = min(max(lim, e), wk, path.n - 1)
        o, h, l, cl, sp = path.o[e:end + 1], path.h[e:end + 1], path.l[e:end + 1], path.c[e:end + 1], path.spr[e:end + 1]
        d = c["dist"]
        buy = c["dir"] > 0
        if buy:
            fill = o[0] + sp[0]
            sl, tp = fill - d, fill + c["rr"] * d
            fav = h - fill
        else:
            fill = o[0]
            sl, tp = fill + d, fill - c["rr"] * d
            fav = fill - (l + sp)

        def first(mask):
            k = np.flatnonzero(mask)
            return int(k[0]) if len(k) else 10 ** 9

        be_bar = 10 ** 9
        if c["be_r"] > 0:
            be_bar = first(fav >= c["be_r"] * d)  # ขยับ BE ได้ตั้งแต่แท่ง be_bar+1 (checklist #5)
        sl_arr = np.full(len(o), sl)
        if be_bar < len(o) - 1:
            sl_arr[be_bar + 1:] = fill
        if buy:
            hit_sl = first(l <= sl_arr)
            hit_tp = first(h >= tp)
        else:
            hit_sl = first(h + sp >= sl_arr)
            hit_tp = first(l + sp <= tp)
        if hit_sl <= hit_tp and hit_sl < len(o):  # checklist #4: SL ก่อนเสมอ
            k = hit_sl
            lvl = sl_arr[k]
            if buy:
                px = min(lvl, o[k]) if k > 0 else lvl
                px -= SL_SLIP
            else:
                px = max(lvl, o[k] + sp[k]) if k > 0 else lvl
                px += SL_SLIP
            outcome = "BE" if k > be_bar else "SL"
        elif hit_tp < len(o):
            k, px, outcome = hit_tp, tp, "FULL_TP"
        else:
            k = len(o) - 1
            px = cl[k] if buy else cl[k] + sp[k]
            outcome = "WEEKEND" if (e + k) == wk and wk < lim else "TIME"
        pnl_px = (px - fill) if buy else (fill - px)
        gap_r = 0.0
        if tf in SWING_TFS and k > 0:
            gi = np.flatnonzero(np.diff(path.t[e:e + k + 1]) > 2 * 86400)
            if len(gi):
                g = (o[gi + 1] - cl[gi]) if buy else (cl[gi] - o[gi + 1])
                gap_r = float(min(0.0, g.min()) / d)
        t_in, t_out = int(path.t[e]), int(path.t[e + k])
        nights = int(t_out // 86400 - t_in // 86400)
        wed = sum(1 for dday in range(t_in // 86400 + 1, t_out // 86400 + 1) if (dday + 3) % 7 == 3)  # rollover คืนพุธ x3
        swap = (nights + 2 * wed) * (swap_l if buy else swap_s)
        pnl = pnl_px * cs * lot + swap - commission
        if outcome == "SL" and pnl > 0:
            outcome = "SL"  # ไม่เกิดจริงใน engine นี้ (ไม่มี trailing) คงไว้เพื่อความชัดเจน
        out.append({"tf": tf, "dir": c["dir"], "t_sig": c["t_sig"], "fill_time_ts": t_in, "exit_time_ts": t_out,
                    "entry": round(fill, 3), "sl": round(sl, 3), "tp": round(tp, 3), "exit": round(px, 3),
                    "pnl_usd": round(pnl, 2), "r": round(pnl_px / d, 3), "outcome": outcome, "swap": round(swap, 2),
                    "gap_r": round(gap_r, 3)})
    return out


def lockout(trades, keep=None):
    """1 position ต่อ TF: สัญญาณที่มาระหว่างถือไม้อยู่ถูกข้าม (checklist #12)"""
    busy = -1
    res = []
    for i, t in enumerate(trades):
        if keep is not None and not keep[i]:
            continue
        if t["fill_time_ts"] < busy:
            continue
        res.append(t)
        busy = t["exit_time_ts"]
    return res


def stats(trades):
    n = len(trades)
    if n == 0:
        return {"n": 0, "net": 0.0, "pf": 0.0, "wr": 0.0, "dd": 0.0, "avg": 0.0}
    p = np.array([t["pnl_usd"] for t in sorted(trades, key=lambda x: x["exit_time_ts"])])
    gw, gl = p[p > 0].sum(), -p[p < 0].sum()
    eq = np.cumsum(p)
    dd = float(np.max(np.maximum.accumulate(np.append(0, eq))[1:] - eq)) if n else 0.0
    oc = {}
    for t in trades:
        oc[t["outcome"]] = oc.get(t["outcome"], 0) + 1
    return {"n": n, "net": round(float(p.sum()), 2), "pf": round(float(gw / gl), 3) if gl > 0 else 99.0,
            "wr": round(100.0 * (p > 0).mean(), 1), "dd": round(max(dd, 0.0), 2), "avg": round(float(p.mean()), 3),
            "outcomes": oc, "worst_weekend_gap_r": round(min([t.get("gap_r", 0.0) for t in trades] + [0.0]), 3)}


def monte_carlo(all_trades, runs=MC_RUNS, drop=MC_DROP, seed=11):
    if len(all_trades) < 5:
        return {"p5": 0.0, "median": 0.0, "pct_pos": 0.0}
    rng = np.random.default_rng(seed)
    nets = []
    for _ in range(runs):
        keep = rng.random(len(all_trades)) >= drop
        nets.append(sum(t["pnl_usd"] for t in lockout(all_trades, keep)))
    nets = np.array(nets)
    return {"p5": round(float(np.percentile(nets, 5)), 2), "median": round(float(np.median(nets)), 2),
            "pct_pos": round(100.0 * (nets > 0).mean(), 1)}


NULL_RUNS = 200


def null_table(tf, df, a, path, meta, M, hold, lot, commission, spread_floor, s_ts, e_ts):
    """checklist #14 (p-hacking guard): ผลของการเข้าไม้ 'ทุกแท่ง' ทั้ง BUY/SELL ด้วยพารามิเตอร์ exit เดียวกับกลยุทธ์
    cache ลงดิสก์ต่อ (tf, sl_atr, rr, hold, be, ช่วงเวลา) — ใช้สุ่ม null distribution ได้เร็ว"""
    key = f"null_{tf}_{M['sl_atr']}_{M['rr']}_{hold}_{M['be_r']}_{M['atr_n']}_{spread_floor:.3f}_{s_ts}_{e_ts}"
    p = os.path.join(D.CACHE, key + ".npz")
    if os.path.exists(p):
        z = np.load(p)
        return {k: z[k] for k in z.files}
    eff_start = max(s_ts, int(path.t[0]))
    cands = []
    for i in range(len(df)):
        t_entry = int(df["time"].iat[i]) + D.TF_SEC[tf]
        if t_entry < eff_start or t_entry >= e_ts or not np.isfinite(a[i]) or a[i] <= 0:
            continue
        dist = max(M["sl_atr"] * a[i], 3 * spread_floor)
        for d in (1, -1):
            cands.append({"t_sig": int(df["time"].iat[i]), "t_entry": t_entry, "dir": d, "dist": float(dist),
                          "rr": M["rr"], "max_hold": hold, "be_r": M["be_r"]})
    tr = simulate(cands, path, tf, meta, lot, commission)
    out = {"fill": np.array([t["fill_time_ts"] for t in tr], dtype=np.int64),
           "exit": np.array([t["exit_time_ts"] for t in tr], dtype=np.int64),
           "dir": np.array([t["dir"] for t in tr], dtype=np.int8),
           "pnl": np.array([t["pnl_usd"] for t in tr], dtype=float)}
    np.savez(p, **out)
    return out


def null_test(tbl, trades, raw_n, runs=NULL_RUNS, seed=5):
    """สุ่มจุดเข้า raw_n จุด (สัดส่วน BUY เท่ากลยุทธ์) + ล็อกคิวเหมือนกัน เทียบ avg P&L/ไม้ → p-value ด้านเดียว"""
    if len(trades) < 5 or len(tbl["pnl"]) < 10:
        return {"p": 1.0, "null_avg_p95": 0.0}
    rng = np.random.default_rng(seed)
    buy_frac = np.mean([t["dir"] > 0 for t in trades])
    ib, isell = np.flatnonzero(tbl["dir"] > 0), np.flatnonzero(tbl["dir"] < 0)
    mine = np.mean([t["pnl_usd"] for t in trades])
    avgs = []
    for _ in range(runs):
        nb = rng.binomial(raw_n, buy_frac)
        idx = np.concatenate([rng.choice(ib, size=min(nb, len(ib)), replace=False),
                              rng.choice(isell, size=min(raw_n - nb, len(isell)), replace=False)])
        idx = idx[np.argsort(tbl["fill"][idx], kind="stable")]
        busy, tot, cnt = -1, 0.0, 0
        f, x, pn = tbl["fill"][idx], tbl["exit"][idx], tbl["pnl"][idx]
        for k in range(len(idx)):
            if f[k] < busy:
                continue
            tot += pn[k]
            cnt += 1
            busy = x[k]
        avgs.append(tot / max(cnt, 1))
    avgs = np.array(avgs)
    return {"p": round(float((avgs >= mine).mean()), 3), "null_avg_p95": round(float(np.percentile(avgs, 95)), 3),
            "mine_avg": round(float(mine), 3)}


def verdict(st, oos, mc, nt=None):
    if (st["n"] >= 30 and st["net"] > 0 and st["pf"] >= 1.15 and oos["net"] > 0 and oos["pf"] >= 1.0
            and mc["p5"] > 0 and (nt is None or nt["p"] < 0.05)):
        return "PASS"
    if st["n"] > 0 and st["net"] > 0:
        return "WEAK"
    return "FAIL" if st["n"] > 0 else "NO_TRADE"


def backtest(name, days=365, start=None, end=None, tfs=None, lot=0.01, spread=None, commission=0.0,
             audit=True, quiet=False, null=True):
    meta = D.load_meta()
    sid, n, mod = load_strategy(name)
    M = dict(sl_atr=1.5, rr=2.0, max_hold=48, be_r=0.0, atr_n=14)
    M.update(getattr(mod, "META", {}))
    spread_floor = spread if spread is not None else meta["spread_pts"] * meta["point"]
    fetched = datetime.strptime(meta["fetched_utc"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)

    def parse(s):
        for f in ("%Y-%m-%d %H:%M", "%Y-%m-%d", "%d-%m-%Y %H:%M", "%d-%m-%Y"):
            try:
                return datetime.strptime(s, f).replace(tzinfo=BKK).astimezone(timezone.utc)
            except ValueError:
                pass
        raise ValueError(s)

    end_dt = parse(end) if end else fetched
    start_dt = parse(start) if start else end_dt - timedelta(days=days)
    s_ts, e_ts = int(start_dt.timestamp()), int(end_dt.timestamp())
    tfs = tfs or ALL_TFS
    paths = {}
    res = {"sid": sid, "name": M.get("name", ""), "concept": M.get("concept", ""),
           "period_bkk": [start_dt.astimezone(BKK).strftime("%Y-%m-%d %H:%M"), end_dt.astimezone(BKK).strftime("%Y-%m-%d %H:%M")],
           "params": {k: M[k] for k in ("sl_atr", "rr", "max_hold", "be_r")}, "spread_floor": round(spread_floor, 3),
           "tf": {}, "data_snapshot_utc": meta["fetched_utc"]}
    all_trades = []
    for tf in tfs:
        df = bars_df(tf, meta)
        sig, sl_dist = run_generate(mod, df, tf)
        assert len(sig) == len(df), f"generate() length mismatch on {tf}"
        a = I.atr(df, M["atr_n"]).to_numpy()
        ptf = "M1" if tf == "M1" else "M5"
        if ptf not in paths:
            paths[ptf] = Path(ptf, meta, spread_floor)
        path = paths[ptf]
        eff_start = max(s_ts, int(path.t[0]))
        hold = M.get("max_hold_tf", {}).get(tf, M["max_hold"])
        cands = []
        for i in np.flatnonzero(sig):
            t_entry = int(df["time"].iat[i]) + D.TF_SEC[tf]
            if t_entry < eff_start or t_entry >= e_ts:
                continue
            dist = sl_dist[i] if sl_dist is not None else M["sl_atr"] * a[i]
            if not np.isfinite(dist) or dist <= 0:
                continue
            dist = max(dist, 3 * spread_floor)  # SL ต้องกว้างกว่า spread อย่างน้อย 3 เท่า
            cands.append({"t_sig": int(df["time"].iat[i]), "t_entry": t_entry, "dir": int(sig[i]), "dist": float(dist),
                          "rr": M["rr"], "max_hold": hold, "be_r": M["be_r"]})
        raw = simulate(cands, path, tf, meta, lot, commission)
        raw.sort(key=lambda t: t["fill_time_ts"])
        trades = lockout(raw)
        split = eff_start + 0.7 * (e_ts - eff_start)
        ins = [t for t in trades if t["fill_time_ts"] < split]
        oos = [t for t in trades if t["fill_time_ts"] >= split]
        st, si, so = stats(trades), stats(ins), stats(oos)
        mc = monte_carlo(raw)
        aud = lookahead_audit(mod, df, tf, sig) if audit and tf in ("M15", "H1", "H4") else None
        days_cov = round((e_ts - eff_start) / 86400, 1)
        nt = None
        if null and st["n"] >= 30 and st["net"] > 0:  # null test เฉพาะ TF ที่มีลุ้นผ่าน (ประหยัดเวลา)
            tbl = null_table(tf, df, a, path, meta, M, hold, lot, commission, spread_floor, s_ts, e_ts)
            nt = null_test(tbl, trades, len(raw))
        res["tf"][tf] = {"days": days_cov, **st, "is": si, "oos": so, "mc": mc, "audit": aud, "null": nt,
                         "signals": int(len(cands)), "verdict": verdict(st, so, mc, nt if null else None)}
        for t in trades:
            t.update({"sid": sid, "symbol": meta["symbol"], "signal": "BUY" if t["dir"] > 0 else "SELL",
                      "type": "BUY" if t["dir"] > 0 else "SELL", "lot": lot, "leg": f"S{sid}_{tf}"})
        all_trades += trades
    res["total"] = stats(all_trades)
    res["pass_tfs"] = [tf for tf, v in res["tf"].items() if v["verdict"] == "PASS"]
    aud_all = [v["audit"] for v in res["tf"].values() if v["audit"]]
    res["lookahead_ok"] = all(x["mismatch"] == 0 for x in aud_all) if aud_all else None
    if not quiet:
        print_report(res)
    return res, all_trades, (start_dt, end_dt)


def print_report(res):
    print("=" * 118)
    print(f" S{res['sid']} — {res['name']}")
    print(f" Period (BKK): {res['period_bkk'][0]} → {res['period_bkk'][1]} | params {res['params']} | spread≥{res['spread_floor']}")
    print("-" * 118)
    print(f" {'TF':<4}{'days':>6}{'n':>6}{'WR%':>7}{'Net$':>10}{'PF':>7}{'DD$':>9}{'IS net':>9}{'IS PF':>7}{'OOS net':>9}{'OOS PF':>7}{'MC p5':>9}{'MC%+':>7}{'nullp':>7}  verdict  outcomes")
    for tf, v in res["tf"].items():
        print(f" {tf:<4}{v['days']:>6}{v['n']:>6}{v['wr']:>7}{v['net']:>10.2f}{v['pf']:>7}{v['dd']:>9.2f}"
              f"{v['is']['net']:>9.2f}{v['is']['pf']:>7}{v['oos']['net']:>9.2f}{v['oos']['pf']:>7}"
              f"{v['mc']['p5']:>9.2f}{v['mc']['pct_pos']:>7}{str((v['null'] or {}).get('p', '-')):>7}  {v['verdict']:<8} {v.get('outcomes', {})}")
    t = res["total"]
    print("-" * 118)
    print(f" TOTAL n={t['n']} net=${t['net']:.2f} PF={t['pf']} WR={t['wr']}% DD=${t['dd']:.2f} | PASS TFs: {res['pass_tfs'] or '-'} | lookahead audit ok: {res['lookahead_ok']}")
    print("=" * 118)


def save_reports(res, trades, out_dir, n):
    os.makedirs(out_dir, exist_ok=True)
    rows = []
    for t in sorted(trades, key=lambda x: x["fill_time_ts"]):
        rows.append({"Time (BKK)": datetime.fromtimestamp(t["fill_time_ts"], BKK).strftime("%d-%m-%Y %H:%M"),
                     "Close Time": datetime.fromtimestamp(t["exit_time_ts"], BKK).strftime("%d-%m-%Y %H:%M"),
                     "TF": t["tf"], "Type": t["signal"], "Entry": t["entry"], "SL": t["sl"], "TP": t["tp"],
                     "Exit": t["exit"], "Lot": t["lot"], "Swap": t["swap"], "P&L": t["pnl_usd"], "R": t["r"], "Outcome": t["outcome"]})
    df = pd.DataFrame(rows)
    base = os.path.join(out_dir, f"S20_{n}")
    df.to_csv(base + "_trades.csv", index=False, encoding="utf-8")
    if len(df):
        df["date"] = pd.to_datetime(df["Time (BKK)"], format="%d-%m-%Y %H:%M")
        for per, fmt in (("daily", "%Y-%m-%d"), ("monthly", "%Y-%m")):
            g = df.groupby(df["date"].dt.strftime(fmt))
            pd.DataFrame({"Trades": g.size(), "Win": g["P&L"].apply(lambda x: (x > 0).sum()),
                          "Net Profit": g["P&L"].sum().round(2)}).to_csv(base + f"_{per}.csv", encoding="utf-8")
    with open(os.path.join(ROOT, "strategy", f"s20.{n}", "result_365d.json"), "w", encoding="utf-8") as f:
        json.dump(res, f, indent=1, ensure_ascii=False)


def main():
    ap = argparse.ArgumentParser(description="S20.140-299 checklist-compliant backtest")
    ap.add_argument("--strategy", required=True)
    ap.add_argument("--days", "--day", dest="days", type=int, default=365)
    ap.add_argument("--start", default=None, help="BKK time YYYY-MM-DD[ HH:MM]")
    ap.add_argument("--end", default=None, help="BKK time YYYY-MM-DD[ HH:MM] (default = data snapshot end)")
    ap.add_argument("--tfs", default=",".join(ALL_TFS))
    ap.add_argument("--lot", type=float, default=0.01)
    ap.add_argument("--spread", type=float, default=None, help="spread floor (price units), default = symbol spread")
    ap.add_argument("--commission", type=float, default=0.0, help="USD per trade")
    ap.add_argument("--compare", action="store_true", help="เทียบกับดีลจริงใน MT5 (bipartite best-score matching)")
    ap.add_argument("--compare-profile", default=D.DEFAULT_PROFILE)
    ap.add_argument("--out-dir", default=None)
    ap.add_argument("--no-audit", action="store_true")
    ap.add_argument("--no-null", action="store_true", help="ข้าม null-distribution test (เร็วขึ้น แต่ verdict จะหลวม)")
    a = ap.parse_args()
    sid, n = sid_parts(a.strategy)
    res, trades, (sdt, edt) = backtest(a.strategy, a.days, a.start, a.end, [x.strip().upper() for x in a.tfs.split(",")],
                                       a.lot, a.spread, a.commission, audit=not a.no_audit, null=not a.no_null)
    out_dir = a.out_dir or os.path.join(ROOT, "reports", f"s20_{n}")
    if a.start is None and a.end is None and a.days == 365 and set(a.tfs.upper().split(",")) == set(ALL_TFS):
        save_reports(res, trades, out_dir, n)
    else:
        os.makedirs(out_dir, exist_ok=True)
    if a.compare:
        sys.path.insert(0, os.path.join(ROOT, "strategy"))
        sys.path.insert(0, ROOT)
        from s20_compare_engine import run_s20_compare
        run_s20_compare(portfolio_name=f"S20_{n}", backtest_trades=trades, start_balance=5000.0, output_dir=out_dir,
                        start_dt=sdt, end_dt=edt, target_sids=[sid], symbols_to_run=[D.load_meta()["symbol"]],
                        profile_name=a.compare_profile, root_dir=ROOT)


if __name__ == "__main__":
    main()
