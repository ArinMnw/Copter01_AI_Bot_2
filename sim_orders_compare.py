#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sim_orders_compare.py
เทียบ OLD vs NEW (หลังแก้ group guard) ราย order สำหรับ XAUUSD 5/26-5/30
- OLD  = profit จริงจาก log
- NEW  = จำลอง group guard (config ปัจจุบัน: GROUP_ENABLED, count=2)
         * order ที่ถูก "สร้าง" ระหว่าง (tf,side) ถูก block  -> AVOIDED (NEW=0)
         * order ที่เปิดอยู่ตอน guard activate                -> CLOSE_EARLY (ปิดที่ราคา activate)
         * อื่น ๆ                                              -> SAME (NEW=OLD)
ออก CSV เต็ม + แสดงเฉพาะ order ที่ผลต่าง + ตาราง ORDER_FAILED
สมมติฐาน: ใช้ SL events จริงขับ guard (counterfactual flag) — ไม่ re-derive loop
"""
import os, re, io, sys, csv
from datetime import datetime, timedelta, timezone
from collections import defaultdict, Counter
import MetaTrader5 as mt5

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
ROOT = os.path.dirname(os.path.abspath(__file__))

def _log_files():
    """รวม log ที่ครอบ window: monthly archive (old_logs) + bot.log ปัจจุบัน (ถ้ามี)
    เรียงตามลำดับเวลาเพื่อ parse ต่อเนื่องได้ถูกต้อง"""
    names = ["old_logs/bot-2026-05.log", "old_logs/bot-2026-06.log", "bot.log"]
    return [os.path.join(ROOT, "logs", n) for n in names
            if os.path.exists(os.path.join(ROOT, "logs", n))]

def iter_log_lines():
    for p in _log_files():
        with open(p, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                yield line

BKK = timezone(timedelta(hours=7))
SYMBOL = "XAUUSD.iux"
WIN_START = "2026-05-26"

GROUPS = [["H4","H12","D1"],["H1","H4","H12"],["M30","H1","H4"],
          ["M15","M30","H1"],["M5","M15","M30"],["M1","M5","M15"],["M1","M5"]]
GROUP_COUNT = 2
TF_SECS = {"M1":60,"M5":300,"M15":900,"M30":1800,"H1":3600,"H4":14400,"H12":43200,"D1":86400}
TF_MT5 = {"M1":mt5.TIMEFRAME_M1,"M5":mt5.TIMEFRAME_M5,"M15":mt5.TIMEFRAME_M15,
          "M30":mt5.TIMEFRAME_M30,"H1":mt5.TIMEFRAME_H1,"H4":mt5.TIMEFRAME_H4}

_TS = re.compile(r"^\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\]\s+(\S+)")
def fld(line, key):
    m = re.search(rf"{key}=([^|]+?)(?:\s*\||$)", line); return m.group(1).strip() if m else None
def to_dt(s): return datetime.strptime(s, "%Y-%m-%d %H:%M:%S").replace(tzinfo=BKK)

def parse_log():
    created, filled, closed = {}, {}, []
    order_failed = Counter(); of_day = Counter(); of_first=[None]; of_last=[None]
    if True:
        for line in iter_log_lines():
            m = _TS.match(line)
            if not m: continue
            ts, kind = m.group(1), m.group(2)
            if ts[:10] < WIN_START: continue
            if kind == "ORDER_CREATED":
                tk = fld(line,"ticket")
                if tk: created[tk] = {"ts":ts,"tf":fld(line,"tf"),"side":fld(line,"signal") or fld(line,"side"),
                                      "sid":fld(line,"sid"),"entry":float(fld(line,"entry") or 0),
                                      "sl":float(fld(line,"sl") or 0),"tp":float(fld(line,"tp") or 0)}
            elif kind == "ENTRY_FILL":
                tk = fld(line,"ticket")
                if tk: filled[tk] = ts
            elif kind == "POSITION_CLOSED" and "symbol=XAUUSD" in line:
                closed.append({"ts":ts,"ticket":fld(line,"ticket"),"side":fld(line,"side"),
                    "tf":fld(line,"tf"),"sid":fld(line,"sid"),"entry":float(fld(line,"open_price") or 0),
                    "close":float(fld(line,"close_price") or 0),"sl":float(fld(line,"sl") or 0),
                    "profit":float(fld(line,"profit") or 0),"is_sl":"SL Hit" in line,
                    "tfilt":(fld(line,"trend_filter") or "").lower()})
            elif kind == "ORDER_FAILED":
                mm = re.search(r"ORDER_FAILED \| (.+?)(?:\s*\| tf=|\s*\| sid=|$)", line)
                rk = (mm.group(1).strip() if mm else "?")[:50]
                order_failed[rk]+=1; of_day[ts[:10]]+=1
                if of_first[0] is None: of_first[0]=ts
                of_last[0]=ts
    return created, filled, closed, order_failed, of_day, of_first[0], of_last[0]

def fetch_candles():
    cd = {}
    s = datetime(2026,5,25,tzinfo=BKK); e = datetime(2026,6,2,12,tzinfo=BKK)
    for tf,v in TF_MT5.items():
        r = mt5.copy_rates_range(SYMBOL, v, s, e)
        cd[tf] = [(int(x["time"]), float(x["high"]), float(x["low"])) for x in r] if r is not None else []
    return cd

def ref_level(cand, side, T_unix, lookback_bars=20):
    """swing_ref ตอน activate = max high(SELL)/min low(BUY) ของ ~20 แท่งก่อน T
    (swing-scale: ปลดล็อกเมื่อราคาทำ local extreme ใหม่ ตามความถี่ swing จริง)"""
    sub = [c for c in cand if c[0] <= T_unix][-lookback_bars:]
    if not sub: return None
    return max(c[1] for c in sub) if side=="SELL" else min(c[2] for c in sub)

def unblock_time(cand, side, since_unix, ref, max_bars=30, tf_secs=60):
    """แท่งแรกหลัง since ที่ high>ref(SELL)/low<ref(BUY); ถ้าไม่เจอใน max_bars -> ปลดล็อก"""
    if ref is None: return since_unix + max_bars*tf_secs
    n = 0
    for t,h,l in cand:
        if t <= since_unix: continue
        n += 1
        if (side=="SELL" and h > ref) or (side=="BUY" and l < ref):
            return t
        if n >= max_bars:
            return t   # cap: ไม่เจอ swing ใน 30 แท่ง -> ถือว่าปลดล็อก (กันบล็อกยาวเกินจริง)
    return since_unix + max_bars*tf_secs

def build_blocked_intervals(closed, candles):
    """คืน dict[(tf,side)] = list of (start_unix, end_unix) ช่วงที่ถูก block
       + list ของ activation events (ts_unix, side, group) สำหรับ close-early"""
    sl_ev = sorted([c for c in closed if c["is_sl"] and c["tf"] in TF_SECS],
                   key=lambda c: c["ts"])
    intervals = defaultdict(list)
    activations = []  # (unix, side, set(tfs_in_group))
    for side in ("BUY","SELL"):
        for g in GROUPS:
            gset = set(g)
            count = 0; active_until = 0
            for c in sl_ev:
                if c["side"] != side or c["tf"] not in gset: continue
                T = int(to_dt(c["ts"]).timestamp())
                if T < active_until:    # ยัง active อยู่ -> ข้าม (order หลุดมาก่อน block)
                    continue
                count += 1
                if count >= GROUP_COUNT:
                    # ACTIVATE
                    maxu = T
                    for tf in g:
                        if tf not in candles: continue
                        ref = ref_level(candles[tf], side, T)
                        ut = unblock_time(candles[tf], side, T, ref, max_bars=30, tf_secs=TF_SECS[tf])
                        intervals[(tf,side)].append((T, ut))
                        maxu = max(maxu, ut)
                    activations.append((T, side, gset))
                    active_until = maxu
                    count = 0
    return intervals, activations

def is_blocked(intervals, tf, side, t_unix):
    for (s,e) in intervals.get((tf,side), []):
        if s <= t_unix < e: return True
    return False

def price_at(candles, tf, t_unix):
    """ราคา ~close ณ เวลา t (ใช้ high/low เฉลี่ยของแท่งที่ครอบ)"""
    cand = candles.get(tf, [])
    best = None
    for c in cand:
        if c[0] <= t_unix: best = c
        else: break
    return (best[1]+best[2])/2 if best else None

def main():
    if not mt5.initialize(): print("MT5 init failed", mt5.last_error()); return
    created, filled, closed, ofail, ofday, of_first, of_last = parse_log()
    candles = fetch_candles()
    intervals, activations = build_blocked_intervals(closed, candles)

    rows = []
    for c in closed:
        if not c["is_sl"]: continue
        tk = c["ticket"]
        cr = created.get(tk)
        create_ts = cr["ts"] if cr else (filled.get(tk) or c["ts"])
        t_create = int(to_dt(create_ts).timestamp())
        t_fill = int(to_dt(filled.get(tk, create_ts)).timestamp())
        old = c["profit"]; new = old; status = "SAME"

        # 1) AVOIDED: สร้างตอน (tf,side) ถูก block
        if c["tf"] in TF_SECS and is_blocked(intervals, c["tf"], c["side"], t_create):
            new = 0.0; status = "AVOIDED"
        else:
            # 2) CLOSE_EARLY: เปิดอยู่ตอน guard activate (ฝั่งเดียวกัน, fill ก่อน activate, close หลัง)
            t_close = int(to_dt(c["ts"]).timestamp())
            for (ta, side_a, gset) in activations:
                if side_a == c["side"] and t_fill <= ta < t_close:
                    pa = price_at(candles, c["tf"], ta)
                    if pa and c["entry"] and c["sl"] != c["entry"]:
                        dirn = 1 if c["side"]=="BUY" else -1
                        # scale loss ตามระยะที่ราคาไปถึงตอน activate เทียบ SL
                        denom = (c["sl"]-c["entry"])*dirn
                        if denom != 0:
                            frac = ((pa-c["entry"])*dirn)/denom
                            frac = max(min(frac,1.0),-0.2)
                            new = old*frac
                            status = "CLOSE_EARLY"
                    break
        rows.append({**c, "old":old, "new":new, "diff":new-old, "status":status, "create_ts":create_ts})

    # ── CSV เต็ม ──
    out = os.path.join(ROOT, "orders_old_vs_new.csv")
    with open(out, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["ticket","create_ts","close_ts","side","tf","sid","entry","sl","close",
                    "OLD_profit","NEW_profit","diff","status","trend_filter"])
        for r in rows:
            w.writerow([r["ticket"],r["create_ts"],r["ts"],r["side"],r["tf"],r["sid"],
                        r["entry"],r["sl"],r["close"],f"{r['old']:.2f}",f"{r['new']:.2f}",
                        f"{r['diff']:.2f}",r["status"],r["tfilt"]])

    old_tot = sum(r["old"] for r in rows)
    new_tot = sum(r["new"] for r in rows)
    n_av = sum(1 for r in rows if r["status"]=="AVOIDED")
    n_ce = sum(1 for r in rows if r["status"]=="CLOSE_EARLY")
    print("="*100)
    print(f"  เทียบ OLD vs NEW (group guard fix) — SL orders XAUUSD {WIN_START}+  [{len(rows)} orders]")
    print("="*100)
    print(f"  OLD รวม SL P/L : {old_tot:>10.2f}")
    print(f"  NEW รวม SL P/L : {new_tot:>10.2f}")
    print(f"  ต่าง (ดีขึ้น)   : {new_tot-old_tot:>10.2f}")
    print(f"  AVOIDED={n_av}  CLOSE_EARLY={n_ce}  SAME={len(rows)-n_av-n_ce}")
    print(f"  CSV เต็ม -> {os.path.basename(out)}")
    print()

    aff = [r for r in rows if r["status"]!="SAME"]
    # เรียงตาม loss มากสุดก่อน (order ผิดปกติสุด = ขาดทุนเยอะที่ถูกกัน)
    aff.sort(key=lambda r: r["old"])
    print(f"  ── TOP 40 order ผิดปกติ (loss มากสุดที่ guard ใหม่จะกัน) จาก {len(aff)} ตัว ──")
    print(f"  {'create':<17}{'ticket':>11} {'sd':>4} {'tf':>4} {'sid':>4} {'OLD':>8} {'NEW':>8} {'diff':>8}  status  trend")
    for r in aff[:40]:
        print(f"  {r['create_ts']:<17}{str(r['ticket']):>11} {r['side']:>4} {str(r['tf']):>4} "
              f"{str(r['sid']):>4} {r['old']:>8.2f} {r['new']:>8.2f} {r['diff']:>8.2f}  {r['status']:<11} {r['tfilt']}")
    if len(aff) > 40: print(f"  ... อีก {len(aff)-40} ตัว (ดูใน orders_old_vs_new.csv)")
    # สรุปตาม sid: order ที่ถูกกัน
    print()
    print("  ── สรุป order ที่ผลต่าง แยกตาม sid ──")
    by_sid = defaultdict(lambda:[0,0.0])
    for r in aff:
        by_sid[r["sid"]][0]+=1; by_sid[r["sid"]][1]+=r["diff"]
    for sid in sorted(by_sid, key=lambda s:-by_sid[s][1]):
        print(f"    S{str(sid):<3}: {by_sid[sid][0]:>3d} orders | รวม diff (ดีขึ้น) {by_sid[sid][1]:>9.2f}")

    # ── ORDER_FAILED ──
    print()
    print("="*100)
    print(f"  ORDER_FAILED — รวม {sum(ofail.values())} ครั้ง ({of_first} -> {of_last})  [order พวกนี้ไม่เปิด = P/L 0]")
    print("="*100)
    print(f"  {'count':>8}  reason")
    for r,n in ofail.most_common(12):
        print(f"  {n:>8}  {r}")
    print("  ── by day ──  " + "  ".join(f"{d[5:]}:{n}" for d,n in sorted(ofday.items())))
    mt5.shutdown()

if __name__ == "__main__":
    main()
