"""
sim_sweep_fix.py — จำลอง sweep_filter M1 SWEEP_HIGH
เปรียบเทียบ OLD (มี re-activation bug) vs NEW (มี _reset_blocked_ts fix)

ใช้ข้อมูลจาก bot.log วันที่ 2026-06-18
ไม่แตะไฟล์เดิม — standalone script
"""

import re
from datetime import datetime, timezone

LOG_FILE = "D:/Project/Copter01_AI_Bot_2/logs/bot.log"
TARGET_DATE = "2026-06-18"
TF = "M1"
SWEEP_TYPE = "SWEEP_HIGH"
EXPIRY_MIN = 60  # M1 = 60 นาที

# ─── parse log ───────────────────────────────────────────────────────────────

LINE_RE = re.compile(
    r"\[(?P<ts>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\] "
    r"(?P<event>\w+) \| (?P<rest>.*)"
)
SWEEP_BAR_RE = re.compile(r"sweep_bar=(?P<t>\d{2}:\d{2}) (?P<d>\d{2}-\w{3}-\d{4})")
REF_RE = re.compile(r"ref_price=(?P<p>[\d.]+)")
REASON_RE = re.compile(r"reason=(?P<r>\S+)")

MONTH_MAP = {
    "Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "Jun": 6,
    "Jul": 7, "Aug": 8, "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12,
}


def parse_sweep_bar_ts(t_str: str, d_str: str) -> datetime:
    hh, mm = map(int, t_str.split(":"))
    day, mon_s, yr = d_str.split("-")
    return datetime(int(yr), MONTH_MAP[mon_s], int(day), hh, mm)


def parse_log_ts(s: str) -> datetime:
    return datetime.strptime(s, "%Y-%m-%d %H:%M:%S")


def load_events():
    events = []
    with open(LOG_FILE, encoding="utf-8", errors="replace") as f:
        for line in f:
            if TARGET_DATE not in line:
                continue
            m = LINE_RE.match(line.strip())
            if not m:
                continue
            ts = parse_log_ts(m["ts"])
            ev = m["event"]
            rest = m["rest"]

            if ev == "SWEEP_ACTIVATE" and SWEEP_TYPE in rest and f"tf={TF}" in rest:
                sb = SWEEP_BAR_RE.search(rest)
                rf = REF_RE.search(rest)
                if sb:
                    events.append({
                        "ts": ts, "type": "ACTIVATE",
                        "bar_ts": parse_sweep_bar_ts(sb["t"], sb["d"]),
                        "ref_price": float(rf["p"]) if rf else 0,
                    })

            elif ev == "SWEEP_RESET" and SWEEP_TYPE in rest and f"tf={TF}" in rest:
                rs = REASON_RE.search(rest)
                events.append({
                    "ts": ts, "type": "RESET",
                    "reason": rs["r"] if rs else "?",
                })

            elif ev == "TREND_FILTER_BLOCK" and "sweep_high_block_buy" in rest and f"tf={TF}" in rest:
                sid_m = re.search(r"sid=(\d+)", rest)
                events.append({
                    "ts": ts, "type": "BLOCK",
                    "sid": int(sid_m[1]) if sid_m else 0,
                })

    return events


# ─── simulate ────────────────────────────────────────────────────────────────

def simulate(events: list, use_fix: bool) -> list:
    """คืน list ของ (ts, action, detail) ที่เกิดขึ้น"""
    result = []
    active_bar_ts = None        # bar_ts ที่ active อยู่
    activated_at = None         # เวลาที่ activate (เพื่อเช็ค expiry)
    reset_blocked_ts = None     # NEW: block re-activation

    for ev in events:
        ts = ev["ts"]

        if ev["type"] == "RESET":
            if active_bar_ts is not None:
                if use_fix:
                    reset_blocked_ts = active_bar_ts  # จำ bar_ts เดิมไว้ block
                result.append((ts, "RESET", f"reason={ev['reason']} | was={active_bar_ts.strftime('%H:%M')}"))
                active_bar_ts = None
                activated_at = None

        elif ev["type"] == "ACTIVATE":
            bar_ts = ev["bar_ts"]

            if use_fix and reset_blocked_ts == bar_ts:
                result.append((ts, "ACTIVATE_BLOCKED", f"bar_ts={bar_ts.strftime('%H:%M')} (same as reset → skip)"))
                continue

            # clear block เมื่อ bar_ts ใหม่มา
            if use_fix:
                reset_blocked_ts = None

            # เช็ค expiry ก่อน activate (ถ้ามี active อยู่แล้ว)
            if activated_at and (ts - activated_at).total_seconds() > EXPIRY_MIN * 60:
                result.append((ts, "EXPIRED_BEFORE_ACTIVATE", f"age={(ts-activated_at).seconds//60}min"))
                active_bar_ts = None

            active_bar_ts = bar_ts
            activated_at = ts
            result.append((ts, "ACTIVATE", f"bar_ts={bar_ts.strftime('%H:%M')} ref={ev['ref_price']}"))

        elif ev["type"] == "BLOCK":
            if active_bar_ts:
                # เช็ค expiry ณ ตอน block
                age_min = (ts - activated_at).total_seconds() / 60 if activated_at else 0
                if age_min > EXPIRY_MIN:
                    result.append((ts, "WOULD_EXPIRE", f"age={age_min:.0f}min → sweep already expired"))
                else:
                    result.append((ts, "BLOCK", f"sid={ev['sid']} bar_ts={active_bar_ts.strftime('%H:%M')} age={age_min:.0f}min"))
            else:
                result.append((ts, "BLOCK_NO_SWEEP", f"sid={ev['sid']} (sweep not active → should NOT block)"))

    return result


