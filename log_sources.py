#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
log_sources.py — helper กลางสำหรับรวมไฟล์ bot log ทุกแบบ
ใช้โดย sim_*/check_*/analyze_*/backtest_* scripts

รองรับไฟล์:
- logs/bot.log                          (active เดือนปัจจุบัน)
- logs/old_logs/bot-YYYY-MM.log         (monthly archive)
- logs/old_logs/bot-YYYY-MM-DD-NN.log   (daily-split จาก archive_logs ตอนเกิน 100 MB)
- logs/old_logs/bot-*.log.bak-*         (backup จากการรัน archive ซ้ำ)

ออกแบบให้ time-window filter ของแต่ละ script ทำงานต่อได้เหมือนเดิม
(อ่านทุกไฟล์ แล้ว filter ตามช่วงเวลาในตัว script)
"""
import os
import glob

# bot-2026-06.log / bot-2026-06-14-00.log (ไม่รวม .bak)
_ARCHIVE_GLOB = "bot-2[0-9][0-9][0-9]-[0-9][0-9]*.log"
# bot-2026-06.log.bak-... / bot-2026-06-14-00.log.bak-...
_BAK_GLOB     = "bot-2[0-9][0-9][0-9]-[0-9][0-9]*.log.bak-*"


def bot_log_files(root: str = None, include_bak: bool = True) -> list:
    """คืน list path ของ bot log ทั้งหมด เรียงเก่า→ใหม่ (archive ก่อน, bot.log ท้ายสุด), dedup

    root: โฟลเดอร์ที่มี logs/ (default = โฟลเดอร์ของไฟล์นี้)
    include_bak: รวมไฟล์ .bak-* ด้วยหรือไม่ (default True ตามพฤติกรรมเดิมของ sim scripts)
    """
    if root is None:
        root = os.path.dirname(os.path.abspath(__file__))
    log_dir = os.path.join(root, "logs")
    old_dir = os.path.join(log_dir, "old_logs")

    files = sorted(glob.glob(os.path.join(old_dir, _ARCHIVE_GLOB)))
    if include_bak:
        files += sorted(glob.glob(os.path.join(old_dir, _BAK_GLOB)))
    active = os.path.join(log_dir, "bot.log")
    if os.path.exists(active):
        files.append(active)

    seen, uniq = set(), []
    for p in files:
        ap = os.path.abspath(p)
        if ap not in seen and os.path.isfile(p):
            seen.add(ap)
            uniq.append(p)
    return uniq


def iter_bot_log_lines(root: str = None, include_bak: bool = True):
    """yield ทุกบรรทัดจาก bot log ทั้งหมดตามลำดับเก่า→ใหม่ (เปิด/ปิดทีละไฟล์ ไม่กิน RAM)"""
    for p in bot_log_files(root, include_bak):
        try:
            with open(p, "r", encoding="utf-8", errors="replace") as f:
                for line in f:
                    yield line
        except OSError:
            continue
