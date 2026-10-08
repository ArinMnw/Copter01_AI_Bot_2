# -*- coding: utf-8 -*-
"""legacy.py — รัน S20.55–S20.129 (strategy20_N.py แบบ extract_setups_s20_N(df)) ด้วย engine/เกณฑ์เดียวกับ S20.140–299

    python strategy/s20_gen/legacy.py --strategy S20.55 --days 365
    python strategy/s20_gen/legacy.py --strategy S20.55,S20.56 --start 2025-12-01 --end 2026-09-29 --tfs H1,H4
    python strategy/s20_gen/legacy.py --all --md          # ทั้ง 55–129 + เขียน backtest-summary/S20_55_to_129_365_day.md
    python strategy/s20_gen/legacy.py --strategy S20.55 --compare --compare-profile demo-exness-434237129

ต่างจาก engine.py ตรงที่ strategy พวกนี้ส่ง "limit setup" (entry/sl/risk) ไม่ใช่สัญญาณ market:
  - ส่งออเดอร์หลังแท่งสัญญาณปิด (t = bar_open + tf_sec) รอ fill ได้ตามอายุที่สัมพันธ์กับ TF (checklist #10)
  - BUY limit fill เมื่อ low <= entry − spread − 0.10 (Ask แตะ+ทะลุ), SELL limit fill เมื่อ high >= entry + 0.10 (#6/#7/#8)
  - แท่งที่ fill: เช็ค SL (pessimistic) ได้ แต่ TP ได้เฉพาะถึง close (#4/#5)
  - TP = tp_r × risk โดย tp_r = 5.5 + 0.1×(N−55) ตามที่ใช้ตอนสร้าง (stages=[] = ไม่มี trailing)
  - เกณฑ์ PASS/MC/IS-OOS/null เหมือน engine.py; null test = สุ่มจังหวะเข้า ใช้ geometry (offset/SL/RR) มัธยฐานของกลยุทธ์เอง
  - lookahead audit: ตัดแท่งราคาแล้วรัน compute_indicators+extract_setups ใหม่ ต้องได้ setup เดิม
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
for p in (HERE, os.path.join(ROOT, "strategy"), ROOT):
    if p not in sys.path:
        sys.path.insert(0, p)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)

import data as D
import engine as E
from goal_s20_53_to_100 import compute_indicators

PEN = 0.10
WAIT_SEC = {"M1": 900, "M5": 1800, "M15": 3600, "M30": 3600, "H1": 3600, "H4": 14400, "D1": 86400}
HOLD_BARS = {"M1": 1440, "M5": 576, "M15": 192, "M30": 96, "H1": 48, "H4": 30, "D1": 20}
SWING = ("H4", "D1")
NAMES = {}


def tp_r_for(n):
    return 5.5 + (n - 55) * 0.1


def load_mod(n):
    p = os.path.join(ROOT, "strategy", f"s20.{n}", f"strategy20_{n}.py")
    spec = importlib.util.spec_from_file_location(f"legacy20_{n}", p)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return getattr(m, f"extract_setups_s20_{n}")


def strat_name(n):
    p = os.path.join(ROOT, "strategy", f"s20.{n}", f"strategy20_{n}.py")
    with open(p, encoding="utf-8") as f:
        for line in f:
            if line.startswith(f"Strategy S20.{n}:"):
                return line.split(":", 1)[1].strip()
    return f"S20.{n}"


def closed_rates(tf, meta):
    a = D.load_bars(tf)
    fetched = int(datetime.strptime(meta["fetched_utc"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc).timestamp())
    return a[a["time"].astype(np.int64) + D.TF_SEC[tf] <= fetched]


def to_cands(setups, n, tf, spread_floor, eff_start, e_ts):
    out = []
    for s in setups:
        t0 = int(s["time"]) + D.TF_SEC[tf]  # ส่งออเดอร์หลังแท่งสัญญาณปิด
        if t0 < eff_start or t0 >= e_ts:
            continue
        d = 1 if s["signal"] == "BUY" else -1
        entry = float(s["entry"])
        risk = max(abs(entry - float(s["sl"])), 3 * spread_floor)
        if not np.isfinite(entry) or not np.isfinite(risk) or risk <= 0:
            continue
        out.append({"t_sig": int(s["time"]), "t0": t0, "dir": d, "entry": entry, "dist": risk, "rr": tp_r_for(n)})
    return out


def simulate_limit(cands, path, tf, meta, lot, commission):
    tf_sec = D.TF_SEC[tf]
    cs, pt = meta["contract_size"], meta["point"]
    swap_l, swap_s = meta["swap_long"] * pt * cs * lot, meta["swap_short"] * pt * cs * lot
    wait = WAIT_SEC[tf]
    hold = HOLD_BARS[tf] * tf_sec
    out = []
    for c in cands:
        s = int(np.searchsorted(path.t, c["t0"], side="left"))
        if s >= path.n:
            continue
        ee = int(np.searchsorted(path.t, c["t0"] + wait, side="left"))
        if ee <= s:
            continue
        buy = c["dir"] > 0
        entry, d = c["entry"], c["dist"]
        if buy:
            fm = path.l[s:ee] <= entry - path.spr[s:ee] - PEN
        else:
            fm = path.h[s:ee] >= entry + PEN
        k = np.flatnonzero(fm)
        if not len(k):
            continue
        e = s + int(k[0])
        sl = entry - d if buy else entry + d
        tp = entry + c["rr"] * d if buy else entry - c["rr"] * d
        w = np.searchsorted(path.wk_idx, e, side="left")
        wk = int(path.wk_idx[w]) if w < len(path.wk_idx) else path.n - 1
        if tf in SWING:
            wk = path.n - 1
        lim = int(np.searchsorted(path.t, path.t[e] + hold, side="left")) - 1
        end = min(max(lim, e), wk, path.n - 1)
        o, h, l, cl, sp = path.o[e:end + 1], path.h[e:end + 1], path.l[e:end + 1], path.c[e:end + 1], path.spr[e:end + 1]

        def first(mask):
            q = np.flatnonzero(mask)
            return int(q[0]) if len(q) else 10 ** 9

        # แท่ง fill (index 0): SL ได้ / TP ได้เฉพาะ close
        if buy:
            hit_sl, hit_tp = first(l <= sl), first(h >= tp)
            if hit_tp == 0 and not cl[0] >= tp:
                hit_tp = first(np.where(np.arange(len(h)) == 0, False, h >= tp))
        else:
            hit_sl, hit_tp = first(h + sp >= sl), first(l + sp <= tp)
            if hit_tp == 0 and not cl[0] + sp[0] <= tp:
                hit_tp = first(np.where(np.arange(len(l)) == 0, False, l + sp <= tp))
        if hit_sl <= hit_tp and hit_sl < len(o):
            kx = hit_sl
            if buy:
                px = (min(sl, o[kx]) if kx > 0 else sl) - E.SL_SLIP
            else:
                px = (max(sl, o[kx] + sp[kx]) if kx > 0 else sl) + E.SL_SLIP
            outcome = "SL"
        elif hit_tp < len(o):
            kx, px, outcome = hit_tp, tp, "FULL_TP"
        else:
            kx = len(o) - 1
            px = cl[kx] if buy else cl[kx] + sp[kx]
            outcome = "WEEKEND" if (e + kx) == wk and wk < lim else "TIME"
        pnl_px = (px - entry) if buy else (entry - px)
        t_in, t_out = int(path.t[e]), int(path.t[e + kx])
        nights = int(t_out // 86400 - t_in // 86400)
        wed = sum(1 for dd in range(t_in // 86400 + 1, t_out // 86400 + 1) if (dd + 3) % 7 == 3)
        swap = (nights + 2 * wed) * (swap_l if buy else swap_s)
        pnl = pnl_px * cs * lot + swap - commission
        out.append({"tf": tf, "dir": c["dir"], "t_sig": c["t_sig"], "fill_time_ts": t_in, "exit_time_ts": t_out,
                    "entry": round(entry, 3), "sl": round(sl, 3), "tp": round(tp, 3), "exit": round(px, 3),
                    "pnl_usd": round(pnl, 2), "r": round(pnl_px / d, 3), "outcome": outcome, "swap": round(swap, 2)})
    return out


def setup_keys(setups):
    return {(int(s["time"]), s["signal"], round(float(s["entry"]), 2)) for s in setups}


def null_tbl(df, setups, n, tf, path, meta, lot, commission, spread_floor, eff_start, e_ts):
    """สุ่มจังหวะเข้า: ทุกแท่ง × 2 ทิศ ใช้ geometry มัธยฐานของกลยุทธ์ (offset entry จาก close, risk, RR)"""
    if not setups:
        return None
    cl = df.set_index("time")["close"]
    geo = {}
    for sig, d in (("BUY", 1), ("SELL", -1)):
        ss = [s for s in setups if s["signal"] == sig]
        if ss:
            geo[d] = (float(np.median([(s["entry"] - cl.get(s["time"], s["entry"])) * d for s in ss])),
                      float(np.median([s["risk"] for s in ss])))
    if not geo:
        return None
    t = df["time"].to_numpy(); c = df["close"].to_numpy()
    cands = []
    for i in range(len(df)):
        t0 = int(t[i]) + D.TF_SEC[tf]
        if t0 < eff_start or t0 >= e_ts:
            continue
        for d, (off, risk) in geo.items():
            cands.append({"t_sig": int(t[i]), "t0": t0, "dir": d, "entry": c[i] + d * off,
                          "dist": max(risk, 3 * spread_floor), "rr": tp_r_for(n)})
    tr = simulate_limit(cands, path, tf, meta, lot, commission)
    if len(tr) < 10:
        return None
    return {"fill": np.array([x["fill_time_ts"] for x in tr], dtype=np.int64),
            "exit": np.array([x["exit_time_ts"] for x in tr], dtype=np.int64),
            "dir": np.array([x["dir"] for x in tr], dtype=np.int8),
            "pnl": np.array([x["pnl_usd"] for x in tr], dtype=float)}


def run(ns, days=365, start=None, end=None, tfs=None, lot=0.01, spread=None, commission=0.0, audit=True, quiet=False):
    meta = D.load_meta()
    spread_floor = spread if spread is not None else meta["spread_pts"] * meta["point"]
    fetched = datetime.strptime(meta["fetched_utc"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)

    def parse(s):
        for f in ("%Y-%m-%d %H:%M", "%Y-%m-%d", "%d-%m-%Y %H:%M", "%d-%m-%Y"):
            try:
                return datetime.strptime(s, f).replace(tzinfo=E.BKK).astimezone(timezone.utc)
            except ValueError:
                pass
        raise ValueError(s)

    end_dt = parse(end) if end else fetched
    start_dt = parse(start) if start else end_dt - timedelta(days=days)
    s_ts, e_ts = int(start_dt.timestamp()), int(end_dt.timestamp())
    tfs = tfs or E.ALL_TFS
    mods = {n: load_mod(n) for n in ns}
    res = {n: {"sid": f"20.{n}", "name": strat_name(n), "tf": {}, "tp_r": round(tp_r_for(n), 2),
               "period_bkk": [start_dt.astimezone(E.BKK).strftime("%Y-%m-%d %H:%M"), end_dt.astimezone(E.BKK).strftime("%Y-%m-%d %H:%M")],
               "spread_floor": round(spread_floor, 3), "data_snapshot_utc": meta["fetched_utc"]} for n in ns}
    trades_all = {n: [] for n in ns}
    sigs = {n: {} for n in ns}
    paths = {}
    for tf in tfs:
        rates = closed_rates(tf, meta)
        df = compute_indicators(rates)
        ptf = "M1" if tf == "M1" else "M5"
        if ptf not in paths:
            paths[ptf] = E.Path(ptf, meta, spread_floor)
        path = paths[ptf]
        eff_start = max(s_ts, int(path.t[0]))
        split = eff_start + 0.7 * (e_ts - eff_start)
        full = {}
        for n in ns:
            try:
                su = mods[n](df)
            except Exception as ex:  # noqa
                print(f"  ! S20.{n} {tf} extract error: {ex}")
                su = []
            full[n] = su
            if tf in ("M15", "H1"):
                sigs[n][tf] = {(s["time"], s["signal"]) for s in su}
        aud = {n: None for n in ns}
        if audit and tf in ("M15", "H1", "H4") and len(rates) > 400:
            rng = np.random.default_rng(7)
            lo = max(300, int(len(rates) * 0.5))
            cuts = sorted(rng.choice(np.arange(lo, len(rates)), size=min(6, len(rates) - lo), replace=False))
            mism = {n: 0 for n in ns}
            for k in cuts:
                dfc = compute_indicators(rates[:k + 1])
                t_lo, t_hi = int(rates["time"][max(0, k - 5)]), int(rates["time"][k])
                for n in ns:
                    try:
                        sc = mods[n](dfc)
                    except Exception:
                        sc = []
                    a = {x for x in setup_keys(sc) if t_lo <= x[0] <= t_hi}
                    b = {x for x in setup_keys(full[n]) if t_lo <= x[0] <= t_hi}
                    if a != b:
                        mism[n] += 1
            aud = {n: {"cuts": len(cuts), "mismatch": mism[n]} for n in ns}
        for n in ns:
            cands = to_cands(full[n], n, tf, spread_floor, eff_start, e_ts)
            raw = simulate_limit(cands, path, tf, meta, lot, commission)
            raw.sort(key=lambda t: t["fill_time_ts"])
            trades = E.lockout(raw)
            ins = [t for t in trades if t["fill_time_ts"] < split]
            oos = [t for t in trades if t["fill_time_ts"] >= split]
            st, si, so = E.stats(trades), E.stats(ins), E.stats(oos)
            mc = E.monte_carlo(raw)
            leak = aud[n] is not None and aud[n]["mismatch"] > 0
            nt = None
            base_ok = (st["n"] >= 30 and st["net"] > 0 and st["pf"] >= 1.15 and so["net"] > 0 and so["pf"] >= 1.0 and mc["p5"] > 0)
            if base_ok and not leak:
                tbl = null_tbl(df, full[n], n, tf, path, meta, lot, commission, spread_floor, eff_start, e_ts)
                nt = E.null_test(tbl, trades, len(raw)) if tbl else {"p": 1.0}
            v = E.verdict(st, so, mc, nt if base_ok else None)
            if leak:
                v = "LEAK"
            res[n]["tf"][tf] = {"days": round((e_ts - eff_start) / 86400, 1), **st, "is": si, "oos": so, "mc": mc,
                                "audit": aud[n], "null": nt, "signals": len(cands), "verdict": v}
            for t in trades:
                t.update({"sid": f"20.{n}", "symbol": meta["symbol"], "signal": "BUY" if t["dir"] > 0 else "SELL",
                          "type": "BUY" if t["dir"] > 0 else "SELL", "lot": lot, "leg": f"S20_{n}_{tf}"})
            trades_all[n] += trades
        print(f" {tf} done ({len(df)} bars)", flush=True)
    for n in ns:
        r = res[n]
        r["total"] = E.stats(trades_all[n])
        r["pass_tfs"] = [tf for tf, v in r["tf"].items() if v["verdict"] == "PASS"]
        r["leak_tfs"] = [tf for tf, v in r["tf"].items() if v["verdict"] == "LEAK"]
        if not quiet and len(ns) <= 3:
            E.print_report({**r, "params": {"tp_r": r["tp_r"]}, "lookahead_ok": not r["leak_tfs"]})
    return res, trades_all, sigs, (start_dt, end_dt)


def jaccard_pairs(sigs, ns, thr=0.5):
    bad = []
    for i, a in enumerate(ns):
        for b in ns[i + 1:]:
            j = 0.0
            for tf in ("M15", "H1"):
                x, y = sigs[a].get(tf, set()), sigs[b].get(tf, set())
                if x or y:
                    j = max(j, len(x & y) / len(x | y))
            if j > thr:
                bad.append((a, b, round(j, 2)))
    return bad


def write_md(res, dup, path):
    TFS = E.ALL_TFS
    f = lambda x: f"{x:+,.0f}"
    r0 = res[min(res)]
    ns = sorted(res)
    L = [f"# สรุป Backtest S20.{ns[0]} – S20.{ns[-1]} (365 วัน)\n"]
    L.append(f"- Symbol: XAUUSD (Exness `XAUUSDm`) lot 0.01 | ช่วง BKK {r0['period_bkk'][0]} → {r0['period_bkk'][1]} | snapshot {r0['data_snapshot_utc']} UTC")
    L.append("- รันใหม่ด้วย `strategy/s20_gen/legacy.py` (engine/เกณฑ์เดียวกับ S20.140–299) — **แทนที่ผลเดิมของไฟล์นี้ทั้งหมด** (ผลเดิมใช้ ✅ = กำไร > 0 อย่างเดียว ไม่ได้ผ่านเกณฑ์ PASS)")
    L.append("- ต้นทุน: spread จริงของ symbol (0.24), swap, SL slippage 0.10; ออเดอร์ Limit ส่งหลังแท่งสัญญาณปิด, fill เมื่อราคาทะลุ entry ≥ 0.10 (+spread ฝั่ง BUY), รอ fill ตาม TF (M1 15 นาที, M5 30 นาที, M15–H1 1 ชม., H4 4 ชม., D1 1 วัน), SL-first, แท่ง fill รับ TP เฉพาะถึง close")
    L.append("- TP = (5.5 + 0.1×(N−55))R ตามที่กลยุทธ์ถูกสร้าง ไม่มี trailing; ถือสูงสุด ~1–2 วัน (M1 1 วัน, M5/M15 2 วัน, ฯลฯ) และปิดก่อน weekend (ยกเว้น H4/D1)")
    L.append("- ⚠️ **M1 มีข้อมูลแค่ ~103 วัน** (terminal maxbars=100000) ส่วน M5–D1 ครบ 365 วัน")
    L.append("- **PASS** = n≥30, PF≥1.15, OOS(30%) กำไรและ PF≥1, Monte-Carlo p5>0 และชนะ null test (สุ่มจังหวะเข้า 200 ชุด geometry เดียวกัน p<0.05) และผ่าน lookahead audit")
    L.append("- **LEAK** = lookahead audit ไม่ผ่าน (setup เปลี่ยนเมื่อตัดข้อมูลอนาคตทิ้ง) → ไม่นับ PASS")
    L.append("- ✅ = TF ที่ผ่านเกณฑ์ PASS | ❌ = ติด LEAK | `–` = ไม่มีไม้ | ตัวเลขในช่อง = กำไรสุทธิ $\n")
    npass = sum(1 for r in res.values() if r["pass_tfs"])
    pairs_pass = sum(len(r["pass_tfs"]) for r in res.values())
    L.append(f"**ภาพรวม:** {len(ns)} กลยุทธ์ | มี TF ผ่านเกณฑ์ {npass} ตัว (รวม {pairs_pass} คู่ strategy×TF) | กำไรรวมเป็นบวก {sum(1 for r in res.values() if r['total']['net'] > 0)} ตัว | ขาดทุนรวม {sum(1 for r in res.values() if r['total']['net'] <= 0)} ตัว | ติด LEAK {sum(1 for r in res.values() if r['leak_tfs'])} ตัว")
    if dup:
        L.append(f"\n> ℹ️ **ความซ้ำของสัญญาณ:** พบ {len(dup)} คู่ที่ setup ซ้ำกัน >50% บน M15/H1 (กลยุทธ์ชุดนี้ใช้ template เดียวกันปรับพารามิเตอร์) ตัวอย่าง: "
                 + ", ".join(f"S{a}–S{b} ({j})" for a, b, j in dup[:8]))
    L.append("\n## ตารางที่ 1 — PnL ($) ของทุกกลยุทธ์ แยกตาม TF\n")
    L.append("| S20 | ชื่อ | " + " | ".join(TFS) + " | รวม $ | PF รวม | ผ่านที่ TF |")
    L.append("|---|---|" + "---:|" * 7 + "---:|---:|---|")
    for n in ns:
        r = res[n]; cells = []
        for tf in TFS:
            v = r["tf"].get(tf)
            if not v or v["n"] == 0:
                cells.append("–")
            else:
                cells.append(f(v["net"]) + (" ✅" if v["verdict"] == "PASS" else (" ❌" if v["verdict"] == "LEAK" else "")))
        L.append(f"| {n} | {r['name']} | " + " | ".join(cells) + f" | {f(r['total']['net'])} | {r['total']['pf']} | {', '.join(r['pass_tfs']) or '–'} |")
    L.append("\n## ตารางที่ 2 — กลยุทธ์/TF ที่ได้กำไร (net > 0) เรียงตามกำไรมากไปน้อย\n")
    L.append("> ✅ PASS = ผ่านเกณฑ์ครบ | ⚠️ = กำไรแต่ไม่ผ่านเกณฑ์ (ไม้น้อย, PF ต่ำ, OOS ลบ, MC/null ไม่ผ่าน) | ❌ LEAK = lookahead audit ไม่ผ่าน\n")
    rows = []
    for n in ns:
        for tf in TFS:
            v = res[n]["tf"].get(tf)
            if v and v["n"] > 0 and v["net"] > 0:
                rows.append((v["net"], n, res[n]["name"], tf, v))
    rows.sort(reverse=True)
    L.append("| # | S20 | ชื่อ | TF | ไม้ | WR% | กำไร $ | PF | OOS $ | สถานะ |")
    L.append("|---:|---|---|---|---:|---:|---:|---:|---:|---|")
    for i, (net, n, name, tf, v) in enumerate(rows, 1):
        st = {"PASS": "✅ PASS", "LEAK": "❌ LEAK"}.get(v["verdict"], "⚠️ ไม่ผ่าน")
        L.append(f"| {i} | {n} | {name} | {tf} | {v['n']} | {v['wr']} | {f(net)} | {v['pf']} | {f(v['oos']['net'])} | {st} |")
    L.append(f"\nรวม {len(rows)} คู่ (strategy×TF) ที่กำไร — ผ่านเกณฑ์ {sum(1 for x in rows if x[4]['verdict'] == 'PASS')} คู่")
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(L) + "\n")


def main():
    ap = argparse.ArgumentParser(description="S20.55-129 backtest (checklist-compliant, same PASS criteria as S20.140-299)")
    ap.add_argument("--strategy", default=None, help="เช่น S20.55 หรือ 55,56,57")
    ap.add_argument("--all", action="store_true", help="S20.55–S20.129 ทั้งหมด")
    ap.add_argument("--days", type=int, default=365)
    ap.add_argument("--start", default=None)
    ap.add_argument("--end", default=None)
    ap.add_argument("--tfs", default=",".join(E.ALL_TFS))
    ap.add_argument("--lot", type=float, default=0.01)
    ap.add_argument("--spread", type=float, default=None)
    ap.add_argument("--commission", type=float, default=0.0)
    ap.add_argument("--no-audit", action="store_true")
    ap.add_argument("--md", action="store_true", help="เขียน strategy/backtest-summary/S20_55_to_129_365_day.md (ใช้กับ --all)")
    ap.add_argument("--compare", action="store_true")
    ap.add_argument("--compare-profile", default=D.DEFAULT_PROFILE)
    ap.add_argument("--out-dir", default=os.path.join(ROOT, "reports", "s20_55_129"))
    a = ap.parse_args()
    if a.all:
        ns = list(range(55, 130))
    else:
        ns = [int(x.upper().replace("S", "").replace("20.", "").strip()) for x in (a.strategy or "").split(",") if x.strip()]
    if not ns:
        ap.error("ต้องระบุ --strategy หรือ --all")
    ns = [n for n in ns if os.path.exists(os.path.join(ROOT, "strategy", f"s20.{n}", f"strategy20_{n}.py"))]
    res, trades, sigs, (sdt, edt) = run(ns, a.days, a.start, a.end, [x.strip().upper() for x in a.tfs.split(",")], a.lot,
                                        a.spread, a.commission, audit=not a.no_audit)
    os.makedirs(a.out_dir, exist_ok=True)
    with open(os.path.join(a.out_dir, "results.json"), "w", encoding="utf-8", newline="\n") as fh:
        json.dump({str(k): v for k, v in res.items()}, fh, ensure_ascii=False, indent=1)
    dup = jaccard_pairs(sigs, ns) if len(ns) > 1 else []
    if a.md:
        write_md(res, dup, os.path.join(ROOT, "strategy", "backtest-summary", "S20_55_to_129_365_day.md"))
        print("เขียน md แล้ว")
    if a.compare:
        from s20_compare_engine import run_s20_compare
        allt = [t for n in ns for t in trades[n]]
        run_s20_compare(portfolio_name="S20_55_129" if len(ns) > 1 else f"S20_{ns[0]}", backtest_trades=allt, start_balance=5000.0,
                        output_dir=a.out_dir, start_dt=sdt, end_dt=edt, target_sids=[f"20.{n}" for n in ns],
                        symbols_to_run=[D.load_meta()["symbol"]], profile_name=a.compare_profile, root_dir=ROOT)
    if len(ns) > 3:
        print(f"{len(ns)} strategies | ผ่าน {sum(1 for r in res.values() if r['pass_tfs'])} ตัว | dup pairs {len(dup)}")


if __name__ == "__main__":
    main()
