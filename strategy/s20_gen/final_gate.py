# -*- coding: utf-8 -*-
"""final_gate.py — ด่านสุดท้ายของกลยุทธ์ที่มี TF ได้ PASS (กันตัวที่ผ่านเพราะฟลุกจากการลองหลายตัว)

    python strategy/s20_gen/final_gate.py 339              # TF = pass_tfs ใน result_365d.json
    python strategy/s20_gen/final_gate.py 339 --tfs M30,H1
    python strategy/s20_gen/final_gate.py 339 --compare    # ทดสอบ --compare ด้วย (ต้องเปิด MT5)

ต้องรัน run_one.py <N> ก่อน (ใช้ result_365d.json เป็นฐาน) และไฟล์นี้ไม่เขียนทับ result_365d.json
เกณฑ์ต่อ TF (ใช้พารามิเตอร์เดิม ห้ามแก้):
  1. walk-forward 4 ไตรมาสของช่วง 365 วันเดิม: net บวก ≥ 3/4
  2. spread 0.40: net 365 วันยังบวก
  3. null p (จาก result_365d.json) < 0.01
ผล: WINNER (ผ่านครบ) / BORDERLINE_INFO_ONLY (ตกแค่ข้อ 3 และ p ≤ 0.010) / FAILED_GATE
     / INSUFFICIENT_DATA (ทุก TF มีข้อมูลไม่ครบ 4 ไตรมาส เช่น M1) — TF ที่ข้อมูลไม่พอไม่นับเป็น WINNER
เขียน strategy/s20.<N>/final_gate.txt (UTF-8) บรรทัดแรกเป็นผลรวม
"""
import os
import sys
import io
import json
import argparse
import contextlib
from datetime import datetime, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, HERE)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)

import engine as E

STRESS_SPREAD = 0.40
NULL_MAX = 0.01
WF_MIN_POS = 3


def _run(name, **kw):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        res, trades, span = E.backtest(name, quiet=False, audit=False, null=False, **kw)
    return res, trades, span, buf.getvalue()


def quarters(period_bkk):
    s = datetime.strptime(period_bkk[0], "%Y-%m-%d %H:%M")
    e = datetime.strptime(period_bkk[1], "%Y-%m-%d %H:%M")
    step = (e - s) / 4
    pts = [s + step * i for i in range(4)] + [e]
    return [(pts[i].strftime("%Y-%m-%d %H:%M"), pts[i + 1].strftime("%Y-%m-%d %H:%M")) for i in range(4)]