# ─── main ─────────────────────────────────────────────────────────────────────

def main():
    events = load_events()
    print(f"Loaded {len(events)} events (ACTIVATE/RESET/BLOCK) for {SWEEP_TYPE} {TF}\n")

    old = simulate(events, use_fix=False)
    new = simulate(events, use_fix=True)

    # สรุปเฉพาะ BLOCK ที่ต่างกัน
    old_blocks = {(r[0], r[2]) for r in old if r[1] == "BLOCK"}
    new_blocks = {(r[0], r[2]) for r in new if r[1] == "BLOCK"}
    prevented = [(r[0], r[2]) for r in old if r[1] == "BLOCK" and (r[0], r[2]) not in new_blocks]
    wrong_blocks = [(r[0], r[2]) for r in new if r[1] == "BLOCK_NO_SWEEP"]

    # ─── print OLD timeline (compact: แสดง ACTIVATE/RESET/BLOCK แรกในแต่ละช่วง) ───
    print("=" * 70)
    print("OLD (bug present) — ACTIVATE/RESET timeline:")
    print("=" * 70)
    last_action = None
    last_bar = None
    for ts, action, detail in old:
        if action in ("ACTIVATE", "RESET", "ACTIVATE_BLOCKED", "EXPIRED_BEFORE_ACTIVATE"):
            print(f"  {ts.strftime('%H:%M:%S')}  {action:28s}  {detail}")
            last_action = action
            last_bar = detail
        elif action == "BLOCK" and last_action != "BLOCK":
            print(f"  {ts.strftime('%H:%M:%S')}  {'BLOCK (BUY suppressed)':28s}  {detail}")
            last_action = "BLOCK"

    print()
    print("=" * 70)
    print("NEW (fix applied) — ACTIVATE/RESET timeline:")
    print("=" * 70)
    last_action = None
    for ts, action, detail in new:
        if action in ("ACTIVATE", "RESET", "ACTIVATE_BLOCKED", "EXPIRED_BEFORE_ACTIVATE"):
            print(f"  {ts.strftime('%H:%M:%S')}  {action:28s}  {detail}")
            last_action = action
        elif action == "BLOCK" and last_action != "BLOCK":
            print(f"  {ts.strftime('%H:%M:%S')}  {'BLOCK (BUY suppressed)':28s}  {detail}")
            last_action = "BLOCK"
        elif action == "BLOCK_NO_SWEEP":
            print(f"  {ts.strftime('%H:%M:%S')}  {'BLOCK_NO_SWEEP (bug!)':28s}  {detail}")
            last_action = action

    print()
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    old_block_count = sum(1 for r in old if r[1] == "BLOCK")
    new_block_count = sum(1 for r in new if r[1] == "BLOCK")
    prevented_count = sum(1 for r in old if r[1] == "ACTIVATE" and
                          any(r2[1] == "ACTIVATE_BLOCKED" and r2[2] == r[2].replace("ref=","").split()[0]
                              for r2 in new))

    reactivations_old = sum(1 for r in old if r[1] == "ACTIVATE")
    reactivations_new = sum(1 for r in new if r[1] == "ACTIVATE")
    blocked_activations = sum(1 for r in new if r[1] == "ACTIVATE_BLOCKED")

    print(f"  Activations OLD : {reactivations_old}")
    print(f"  Activations NEW : {reactivations_new}  (+{blocked_activations} blocked re-activations)")
    print(f"  BUY blocks OLD  : {old_block_count}")
    print(f"  BUY blocks NEW  : {new_block_count}")
    print(f"  BUY blocks prevented by fix: {old_block_count - new_block_count}")

    if prevented:
        print(f"\n  ตัวอย่าง BUY blocks ที่ป้องกันได้ด้วย fix (แสดง 10 รายการแรก):")
        for ts, detail in prevented[:10]:
            print(f"    {ts.strftime('%H:%M:%S')}  {detail}")


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    main()
