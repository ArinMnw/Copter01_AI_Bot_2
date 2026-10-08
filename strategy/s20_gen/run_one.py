# -*- coding: utf-8 -*-
"""run_one.py — pipeline ต่อ 1 กลยุทธ์ของแคมเปญ S20.140–S20.299

    python strategy/s20_gen/run_one.py 140        # backtest 365d 7TF + uniqueness + docs + progress
    python strategy/s20_gen/run_one.py 140 --no-docs

ขั้นตอน:
 1. backtest มาตรฐาน (engine.backtest, 365 วัน, M1..D1) → reports/s20_<N>/ + strategy/s20.<N>/result_365d.json
 2. uniqueness: เทียบ signal (เวลา+ทิศ) บน M15/H1 กับทุกตัวก่อนหน้าในแคมเปญ — Jaccard > 0.5 = ซ้ำ → FAIL
 3. สร้าง backtest_s20_<N>.py wrapper (รองรับ --days --start --end --compare ผ่าน engine)
 4. อัปเดต strategy/strategy.md + strategy/strategy_evolution.md (idempotent ด้วย marker)
 5. บันทึก progress.json (ใช้ resume หลัง token reset)
"""
import os
import sys
import json
import argparse
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, HERE)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)

import data as D
import engine as E
import docs

SIG_DIR = os.path.join(HERE, ".cache", "signatures")
PROGRESS = os.path.join(HERE, "progress.json")
UNIQ_TFS = ("M15", "H1")
DUP_THRESHOLD = 0.5

WRAPPER = '''# -*- coding: utf-8 -*-
"""Backtest wrapper S20.{n} — ส่งต่อ argument ทั้งหมดให้ strategy/s20_gen/engine.py
    python strategy/s20.{n}/backtest_s20_{n}.py --days 365
    python strategy/s20.{n}/backtest_s20_{n}.py --start 2026-01-01 --end 2026-06-30 --tfs H1,H4
    python strategy/s20.{n}/backtest_s20_{n}.py --days 90 --compare --compare-profile demo-exness-434237129
"""
import os, sys, runpy
sys.argv = [sys.argv[0], "--strategy", "S20.{n}"] + sys.argv[1:]
runpy.run_path(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen", "engine.py"), run_name="__main__")
'''


def signature(n):
    meta = D.load_meta()
    _, _, mod = E.load_strategy(f"S20.{n}")
    sig = {}
    for tf in UNIQ_TFS:
        df = E.bars_df(tf, meta)
        s, _ = E.run_generate(mod, df, tf)
        idx = np.flatnonzero(s)
        sig[tf] = (df["time"].to_numpy()[idx] * np.sign(s[idx]).astype(np.int64)).astype(np.int64)
    return sig


def jaccard(a, b):
    if len(a) == 0 and len(b) == 0:
        return 0.0
    sa, sb = set(a.tolist()), set(b.tolist())
    return len(sa & sb) / max(1, len(sa | sb))


def uniqueness(n):
    os.makedirs(SIG_DIR, exist_ok=True)
    me = signature(n)
    np.savez(os.path.join(SIG_DIR, f"s{n}.npz"), **me)
    worst, worst_with = 0.0, None
    for m in range(140, n):
        p = os.path.join(SIG_DIR, f"s{m}.npz")
        if not os.path.exists(p):
            src = os.path.join(ROOT, "strategy", f"s20.{m}", f"strategy20_{m}.py")
            if os.path.exists(src) and "def generate(" in open(src, encoding="utf-8", errors="ignore").read():
                other = signature(m)
                np.savez(p, **other)
            else:
                continue
        other = np.load(p)
        j = max(jaccard(me[tf], other[tf]) for tf in UNIQ_TFS)
        if j > worst:
            worst, worst_with = j, m
    return {"max_jaccard": round(worst, 3), "with": f"S20.{worst_with}" if worst_with else None,
            "unique": worst <= DUP_THRESHOLD}


