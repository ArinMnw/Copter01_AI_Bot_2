#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
archive_logs_by_month.py
─────────────────────────────────────────────────────────────────────────────
ย้าย/รวมข้อมูล log ที่ "ยังไม่ได้แยกตามเดือน" (bot.log, system/system.log,
logs/error.log ถ้ามี) ไปต่อในไฟล์รายเดือน เช่น

    logs/bot.log              -> logs/old_logs/bot-YYYY-MM.log
    logs/system/system.log    -> logs/old_logs/system-YYYY-MM.log
    logs/error.log            -> logs/error-YYYY-MM.log  (เดือนนี้)  / old_logs (เดือนก่อน)

คุณสมบัติ:
- อ่านแบบ streaming (รองรับไฟล์หลายร้อย MB โดยไม่กิน RAM)
- route แต่ละบรรทัดเข้าไฟล์เดือนของมันเองจาก timestamp `[YYYY-MM-DD HH:MM:SS]`
  (บรรทัด continuation ที่ไม่มี timestamp จะใช้เดือนของบรรทัดก่อนหน้า)
- system.log ใช้ timestamp รูปแบบ `YYYY-MM-DD HH:MM:SS,mmm` (ไม่มี [])
- ป้องกันการซ้ำ: ถ้าไฟล์เดือนปลายทางมีอยู่แล้ว จะ backup เป็น .bak-<runts>
  ก่อนเขียนใหม่ (กันบรรทัดซ้ำจาก fragment เดิม เช่น bot-2026-05.log 5/20-5/22)
- UTF-8 ตลอด (errors='replace')

⚠️ ควรรันตอน "หยุด bot แล้ว" เพื่อไม่ให้ชน file handle ที่เปิดค้างอยู่

วิธีใช้:
    python archive_logs_by_month.py            # รันจริง
    python archive_logs_by_month.py --dry-run  # แสดงผลที่จะทำ ไม่แตะไฟล์
