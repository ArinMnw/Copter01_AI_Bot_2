#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
orders_health.py — ตรวจสุขภาพราย order (XAUUSD 5/26-ปัจจุบัน)
เช็คต่อ ticket: lot ปกติ? / trend (สวน+recheck blind?) / PD zone / scale-out (TSO) / SL guard
ออก CSV เต็ม + สรุป anomaly ต่อ subsystem + ตัวอย่าง order ที่ผิดปกติหลายจุด
"""
import os, re, io, sys, csv
from collections import defaultdict, Counter
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
ROOT = os.path.dirname(os.path.abspath(__file__))
CSV_CMP = os.path.join(ROOT, "orders_old_vs_new.csv")
WIN_START = "2026-05-26"
EXPECT_LOT = 0.04   # XAU base 0.01 × TSO4

def _log_files():
    """รวม log ที่ครอบ window: monthly archive (old_logs) + bak files + bot.log ปัจจุบัน (ถ้ามี)"""
    import glob as _glob
    result = []
    log_dir = os.path.join(ROOT, "logs")
    # ไฟล์ fixed (May archive + June current)
    for name in ["old_logs/bot-2026-05.log", "old_logs/bot-2026-06.log", "bot.log"]:
        p = os.path.join(log_dir, name)
        if os.path.exists(p):
            result.append(p)
    # bak files สำหรับ June (เกิดจาก restart หลายครั้ง) — sort by name = chronological
    bak_pattern = os.path.join(log_dir, "old_logs", "bot-2026-06.log.bak-*")
    for p in sorted(_glob.glob(bak_pattern)):
        if p not in result:
            result.append(p)
    return result

def iter_log_lines():
    for p in _log_files():
        with open(p, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                yield line

_TS = re.compile(r"^\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\]\s+(\S+)")
def fld(line, key):
    m = re.search(rf"{key}=([^|]+?)(?:\s*\||$)", line); return m.group(1).strip() if m else None
def ffloat(line, key):
    v = fld(line, key)
    try: return float(v) if v is not None else None
    except: return None

# per-ticket aggregate
T = defaultdict(lambda: {
    "create_ts":None,"tf":None,"side":None,"sid":None,"trend_filter":None,
    "lot":None,"base":None,"tso_reg":False,"tso_partials":0,
    "fill_ts":None,"trend_at_fill":None,
    "pd_fill":None,"pd_round1":None,
    "tr_blind":0,"tr_ran":False,"tr_closed":False,
    "closed":False,"profit":None,"reason":None,"is_sl":False,"is_tp":False,"close_ts":None,
})

for line in iter_log_lines():
        m = _TS.match(line)
        if not m: continue
        ts, kind = m.group(1), m.group(2)
        if ts[:10] < WIN_START: continue
        tk = fld(line, "ticket")
        if kind == "ORDER_CREATED" and tk:
            r = T[tk]
            r["create_ts"]=ts; r["tf"]=fld(line,"tf"); r["side"]=fld(line,"signal") or fld(line,"side")
            r["sid"]=fld(line,"sid"); r["trend_filter"]=(fld(line,"trend_filter") or "").lower()
            sv=ffloat(line,"scaled_volume")
            if sv is not None: r["lot"]=sv
        elif kind == "TSO_REGISTERED" and tk:
            r=T[tk]; r["tso_reg"]=True
            r["lot"]=ffloat(line,"scaled_volume") or r["lot"]; r["base"]=ffloat(line,"base_volume")
        elif kind.startswith("TSO_PARTIAL_CLOSE") and tk:
            T[tk]["tso_partials"]+=1
        elif kind == "ENTRY_FILL" and tk:
            r=T[tk]; r["fill_ts"]=ts; r["trend_at_fill"]=fld(line,"trend")
        elif kind in ("PD_ZONE_CHECK", "PDFIBOPLUS") and tk:
            sub = line.split("|")[1].strip() if "|" in line else ""
            res = fld(line,"result")
            if sub == "fill_check": T[tk]["pd_fill"]=res
            elif sub.startswith("round1"): T[tk]["pd_round1"]=res or sub
        elif kind == "TREND_RECHECK" and tk:
            sub = line.split("|")[1].strip() if "|" in line else ""
            r=T[tk]
            if "skip_no_data" in sub: r["tr_blind"]+=1
            elif "fill_close" in sub: r["tr_closed"]=True
            elif sub.startswith("fill_round"): r["tr_ran"]=True  # recheck รันจริง (decision/follow-up)
        elif kind == "POSITION_CLOSED" and tk and "symbol=XAUUSD" in line:
            r=T[tk]; r["closed"]=True; r["profit"]=ffloat(line,"profit")
            r["reason"]=fld(line,"reason"); r["is_sl"]="SL Hit" in line; r["is_tp"]="TP Hit" in line
            r["close_ts"]=ts; r["tf"]=r["tf"] or fld(line,"tf"); r["side"]=r["side"] or fld(line,"side")
            r["sid"]=r["sid"] or fld(line,"sid")
            if not r["trend_filter"]: r["trend_filter"]=(fld(line,"trend_filter") or "").lower()

# SL guard status จาก compare CSV
guard_status = {}
if os.path.exists(CSV_CMP):
    with open(CSV_CMP, encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            guard_status[row["ticket"]] = row["status"]

# เฉพาะ XAU ที่ปิดแล้ว
orders = {tk:r for tk,r in T.items() if r["closed"]}

def trend_dir(tf):
    if "bull" in (tf or ""): return "BULL"
    if "bear" in (tf or ""): return "BEAR"
    return "SW"

rows=[]
for tk,r in orders.items():
    side=r["side"]; td=trend_dir(r["trend_filter"])
    counter = (td=="BULL" and side=="SELL") or (td=="BEAR" and side=="BUY")
    # flags
    lot_ok = (r["lot"]==EXPECT_LOT) if r["lot"] is not None else None
    trend_flag = "COUNTER" if counter else "ok"
    recheck_flag = ("closed" if r["tr_closed"] else
                    ("ran" if r["tr_ran"] else
                     ("BLIND" if r["tr_blind"]>0 else "none")))
    pd_flag = r["pd_fill"] or r["pd_round1"] or "none"
    tso_flag = "off" if not r["tso_reg"] else f"on/{r['tso_partials']}p"
    g = guard_status.get(tk,"")
    guard_flag = "SHOULD-BLOCK" if g in ("AVOIDED","CLOSE_EARLY") else ("ok" if r["is_sl"] else "-")
    rows.append({**r,"ticket":tk,"counter":counter,"lot_ok":lot_ok,"trend_flag":trend_flag,
                 "recheck_flag":recheck_flag,"pd_flag":pd_flag,"tso_flag":tso_flag,"guard_flag":guard_flag})

rows.sort(key=lambda r: r["close_ts"] or r["create_ts"] or "")

# ── CSV ──
out=os.path.join(ROOT,"orders_health.csv")
with open(out,"w",newline="",encoding="utf-8-sig") as f:
    w=csv.writer(f)
    w.writerow(["close_ts","ticket","side","tf","sid","lot","lot_ok","trend_filter","trend",
                "recheck","pd","tso","sl_guard","profit","reason"])
    for r in rows:
        w.writerow([r["close_ts"],r["ticket"],r["side"],r["tf"],r["sid"],r["lot"],
            "" if r["lot_ok"] is None else ("Y" if r["lot_ok"] else "N"),r["trend_filter"],
            r["trend_flag"],r["recheck_flag"],r["pd_flag"],r["tso_flag"],r["guard_flag"],
            f"{r['profit']:.2f}" if r["profit"] is not None else "",r["reason"]])

n=len(rows)
print("="*92)
print(f"  ORDERS HEALTH-CHECK — XAUUSD {WIN_START}+  ({n} closed orders)  -> orders_health.csv")
print("="*92)

# LOT
lc=Counter(r["lot"] for r in rows)
abn_lot=[r for r in rows if r["lot_ok"] is False]
print(f"\n  💰 LOT: คาดหวัง {EXPECT_LOT}")
for lot,c in sorted(lc.items(), key=lambda x:-x[1]):
    tag = "✅" if lot==EXPECT_LOT else ("❓" if lot else "?")
    print(f"      lot={lot}: {c} {tag}")
print(f"      ผิดปกติ (lot≠{EXPECT_LOT}): {len(abn_lot)}")

# TREND
nc=sum(1 for r in rows if r["counter"])
print(f"\n  📈 TREND: สวนเทรนด์ {nc}/{n} ({nc/n*100:.0f}%)")
rc=Counter(r["recheck_flag"] for r in rows)
print(f"      Trend Recheck: " + " | ".join(f"{k}={v}" for k,v in rc.most_common()))
print(f"      → BLIND = recheck พังช่วงนั้น (ไม่เคยตัดสิน)")

# PD
pc=Counter(r["pd_flag"] for r in rows)
print(f"\n  ⚖️ PD ZONE: " + " | ".join(f"{k}={v}" for k,v in pc.most_common()))

# TSO
tc=Counter(("off" if not r["tso_reg"] else "on") for r in rows)
pp=Counter(r["tso_partials"] for r in rows if r["tso_reg"])
print(f"\n  📈 SCALE-OUT: on={tc.get('on',0)} off={tc.get('off',0)}")
print(f"      partials/order: " + " | ".join(f"{k}p={v}" for k,v in sorted(pp.items())))

# SL GUARD
gc=Counter(r["guard_flag"] for r in rows)
print(f"\n  🛡️ SL GUARD: " + " | ".join(f"{k}={v}" for k,v in gc.most_common()))
print(f"      SHOULD-BLOCK = guard เก่าควรบล็อกแต่ไม่ทำ (bug) = {gc.get('SHOULD-BLOCK',0)} orders")

# multi-flag abnormal
print("\n"+"="*92)
print("  🔴 TOP order ผิดปกติหลายจุด (สวนเทรนด์ + recheck blind + guard ควรบล็อก) — loss มากสุด")
print("="*92)
def score(r): return (r["counter"]) + (r["recheck_flag"]=="BLIND") + (r["guard_flag"]=="SHOULD-BLOCK") + (r["lot_ok"] is False)
bad=[r for r in rows if score(r)>=2 and (r["profit"] or 0)<0]
bad.sort(key=lambda r:r["profit"] or 0)
print(f"  {'close_ts':<17}{'ticket':>11}{'sd':>5}{'tf':>4}{'sid':>4}{'lot':>6} {'trend':>8}{'recheck':>8}{'pd':>6}{'tso':>7}{'guard':>13}{'P/L':>8}")
for r in bad[:30]:
    print(f"  {r['close_ts']:<17}{r['ticket']:>11}{r['side']:>5}{str(r['tf']):>4}{str(r['sid']):>4}"
          f"{str(r['lot']):>6} {r['trend_filter'][:7]:>8}{r['recheck_flag']:>8}{str(r['pd_flag'])[:5]:>6}"
          f"{r['tso_flag']:>7}{r['guard_flag']:>13}{(r['profit'] or 0):>8.2f}")
print(f"\n  รวม order ผิดปกติ ≥2 จุด ที่ขาดทุน: {len(bad)} ตัว | loss รวม {sum(r['profit'] or 0 for r in bad):.2f}")
