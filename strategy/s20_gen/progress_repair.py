# -*- coding: utf-8 -*-
"""progress_repair.py — สร้าง strategy/s20_gen/progress.json ใหม่จาก result_365d.json ที่มีอยู่จริงบนดิสก์

เหตุผล: เจอซ้ำ 2 ครั้ง (2026-10-04, 2026-10-05) ว่า run_one.py พิมพ์ "✅ บันทึกแล้ว" (save_progress เขียนสำเร็จ
ตามโค้ด) แต่ progress.json ที่เหลืออยู่จริงกลับไม่มี entry ของหลายสิบ sid ทั้งที่ strategy.md/strategy_evolution.md
มีแถวครบ และ result_365d.json ของ sid นั้นก็มีอยู่จริง — สาเหตุยังไม่ทราบแน่ชัด (ไม่ใช่ race จากการรันขนาน
เพราะ timestamp เรียงลำดับปกติ) คาดว่าเกี่ยวกับการ sync ไฟล์ของเครื่อง ไม่ใช่บั๊กใน run_one.py เอง

ใช้งาน:
    python strategy/s20_gen/progress_repair.py          # ซ่อมจริง (เขียนทับ progress.json)
    python strategy/s20_gen/progress_repair.py --check  # แค่รายงานว่าหาย sid ไหนบ้าง ไม่เขียนไฟล์

สแกน strategy/s20.<N>/result_365d.json ทุกตัวที่ N อยู่ในช่วง [range[0], ตัวที่ใหญ่สุดที่พบ] แล้ว rebuild
ทั้ง "done" และ "next" ใหม่ทั้งหมด (ไม่ไว้ใจ progress.json เดิมเลย ยกเว้น "range")
"""
import argparse
import glob
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
PROGRESS = os.path.join(HERE, "progress.json")


def scan():
    done = {}
    for f in glob.glob(os.path.join(ROOT, "strategy", "s20.*", "result_365d.json")):
        m = re.search(r"s20\.(\d+)[\\/]result_365d\.json$", f.replace("\\", "/"))
        if not m:
            continue
        n = int(m.group(1))
        try:
            d = json.load(open(f, encoding="utf-8"))
        except Exception as e:
            print(f"  ข้าม S20.{n}: อ่านไม่ได้ ({e})")
            continue
        done[str(n)] = {"name": d.get("name", ""), "pass_tfs": d.get("pass_tfs", []),
                         "total_net": d.get("total", {}).get("net", 0.0),
                         "total_pf": d.get("total", {}).get("pf", 0.0)}
    return done


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="แค่รายงาน ไม่เขียนไฟล์")
    a = ap.parse_args()

    old = json.load(open(PROGRESS, encoding="utf-8")) if os.path.exists(PROGRESS) else {"range": [140, 299]}
    disk = scan()
    missing = sorted((int(k) for k in disk if k not in old.get("done", {})), key=int)
    extra = sorted((int(k) for k in old.get("done", {}) if k not in disk), key=int)

    print(f"บนดิสก์มี result_365d.json ของ {len(disk)} sid | progress.json เดิมมี {len(old.get('done', {}))} entries")
    print(f"หายจาก progress.json แต่มีไฟล์จริง: {missing or '(ไม่มี)'}")
    if extra:
        print(f"⚠️ มีใน progress.json แต่ไม่มีไฟล์จริง (อาจถูกลบเป็น DUPLICATE แล้วลืมลบ entry): {extra}")

    if a.check:
        return

    new = {"range": old.get("range", [140, 299]), "done": dict(sorted(disk.items(), key=lambda kv: int(kv[0])))}
    new["next"] = (max(int(k) for k in disk) + 1) if disk else new["range"][0]
    with open(PROGRESS, "w", encoding="utf-8", newline="\n") as f:
        json.dump(new, f, indent=1, ensure_ascii=False)
    print(f"ซ่อมแล้ว: done={len(new['done'])} entries, next={new['next']}")


if __name__ == "__main__":
    main()
