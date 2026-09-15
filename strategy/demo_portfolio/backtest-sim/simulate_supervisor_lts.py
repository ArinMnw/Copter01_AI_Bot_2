"""
simulate_supervisor_lts.py — จำลองการทำงานของ supervisor_lts_avengers.py ย้อนหลัง

ไม่เข้า order จริงเลย (dry-run 100%) — ใช้ตรวจสอบก่อนปล่อย supervisor ตัวจริงรันว่า:
  1. current_start ขยับไปยังไงบ้างตลอดช่วงที่ทดสอบ
  2. สัญญาณที่ "จะเข้า order" ตรงกับที่ live จริงเข้าไปแล้ว (จาก scan เดิม) ไหม —
     เทียบ entry/sl/tp/เวลาเข้า/เวลาปิด (TP หรือ SL) กับ deal history จริงใน MT5

วิธีทำงาน: จำลองนาฬิกาเดินหน้าทีละ 15 นาที (:00/:15/:30/:45) ตั้งแต่ --start ถึง --end
(default = ตอนนี้) ในแต่ละก้าวเรียก run_lts_af_backtest(..., end_str=<เวลาจำลอง ณ ก้าวนั้น>)
— ใช้ end_str ควบคุมมุมมอง "ตอนนี้จำลอง" แทนเวลาจริงของเครื่อง ทำให้ replay อดีตได้ตรงเป๊ะ
โดยไม่ต้องรอเวลาจริงผ่านไป — logic การขยับ current_start / stale check เหมือน
supervisor_lts_avengers.py ทุกประการ ต่างแค่จุดที่ควรจะ "เข้า order จริง" เปลี่ยนเป็น
"หา deal จริงที่ตรงกันในประวัติ MT5 มาเทียบแทน"

รัน:
  python strategy/demo_portfolio/backtest-sim/simulate_supervisor_lts.py --portfolio LTS_AUS3 --start "24-08-2026 00:00"
  python strategy/demo_portfolio/backtest-sim/simulate_supervisor_lts.py --portfolio LTS_AHR3 --start "24-08-2026 00:00"
"""

import argparse
import os
import re
import sys
from datetime import datetime, timedelta

script_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, script_dir)
root_dir = os.path.dirname(os.path.dirname(os.path.dirname(script_dir)))
sys.path.insert(0, root_dir)

import MetaTrader5 as mt5  # noqa: E402
import config  # noqa: E402
import demo_portfolio as dp  # noqa: E402
import run_backtest_sim as rbs  # noqa: E402

STALE_ENTRY_SEC = 20 * 60


def _leg_key_from_comment(comment: str):
    m = re.search(r"(LTS_[A-Z0-9]+_\d+)", str(comment or ""))
    return m.group(1) if m else None


def _fetch_all_deals(date_from: datetime, date_to: datetime, magic: int):
    deals = mt5.history_deals_get(date_from, date_to) or []
    return [d for d in deals if d.magic == magic]


def _find_real_entry(leg_key: str, side: str, fill_dt: datetime, entry_deals: list, tol_min: int = 45):
    want_type = 0 if side == "BUY" else 1  # mt5 DEAL_TYPE_BUY=0 / SELL=1
    best = None
    best_diff = None
    for d in entry_deals:
        if d.type != want_type:
            continue
        if _leg_key_from_comment(d.comment) != leg_key:
            continue
        d_dt = datetime.fromtimestamp(d.time)
        diff = abs((d_dt - fill_dt).total_seconds())
        if diff <= tol_min * 60 and (best_diff is None or diff < best_diff):
            best, best_diff = d, diff
    return best


