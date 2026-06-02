#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sim_sl_guard.py — Simulate SL Guard Group ย้อนหลังจาก log
จำลอง: activation / block / unblock ตาม logic เดียวกับ trailing.py
แสดง: orders ที่จะถูก block, orders ที่จะถูกปิดก่อน SL, P/L diff

Usage: python sim_sl_guard.py [--from YYYY-MM-DD] [--verbose]
"""
import os, re, io, sys, glob, time as _time
from collections import defaultdict
from datetime import datetime, timezone, timedelta

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
ROOT = os.path.dirname(os.path.abspath(__file__))
BKK  = timezone(timedelta(hours=7))

SIM_START   = "2026-06-01"          # วันเริ่ม sim
THRESHOLD   = 2                      # SL hits ต้องครบ 2 จึง activate
GROUPS = [                           # ต้องตรงกับ config.SL_GUARD_GROUP_GROUPS
    ["H4","H12","D1"],
    ["H1","H4","H12"],
    ["M30","H1","H4"],
    ["M15","M30","H1"],
    ["M5","M15","M30"],
    ["M1","M5","M15"],
    ["M1","M5"],
]
# S9/S10/S14 bypass guard (ไม่นับ SL hit จาก bypass sids)
BYPASS_SIDS = {9, 10, 14}
# Sids that bypass the block check (can still place orders when blocked)
BYPASS_BLOCK_SIDS = {9, 10, 14}

# ─────────────────────────────────────────────────────────────────────
# Log file reader
# ─────────────────────────────────────────────────────────────────────
def _log_files():
    log_dir = os.path.join(ROOT, "logs")
    result = []
    for name in ["old_logs/bot-2026-05.log", "old_logs/bot-2026-06.log",
                 "bot.log"]:
        p = os.path.join(log_dir, name)
        if os.path.exists(p):
            result.append(p)
    for p in sorted(glob.glob(os.path.join(log_dir, "old_logs", "bot-2026-06.log.bak-*"))):
        if p not in result:
            result.append(p)
    return result

_TS = re.compile(r"^\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\]")
def fld(line, key):
    m = re.search(rf"{key}=([^|\s]+)", line)
    return m.group(1).strip() if m else None

def parse_events():
    """Parse log → list of dicts sorted by timestamp"""
    events = []
    seen_close = set()
    for path in _log_files():
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                for line in f:
                    m = _TS.match(line)
                    if not m:
                        continue
                    ts_str = m.group(1)
                    if ts_str[:10] < SIM_START:
                        continue
                    ev_m = re.match(r"^\[\S+ \S+\]\s+(\S+)", line)
                    if not ev_m:
                        continue
                    ev_type = ev_m.group(1)

                    if ev_type == "POSITION_CLOSED":
                        ticket = fld(line, "ticket")
                        if not ticket or ticket in seen_close:
                            continue
                        seen_close.add(ticket)
                        side   = fld(line, "side")
                        tf     = fld(line, "tf")
                        sid    = fld(line, "sid")
                        profit_s = fld(line, "profit")
                        profit = float(profit_s) if profit_s else 0.0
                        close_type = "SL" if "SL Hit" in line else ("TP" if "TP Hit" in line else "BOT")
                        events.append({
                            "ts": ts_str, "type": "CLOSE",
                            "ticket": ticket, "side": side, "tf": tf,
                            "sid": int(sid) if sid and sid.isdigit() else 0,
                            "profit": profit, "close_type": close_type,
                        })

                    elif ev_type == "ORDER_CREATED":
                        ticket = fld(line, "ticket")
                        if not ticket:
                            continue
                        side   = fld(line, "signal") or fld(line, "side")
                        tf     = fld(line, "tf")
                        sid    = fld(line, "sid")
                        entry  = fld(line, "entry")
                        sl     = fld(line, "sl")
                        tp     = fld(line, "tp")
                        events.append({
                            "ts": ts_str, "type": "ORDER_CREATED",
                            "ticket": ticket, "side": side, "tf": tf,
                            "sid": int(sid) if sid and sid.isdigit() else 0,
                            "entry": float(entry) if entry else 0.0,
                            "sl": float(sl) if sl else 0.0,
                            "tp": float(tp) if tp else 0.0,
                        })

                    elif ev_type == "ENTRY_FILL":
                        ticket = fld(line, "ticket")
                        if not ticket:
                            continue
                        side   = fld(line, "side")
                        tf     = fld(line, "tf")
                        sid    = fld(line, "sid")
                        price  = fld(line, "price")
                        events.append({
                            "ts": ts_str, "type": "ENTRY_FILL",
                            "ticket": ticket, "side": side, "tf": tf,
                            "sid": int(sid) if sid and sid.isdigit() else 0,
                            "price": float(price) if price else 0.0,
                        })
        except Exception as e:
            pass

    events.sort(key=lambda x: x["ts"])
    return events

# ─────────────────────────────────────────────────────────────────────
# Guard simulation state
# ─────────────────────────────────────────────────────────────────────
def _gkey(group): return "+".join(group)

class GuardSim:
    def __init__(self):
        # {side: {gkey: {count, active, tf_blocked, tf_since, tf_swing_ref}}}
        self.state = {}
        # {ticket: {side, tf, entry_ts}} open positions
        self.open_pos = {}
        # results
        self.activations    = []   # (ts, side, gkey, count)
        self.blocked_orders = []   # orders that would have been blocked
        self.proactive_closes= []  # positions that would have been closed by guard
        self.unblocks       = []   # (ts, side, tf, gkey)
        # unblock heuristic: use next TP Hit on blocked TF or timeout
        self._pending_unblock = {}  # {(side,gkey): ts_activated}

    def record_sl(self, ts, tf, side, profit, sid):
        """SL hit landed — record in guard state"""
        if profit >= 0:
            return []  # profitable SL → ไม่นับ
        if sid in BYPASS_SIDS:
            return []  # bypass strategies ไม่นับ
        side = side.upper()
        activated = []
        for group in GROUPS:
            if tf not in group:
                continue
            gkey = _gkey(group)
            sg_side = self.state.setdefault(side, {})
            sg = sg_side.setdefault(gkey, {
                "count": 0, "active": False,
                "tf_blocked": {}, "tf_since": {},
            })
            sg["count"] += 1
            if sg["count"] >= THRESHOLD and not sg["active"]:
                sg["active"] = True
                for t in group:
                    sg["tf_blocked"][t] = True
                    sg["tf_since"][t] = ts
                activated.append((gkey, group, sg["count"]))
                self.activations.append((ts, side, gkey, sg["count"]))
                self._pending_unblock[(side, gkey)] = ts
        return activated

    def is_blocked(self, tf, side):
        side = side.upper()
        for sg in self.state.get(side, {}).values():
            if sg.get("active") and sg.get("tf_blocked", {}).get(tf):
                return True
        return False

    def check_unblock_by_tp(self, ts, tf, side, close_type):
        """TP Hit on blocked TF → unblock that TF (swing formed)"""
        if close_type != "TP":
            return
        side = side.upper()
        for gkey, sg in self.state.get(side, {}).items():
            if sg.get("active") and sg.get("tf_blocked", {}).get(tf):
                sg["tf_blocked"][tf] = False
                group_tfs = gkey.split("+")
                all_clear = all(not sg["tf_blocked"].get(t) for t in group_tfs)
                if all_clear:
                    sg["active"] = False
                    sg["count"] = 0
                    self._pending_unblock.pop((side, gkey), None)
                self.unblocks.append((ts, side, tf, gkey))

    def check_unblock_by_timeout(self, ts, timeout_min=60):
        """หลัง N นาที ไม่มี SL hit ใหม่ → unblock (heuristic)"""
        for (side, gkey), act_ts in list(self._pending_unblock.items()):
            delta = (datetime.strptime(ts, "%Y-%m-%d %H:%M:%S") -
                     datetime.strptime(act_ts, "%Y-%m-%d %H:%M:%S")).total_seconds()
            if delta >= timeout_min * 60:
                sg = self.state.get(side, {}).get(gkey)
                if sg and sg.get("active"):
                    # reset
                    sg["active"] = False
                    sg["count"] = 0
                    for t in sg["tf_blocked"]:
                        sg["tf_blocked"][t] = False
                    self.unblocks.append((ts, side, "ALL", gkey))
                del self._pending_unblock[(side, gkey)]

# ─────────────────────────────────────────────────────────────────────
# Main simulation
# ─────────────────────────────────────────────────────────────────────
def run_sim():
    print("Loading log events from", SIM_START, "...")
    events = parse_events()
    print(f"Loaded {len(events)} events")

    guard = GuardSim()
    # ticket → result from POSITION_CLOSED
    close_map = {e["ticket"]: e for e in events if e["type"] == "CLOSE"}
    # ticket → ORDER_CREATED
    order_map  = {e["ticket"]: e for e in events if e["type"] == "ORDER_CREATED"}
    # ticket → ENTRY_FILL
    fill_map   = {e["ticket"]: e for e in events if e["type"] == "ENTRY_FILL"}

    blocked_orders  = []   # {ticket, ts, side, tf, sid, outcome, pl_actual}
    proactive_close = []   # {ticket, ts_activate, ts_actual_close, side, tf, pl_actual, close_type}

    # Track which positions were open at each activation
    open_fills = {}  # ticket → {ts_fill, side, tf, sid}

    # Timeout heuristic: 45 minutes
    TIMEOUT_MIN = 45

    for ev in events:
        ts   = ev["ts"]
        etype = ev["type"]

        # Check timeout unblock
        guard.check_unblock_by_timeout(ts, timeout_min=TIMEOUT_MIN)

        if etype == "ENTRY_FILL":
            open_fills[ev["ticket"]] = {
                "ts": ts, "side": ev["side"], "tf": ev["tf"], "sid": ev["sid"]
            }

        elif etype == "CLOSE":
            t = ev["ticket"]
            # Check unblock by TP
            if ev["tf"]:
                guard.check_unblock_by_tp(ts, ev["tf"], ev["side"] or "", ev["close_type"])
            # Remove from open fills
            open_fills.pop(t, None)

            # Record SL hit → guard state
            if ev["close_type"] == "SL":
                activated = guard.record_sl(ts, ev["tf"] or "", ev["side"] or "",
                                            ev["profit"], ev["sid"])
                # For each activation: find open positions to proactively close
                for gkey, group, count in activated:
                    side = ev["side"].upper() if ev["side"] else ""
                    for tk, finfo in list(open_fills.items()):
                        if finfo["side"] and finfo["side"].upper() == side:
                            ftf = finfo["tf"] or ""
                            # Normalize composite TF
                            ftf_parts = re.split(r'[+_\[\]]', ftf)
                            if any(p in group for p in ftf_parts):
                                # This position would have been closed proactively
                                cl = close_map.get(tk)
                                proactive_close.append({
                                    "ticket": tk,
                                    "ts_activate": ts,
                                    "ts_actual_close": cl["ts"] if cl else "OPEN",
                                    "side": side,
                                    "tf": ftf,
                                    "sid": finfo["sid"],
                                    "pl_actual": cl["profit"] if cl else None,
                                    "actual_fate": cl["close_type"] if cl else "OPEN",
                                    "gkey": gkey,
                                })

        elif etype == "ORDER_CREATED":
            t  = ev["ticket"]
            tf = ev["tf"] or ""
            sd = (ev["side"] or "").upper()
            sid = ev["sid"]

            if not tf or not sd:
                continue
            if sid in BYPASS_BLOCK_SIDS:
                continue

            # Normalize composite TF (e.g. [M1+M5] → check M1, M5)
            tf_parts = re.split(r'[+_\[\]]', tf)
            tf_parts = [p for p in tf_parts if p]

            # Check if any TF in this order is blocked
            blocked_tf = next((p for p in tf_parts if guard.is_blocked(p, sd)), None)
            if not blocked_tf:
                continue

            # This order would have been blocked!
            cl = close_map.get(t)
            blocked_orders.append({
                "ticket": t,
                "ts_created": ts,
                "side": sd,
                "tf": tf,
                "blocked_tf": blocked_tf,
                "sid": sid,
                "pl_actual": cl["profit"] if cl else None,
                "actual_fate": cl["close_type"] if cl else "OPEN",
            })

    return guard, blocked_orders, proactive_close

# ─────────────────────────────────────────────────────────────────────
# Report
# ─────────────────────────────────────────────────────────────────────
def report(guard, blocked_orders, proactive_close):
    print()
    print("=" * 80)
    print(f"  SL GUARD GROUP SIM — {SIM_START} ถึงปัจจุบัน")
    print("=" * 80)

    # Activations
    print(f"\n🛡️  Guard Activations: {len(guard.activations)}")
    for ts, side, gkey, cnt in guard.activations:
        print(f"  {ts}  {side} group=[{gkey}] count={cnt}")

    print(f"\n🔓 Guard Unblocks: {len(guard.unblocks)}")
    for ts, side, tf, gkey in guard.unblocks:
        print(f"  {ts}  {side} [{tf}] group=[{gkey}]")

    # Blocked orders
    print()
    print("=" * 80)
    print(f"  🚫 BLOCKED ORDERS (สร้างระหว่าง guard active) — {len(blocked_orders)} orders")
    print("=" * 80)
    print(f"  {'ts_created':22} {'ticket':12} {'sd':4} {'tf':15} {'sid':4} {'fate':6} {'P/L':8}")
    print("  " + "-" * 75)

    total_blocked_pl = 0.0
    blocked_loss = 0
    blocked_gain = 0
    blocked_open = 0
    for o in sorted(blocked_orders, key=lambda x: x["pl_actual"] or 0):
        pl    = o["pl_actual"]
        fate  = o["actual_fate"]
        pl_s  = f"{pl:+.2f}" if pl is not None else "OPEN"
        if pl is None:
            blocked_open += 1
        elif pl < 0:
            blocked_loss += 1
            total_blocked_pl += pl
        else:
            blocked_gain += 1
            total_blocked_pl += pl
        print(f"  {o['ts_created']:22} {o['ticket']:12} {o['side']:4} {o['tf']:15} S{o['sid']:3} {fate:6} {pl_s:8}")

    print(f"\n  รวม blocked: {len(blocked_orders)} orders")
    print(f"  ขาดทุน: {blocked_loss} | กำไร: {blocked_gain} | open: {blocked_open}")
    print(f"  P/L รวมที่ SAVED (loss blocked): {total_blocked_pl:+.2f} USD")

    # Proactive closes
    print()
    print("=" * 80)
    print(f"  ⚡ PROACTIVE CLOSE (guard ปิดก่อน SL) — {len(proactive_close)} positions")
    print("=" * 80)
    print(f"  {'activate':22} {'ticket':12} {'sd':4} {'tf':12} {'sid':4} {'actual_fate':10} {'actual_pl':9}")
    print("  " + "-" * 75)

    total_proactive_saved = 0.0
    for pc in sorted(proactive_close, key=lambda x: x.get("pl_actual") or 0):
        pl   = pc["pl_actual"]
        fate = pc["actual_fate"]
        # Proactive close saves the difference between close-at-activation price and actual SL
        # We approximate: if SL Hit → saved (positive) | TP Hit → missed (negative)
        pl_s = f"{pl:+.2f}" if pl is not None else "OPEN"
        tag  = ""
        if fate == "SL" and pl is not None and pl < 0:
            total_proactive_saved += abs(pl)  # would have closed at breakeven vs SL loss
            tag = "← SAVED"
        elif fate == "TP":
            tag = "← MISSED TP"
        print(f"  {pc['ts_activate']:22} {pc['ticket']:12} {pc['side']:4} {pc['tf']:12} S{pc['sid']:3} {fate:10} {pl_s:9}  {tag}")

    print(f"\n  SL Hit ที่หลีกเลี่ยงได้ (approx saved): {total_proactive_saved:+.2f} USD")

    # Summary
    print()
    print("=" * 80)
    print("  📊 SUMMARY")
    print("=" * 80)
    total_impact = total_blocked_pl + total_proactive_saved
    blocked_saved = sum(o["pl_actual"] for o in blocked_orders
                        if o["pl_actual"] is not None and o["pl_actual"] < 0)
    blocked_missed = sum(o["pl_actual"] for o in blocked_orders
                         if o["pl_actual"] is not None and o["pl_actual"] > 0)
    print(f"  Guard activations     : {len(guard.activations)}")
    print(f"  Blocked orders        : {len(blocked_orders)}")
    print(f"    P/L ถ้าไม่ block    : {blocked_saved:+.2f} USD (losses avoided)")
    print(f"    P/L ถ้าไม่ block    : {blocked_missed:+.2f} USD (gains missed)")
    print(f"    Net blocked saving  : {total_blocked_pl:+.2f} USD")
    print(f"  Proactive close saves : {total_proactive_saved:+.2f} USD (approx)")
    print(f"  ─────────────────────────────────────")
    print(f"  Total estimated saving: {(total_blocked_pl + total_proactive_saved):+.2f} USD")
    print()

if __name__ == "__main__":
    guard, blocked_orders, proactive_close = run_sim()
    report(guard, blocked_orders, proactive_close)
