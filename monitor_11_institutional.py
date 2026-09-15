# -*- coding: utf-8 -*-
"""
monitor_11_institutional.py
Live monitor checklist for 11 Institutional Strategies (S20.18 to S20.304)
Reads live bot state and logs from profile demo-iux-2101183586.
"""

import os
import sys
import json
import re
import datetime
from datetime import timezone, timedelta

# Ensure UTF-8 output on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
PROFILE_DIR = os.path.join(ROOT_DIR, "profiles", "demo", "demo-iux-2101183586")
STATE_FILE = os.path.join(PROFILE_DIR, "bot_state.json")
LOG_FILE = os.path.join(PROFILE_DIR, "logs", "bot.log")
TRACKER_FILE = os.path.join(ROOT_DIR, "institutional_order_tracker.json")

BKK = timezone(timedelta(hours=7))

TARGET_STRATEGIES = [
    "20.18", "20.19", "20.20", "20.21", "20.22",
    "20.24", "20.28", "20.301", "20.302", "20.303", "20.304"
]

S304_SYMBOLS = [
    "XAUUSD.iux", "XAGUSD.iux", "EURUSD.iux", "GBPUSD.iux", "USDJPY.iux"
]

def load_tracker():
    if os.path.exists(TRACKER_FILE):
        try:
            with open(TRACKER_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "start_time": datetime.datetime.now(BKK).strftime("%Y-%m-%d %H:%M:%S"),
        "strategies": {s: [] for s in TARGET_STRATEGIES},
        "s304_symbols": {sym: [] for sym in S304_SYMBOLS},
        "all_completed": False
    }