def load_progress():
    if os.path.exists(PROGRESS):
        with open(PROGRESS, encoding="utf-8") as f:
            return json.load(f)
    return {"range": [140, 299], "done": {}, "next": 140}


def save_progress(p):
    import tempfile
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(PROGRESS), text=True)
    with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
        json.dump(p, f, indent=1, ensure_ascii=False)
    try:
        os.remove(PROGRESS)
    except Exception:
        pass
    os.rename(tmp, PROGRESS)


def check_mix_parents_eligible(n, mod):
    """บังคับกฎ 'ตัวผสมที่เป็นผู้ชนะ ใช้เป็นตัวแม่ของรอบถัดไปได้' ด้วยโค้ด (mix_strategy_prompt.md ส่วนการเก็บผล)
    ตัวแม่ที่เป็น "ตัวผสม" เอง (มี parents ใน META ของมัน) ต้องมี final_gate.txt ขึ้นต้นด้วย WINNER อย่างน้อย 1 TF ก่อน
    ถึงจะเอาไปผสมต่อได้ (ตัวแม่ดั้งเดิมที่ไม่ใช่ตัวผสม เช่น S20.339/422 ไม่เข้าเงื่อนไขนี้ ใช้กฎ M1 เดิม)
    (2026-10-07: พบว่า agent เอาตัวผสมที่ตก mix_check ไปแล้ว (761/762/765/766) มาผสมต่อเป็นชั้นที่ 2 — ขยาย search space
    แบบไม่จำกัดและเพิ่มความเสี่ยง false-positive สะสม ทั้งที่กฎใน prompt ห้ามไว้ชัดเจน)"""
    parents = getattr(mod, "META", {}).get("parents")
    if not parents or len(parents) != 2:
        return
    for p in parents:
        pid = str(p).split(".")[-1]
        src = os.path.join(ROOT, "strategy", f"s20.{pid}", f"strategy20_{pid}.py")
        if not os.path.exists(src):
            continue
        ptxt = open(src, encoding="utf-8", errors="ignore").read()
        if '"parents"' not in ptxt and "'parents'" not in ptxt:
            continue  # ตัวแม่ดั้งเดิม ไม่ใช่ตัวผสม ไม่ต้องเช็คข้อนี้
        gate_path = os.path.join(ROOT, "strategy", f"s20.{pid}", "final_gate.txt")
        head = open(gate_path, encoding="utf-8-sig").readline().strip() if os.path.exists(gate_path) else ""
        if not head.startswith("WINNER"):
            print(f" ❌ ห้ามบันทึกผล: ตัวแม่ S20.{pid} เป็นตัวผสมที่ยังไม่ใช่ผู้ชนะ (final_gate: '{head or 'ไม่มีไฟล์'}')"
                 f" — ใช้ตัวผสมเป็นตัวแม่ของรอบถัดไปได้เฉพาะตัวที่ WINNER เท่านั้น")
            sys.exit(8)


def check_mix_pair_cap(n, mod):
    """บังคับกฎ M3 ของ mix_strategy_prompt.md ด้วยโค้ด ไม่พึ่ง agent ทำตาม prompt อย่างเดียว
    (เจอมาแล้วหลายครั้งว่า agent ไม่ได้เรียก mix_pair_check.py จริงก่อนเขียนโค้ด — 2026-10-05)"""
    parents = getattr(mod, "META", {}).get("parents")
    if not parents or len(parents) != 2:
        return
    import mix_pair_check as MPC
    pa, pb = (str(p).split(".")[-1] for p in parents)
    used = [(ra, rb, method, result) for ra, rb, method, result in MPC.load_rows() if frozenset((ra, rb)) == frozenset((pa, pb))]
    print(f" mix_pair_check: S20.{pa} + S20.{pb} ลองไปแล้ว {len(used)}/{MPC.MAX_PER_PAIR} ครั้ง")
    for _, _, method, result in used:
        print(f"   - {method}: {result}")
    if len(used) >= MPC.MAX_PER_PAIR:
        print(f" ❌ ห้ามบันทึกผล: คู่นี้เกินเพดาน M3 (สูงสุด {MPC.MAX_PER_PAIR} ครั้งต่อคู่) — เปลี่ยนคู่ตัวแม่ก่อนรันใหม่")
        sys.exit(6)