"""

import os
import re
import sys
import io
import time
from datetime import datetime

# force UTF-8 stdout เพื่อให้ภาษาไทยแสดงถูกต้องทุก terminal (รวม Windows CMD)
if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT       = os.path.dirname(os.path.abspath(__file__))
LOG_DIR    = os.path.join(ROOT, "logs")
OLD_DIR    = os.path.join(LOG_DIR, "old_logs")
SYS_DIR    = os.path.join(LOG_DIR, "system")

# timestamp ที่ต้นบรรทัด:  [2026-05-27 01:29:04]  หรือ  2026-05-27 01:29:04,123
_TS_RE = re.compile(r"^\[?(\d{4})-(\d{2})-(\d{2})[ T]\d{2}:\d{2}:\d{2}")

DRY = "--dry-run" in sys.argv
RUN_TS = datetime.now().strftime("%Y%m%d-%H%M%S")


def _month_of(line: str):
    """คืน (year, month) จาก timestamp ต้นบรรทัด หรือ None ถ้าไม่มี"""
    m = _TS_RE.match(line)
    if not m:
        return None
    return (m.group(1), m.group(2))   # ('2026', '05')


def _target_path(prefix: str, ym: tuple, cur_ym: tuple) -> str:
    """
    path ปลายทางของไฟล์รายเดือน
    - error เดือนปัจจุบัน -> logs/error-YYYY-MM.log
    - ที่เหลือ            -> logs/old_logs/<prefix>-YYYY-MM.log
    """
    year, month = ym
    name = f"{prefix}-{year}-{month}.log"
    if prefix == "error" and ym == cur_ym:
        return os.path.join(LOG_DIR, name)
    return os.path.join(OLD_DIR, name)


def _backup_if_exists(path: str) -> str | None:
    """ถ้าไฟล์ปลายทางมีอยู่ → rename เป็น .bak-<runts> กันบรรทัดซ้ำ"""
    if not os.path.exists(path):
        return None
    bak = f"{path}.bak-{RUN_TS}"
    if DRY:
        print(f"   [dry] backup {os.path.basename(path)} -> {os.path.basename(bak)}")
        return bak
    os.rename(path, bak)
    print(f"   backup {os.path.basename(path)} -> {os.path.basename(bak)}")
    return bak


def process_source(src_path: str, prefix: str, cur_ym: tuple) -> dict:
    """split ไฟล์ src ออกเป็นรายเดือน แล้ว append เข้าไฟล์ปลายทาง"""
    result = {"src": src_path, "exists": False, "lines": 0, "months": {}, "bytes": 0}
    if not os.path.exists(src_path):
        print(f"  - {src_path}: ไม่พบไฟล์ (ข้าม)")
        return result
    size = os.path.getsize(src_path)
    result["exists"] = True
    result["bytes"] = size
    print(f"  + {src_path}  ({size/1024/1024:.1f} MB)")

    # ── เตรียม source ──────────────────────────────────────────────────────────
    # พยายาม rename ก่อน (กรณีหยุด bot แล้ว) เพื่อให้ bot สร้างไฟล์ใหม่สะอาด
    # ถ้า rename ไม่ได้ (ไฟล์ถูก lock โดย bot ที่ยังรันอยู่) → fallback อ่านโดยตรง
    # แล้ว truncate หลัง archive (bot จะเขียน log ต่อจาก position 0 ของไฟล์ว่าง)
    work_path = src_path + ".archiving"
    locked_mode = False   # True = อ่านตรงจาก src แล้ว truncate, False = rename→.archiving→ลบ
    if not DRY:
        if os.path.exists(work_path):
            try:
                os.remove(work_path)
            except PermissionError:
                pass
        try:
            os.rename(src_path, work_path)
        except PermissionError:
            # ไฟล์ถูก lock โดย process อื่น — อ่านโดยตรงแล้ว truncate ทีหลัง
            locked_mode = True
            work_path   = src_path
            print("    [LOCK] file locked (bot running) -- reading directly + truncate after archive")
    else:
        work_path = src_path  # dry-run อ่านไฟล์เดิม

    # ── backup ไฟล์ปลายทางที่มีอยู่ก่อน (กันซ้ำ) — ทำครั้งเดียวต่อเดือน ──
    backed_up: set = set()
    writers: dict = {}      # ym -> file handle
    last_ym = None

    try:
        with open(work_path, "r", encoding="utf-8", errors="replace") as fin:
            for line in fin:
                result["lines"] += 1
                ym = _month_of(line) or last_ym
                if ym is None:
                    # บรรทัดแรกๆ ที่ยังไม่มี ts -> ใส่เดือนปัจจุบันกันข้อมูลหาย
                    ym = cur_ym
                last_ym = ym

                if ym not in writers:
                    tgt = _target_path(prefix, ym, cur_ym)
                    if tgt not in backed_up:
                        _backup_if_exists(tgt)
                        backed_up.add(tgt)
                    if DRY:
                        writers[ym] = None
                    else:
                        os.makedirs(os.path.dirname(tgt), exist_ok=True)
                        writers[ym] = open(tgt, "a", encoding="utf-8")
                    result["months"].setdefault(ym, 0)

                result["months"][ym] += 1
                if not DRY:
                    writers[ym].write(line)
    finally:
        for w in writers.values():
            if w:
                w.close()

    # ── cleanup ────────────────────────────────────────────────────────────────
    if not DRY:
        if locked_mode:
            # truncate ไฟล์ต้นฉบับ (bot จะเขียนต่อจาก position 0 = ไฟล์ใหม่สะอาด)
            try:
                with open(src_path, "w", encoding="utf-8"):
                    pass
                print(f"    [OK] truncated {os.path.basename(src_path)}")
            except PermissionError:
                print(f"    [WARN] cannot truncate -- bot will continue writing to existing file")
        else:
            # ลบ .archiving (ข้อมูลถูกย้ายหมดแล้ว)
            if os.path.exists(work_path):
                os.remove(work_path)

    for ym, n in sorted(result["months"].items()):
        tgt = _target_path(prefix, ym, cur_ym)
        print(f"      {ym[0]}-{ym[1]}: {n:>8d} บรรทัด -> {os.path.relpath(tgt, ROOT)}")
    return result


def main():
    os.makedirs(OLD_DIR, exist_ok=True)
    cur_ym = (datetime.now().strftime("%Y"), datetime.now().strftime("%m"))
    print("=" * 70)
    print(f"archive_logs_by_month  {'[DRY-RUN]' if DRY else '[RUN]'}  เดือนปัจจุบัน={cur_ym[0]}-{cur_ym[1]}")
    print("=" * 70)

    sources = [
        (os.path.join(LOG_DIR, "bot.log"),        "bot"),
        (os.path.join(SYS_DIR, "system.log"),     "system"),
        (os.path.join(LOG_DIR, "error.log"),      "error"),   # ถ้ามีไฟล์ error.log ที่ยังไม่ split
    ]

    grand = 0
    for src, prefix in sources:
        r = process_source(src, prefix, cur_ym)
        grand += r["lines"]

    print("=" * 70)
    print(f"รวมทั้งหมด {grand} บรรทัด {'(dry-run ไม่ได้เขียนไฟล์)' if DRY else 'ย้ายเสร็จ'}")
    print("=" * 70)


if __name__ == "__main__":
    main()