def main():
    parser = argparse.ArgumentParser(description="จำลอง supervisor_lts_avengers.py ย้อนหลัง (dry-run)")
    parser.add_argument("--portfolio", type=str, required=True, choices=["LTS_AUS3", "LTS_AHR3"])
    parser.add_argument("--start", type=str, required=True, help="dd-MM-yyyy HH:mm (BKK)")
    parser.add_argument("--end", type=str, default=None, help="dd-MM-yyyy HH:mm (BKK) — default ตอนนี้")
    parser.add_argument("--days", type=int, default=30)
    args = parser.parse_args()

    portfolio_name = args.portfolio
    config.IN_BACKTEST = True
    rbs.setup_mt5_for_portfolio(portfolio_name)
    if not config.mt5_initialize(mt5):
        print("❌ MT5 initialize failed")
        return
    config.resolve_mt5_symbol(mt5, "XAUUSD", set_runtime=True)
    magic = dp._portfolio_magic(portfolio_name)

    sim_start = datetime.strptime(args.start, "%d-%m-%Y %H:%M")
    sim_end = datetime.strptime(args.end, "%d-%m-%Y %H:%M") if args.end else datetime.now()

    print(f"🧪 จำลอง supervisor สำหรับ {portfolio_name} (magic={magic})")
    print(f"   ช่วง: {sim_start.strftime('%d-%m-%Y %H:%M')} -> {sim_end.strftime('%d-%m-%Y %H:%M')}")
    print("=" * 70)

    # ดึง deal ประวัติจริงทั้งหมดของพอร์ตนี้มาเตรียมไว้เทียบ (entry เท่านั้น, entry==0)
    all_deals = _fetch_all_deals(sim_start - timedelta(days=1), sim_end + timedelta(hours=6), magic)
    entry_deals = [d for d in all_deals if d.entry == 0]
    exit_deals = [d for d in all_deals if d.entry == 1]
    print(f"   deal จริงทั้งหมดของพอร์ตนี้ในช่วง: entry={len(entry_deals)} exit={len(exit_deals)}")

    current_start = sim_start
    processed = set()
    step = timedelta(minutes=15)
    sim_now = sim_start
    would_enter, matched_real, skipped_stale = [], [], []
    advance_log = []

    while sim_now < sim_end:
        sim_now += step
        # align ไปที่ :00/:15/:30/:45 ที่ใกล้ที่สุดถัดไป (เผื่อ --start ไม่ได้ลงตัว 15 นาที)
        minute_block = (sim_now.minute // 15) * 15
        sim_now = sim_now.replace(minute=minute_block, second=0, microsecond=0)

        start_str = current_start.strftime("%Y-%m-%d %H:%M")
        end_str = sim_now.strftime("%Y-%m-%d %H:%M")
        trades = rbs.run_lts_af_backtest(
            portfolio_name, args.days, start_str, end_str, 1.0, apply_circuit_breaker=False,
        )

        window_floor = current_start - timedelta(hours=1)
        new_keys_this_step = set()

        for t in trades:
            fill_ts = int(t.get("fill_time_ts", 0) or 0)
            if fill_ts <= 0:
                continue
            fill_dt = datetime.fromtimestamp(fill_ts)
            if fill_dt < window_floor:
                continue
            leg_key = t.get("leg", "").split(" ")[0]
            side = t.get("signal")
            key = (leg_key, fill_ts, side)
            if key in processed:
                continue

            real_deal = _find_real_entry(leg_key, side, fill_dt, entry_deals)
            if real_deal is not None:
                matched_real.append({
                    "leg": leg_key, "side": side,
                    "sim_fill": fill_dt, "sim_entry": t.get("entry"), "sim_sl": t.get("sl"), "sim_tp": t.get("tp"),
                    "real_time": datetime.fromtimestamp(real_deal.time), "real_price": real_deal.price,
                    "real_ticket": real_deal.ticket, "checked_at": sim_now,
                })
            else:
                age_sec = (sim_now - fill_dt).total_seconds()
                if age_sec > STALE_ENTRY_SEC:
                    skipped_stale.append({
                        "leg": leg_key, "side": side, "sim_fill": fill_dt, "checked_at": sim_now, "age_sec": age_sec,
                    })
                else:
                    would_enter.append({
                        "leg": leg_key, "side": side, "sim_fill": fill_dt,
                        "sim_entry": t.get("entry"), "sim_sl": t.get("sl"), "sim_tp": t.get("tp"),
                        "checked_at": sim_now, "age_sec": age_sec,
                    })
            new_keys_this_step.add(key)

        processed |= new_keys_this_step

        unresolved_ts = [
            int(t.get("fill_time_ts", 0) or 0)
            for t in trades
            if int(t.get("fill_time_ts", 0) or 0) > 0
            and datetime.fromtimestamp(int(t["fill_time_ts"])) >= window_floor
            and (t.get("leg", "").split(" ")[0], int(t.get("fill_time_ts", 0) or 0), t.get("signal")) not in processed
        ]
        next_start = datetime.fromtimestamp(min(unresolved_ts)) if unresolved_ts else sim_now
        if next_start > current_start:
            advance_log.append((sim_now, current_start, next_start))
            current_start = next_start

    mt5.shutdown()

    print(f"\n📊 สรุปหลังจำลอง {len(advance_log)} ครั้งที่ current_start ขยับ (จากทั้งหมด "
          f"{int((sim_end - sim_start) / step)} รอบ 15 นาที)")
    print(f"   ✓ matched กับ deal จริง: {len(matched_real)}")
    print(f"   🆕 would-enter (ไม่มี deal จริงตรงกัน, ยังสดพอ): {len(would_enter)}")
    print(f"   ⏭️ stale-skip (ไม่มี deal จริงตรงกัน, เก่าเกินไป): {len(skipped_stale)}")

    print("\n── current_start advance log (10 รายการแรก) ──")
    for sim_t, old_s, new_s in advance_log[:10]:
        print(f"   [{sim_t.strftime('%d/%m %H:%M')}] {old_s.strftime('%d/%m %H:%M')} -> {new_s.strftime('%d/%m %H:%M')}")

    print("\n── matched กับ deal จริง (entry/sl/tp เทียบ backtest vs จริง, 20 รายการแรก) ──")
    for m in matched_real[:20]:
        entry_diff = abs(float(m["sim_entry"]) - float(m["real_price"])) if m["sim_entry"] else 0
        print(f"   {m['leg']:20s} {m['side']:4s} sim_fill={m['sim_fill'].strftime('%d/%m %H:%M')} "
              f"real_time={m['real_time'].strftime('%d/%m %H:%M:%S')} "
              f"sim_entry={m['sim_entry']} real_price={m['real_price']} diff={entry_diff:.2f} "
              f"ticket={m['real_ticket']}")

    if would_enter:
        print(f"\n── ⚠️ would-enter ที่ไม่มี deal จริงรองรับ ({len(would_enter)} รายการ, 20 แรก) ──")
        for w in would_enter[:20]:
            print(f"   {w['leg']:20s} {w['side']:4s} fill={w['sim_fill'].strftime('%d/%m %H:%M')} "
                  f"entry={w['sim_entry']} sl={w['sim_sl']} tp={w['sim_tp']} age={w['age_sec']:.0f}s")


if __name__ == "__main__":
    main()