def check_not_overwriting_kept_result(n, mod):
    """กันการ reuse sid ทับผลที่เก็บไว้แล้ว (ไม่ใช่ DUPLICATE) โดยไม่ตั้งใจ ด้วยโค้ด ไม่พึ่งข้อความ prompt อย่างเดียว
    (2026-10-05: antigravity reuse sid 467 ข้ามคู่ตัวแม่ทับผล PASS 2 ตัวถาวรก่อนเข้า final_gate — ตอนนั้นแก้แค่ข้อความใน prompt
    รอบถัดมา (519-614) ไม่เกิดซ้ำแล้ว แต่ใส่โค้ดกันไว้ด้วยเผื่อ agent ตัวอื่น/รอบอื่นพลาดอีก ใช้ได้ทั้ง to_the_moon/single/mix)"""
    path = os.path.join(ROOT, "strategy", f"s20.{n}", "result_365d.json")
    if not os.path.exists(path):
        return
    old = json.load(open(path, encoding="utf-8"))
    old_name, new_name = old.get("name", ""), getattr(mod, "META", {}).get("name", "")
    if old_name and new_name and old_name != new_name:
        print(f" ⚠️ S20.{n} มีผลเดิมอยู่แล้วชื่อ '{old_name}' (pass_tfs={old.get('pass_tfs')}) แต่โค้ดใหม่คือ '{new_name}' — กำลังจะเขียนทับ")
        if old.get("pass_tfs"):
            print(f" ❌ ผลเดิมเป็น PASS จริง ห้ามเขียนทับ: ลบ strategy/s20.{n}/ ทิ้งเองถ้าตั้งใจจริง มิฉะนั้นใช้ sid ใหม่แทน")
            sys.exit(7)