def gate(n, tfs=None, compare=False, profile=None):
    name = f"S20.{n}"
    path = os.path.join(ROOT, "strategy", f"s20.{n}", "result_365d.json")
    base = json.load(open(path, encoding="utf-8"))
    tfs = tfs or base["pass_tfs"]
    if not tfs:
        print(f"S20.{n}: ไม่มี TF ที่ PASS — ไม่ต้องเข้าด่านสุดท้าย")
        return None
    log = [f"S20.{n} — {base['name']} | base period {base['period_bkk'][0]} → {base['period_bkk'][1]} | TFs {tfs}",
           f"params {base['params']} (เดิม ห้ามแก้)", ""]
    qs = quarters(base["period_bkk"])

    q_net = {tf: [] for tf in tfs}
    q_has = {tf: [] for tf in tfs}
    log.append("=== 1. Walk-forward 4 ไตรมาส ===")
    for s, e in qs:
        res, _, _, out = _run(name, start=s, end=e, tfs=tfs)
        log.append(out)
        for tf in tfs:
            q_net[tf].append(res["tf"][tf]["net"])
            q_has[tf].append(res["tf"][tf]["days"] >= 30)

    log.append(f"=== 2. Stress spread {STRESS_SPREAD} (365 วันเดิม) ===")
    res, _, _, out = _run(name, start=base["period_bkk"][0], end=base["period_bkk"][1], tfs=tfs, spread=STRESS_SPREAD)
    log.append(out)
    sp_net = {tf: res["tf"][tf]["net"] for tf in tfs}

    log.append("=== 4. ทดสอบ argument: --start/--end และ --day 30 ===")
    _, _, _, out = _run(name, start=qs[1][0], end=qs[2][1], tfs=tfs)
    log.append(out)
    _, trades30, span30, out = _run(name, days=30, tfs=tfs)
    log.append(out)
    if compare:
        sys.path.insert(0, os.path.join(ROOT, "strategy"))
        sys.path.insert(0, ROOT)
        from s20_compare_engine import run_s20_compare
        import data as D
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            run_s20_compare(portfolio_name=f"S20_{n}", backtest_trades=trades30, start_balance=5000.0,
                            output_dir=os.path.join(ROOT, "reports", f"s20_{n}"), start_dt=span30[0], end_dt=span30[1],
                            target_sids=[base["sid"]], symbols_to_run=[D.load_meta()["symbol"]],
                            profile_name=profile or D.DEFAULT_PROFILE, root_dir=ROOT)
        log.append(buf.getvalue())

    verdicts = {}
    log.append("=== สรุปต่อ TF === (ไตรมาสที่มีข้อมูล < 30 วันไม่นับ → INSUFFICIENT_DATA ไม่ใช่ WINNER)")
    for tf in tfs:
        nullp = (base["tf"][tf].get("null") or {}).get("p", 1.0)
        pos = sum(x > 0 for x in q_net[tf])
        n_has = sum(q_has[tf])
        ok = {"1 walk-forward": pos >= WF_MIN_POS, "2 spread": sp_net[tf] > 0, "3 null p": nullp < NULL_MAX}
        fails = [k for k, v in ok.items() if not v]
        if n_has < 4:
            v = "INSUFFICIENT_DATA"
            fails = [f"มีข้อมูลแค่ {n_has}/4 ไตรมาส (เช่น M1 terminal เก็บได้ ~100 วัน) ตัดสิน walk-forward ไม่ได้"]
        elif not fails:
            v = "WINNER"
        elif fails == ["3 null p"] and nullp <= NULL_MAX + 1e-9:
            v = "BORDERLINE"
        else:
            v = "FAILED"
        verdicts[tf] = (v, fails)
        log.append(f"{tf}: quarter nets {q_net[tf]} (บวก {pos}/4) | spread {STRESS_SPREAD} net {sp_net[tf]} | null p {nullp}"
                   f" -> {v}{'' if not fails else ' (ตก: ' + ', '.join(fails) + ')'}")

    win = [tf for tf, (v, _) in verdicts.items() if v == "WINNER"]
    bord = [tf for tf, (v, _) in verdicts.items() if v == "BORDERLINE"]
    insuf = [tf for tf, (v, _) in verdicts.items() if v == "INSUFFICIENT_DATA"]
    if win:
        head = f"WINNER: {', '.join(win)}"
    elif bord:
        head = f"BORDERLINE_INFO_ONLY: {', '.join(bord)} (ตกแค่ null p = 0.010 ไม่นับเป็น WINNER)"
    elif insuf and len(insuf) == len(verdicts):
        head = f"INSUFFICIENT_DATA: {', '.join(insuf)}"
    else:
        head = "FAILED_GATE: " + "; ".join(f"{tf} ข้อ {', '.join(f)}" for tf, (v, f) in verdicts.items() if v != "INSUFFICIENT_DATA")
    out_path = os.path.join(ROOT, "strategy", f"s20.{n}", "final_gate.txt")
    with open(out_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(head + "\n" + f"(final_gate.py {datetime.now():%Y-%m-%d %H:%M})\n\n" + "\n".join(log) + "\n")
    print(head)
    for line in log[-len(tfs):]:
        print(" ", line)
    print(f" บันทึก: {out_path}")
    return head


def main():
    ap = argparse.ArgumentParser(description="ด่านสุดท้ายของ S20 (walk-forward 4 ไตรมาส + spread 0.40 + null p<0.01)")
    ap.add_argument("n", type=int)
    ap.add_argument("--tfs", default=None, help="ค่าเริ่มต้น = pass_tfs ใน result_365d.json")
    ap.add_argument("--compare", action="store_true")
    ap.add_argument("--compare-profile", default=None)
    a = ap.parse_args()
    tfs = [x.strip().upper() for x in a.tfs.split(",")] if a.tfs else None
    gate(a.n, tfs, a.compare, a.compare_profile)


if __name__ == "__main__":
    main()
