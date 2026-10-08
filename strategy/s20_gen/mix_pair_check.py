# -*- coding: utf-8 -*-
"""mix_pair_check.py — บังคับเช็คกฎ M3 ของ mix_strategy_prompt.md ด้วยสคริปต์ ไม่ใช่ให้ agent จำเอง

ใช้งาน (ก่อนเขียน strategy20_<N>.py ของตัวผสมทุกครั้ง):
    python strategy/s20_gen/mix_pair_check.py 339 161

พิมพ์จำนวนครั้งที่คู่นี้ (ไม่สนลำดับ A/B หรือ sid) ถูกลองไปแล้วใน mix_log.md กับวิธีผสมที่ใช้ไปแล้ว
exit code 0 = ลองได้ (ยังไม่ครบ 2 ครั้ง), exit code 1 = ห้ามลองคู่นี้อีก (ครบ 2 ครั้งแล้วตามกฎ M3)
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
LOG = os.path.join(HERE, "mix_log.md")
MAX_PER_PAIR = 2

ROW = re.compile(
    r"\|\s*[^|]+\|\s*20\.(\d+)[^|]*\|\s*20\.(\d+)[^|]*\|\s*([^|]+?)\s*\|\s*[^|]+\|\s*([^|]+)\|"
)


def load_rows():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if not os.path.exists(LOG):
        return []
    rows = []
    for line in open(LOG, encoding="utf-8-sig"):
        m = ROW.match(line.strip())
        if m:
            a, b, method, result = m.groups()
            method = method.split("(")[0].strip().upper()
            rows.append((a, b, method, result.strip()))
    return rows


def main():
    if len(sys.argv) != 3:
        print("usage: mix_pair_check.py <parent_A_sid_number> <parent_B_sid_number>")
        sys.exit(2)
    a, b = sys.argv[1], sys.argv[2]
    pair = frozenset((a, b))
    rows = load_rows()
    used = [(method, result) for ra, rb, method, result in rows if frozenset((ra, rb)) == pair]
    print(f"คู่ S20.{a} + S20.{b}: ลองไปแล้ว {len(used)}/{MAX_PER_PAIR} ครั้ง")
    for method, result in used:
        print(f"  - {method}: {result}")
    if len(used) >= MAX_PER_PAIR:
        print(f"❌ ห้ามลองคู่นี้อีก (ครบ {MAX_PER_PAIR} ครั้งตามกฎ M3 แล้ว) — เลือกคู่ตัวแม่อื่น")
        sys.exit(1)
    tried_methods = {m for m, _ in used}
    remaining = {"CONFIRM", "FILTER", "VETO", "MTF"} - tried_methods
    print(f"วิธีผสมที่ยังไม่ลองกับคู่นี้: {sorted(remaining)}")
    sys.exit(0)


if __name__ == "__main__":
    main()
