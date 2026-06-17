"""
show_orders_by_time.py — ดู orders ที่ create ในช่วงเวลาที่กำหนด

Usage:
    python show_orders_by_time.py 2026-06-17 10:00
    python show_orders_by_time.py 2026-06-17 10:00 10:30
    python show_orders_by_time.py 2026-06-17 10:00 --window 15
"""
import re, sys, os
from datetime import datetime, timedelta

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.abspath(__file__))


def parse_args():
    args = sys.argv[1:]
    if len(args) < 2:
        print("Usage: python show_orders_by_time.py <date> <start_time> [end_time] [--window N]")
        print("       python show_orders_by_time.py 2026-06-17 10:00")
        print("       python show_orders_by_time.py 2026-06-17 10:00 10:30")
        print("       python show_orders_by_time.py 2026-06-17 10:00 --window 15")
        sys.exit(0)

    date_str = args[0]
    start_str = args[1]
    end_str = None
    window = 1  # default 1 minute window

    i = 2
    while i < len(args):
        if args[i] == "--window" and i + 1 < len(args):
            window = int(args[i + 1])
            i += 2
        elif not args[i].startswith("--"):
            end_str = args[i]
            i += 1
        else:
            i += 1

    start_dt = datetime.strptime(f"{date_str} {start_str}", "%Y-%m-%d %H:%M")
    if end_str:
        end_dt = datetime.strptime(f"{date_str} {end_str}", "%Y-%m-%d %H:%M")
    else:
        end_dt = start_dt + timedelta(minutes=window)

    return start_dt, end_dt


def fld(line, key):
    m = re.search(rf"{key}=([^|\s]+)", line)
    return m.group(1) if m else ""


def load_log_files():
    try:
        sys.path.insert(0, ROOT)
        from log_sources import bot_log_files
        files = bot_log_files()
        if files:
            return files
    except Exception:
        pass
    files = []
    log_dir = os.path.join(ROOT, "logs")
    if os.path.isdir(log_dir):
        import glob
        files += sorted(glob.glob(os.path.join(log_dir, "bot-2[0-9][0-9][0-9]-[0-9][0-9]*.log")))
        files += sorted(glob.glob(os.path.join(log_dir, "bot-2[0-9][0-9][0-9]-[0-9][0-9]*.log.bak-*")))
    bot_log = os.path.join(ROOT, "logs", "bot.log")
    if os.path.exists(bot_log):
        files.append(bot_log)
    return files


def main():
    start_dt, end_dt = parse_args()

    print(f"\nช่วงเวลา: {start_dt.strftime('%Y-%m-%d %H:%M')} → {end_dt.strftime('%Y-%m-%d %H:%M')}")
    print("=" * 100)

    found = []
    seen_tickets = set()

    for path in load_log_files():
        try:
            with open(path, encoding="utf-8", errors="replace") as f:
                for line in f:
                    if "ORDER_CREATED" not in line:
                        continue
                    m = re.match(r"^\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\]", line)
                    if not m:
                        continue
                    ts_str = m.group(1)
                    try:
                        ts = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
                    except ValueError:
                        continue
                    if not (start_dt <= ts < end_dt):
                        continue

                    ticket = fld(line, "ticket")
                    if ticket in seen_tickets:
                        continue
                    seen_tickets.add(ticket)

                    sid     = fld(line, "sid")
                    tf      = fld(line, "tf")
                    signal  = fld(line, "signal")
                    entry   = fld(line, "entry")
                    sl      = fld(line, "sl")
                    tp      = fld(line, "tp")
                    pattern = ""
                    pm = re.match(r"^\[.*?\]\s+ORDER_CREATED\s+\|\s+([^|]+)\|", line)
                    if pm:
                        pattern = pm.group(1).strip()

                    found.append({
                        "ts": ts_str,
                        "ticket": ticket,
                        "sid": sid,
                        "tf": tf,
                        "signal": signal,
                        "entry": entry,
                        "sl": sl,
                        "tp": tp,
                        "pattern": pattern,
                    })
        except Exception:
            pass

    found.sort(key=lambda r: (r["ts"], r["ticket"]))

    if not found:
        print("  ไม่พบ order ในช่วงเวลานี้")
    else:
        print(f"  {'time':<20} {'ticket':>11}  {'S#':>3} {'TF':>4}  {'sig':>4}  {'entry':>8}  {'sl':>8}  {'tp':>8}  pattern")
        print("  " + "-" * 98)
        for r in found:
            sig_icon = "🟢" if r["signal"] == "BUY" else "🔴"
            print(
                f"  {r['ts']:<20} {r['ticket']:>11}  S{r['sid']:>2} {r['tf']:>4}  {sig_icon}    "
                f"{r['entry']:>8}  {r['sl']:>8}  {r['tp']:>8}  {r['pattern']}"
            )
        print("  " + "-" * 98)
        print(f"  รวม {len(found)} orders")

    print()


if __name__ == "__main__":
    main()