def save_tracker(data):
    with open(TRACKER_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def scan_live_state():
    tracker = load_tracker()
    
    # 1. Read bot_state.json
    state = {}
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                state = json.load(f)
        except Exception as e:
            print(f"Error reading bot_state.json: {e}")

    pos_sid = state.get("position_sid", {})
    pos_pat = state.get("position_pattern", {})
    pos_tf = state.get("position_tf", {})

    for ticket_str, sid_val in pos_sid.items():
        sid_str = str(sid_val)
        if sid_str in TARGET_STRATEGIES:
            pat = pos_pat.get(ticket_str, "")
            tf = pos_tf.get(ticket_str, "")
            existing = [x["ticket"] for x in tracker["strategies"][sid_str]]
            ticket_int = int(ticket_str)
            if ticket_int not in existing:
                # Infer symbol
                sym = "XAUUSD.iux"
                for target_sym in S304_SYMBOLS:
                    clean = target_sym.split(".")[0]
                    if clean in pat:
                        sym = target_sym
                        break
                rec = {
                    "ticket": ticket_int,
                    "symbol": sym,
                    "tf": tf,
                    "pattern": pat,
                    "time": state.get("saved_at", datetime.datetime.now(BKK).strftime("%Y-%m-%d %H:%M:%S"))
                }
                tracker["strategies"][sid_str].append(rec)
                
                if sid_str == "20.304":
                    for sym_name in S304_SYMBOLS:
                        if sym_name == sym or sym_name.split(".")[0] in pat:
                            if ticket_int not in [x["ticket"] for x in tracker["s304_symbols"][sym_name]]:
                                tracker["s304_symbols"][sym_name].append(rec)

    # 2. Parse bot.log for historical ORDER_CREATED lines
    if os.path.exists(LOG_FILE):
        try:
            with open(LOG_FILE, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    if "ORDER_CREATED" in line:
                        # Extract sid
                        m_sid = re.search(r"sid=([0-9.]+)", line)
                        m_ticket = re.search(r"ticket=(\d+)", line)
                        m_tf = re.search(r"tf=([A-Za-z0-9]+)", line)
                        m_time = re.search(r"\[([0-9\- :]+)\]", line)
                        if m_sid and m_ticket:
                            sid = m_sid.group(1)
                            ticket = int(m_ticket.group(1))
                            tf = m_tf.group(1) if m_tf else ""
                            t_str = m_time.group(1) if m_time else ""
                            
                            # Symbol
                            sym = "XAUUSD.iux"
                            for target_sym in S304_SYMBOLS:
                                clean = target_sym.split(".")[0]
                                if clean in line:
                                    sym = target_sym
                                    break
                            
                            if sid in TARGET_STRATEGIES:
                                existing = [x["ticket"] for x in tracker["strategies"][sid]]
                                if ticket not in existing:
                                    rec = {
                                        "ticket": ticket,
                                        "symbol": sym,
                                        "tf": tf,
                                        "pattern": f"S{sid}_{sym.split('.')[0]}",
                                        "time": t_str
                                    }
                                    tracker["strategies"][sid].append(rec)

                            if sid == "20.304":
                                for sym_name in S304_SYMBOLS:
                                    clean = sym_name.split(".")[0]
                                    if clean in line or sym_name in line:
                                        if ticket not in [x["ticket"] for x in tracker["s304_symbols"][sym_name]]:
                                            tracker["s304_symbols"][sym_name].append({
                                                "ticket": ticket,
                                                "symbol": sym_name,
                                                "tf": tf,
                                                "time": t_str
                                            })
        except Exception as e:
            print(f"Error parsing bot.log: {e}")

    # Check overall completion
    all_strats_found = all(len(tracker["strategies"][s]) > 0 for s in TARGET_STRATEGIES)
    all_s304_syms_found = all(len(tracker["s304_symbols"][sym]) > 0 for sym in S304_SYMBOLS)
    tracker["all_completed"] = all_strats_found and all_s304_syms_found

    save_tracker(tracker)
    return tracker

def generate_report(tracker):
    now_str = datetime.datetime.now(BKK).strftime("%Y-%m-%d %H:%M:%S")
    lines = []
    lines.append(f"📊 **Institutional Strategy Checklist Report** (เวลา BKK: `{now_str}`)")
    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    
    # 1. 11 Strategies Summary
    strat_found_count = sum(1 for s in TARGET_STRATEGIES if len(tracker["strategies"][s]) > 0)
    lines.append(f"### 1. ความคืบหน้า 11 กลยุทธ์: **{strat_found_count}/{len(TARGET_STRATEGIES)}**")
    lines.append("| กลยุทธ์ | Symbol ที่ตั้งค่า | สถานะ Order | ออเดอร์ล่าสุด | Timeframe | เวลา |")
    lines.append("|---|---|---|---|---|---|")
    for s in TARGET_STRATEGIES:
        orders = tracker["strategies"][s]
        configured_sym = "All 5 Symbols" if s == "20.304" else "XAUUSD.iux"
        if orders:
            latest = orders[-1]
            lines.append(f"| **S{s}** | `{configured_sym}` | ✅ **เจอ Order แล้ว** ({len(orders)} ไม้) | Ticket `#{latest['ticket']}` | `{latest.get('tf', '-')}` | `{latest.get('time', '-')}` |")
        else:
            lines.append(f"| **S{s}** | `{configured_sym}` | ⏳ กำลังรอ Setup แท่งเทียน | - | - | - |")
            
    lines.append("")
    # 2. S20.304 Multi-Symbol Summary
    s304_found_count = sum(1 for sym in S304_SYMBOLS if len(tracker["s304_symbols"][sym]) > 0)
    lines.append(f"### 2. S20.304 Cross-Asset Checklist: **{s304_found_count}/{len(S304_SYMBOLS)}** สัญลักษณ์")
    lines.append("| สัญลักษณ์ | สถานะ Order | Ticket ล่าสุด | Timeframe | เวลา |")
    lines.append("|---|---|---|---|---|")
    for sym in S304_SYMBOLS:
        orders = tracker["s304_symbols"][sym]
        if orders:
            latest = orders[-1]
            lines.append(f"| `{sym}` | ✅ **เจอ Order แล้ว** ({len(orders)} ไม้) | Ticket `#{latest['ticket']}` | `{latest.get('tf', '-')}` | `{latest.get('time', '-')}` |")
        else:
            lines.append(f"| `{sym}` | ⏳ ตรวจสอบสแกนอยู่ (รอวางออเดอร์) | - | - | - |")

    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    if tracker["all_completed"]:
        lines.append("🎉 **เป้าหมายสำเร็จครบถ้วน 100%!** พบ Order ครบทั้ง 11 กลยุทธ์ และครบทุกสัญลักษณ์ของ S20.304 เรียบร้อยแล้วค่ะ")
    else:
        lines.append("🔄 **สถานะการติดตาม:** ระบบกำลังรันบอทและมอนิเตอร์ให้อย่างต่อเนื่องทุกชั่วโมงจนกว่าจะครบทั้งหมดค่ะ")
        
    return "\n".join(lines)

if __name__ == "__main__":
    tracker = scan_live_state()
    report = generate_report(tracker)
    print(report)
