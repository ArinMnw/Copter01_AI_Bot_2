"""
sim_sg_loss.py — Compare SL Guard: Loss mode OFF vs ON
────────────────────────────────────────────────────────
Mode A (current):  นับเฉพาะ SL hit จริง
Mode B (new):      นับ SL hit + non-SL close ที่ขาดทุน > LOSS_THRESHOLD

สำหรับ orders ที่ถูก block เพิ่มเติมใน Mode B → คำนวณ P&L diff

Usage: python sim_sg_loss.py [--from 26-05-2026] [--threshold 5]
"""
import re, sys, io, os, glob
from collections import defaultdict
from datetime import datetime, timezone, timedelta

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT      = os.path.dirname(os.path.abspath(__file__))
BKK       = timezone(timedelta(hours=7))
SIM_START = "2026-05-26"
LOSS_THR  = 5.0    # default threshold

for i, a in enumerate(sys.argv[1:]):
    if a == "--from" and i + 1 < len(sys.argv) - 1:
        SIM_START = sys.argv[i + 2].replace("-", "-")
    if a == "--threshold" and i + 1 < len(sys.argv) - 1:
        LOSS_THR = float(sys.argv[i + 2])

THRESHOLD = 2
GROUPS = [
    ["H4","H12","D1"],
    ["H1","H4","H12"],
    ["M30","H1","H4"],
    ["M15","M30","H1"],
    ["M5","M15","M30"],
    ["M1","M5","M15"],
    ["M1","M5"],
]
BYPASS_SIDS       = {9, 10, 14}
BYPASS_BLOCK_SIDS = {9, 10, 14}
TIMEOUT_MIN       = 45

# ── Log files ─────────────────────────────────────────────────────────
def _log_files():
    log_dir = os.path.join(ROOT, "logs")
    result = []
    for name in ["old_logs/bot-2026-05.log", "old_logs/bot-2026-06.log", "bot.log"]:
        p = os.path.join(log_dir, name)
        if os.path.exists(p):
            result.append(p)
    return result

_TS = re.compile(r"^\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\]")

def fld(line, key):
    m = re.search(rf"\b{key}=([^|\s]+)", line)
    return m.group(1).strip() if m else None

# ── Parse events ──────────────────────────────────────────────────────
def parse_events():
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
                    if ts_str[:10] < SIM_START[:10]:
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
                        sym = fld(line, "symbol") or ""
                        if "XAU" not in sym.upper():
                            continue   # XAUUSD only
                        sid_s  = fld(line, "sid")
                        profit_s = fld(line, "profit")
                        close_type = ("SL" if "SL Hit" in line
                                      else "TP" if "TP Hit" in line else "BOT")
                        events.append({
                            "ts": ts_str, "type": "CLOSE",
                            "ticket": ticket,
                            "side":   fld(line, "side") or "",
                            "tf":     fld(line, "tf")   or "",
                            "sid":    int(sid_s) if sid_s and sid_s.isdigit() else 0,
                            "profit": float(profit_s) if profit_s else 0.0,
                            "close_type": close_type,
                        })

                    elif ev_type == "ORDER_CREATED":
                        ticket = fld(line, "ticket")
                        if not ticket:
                            continue
                        sid_s  = fld(line, "sid")
                        order_type = fld(line, "order_type") or ""
                        if "MARKET" in order_type.upper():
                            continue
                        sym = fld(line, "symbol") or ""
                        # ถ้าไม่มี symbol field ใน ORDER_CREATED ให้ผ่าน
                        if sym and "XAU" not in sym.upper():
                            continue
                        events.append({
                            "ts": ts_str, "type": "ORDER_CREATED",
                            "ticket": ticket,
                            "side":   (fld(line, "signal") or fld(line, "side") or "").upper(),
                            "tf":     fld(line, "tf")   or "",
                            "sid":    int(sid_s) if sid_s and sid_s.isdigit() else 0,
                        })

                    elif ev_type == "ENTRY_FILL":
                        ticket = fld(line, "ticket")
                        if not ticket:
                            continue
                        sid_s = fld(line, "sid")
                        events.append({
                            "ts": ts_str, "type": "ENTRY_FILL",
                            "ticket": ticket,
                            "side":   fld(line, "side") or "",
                            "tf":     fld(line, "tf")   or "",
                            "sid":    int(sid_s) if sid_s and sid_s.isdigit() else 0,
                        })
        except Exception:
            pass

    events.sort(key=lambda x: x["ts"])
    return events