def auto_mix_check(n, parents, pass_tfs):
    """บังคับส่วนที่ 2 ของด่านสุดท้ายแบบผสม (mix_strategy_prompt.md) ด้วยโค้ด — เทียบกับตัวแม่ A (parents[0])
    ตามรูปแบบเดียวกับที่ใช้ตัดสิน S20.471/512 (เจอมาแล้วว่า agent ลืมรันขั้นนี้เองทั้งที่กฎบังคับ — 2026-10-06)"""
    pa = str(parents[0]).split(".")[-1]
    try:
        da = json.load(open(os.path.join(ROOT, "strategy", f"s20.{pa}", "result_365d.json"), encoding="utf-8"))
    except FileNotFoundError:
        print(f" ⚠️ หา result_365d.json ของตัวแม่ S20.{pa} ไม่เจอ — ข้าม mix_check")
        return
    res = json.load(open(os.path.join(ROOT, "strategy", f"s20.{n}", "result_365d.json"), encoding="utf-8"))
    lines, tf_ok = [], {}
    for tf in pass_tfs:
        v, va = res["tf"][tf], da["tf"].get(tf, {})
        ok_a = bool(va) and v["pf"] >= va["pf"] + 0.10 and v["oos"]["net"] >= va["oos"]["net"]
        ok_b = v["n"] >= 50
        fails = [k for k, ok in (("a", ok_a), ("b", ok_b)) if not ok]
        tf_ok[tf] = not fails
        lines.append(f"{tf}: PF {v['pf']} vs A {va.get('pf')} | OOS {v['oos']['net']} vs A {va.get('oos', {}).get('net')} | N {v['n']}"
                     + (f" -> FAIL {','.join(fails)}" if fails else " -> OK"))
    # หัวไฟล์ต่อ TF (กันกรณีหลาย TF ผลไม่เหมือนกัน — แต่ก่อนรวมเป็นก้อนเดียวทำให้ TF ที่ผ่านจริงถูกนับว่าไม่ผ่านไปด้วย)
    ok_tfs = [tf for tf, ok in tf_ok.items() if ok]
    head = f"MIX_OK: {','.join(ok_tfs)}" if ok_tfs else "MIX_FAIL: " + ", ".join(sorted({f for l in lines if "FAIL" in l for f in l.split("FAIL ")[1].split(",")}))
    if ok_tfs and len(ok_tfs) < len(pass_tfs):
        head += f" (ตกที่ {','.join(tf for tf in pass_tfs if tf not in ok_tfs)})"
    with open(os.path.join(ROOT, "strategy", f"s20.{n}", "mix_check.txt"), "w", encoding="utf-8", newline="\n") as f:
        f.write(head + "\n" + "\n".join(lines) + "\n")
    print(f" mix_check: {head}")
    for l in lines:
        print("   " + l)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("n", type=int)
    ap.add_argument("--no-docs", action="store_true")
    a = ap.parse_args()
    n = a.n
    _, _, mod0 = E.load_strategy(f"S20.{n}")
    old_path = os.path.join(ROOT, "strategy", f"s20.{n}", "result_365d.json")
    is_rerun = False
    if os.path.exists(old_path):
        old = json.load(open(old_path, encoding="utf-8"))
        is_rerun = old.get("name", "") == getattr(mod0, "META", {}).get("name", "")
    if is_rerun:
        print(f" S20.{n}: ชื่อกลยุทธ์เดิมกับผลที่มีอยู่ตรงกัน ถือเป็นการรันซ้ำของเดิม ข้ามเช็ค overwrite/pair-cap (เช็คแค่ตอนสร้างครั้งแรก)")
    else:
        check_not_overwriting_kept_result(n, mod0)
        check_mix_pair_cap(n, mod0)
        check_mix_parents_eligible(n, mod0)
    res, trades, _ = E.backtest(f"S20.{n}", 365)
    E.save_reports(res, trades, os.path.join(ROOT, "reports", f"s20_{n}"), n)
    u = uniqueness(n)
    res["uniqueness"] = u
    with open(os.path.join(ROOT, "strategy", f"s20.{n}", "result_365d.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(res, f, indent=1, ensure_ascii=False)
    with open(os.path.join(ROOT, "strategy", f"s20.{n}", f"backtest_s20_{n}.py"), "w", encoding="utf-8", newline="\n") as f:
        f.write(WRAPPER.replace("{n}", str(n)))
    print(f" uniqueness: max Jaccard={u['max_jaccard']} vs {u['with']} → {'UNIQUE' if u['unique'] else 'DUPLICATE!'}")
    if not u["unique"]:
        print(" ❌ ซ้ำกับกลยุทธ์ก่อนหน้า — ต้องเปลี่ยน logic ก่อนบันทึก")
        sys.exit(2)
    if not res["lookahead_ok"] and res["lookahead_ok"] is not None:
        print(" ❌ lookahead audit ไม่ผ่าน — ห้ามบันทึก")
        sys.exit(3)
    if not a.no_docs:
        docs.update(n, res)
    p = load_progress()
    p["done"][str(n)] = {"name": res["name"], "pass_tfs": res["pass_tfs"], "total_net": res["total"]["net"],
                         "total_pf": res["total"]["pf"]}
    p["next"] = n + 1
    save_progress(p)
    print(f" ✅ S20.{n} บันทึกแล้ว | next = S20.{n + 1}")

    if res["pass_tfs"]:
        print(f" มี TF ผ่าน PASS ({res['pass_tfs']}) -> รันด่านสุดท้ายอัตโนมัติ (final_gate.py + mix_check ถ้าเป็นตัวผสม)")
        import final_gate as FG
        FG.gate(n)
        _, _, mod2 = E.load_strategy(f"S20.{n}")
        parents = getattr(mod2, "META", {}).get("parents")
        if parents and len(parents) == 2:
            auto_mix_check(n, parents, res["pass_tfs"])


if __name__ == "__main__":
    main()
