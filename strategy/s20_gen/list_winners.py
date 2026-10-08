# -*- coding: utf-8 -*-
"""list_winners.py — รวมผู้ชนะ (final_gate WINNER, และถ้าเป็นตัวผสมต้อง mix_check MIX_OK ด้วย) จากทุกแคมเปญ S20.*

ใช้งาน:
    python strategy/s20_gen/list_winners.py

สแกน strategy/s20.*/final_gate.txt ทุกตัว พิมพ์ตารางผู้ชนะจริง (ผ่านครบทุกด่าน พร้อม forward demo)
และลิสต์ตัวที่ผ่าน final_gate แต่ตก mix_check แยกไว้ด้วย (กันสับสนว่าทำไมไม่ถูกนับ)
"""
import glob
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))


def main():
    winners, near_miss = [], []
    for f in sorted(glob.glob(os.path.join(ROOT, "strategy", "s20.*", "final_gate.txt")),
                     key=lambda p: int(re.search(r"s20\.(\d+)", p).group(1))):
        n = int(re.search(r"s20\.(\d+)", f).group(1))
        head = open(f, encoding="utf-8-sig").readline().strip()
        if not head.startswith("WINNER"):
            continue
        tfs = re.findall(r"\b(M1|M5|M15|M30|H1|H4|D1)\b", head)
        result_path = os.path.join(ROOT, "strategy", f"s20.{n}", "result_365d.json")
        if not os.path.exists(result_path):
            continue
        d = json.load(open(result_path, encoding="utf-8"))
        mix_path = os.path.join(ROOT, "strategy", f"s20.{n}", "mix_check.txt")
        is_mix = os.path.exists(mix_path)
        mix_ok_tfs = set()
        mix_head = ""
        if is_mix:
            mix_head = open(mix_path, encoding="utf-8-sig").readline().strip()
            # หัวไฟล์ตั้งแต่ 2026-10-07 เป็น "MIX_OK: TF1,TF2 (ตกที่ TF3)" — เช็คเป็นรายต่อ TF ไม่ใช่ก้อนเดียว (ของเก่าก่อนแก้มี "MIX_OK" เฉยๆ)
            m = re.match(r"MIX_OK:\s*([A-Z0-9,]+)", mix_head)
            if m:
                mix_ok_tfs = set(m.group(1).split(","))
            elif mix_head == "MIX_OK":
                mix_ok_tfs = set(tfs)
        for tf in tfs:
            v = d["tf"][tf]
            row = dict(n=n, name=d["name"], tf=tf, net=v["net"], pf=v["pf"], n_trades=v["n"],
                      oos_pf=v["oos"]["pf"], null_p=v["null"]["p"], is_mix=is_mix, mix_head=mix_head)
            (winners if (not is_mix or tf in mix_ok_tfs) else near_miss).append(row)

    fmt = lambda x: f"{x:+,.0f}"
    print(f"{'S20':>5} {'ชื่อ':<45} {'TF':<5} {'ไม้':>6} {'Net$':>9} {'PF':>6} {'OOS PF':>7} {'null p':>7}  ชนิด")
    print("-" * 100)
    for r in winners:
        kind = "mix(MIX_OK)" if r["is_mix"] else "เดี่ยว"
        print(f"{r['n']:>5} {r['name'][:45]:<45} {r['tf']:<5} {r['n_trades']:>6} {fmt(r['net']):>9} {r['pf']:>6} {r['oos_pf']:>7} {r['null_p']:>7}  {kind}")
    print(f"\nรวมผู้ชนะจริง (พร้อม forward demo): {len(winners)} รายการ จาก {len({r['n'] for r in winners})} กลยุทธ์")

    if near_miss:
        print(f"\nผ่าน final_gate (WINNER) แต่ตก mix_check — ไม่นับเป็นผู้ชนะ ({len(near_miss)} รายการ):")
        for r in near_miss:
            print(f"  S20.{r['n']} {r['name'][:40]:<40} {r['tf']:<5} -> {r['mix_head']}")


if __name__ == "__main__":
    main()