# ── Guard simulator ───────────────────────────────────────────────────
class GuardSim:
    def __init__(self, loss_mode: bool, loss_thr: float):
        self.loss_mode = loss_mode
        self.loss_thr  = loss_thr
        self.state: dict = {}
        self._pending_unblock: dict = {}
        self.activations: list = []

    def _should_count(self, close_type: str, profit: float, sid: int) -> bool:
        if sid in BYPASS_SIDS:
            return False
        if close_type == "SL" and profit < 0:
            return True
        if self.loss_mode and close_type == "BOT" and profit < -self.loss_thr:
            return True
        return False

    def record_close(self, ts, tf, side, profit, sid, close_type):
        if not self._should_count(close_type, profit, sid):
            return []
        side = side.upper()
        activated = []
        for group in GROUPS:
            if tf not in group:
                continue
            gkey = "+".join(group)
            sg_side = self.state.setdefault(side, {})
            sg = sg_side.setdefault(gkey, {
                "count": 0, "active": False, "tf_blocked": {}, "tf_since": {},
            })
            sg["count"] += 1
            if sg["count"] >= THRESHOLD and not sg["active"]:
                sg["active"] = True
                for t in group:
                    sg["tf_blocked"][t] = True
                    sg["tf_since"][t]   = ts
                activated.append((gkey, group, sg["count"]))
                self.activations.append((ts, side, gkey, sg["count"],
                                         "loss" if close_type == "BOT" else "sl"))
                self._pending_unblock[(side, gkey)] = ts
        return activated

    def is_blocked(self, tf, side):
        side = side.upper()
        for sg in self.state.get(side, {}).values():
            if sg.get("active") and sg.get("tf_blocked", {}).get(tf):
                return True
        return False

    def check_unblock_by_tp(self, ts, tf, side, close_type):
        if close_type != "TP":
            return
        side = side.upper()
        for gkey, sg in self.state.get(side, {}).items():
            if sg.get("active") and sg.get("tf_blocked", {}).get(tf):
                sg["tf_blocked"][tf] = False
                if all(not sg["tf_blocked"].get(t) for t in gkey.split("+")):
                    sg["active"] = False
                    sg["count"]  = 0
                    self._pending_unblock.pop((side, gkey), None)

    def check_unblock_timeout(self, ts):
        now = datetime.strptime(ts, "%Y-%m-%d %H:%M:%S")
        for (side, gkey), act_ts in list(self._pending_unblock.items()):
            delta = (now - datetime.strptime(act_ts, "%Y-%m-%d %H:%M:%S")).total_seconds()
            if delta >= TIMEOUT_MIN * 60:
                sg = self.state.get(side, {}).get(gkey)
                if sg and sg.get("active"):
                    sg["active"] = False
                    sg["count"]  = 0
                    for t in sg["tf_blocked"]:
                        sg["tf_blocked"][t] = False
                del self._pending_unblock[(side, gkey)]

# ── Run simulation ────────────────────────────────────────────────────
def run_sim(events, close_map, loss_mode):
    guard = GuardSim(loss_mode=loss_mode, loss_thr=LOSS_THR)
    open_fills    = {}   # ticket → {ts, side, tf, sid}
    blocked_orders= []   # orders blocked by guard
    proactive_cls = []   # open positions closed when guard activates

    for ev in events:
        ts    = ev["ts"]
        etype = ev["type"]
        guard.check_unblock_timeout(ts)

        if etype == "ENTRY_FILL":
            open_fills[ev["ticket"]] = {
                "ts": ts, "side": ev["side"], "tf": ev["tf"], "sid": ev["sid"]
            }

        elif etype == "CLOSE":
            tk = ev["ticket"]
            guard.check_unblock_by_tp(ts, ev["tf"], ev["side"], ev["close_type"])
            open_fills.pop(tk, None)

            activated = guard.record_close(
                ts, ev["tf"], ev["side"], ev["profit"], ev["sid"], ev["close_type"]
            )
            for gkey, group, count in activated:
                side = ev["side"].upper()
                for open_tk, finfo in list(open_fills.items()):
                    if (finfo["side"] or "").upper() == side:
                        ftf_parts = re.split(r"[+_\[\]]", finfo["tf"] or "")
                        if any(p in group for p in ftf_parts):
                            cl = close_map.get(open_tk)
                            proactive_cls.append({
                                "ticket": open_tk, "ts_activate": ts,
                                "side": side, "tf": finfo["tf"], "sid": finfo["sid"],
                                "pl_actual": cl["profit"] if cl else None,
                                "fate": cl["close_type"] if cl else "OPEN",
                            })

        elif etype == "ORDER_CREATED":
            tk  = ev["ticket"]
            tf  = ev["tf"]
            sd  = ev["side"].upper()
            sid = ev["sid"]
            if not tf or not sd or sid in BYPASS_BLOCK_SIDS:
                continue
            tf_parts = [p for p in re.split(r"[+_\[\]]", tf) if p]
            blocked_tf = next((p for p in tf_parts if guard.is_blocked(p, sd)), None)
            if blocked_tf:
                cl = close_map.get(tk)
                blocked_orders.append({
                    "ticket": tk, "ts": ts, "side": sd, "tf": tf,
                    "blocked_tf": blocked_tf, "sid": sid,
                    "pl_actual": cl["profit"] if cl else None,
                    "fate": cl["close_type"] if cl else "OPEN",
                })

    return guard, blocked_orders, proactive_cls

# ── Main ──────────────────────────────────────────────────────────────
print(f"Loading events from {SIM_START}...")
events    = parse_events()
close_map = {e["ticket"]: e for e in events if e["type"] == "CLOSE"}
print(f"Events: {len(events)}  Closes: {len(close_map)}")
print(f"Loss threshold: ${LOSS_THR:.0f}")
print()

print("Running Mode A (SL only)...")
gA, blkA, proA = run_sim(events, close_map, loss_mode=False)

print("Running Mode B (SL + Loss)...")
gB, blkB, proB = run_sim(events, close_map, loss_mode=True)

# ── Compare ────────────────────────────────────────────────────────────
tkA = {b["ticket"] for b in blkA}
tkB = {b["ticket"] for b in blkB}

# orders ที่ถูก block เพิ่มใน Mode B (ไม่เคย block ใน A)
extra_blocked = [b for b in blkB if b["ticket"] not in tkA]

print()
print("=" * 70)
print(f"📊 SL Guard: Loss Mode OFF vs ON (threshold=${LOSS_THR:.0f}) — {SIM_START}")
print("=" * 70)

print(f"\n🛡️  Guard Activations:")
print(f"   Mode A (SL only)    : {len(gA.activations)}")
print(f"   Mode B (SL + Loss)  : {len(gB.activations)}")

print(f"\n🚫 Orders Blocked:")
print(f"   Mode A : {len(blkA)}")
print(f"   Mode B : {len(blkB)}")
print(f"   Extra blocked by Mode B : {len(extra_blocked)}")

if gB.activations:
    print(f"\n   Mode B extra activations (loss-triggered):")
    extra_acts = [a for a in gB.activations if a[4] == "loss"]
    for ts, side, gkey, cnt, src in extra_acts:
        print(f"   ⚡ {ts}  {side} [{gkey}] count={cnt} ← loss trigger")

# P&L impact ของ extra_blocked
extra_with_outcome = [b for b in extra_blocked if b["pl_actual"] is not None]
saves  = [b for b in extra_with_outcome if b["pl_actual"] < 0]
misses = [b for b in extra_with_outcome if b["pl_actual"] > 0]

loss_avoided  = sum(abs(b["pl_actual"]) for b in saves)
profit_missed = sum(b["pl_actual"] for b in misses)
net_diff      = loss_avoided - profit_missed

print(f"\n   Extra blocked orders (Mode B only) — {len(extra_with_outcome)} known outcome:")
for b in extra_blocked:
    tag = "SAVE" if (b["pl_actual"] or 0) < 0 else "MISS" if (b["pl_actual"] or 0) > 0 else "?"
    icon = "🚫" if tag == "SAVE" else ("⚠️" if tag == "MISS" else "❓")
    pl_s = f"${b['pl_actual']:+.2f}" if b["pl_actual"] is not None else "OPEN"
    print(f"   {icon} [{b['ts'][:16]}] #{b['ticket']} {b['tf']} {b['side']} sid={b['sid']} | {pl_s} | {tag}")

print(f"\n   ── P&L Impact (extra blocked by Mode B) ──")
print(f"   🚫 Loss avoided  : ${loss_avoided:>8.2f}  ({len(saves)} orders)")
print(f"   ⚠️  Profit missed : ${profit_missed:>8.2f}  ({len(misses)} orders)")
print(f"   Net improvement  : ${net_diff:>+8.2f}  {'↑ Mode B ดีกว่า' if net_diff > 0 else '↓ Mode A ดีกว่า'}")

print(f"\n   ── Summary (XAUUSD only) ──")
pnl_A_blocked = sum((b["pl_actual"] or 0) for b in blkA if b["pl_actual"] is not None)
pnl_B_blocked = sum((b["pl_actual"] or 0) for b in blkB if b["pl_actual"] is not None)
print(f"   Actual P&L of Mode A blocked orders : ${pnl_A_blocked:>+.2f}")
print(f"   Actual P&L of Mode B blocked orders : ${pnl_B_blocked:>+.2f}")
print(f"   Improvement if enabling Loss Mode   : ${net_diff:>+.2f}")

print("\nDone.")
