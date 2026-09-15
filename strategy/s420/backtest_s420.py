# -*- coding: utf-8 -*-
"""Standalone backtest runner สำหรับ S420 ZigZag PA Strategy โดยเฉพาะ (ไม่ใช้
sim_strategy_backtest.py ร่วมกับ strategy อื่น) รองรับกำหนดช่วงเวลาตรงๆ ด้วย
--start/--end หรือ --days แทนการนับ --months จากปัจจุบันแบบเดิม

lookback (จำนวนแท่งย้อนหลังที่ detector เห็น ณ แต่ละจุด) คำนวณจาก
LOOKBACK_BARS ต่อ TF ในไฟล์นี้เอง (ต้องตรงกับ _ENTRY_BAR_COUNT ใน
demo_portfolio.py เป๊ะ — ดู comment บน LOOKBACK_BARS) ไม่ต้องส่งเป็น
argument แยกอีกต่อไป — ระบบจะไปดึงข้อมูลเพิ่มก่อน --start เองอัตโนมัติ

Usage:
    python backtest_s420.py --start 2026-06-01 --end 2026-08-11 --tf M15
    python backtest_s420.py --days 60 --tf M15
    python backtest_s420.py --days 14 --cfg-json "{\"TP_RATE\": 1.0}"
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import multiprocessing as mp
import os
import re
import shutil
import sys
import time as _time
from datetime import datetime, timedelta, timezone

import MetaTrader5 as mt5

# config.py อยู่ที่ root ของโปรเจกต์ ไม่ใช่ในโฟลเดอร์นี้ (strategy/s420/)
_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import config
from strategy420 import compute_zigzag_state, _ratios

BKK = timezone(timedelta(hours=7))
TF_MAP = {"M1": mt5.TIMEFRAME_M1, "M5": mt5.TIMEFRAME_M5,
          "M15": mt5.TIMEFRAME_M15, "M30": mt5.TIMEFRAME_M30,
          "H1": mt5.TIMEFRAME_H1}
TF_SECONDS = {"M1": 60, "M5": 300, "M15": 900, "M30": 1800, "H1": 3600}

# จำนวนแท่ง base-TF ย้อนหลังที่ detect_s420() เห็น ณ แต่ละจุด — ต้อง**ตรงกับ
# _ENTRY_BAR_COUNT ใน demo_portfolio.py เป๊ะทุก TF** ไม่ใช่ค่าคงที่เดียวข้าม TF
# แบบเดิม (เคยใช้ 1200 คงที่ทุก TF) — 2026-08-14 เจอบั๊กจริงจากการเทียบ --compare
# กับ live บน 3586: pattern EW=4384.35 (Anti Gartley) ที่ live เข้าจริงบน M1
# ต้องการ zigzag pivot chain ที่สร้างจาก 18000 แท่งย้อนหลัง (ตรงกับ
# _ENTRY_BAR_COUNT["M1"]=18000 ของ live) ถ้าใช้ lookback แค่ 1200 แท่ง (๊20
# ชม.) แบบเดิม จะไม่มีทาง detect pattern นี้ได้เลย ("Not enough zigzag pivots")
# เพราะ pivot chain algorithm สร้างจากจุดเริ่ม window ไป ถ้า window สั้นกว่า
# จะไม่มี pivot พอสร้างโครง 5 จุดของ harmonic pattern บางแบบ — ไม่ใช่ repaint
# แค่ lookback ไม่ตรงกับ live (ยืนยันแล้วด้วยการรัน compute_zigzag_state ตรงๆ
# เทียบ 1200 vs 18000 แท่ง ที่บาร์เดียวกันเป๊ะ ได้ None vs Anti Gartley ตรง
# กับ live เป๊ะ) — ดู [[project-s420-zigzagpa-status]] ในความจำสำหรับรายละเอียด
LOOKBACK_BARS = {"M1": 18000, "M5": 3600, "M15": 1200, "M30": 600, "H1": 350}
# ขั้นต่ำที่ยอมให้ใช้ได้ถ้า broker history ไม่ย้อนหลังถึง LOOKBACK_BARS เต็ม — ยืนยันแล้วว่า
# pivot chain ลู่เข้า (ไม่เปลี่ยนค่า) ตั้งแต่ ~300 แท่งขึ้นไป จึงไม่ hard-fail ที่ค่านี้
MIN_LOOKBACK_BARS = 300
DEFAULT_DAYS = 60


def parse_bkk(value):
    parsed = datetime.fromisoformat(value) if value else datetime.now(BKK)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=BKK)
    return parsed.astimezone(BKK)


def fmt_bkk(dt):
    """แปลงเป็นเวลา BKK แล้ว format แบบ 'YYYY-MM-DD HH:MM:SS' (ไม่มี T/offset)."""
    return dt.astimezone(BKK).strftime("%Y-%m-%d %H:%M:%S")


def _csv_path_for_tf(csv_path, tf_name):
    """แทรก _<tf> ก่อนนามสกุลไฟล์ เช่น s420_trades.csv -> s420_trades_M15.csv (ใช้ตอน --tf all)."""
    if "." in csv_path:
        stem, ext = csv_path.rsplit(".", 1)
        return f"{stem}_{tf_name}.{ext}"
    return f"{csv_path}_{tf_name}"


# MQL5\Files ของ terminal 3586 (demo-iux-2101183586) — terminal หลักที่รัน S420
# live จริง เลือกไว้ให้ indicator mql5/backtest_S420.mq5 อ่านไฟล์นี้แสดงผลบน
# ชาร์ตได้ (MQL5 sandbox อ่านได้แค่ Files folder ของ terminal ตัวเอง อ่าน path
# นอกนี้ไม่ได้) ต้องตรงชื่อไฟล์เป๊ะกับที่ indicator คาดหวัง: s420_trades_<TF>.csv
_MQL5_FILES_DIR = os.path.join(_ROOT, "profiles", "demo", "demo-iux-2101183586", "mt5", "MQL5", "Files")


def _sync_csv_to_mql5(csv_path, retries=4, retry_delay=1.5):
    """copy ไฟล์ CSV ที่เพิ่งเขียนไปที่ MQL5\\Files ของ terminal 3586 ให้
    indicator backtest_S420.mq5 อ่านเห็นทันที (indicator เช็ค mtime ไฟล์เองทุก
    InpRefreshSec วิ ไม่ต้อง restart indicator) เงียบๆ ถ้า path ไม่มีอยู่จริง
    (เช่น terminal ยังไม่เคย setup หรือรันบนเครื่องอื่น) ไม่ทำให้ backtest ล้ม

    retry เพราะเจอจริง 2026-08-19: ตอน indicator กำลังแนบอยู่บนชาร์ต TF นั้น
    MT5 ถือ lock ไฟล์ปลายทางไว้เป็นช่วงๆ (exclusive) ทำให้ copy ทับพลาดด้วย
    PermissionError/OSError — ลองใหม่สัก 2-3 ครั้งเผื่อ lock ปล่อยเองระหว่างรอ
    ก่อนค่อยยอมแพ้ (ไม่ควร retry ถี่/นานเกินไป เพราะบางที lock ค้างจริงจนกว่า
    ผู้ใช้จะถอด/สลับ TF ของ indicator เอง)"""
    if not os.path.isdir(_MQL5_FILES_DIR):
        return
    dest = os.path.join(_MQL5_FILES_DIR, os.path.basename(csv_path))
    last_exc = None
    for attempt in range(1, retries + 1):
        try:
            shutil.copyfile(csv_path, dest)
            print(f"  [mql5-sync] copy ไปที่ {dest}" + (f" (สำเร็จตอน retry ครั้งที่ {attempt})" if attempt > 1 else ""))
            return
        except OSError as exc:
            last_exc = exc
            if attempt < retries:
                _time.sleep(retry_delay)
    print(f"  [mql5-sync] copy ไม่สำเร็จหลังลอง {retries} ครั้ง: {last_exc} "
          f"— ไฟล์ปลายทางน่าจะถูก MT5 ล็อกอยู่ (indicator แนบอยู่บนชาร์ต TF นี้) "
          f"ลองถอด/สลับ TF ของ indicator แล้วรัน backtest ใหม่")


# --- MT5 Timezone Rule ของโปรเจกต์นี้ (ยืนยันด้วยราคาจริงเทียบ TradingView) ---
# broker เก็บ bar time แบบ chart=UTC+6 แต่ mt5 python module คืนค่าตัวเลข
# เหมือนเป็น true-UTC ตรงๆ ทำให้:
#   - DISPLAY (raw bar time -> เวลา BKK จริง) ต้อง fromtimestamp(ts,BKK) - 1h
#   - FETCH/QUERY (เวลา BKK จริง -> เวลาที่ต้องส่งให้ mt5 API) ต้อง +1h ก่อนแปลง
def bar_time_to_bkk(raw_time):
    """แปลง raw MT5 bar time (Unix ts) เป็นเวลา BKK จริง (ตรงกับที่เห็นบน
    TradingView/นาฬิกาจริง — ยืนยันแล้วด้วยราคาไม้จริงที่ผู้ใช้เทียบมา)."""
    return datetime.fromtimestamp(int(raw_time), tz=BKK) - timedelta(hours=1)


def bkk_to_query(dt_bkk):
    """แปลงเวลา BKK จริงเป็นเวลาที่ต้องส่งให้ mt5 API ตอน query/fetch."""
    return dt_bkk + timedelta(hours=1)


# Fib rate ของ Pine target01 จริง (EW=0.236/TP=0.618/SL=-0.236) — ไม่ใช่ค่า
# default ของ strategy420.DEFAULT_CFG (TP_RATE=1.618) ที่ถูกปรับไว้เพื่อผ่าน
# เกณฑ์ RR>=1.5 ของ sim_strategy_backtest.py/engine กลางเท่านั้น สคริปต์นี้
# จำลองแบบ stateful เองไม่ผ่าน engine กลาง เลยไม่มีเหตุผลต้องตัด RR ทิ้ง —
# ใช้ rate จริงของ Pine ได้เต็มที่เพื่อความตรงต้นฉบับสูงสุด
PINE_TARGET1_CFG = {"EW_RATE": 0.236, "TP_RATE": 0.618, "SL_RATE": -0.236}


def prepare_rates(tf_name, start_bkk, end_bkk):
    """ดึงราคาช่วง [start_bkk, end_bkk] (เวลา BKK จริง) พร้อม buffer ย้อนหลังพอ
    สำหรับ LOOKBACK_BARS — แปลงผ่าน bkk_to_query()/bar_time_to_bkk() ให้ตรง
    กับ MT5 Timezone Rule ของโปรเจกต์ (ดู comment เหนือฟังก์ชันนั้น)."""
    history_days = math.ceil(LOOKBACK_BARS[tf_name] * TF_SECONDS[tf_name] / 86400.0) + 7
    fetch_start = bkk_to_query(start_bkk - timedelta(days=history_days))
    fetch_end = bkk_to_query(end_bkk)
    if not config.mt5_initialize(mt5):
        raise RuntimeError("MT5 initialization failed")
    acc = mt5.account_info()
    if acc is not None:
        print(f"MT5 account: login={acc.login} server={acc.server} name={acc.name} "
              f"balance={acc.balance:.2f} {acc.currency}")
    else:
        print("MT5 account: ไม่พบข้อมูลบัญชี (account_info() คืนค่า None)")

    tick = mt5.symbol_info_tick(config.SYMBOL)
    if tick is not None:
        server_bkk = bar_time_to_bkk(tick.time)  # tick.time เป็น raw MT5 time เหมือน bar time ต้อง -1h เช่นกัน
        print(f"เวลาปัจจุบันของ broker (raw MT5): {datetime.fromtimestamp(int(tick.time), tz=BKK).strftime('%Y-%m-%d %H:%M:%S')}  "
              f"|  เวลาจริง BKK (แก้ตาม MT5 Timezone Rule): {fmt_bkk(server_bkk)}")
    else:
        print("เวลาปัจจุบันของ broker: ไม่พบ tick ล่าสุด (symbol_info_tick() คืนค่า None)")

    rates = mt5.copy_rates_range(config.SYMBOL, TF_MAP[tf_name], fetch_start, fetch_end)
    mt5.shutdown()
    if rates is None or len(rates) <= MIN_LOOKBACK_BARS:
        raise RuntimeError("not enough MT5 rates")
    bars = list(rates)
    start_query = bkk_to_query(start_bkk)
    start_index = next(
        (index for index, bar in enumerate(bars)
         if int(bar["time"]) >= int(start_query.timestamp())),
        None,
    )
    if start_index is None or start_index < MIN_LOOKBACK_BARS:
        raise RuntimeError(
            f"ประวัติ {tf_name} ก่อน --start มีแค่ {start_index} แท่ง ต่ำกว่าขั้นต่ำที่ต้องการ "
            f"({MIN_LOOKBACK_BARS} แท่ง) — ลองขยับ --start ให้ใกล้ปัจจุบันขึ้น หรือเช็คว่า broker "
            f"มีประวัติ {tf_name} ย้อนหลังพอหรือไม่"
        )
    if start_index < LOOKBACK_BARS[tf_name]:
        print(f"หมายเหตุ: ประวัติก่อน --start มีแค่ {start_index} แท่ง (น้อยกว่า "
              f"LOOKBACK_BARS[{tf_name}]={LOOKBACK_BARS[tf_name]} ที่ตั้งใจไว้ให้ตรง live) — "
              f"ใช้เท่าที่มีแทน ⚠️ ผลอาจเปลี่ยนได้จริง (ยืนยันแล้วว่า lookback สั้นไปทำให้ pivot "
              f"chain ไม่ครบ พลาด pattern บางแบบไปเลย ไม่ใช่แค่ลู่เข้าช้า — ดู comment บน "
              f"LOOKBACK_BARS ด้านบนไฟล์)")
    return bars, start_index


def _compute_signal_range(bars_slice, tf_name, cfg, local_lo, local_hi, lookback):
    """คำนวณ (bull_name,bear_name,fib_ew,fib_tp,fib_sl,x,a,b,c,d) หรือ None ต่อ
    แท่ง สำหรับ local index ช่วง [local_lo, local_hi) ใน bars_slice — ใช้เป็น
    worker ของ multiprocessing.Pool (ต้องเป็น module-level function ถึงจะ
    pickle ได้บน Windows) แต่ละ index ไม่พึ่งผลจาก index อื่นเลย
    (compute_zigzag_state คำนวณใหม่จาก window สดทุกครั้งอยู่แล้ว) จึงแบ่งช่วง
    เวลาคำนวณพร้อมกันหลาย process ได้อย่างปลอดภัย โดยไม่ต้องแก้
    compute_zigzag_state เลย — x/a/b/c/d เก็บไว้ด้วยเพราะ backtest() เอาไปใช้
    สร้าง reason string ตอนเปิดไม้/pending"""
    out = []
    for local_index in range(local_lo, local_hi):
        window = bars_slice[max(0, local_index - lookback + 1):local_index + 1]
        state, _err = compute_zigzag_state(window, tf_name, cfg)
        if state is None:
            out.append(None)
        else:
            out.append((state["bull_name"], state["bear_name"],
                         state["fib_ew"], state["fib_tp"], state["fib_sl"],
                         state["x"], state["a"], state["b"], state["c"], state["d"]))
    return out


def compute_signals_parallel(bars, tf_name, cfg, start_index, end_index, lookback, n_workers=None):
    """คำนวณ signal ของทุกแท่งใน [start_index, end_index) แบบขนานหลาย process —
    แบ่งช่วงเวลาเป็นก้อนๆ ให้แต่ละ worker คำนวณอิสระ (แต่ละก้อนพก lookback
    buffer ของตัวเองไปด้วย ไม่ใช่แชร์ state ข้าม process) คืน list เรียงตรงกับ
    range(start_index, end_index) ทุกประการ — ใช้ทดแทนการเรียก
    compute_zigzag_state ทีละแท่งใน backtest() loop ปกติ (ซึ่งรื้อคำนวณ window
    ~18000 แท่งซ้ำทุกแท่งบน M1 ช้ามาก ใช้ core เดียว) ได้ speedup ~จำนวน core"""
    total = end_index - start_index
    if total <= 0:
        return []
    if n_workers is None:
        n_workers = max(1, min(mp.cpu_count() - 2, 16))
    n_workers = max(1, min(n_workers, total))
    if n_workers == 1:
        return _compute_signal_range(bars, tf_name, cfg, start_index, end_index, lookback)

    chunk_size = math.ceil(total / n_workers)
    tasks = []
    for w in range(n_workers):
        lo = start_index + w * chunk_size
        hi = min(end_index, lo + chunk_size)
        if lo >= hi:
            continue
        slice_start = max(0, lo - lookback + 1)
        tasks.append((bars[slice_start:hi], tf_name, cfg, lo - slice_start, hi - slice_start, lookback))

    with mp.Pool(processes=len(tasks)) as pool:
        results = pool.starmap(_compute_signal_range, tasks)

    merged = []
    for r in results:
        merged.extend(r)
    return merged


def backtest(tf_name, spread, lot, start_bkk, end_bkk, cfg=None, debug_bkk=None, order_type="limit",
             parallel=True, n_workers=None, max_concurrent=1):
    """จำลองแบบ stateful ต่อเนื่องทุกบาร์ (เหมือน Pine/MQL5 EA จริง) แทนที่จะ
    หยุดเช็ค signal ใหม่จนกว่าไม้เดิมจะปิด — เช็ค TP/SL (dynamic re-anchor
    ตาม pivot ล่าสุด) และ pattern ใหม่ทุกบาร์ ปิด+เปิดสวนทางได้ทันที (reversal,
    เฉพาะ order_type="market") ตรงกับพฤติกรรมจริงของ strategy.close/
    strategy.entry ของ Pine

    order_type="limit" (default — ยืนยันแล้วว่าดีกว่า market ทุก TF/ช่วงเวลาที่
    ทดสอบ): วาง pending order ที่ราคา fib_ew พอดี ทันทีที่ pattern match (ไม่ต้อง
    รอ close อยู่ในโซนก่อนแบบ market) แล้วรอแท่งถัดไปแตะราคานั้นจริงถึงจะ fill —
    ยกเลิกถ้าไม่โดนภายใน CANCEL_BARS แท่ง (default 3, ตาม cfg ของ
    strategy420.DEFAULT_CFG) ข้อจำกัด: ยังไม่มี reversal ทันทีแบบ market
    (position เดิมต้องรอ TP/SL ปิดเองก่อน ถึงจะเปิด pending ใหม่ได้) — เป็นการลด
    ความซับซ้อนโดยตั้งใจ เพื่อเทียบผล fill-price ล้วนๆ ก่อน
    order_type="market": เข้าที่ราคาเปิดของแท่งถัดไป ทันทีที่ close อยู่ในโซน EW
    แล้ว (พฤติกรรมเดิมก่อนเทียบผล — เก็บไว้เป็นทางเลือกทดสอบเปรียบเทียบเท่านั้น)

    debug_bkk (datetime หรือ None): ถ้าระบุ จะ print state เต็ม (X,A,B,C,D,
    ratios, bull/bear, OHLC) ของแท่งที่ตรงเวลา BKK นี้ ใช้สำหรับ debug เทียบ
    กับ TradingView/MQL5 โดยไม่ต้องเขียนสคริปต์แยก (ปิด parallel อัตโนมัติเมื่อ
    ระบุ debug_bkk เพราะ tuple สัญญาณแบบย่อไม่มี x/a/b/c/d/ratios ให้ print)

    parallel (bool, default True): คำนวณสัญญาณทุกแท่งแบบขนานหลาย process ก่อน
    (compute_signals_parallel) แล้วค่อยรัน loop จัดการ position/pending แบบ
    sequential ตามปกติ (loop ส่วนนี้เบามาก ไม่ต้องขนาน) — เร็วขึ้นมากบน M1 ที่
    lookback ใหญ่ (18000 แท่ง) เพราะ compute_zigzag_state ไม่พึ่ง state ข้าม
    แท่งเลย แบ่งช่วงเวลาคำนวณพร้อมกันได้ปลอดภัย 100% (ผลลัพธ์เหมือน sequential
    ทุกประการ แค่เร็วกว่า) n_workers=None -> ใช้ cpu_count()-2 อัตโนมัติ

    max_concurrent (int, default 1): จำนวนไม้ (position+pending รวมกัน) สูงสุดที่
    เปิดพร้อมกันได้ต่อ TF นี้ — default=1 ตรงกับ cap ของ live จริง (รอไม้เดิม
    ปิดก่อนถึงเปิดใหม่ได้ เหมือนที่ demo_portfolio.py ใช้ cap=1 กับ S420/S421)
    ใส่ค่าสูงๆ (เช่น 999) เพื่อดูว่า "ถ้าไม่บล็อกไม้ซ้อนเลย" จะออกไม้ได้กี่ไม้/
    P&L เท่าไหร่ — ใช้เทียบกับ live ที่ตอนนี้มีไม้เก่าค้าง cap ไว้จนพลาดสัญญาณไป
    หลายสิบครั้ง (ดู [[project-s420-zigzagpa-status]] ในความจำ)"""
    if order_type not in ("market", "limit"):
        raise ValueError(f"order_type ต้องเป็น 'market' หรือ 'limit' (ได้ {order_type!r})")
    bars, start_index = prepare_rates(tf_name, start_bkk, end_bkk)
    detector_cfg = dict(PINE_TARGET1_CFG)
    detector_cfg.update(cfg or {})
    cancel_bars = int(detector_cfg.get("CANCEL_BARS", 3))
    contract_multiplier = 100.0 * lot

    precomputed_signals = None
    if parallel and debug_bkk is None:
        t_sig = _time.time()
        precomputed_signals = compute_signals_parallel(
            bars, tf_name, detector_cfg, start_index, len(bars) - 1,
            LOOKBACK_BARS[tf_name], n_workers,
        )
        print(f"  [{tf_name}] คำนวณสัญญาณขนานเสร็จใน {_time.time() - t_sig:.0f}s "
              f"({len(precomputed_signals)} แท่ง)", flush=True)

    trades = []
    signals = 0
    positions = []  # list of {"side","entry","sl","tp","entry_time","pattern","reason"}
    pendings = []  # list of {"side","level","sl","tp","cancel_index","pattern","reason"} — เฉพาะ order_type="limit"

    total_bars = len(bars) - 1 - start_index
    progress_step = max(1, total_bars // 20)  # print ~20 ครั้งตลอดการรัน
    progress_start = _time.time()

    def close_position(pos, exit_index, exit_price, outcome):
        side = pos["side"]
        pnl = (side * (exit_price - pos["entry"]) - spread) * contract_multiplier
        trades.append({
            "entry_time": fmt_bkk(pos["entry_time"]),
            "exit_time": fmt_bkk(bar_time_to_bkk(bars[exit_index + 1]["time"])),  # เวลาปิดแท่งที่โดน TP/SL (=เวลาเปิดแท่งถัดไป)
            "direction": "BUY" if side > 0 else "SELL",
            "entry": round(pos["entry"], 2),
            "sl": round(pos["sl"], 2), "tp": round(pos["tp"], 2),
            "outcome": outcome, "profit": round(pnl, 2),
            "pattern": pos["pattern"], "reason": pos["reason"],
            # raw MT5 epoch ดิบ (ไม่แปลง timezone เลย) — ให้ MQL5 ใช้ตรงกับ iTime()
            # ได้ทันทีโดยไม่ต้องเดา/hardcode offset ต่อ broker เอง (broker เดียวกัน
            # raw epoch ตรงกันเป๊ะเสมอ ไม่ว่า server จะตั้ง timezone อะไรก็ตาม) —
            # ดู [[mt5-timezone-rule]] ในความจำ เรื่องพลาด -1h/-6h ที่เจอมาก่อน
            "entry_time_raw": pos["entry_time_raw"],
            "exit_time_raw": int(bars[exit_index + 1]["time"]),
            # เวลาที่ pattern match/วาง pending order จริง (แท่งที่ signal เกิด)
            # ต่างจาก entry_time ที่เป็นเวลา fill จริง (อาจช้ากว่าหลายแท่งถ้าเป็น
            # order_type=limit ที่ต้องรอราคาย้อนมาแตะ fib_ew) — ใช้ตอนพี่อยากให้
            # indicator ลากเส้นตั้งแต่จุด "เข้า pattern/ตั้ง order" ไม่ใช่แค่ fill
            "signal_time": fmt_bkk(bar_time_to_bkk(pos["signal_time_raw"])),
            "signal_time_raw": pos["signal_time_raw"],
        })

    for index in range(start_index, len(bars) - 1):
        done = index - start_index
        if done % progress_step == 0 and done > 0:
            pct = 100.0 * done / total_bars
            elapsed = _time.time() - progress_start
            eta = elapsed / done * (total_bars - done)
            print(f"  [{tf_name}] {done}/{total_bars} แท่ง ({pct:.0f}%) "
                  f"| เวลาที่ใช้ {elapsed:.0f}s | เหลืออีกประมาณ {eta:.0f}s", flush=True)
        if precomputed_signals is not None:
            sig = precomputed_signals[index - start_index]
            if sig is None:
                continue
            bull_name, bear_name, fib_ew, fib_tp, fib_sl, x, a, b, cc, d = sig
            event = bars[index]
        else:
            window = bars[max(0, index - LOOKBACK_BARS[tf_name] + 1):index + 1]  # clamp กัน slice ติดลบเวลา lookback ไม่ครบเต็ม
            state, _err = compute_zigzag_state(window, tf_name, detector_cfg)
            if state is None:
                continue
            event = state["event"]
            bull_name, bear_name = state["bull_name"], state["bear_name"]
            fib_ew, fib_tp, fib_sl = state["fib_ew"], state["fib_tp"], state["fib_sl"]
            x, a, b, cc, d = state["x"], state["a"], state["b"], state["c"], state["d"]

        if debug_bkk is not None:
            bar_bkk = bar_time_to_bkk(event["time"])
            if bar_bkk == debug_bkk:
                x, a, b, cc, d = state["x"], state["a"], state["b"], state["c"], state["d"]
                ratios = _ratios(x, a, b, cc, d)
                xab, xad, abc, bcd = ratios if ratios else (None, None, None, None)
                print(f"[DEBUG {fmt_bkk(bar_bkk)}] O={event['open']:.2f} H={event['high']:.2f} "
                      f"L={event['low']:.2f} C={event['close']:.2f}")
                print(f"  X={x:.2f} A={a:.2f} B={b:.2f} C={cc:.2f} D={d:.2f}")
                print(f"  xab={xab if xab is None else round(xab,4)} "
                      f"xad={xad if xad is None else round(xad,4)} "
                      f"abc={abc if abc is None else round(abc,4)} "
                      f"bcd={bcd if bcd is None else round(bcd,4)}")
                print(f"  bull={bull_name} bear={bear_name} fib_ew={fib_ew:.2f} "
                      f"fib_tp={fib_tp:.2f} fib_sl={fib_sl:.2f}")

        # --- เช็คปิดไม้เดิมก่อน (ใช้ TP/SL ที่ล็อกไว้ตอนเปิดไม้ = pos["tp"]/
        # pos["sl"] เท่านั้น ห้ามใช้ fib_tp/fib_sl ของบาร์นี้ที่มาจาก
        # pattern ล่าสุด — เดิมมีบั๊กใช้ fib_tp/fib_sl ผิด ทำให้ปิดไม้ที่ระดับ
        # ราคาจาก pattern ในอนาคต (หลังเปิดไม้) ซึ่งเป็น look-ahead bias) ---
        still_open = []
        for pos in positions:
            side = pos["side"]
            pos_tp, pos_sl = pos["tp"], pos["sl"]
            if side > 0 and (event["high"] >= pos_tp or event["low"] <= pos_sl):
                hit_tp = event["high"] >= pos_tp
                close_position(pos, index, pos_tp if hit_tp else pos_sl, "TP" if hit_tp else "SL")
            elif side < 0 and (event["low"] <= pos_tp or event["high"] >= pos_sl):
                hit_tp = event["low"] <= pos_tp
                close_position(pos, index, pos_tp if hit_tp else pos_sl, "TP" if hit_tp else "SL")
            else:
                still_open.append(pos)
        positions = still_open

        if order_type == "market":
            # --- เช็คเปิดไม้ใหม่ (ปิดฝั่งตรงข้ามก่อนถ้าเป็น reversal, ไม่ซ้อนไม้ฝั่งเดียวกัน) ---
            buy_entry = bull_name is not None and event["close"] <= fib_ew
            sell_entry = bear_name is not None and event["close"] >= fib_ew
            fill_price = float(bars[index + 1]["open"])
            entry_time = bar_time_to_bkk(bars[index + 1]["time"])  # เวลา fill จริง (เปิดแท่งถัดไป)

            if buy_entry:
                opposite = [p for p in positions if p["side"] < 0]
                if opposite:
                    for pos in opposite:
                        close_position(pos, index, fill_price, "REV")
                    positions = [p for p in positions if p["side"] > 0]
                if len(positions) < max_concurrent:
                    signals += 1
                    if fib_sl < fill_price:  # sanity: SL ต้องอยู่ฝั่งขาดทุนจริง
                        positions.append({
                            "side": 1, "entry": fill_price, "sl": fib_sl, "tp": fib_tp,
                            "entry_time": entry_time, "entry_time_raw": int(bars[index + 1]["time"]),
                            "signal_time_raw": int(bars[index]["time"]),  # แท่งที่ signal เกิด (market fill แท่งถัดไปทันที)
                            "pattern": f"S420 BUY {bull_name}",
                            "reason": (f"{bull_name} X={x:.2f} A={a:.2f} "
                                       f"B={b:.2f} C={cc:.2f} D={d:.2f} "
                                       f"EW={fib_ew:.2f}"),
                        })
            elif sell_entry:
                opposite = [p for p in positions if p["side"] > 0]
                if opposite:
                    for pos in opposite:
                        close_position(pos, index, fill_price, "REV")
                    positions = [p for p in positions if p["side"] < 0]
                if len(positions) < max_concurrent:
                    signals += 1
                    if fib_sl > fill_price:  # sanity: SL ต้องอยู่ฝั่งขาดทุนจริง
                        positions.append({
                            "side": -1, "entry": fill_price, "sl": fib_sl, "tp": fib_tp,
                            "entry_time": entry_time, "entry_time_raw": int(bars[index + 1]["time"]),
                            "signal_time_raw": int(bars[index]["time"]),
                            "pattern": f"S420 SELL {bear_name}",
                            "reason": (f"{bear_name} X={x:.2f} A={a:.2f} "
                                       f"B={b:.2f} C={cc:.2f} D={d:.2f} "
                                       f"EW={fib_ew:.2f}"),
                        })
        else:  # order_type == "limit"
            # --- เช็ค fill ของ pending order ทุกตัว (ต้องเป็นแท่งหลังจากวางออเดอร์เท่านั้น) ---
            still_pending = []
            for pend in pendings:
                side = pend["side"]
                filled = False
                if side > 0 and event["low"] <= pend["level"]:
                    fill_price = min(pend["level"], event["open"])  # gap ผ่านราคาก็ยัง fill ได้ราคาดีกว่าเดิม
                    filled = True
                elif side < 0 and event["high"] >= pend["level"]:
                    fill_price = max(pend["level"], event["open"])
                    filled = True
                if filled:
                    signals += 1
                    positions.append({
                        "side": side, "entry": fill_price, "sl": pend["sl"], "tp": pend["tp"],
                        "entry_time": bar_time_to_bkk(event["time"]), "entry_time_raw": int(event["time"]),
                        "signal_time_raw": pend["armed_time_raw"],  # แท่งที่ pattern match/วาง pending (อาจเก่ากว่า fill หลายแท่ง)
                        "pattern": pend["pattern"], "reason": pend["reason"],
                    })
                elif index < pend["cancel_index"]:
                    still_pending.append(pend)  # ไม่โดนภายใน CANCEL_BARS แท่ง -> ยกเลิกถ้าเลย cancel_index
            pendings = still_pending

            # --- วาง pending order ใหม่ (เฉพาะตอนไม้รวม position+pending ยังไม่เต็ม max_concurrent) ---
            if len(positions) + len(pendings) < max_concurrent:
                if bull_name is not None and fib_sl < fib_ew:  # sanity: SL ต้องอยู่ฝั่งขาดทุนจริง
                    pendings.append({
                        "side": 1, "level": fib_ew, "sl": fib_sl, "tp": fib_tp,
                        "cancel_index": index + cancel_bars, "pattern": f"S420 BUY {bull_name}",
                        "armed_time_raw": int(bars[index]["time"]),  # แท่งที่ pattern match/วาง pending order จริง
                        "reason": (f"{bull_name} X={x:.2f} A={a:.2f} "
                                   f"B={b:.2f} C={cc:.2f} D={d:.2f} "
                                   f"EW={fib_ew:.2f} (limit)"),
                    })
                elif bear_name is not None and fib_sl > fib_ew:
                    pendings.append({
                        "side": -1, "level": fib_ew, "sl": fib_sl, "tp": fib_tp,
                        "cancel_index": index + cancel_bars, "pattern": f"S420 SELL {bear_name}",
                        "armed_time_raw": int(bars[index]["time"]),
                        "reason": (f"{bear_name} X={x:.2f} A={a:.2f} "
                                   f"B={b:.2f} C={cc:.2f} D={d:.2f} "
                                   f"EW={fib_ew:.2f} (limit)"),
                    })

    summary = _summarize(trades, tf_name, order_type, start_bkk, end_bkk, spread, lot, signals)
    return summary, trades


def _summarize(trades, tf_name, order_type, start_bkk, end_bkk, spread, lot, signals):
    profits = [trade["profit"] for trade in trades]
    wins = sum(profit > 0.0 for profit in profits)
    gross_win = sum(profit for profit in profits if profit > 0.0)
    gross_loss = -sum(profit for profit in profits if profit < 0.0)
    net = sum(profits)
    equity = peak = max_drawdown = 0.0
    for profit in profits:
        equity += profit
        peak = max(peak, equity)
        max_drawdown = max(max_drawdown, peak - equity)
    calendar_days = max(1.0, (end_bkk - start_bkk).total_seconds() / 86400.0)
    return {
        "strategy": "S420", "tf": tf_name, "order_type": order_type,
        "start": fmt_bkk(start_bkk), "end": fmt_bkk(end_bkk),
        "days": round(calendar_days, 1), "spread": spread, "lot": lot,
        "signals": signals, "closed": len(trades), "wins": wins,
        "win_rate": wins / len(trades) * 100.0 if trades else None,
        "net_profit": net,
        "pnl_per_day": net / calendar_days,
        "profit_factor": gross_win / gross_loss if gross_loss else (math.inf if gross_win else None),
        "max_drawdown": max_drawdown,
    }


def dedupe_tp_sl(trades):
    """ตัดไม้ที่คู่ (TP, SL) ซ้ำกับไม้ก่อนหน้า (แม้ entry ต่างกัน) ออก เก็บไว้แค่
    ไม้แรกสุดของแต่ละคู่ (tp, sl) ที่พบ — ใช้ดูผลถ้าตัด order ที่ระดับ TP/SL
    ซ้ำกันทิ้ง (เช่น pattern ตรวจจับซ้อนกันแล้วยิง limit ที่ TP/SL เดิมหลายรอบ)"""
    seen = set()
    out = []
    for t in trades:
        key = (round(t["tp"], 2), round(t["sl"], 2))
        if key in seen:
            continue
        seen.add(key)
        out.append(t)
    return out


_LOG_FILLED_RE = re.compile(
    r"^\[(?P<ts>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\] TG_SENT \| .*?\*(?P<label>[^*]+?)\* "
    r"limit filled \| \S+ (?P<dir>BUY|SELL) @ (?P<entry>[\d.]+) \| "
    r"SL `(?P<sl>[\d.]+)` TP `(?P<tp>[\d.]+)` \| Ticket: `(?P<ticket>\d+)`"
)
_LOG_CLOSED_RE = re.compile(
    r"^\[(?P<ts>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\] POSITION_CLOSED \| .*? \| "
    r"ticket=(?P<ticket>\d+) \| side=(?P<dir>BUY|SELL) \| symbol=(?P<symbol>\S+) \| "
    r"tf=(?P<tf>\w+) \| .*? \| open_price=(?P<open>[\d.]+) \| close_price=(?P<close>[\d.]+) \| "
    r"sl=(?P<sl>[\d.]+) \| tp=(?P<tp>[\d.]+) \| profit=(?P<profit>-?[\d.]+) \| "
    r"reason=(?P<reason>.*?) \| close_time="
)


def _parse_log_bkk(ts_str):
    return datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=BKK)


def _fetch_real_trades(profile_dir, start_bkk, end_bkk, comment_prefix):
    """ดึงไม้จริงจาก bot.log ของ profile ตรงๆ (ไม่ใช้ MT5 deal history) — จับคู่
    เวลา "limit filled" (มี label/SL/TP ตามที่ live คำนวณจริง) กับ
    "POSITION_CLOSED" (มี tf/close_price/profit/reason) ด้วย ticket คืน list
    ของ {ticket, tf, direction, entry, sl, tp, open_time, close_time, profit,
    reason, label}"""
    log_path = os.path.join(profile_dir, "logs", "bot.log")
    fills = {}
    closes = {}
    with open(log_path, "r", encoding="utf-8", errors="ignore") as handle:
        for line in handle:
            m = _LOG_FILLED_RE.match(line)
            if m:
                fills[m.group("ticket")] = {
                    "open_time": _parse_log_bkk(m.group("ts")),
                    "direction": m.group("dir"),
                    "entry": float(m.group("entry")),
                    "sl": float(m.group("sl")),
                    "tp": float(m.group("tp")),
                    "label": m.group("label"),
                }
                continue
            m = _LOG_CLOSED_RE.match(line)
            if m:
                closes[m.group("ticket")] = {
                    "close_time": _parse_log_bkk(m.group("ts")),
                    "tf": m.group("tf"),
                    "direction": m.group("dir"),
                    "open_price": float(m.group("open")),
                    "close_price": float(m.group("close")),
                    "sl": float(m.group("sl")),
                    "tp": float(m.group("tp")),
                    "profit": float(m.group("profit")),
                    "reason": m.group("reason"),
                }

    real_trades = []
    for ticket, close in closes.items():
        if not (start_bkk <= close["close_time"] <= end_bkk):
            continue
        fill = fills.get(ticket)
        if fill is None:
            # S420 เข้าด้วย limit เสมอ (order_type="limit") ไม้จริงของ S420 ต้อง
            # มี "limit filled" TG_SENT line เสมอ — ไม่มี fill line แปลว่าเป็นไม้
            # ของ strategy อื่นบนบัญชีเดียวกัน (เช่น S427/S429 ที่เข้าด้วย market
            # order) หลุดเข้ามาปนเพราะ POSITION_CLOSED ไม่มี field ระบุ strategy
            # (sid เป็นค่า placeholder เดียวกันทุก strategy) — ข้ามไปเลย ไม่ fallback
            continue
        if comment_prefix and comment_prefix not in fill["label"]:
            continue
        real_trades.append({
            "ticket": ticket,
            "tf": close["tf"],
            "direction": close["direction"],
            "entry": fill["entry"],
            "sl": fill["sl"],
            "tp": fill["tp"],
            "open_time": fill["open_time"],
            "close_time": close["close_time"],
            "profit": close["profit"],
            "reason": close["reason"],
            "label": fill["label"],
        })
    real_trades.sort(key=lambda t: t["open_time"])
    return real_trades


def _compare_trades(bt_trades, real_trades, tolerance):
    """จับคู่ไม้ backtest กับไม้จริงด้วยทิศทาง + ราคา entry ใกล้เคียงกัน
    (ภายใน tolerance) + เวลาเปิดห่างกันไม่เกิน 1 ชม. คืน (matched, bt_only,
    real_only) — จับคู่แบบ greedy ทีละคู่ที่ใกล้กันที่สุดก่อน"""
    candidates = []
    for bi, bt in enumerate(bt_trades):
        for ri, rt in enumerate(real_trades):
            if bt["direction"] != rt["direction"]:
                continue
            price_diff = abs(bt["entry"] - rt["entry"])
            if price_diff > tolerance:
                continue
            time_diff = abs((bt["open_time"] - rt["open_time"]).total_seconds())
            if time_diff > 3600:
                continue
            candidates.append((price_diff + time_diff / 3600.0, bi, ri))
    candidates.sort(key=lambda c: c[0])

    used_bt, used_real = set(), set()
    matched = []
    for _, bi, ri in candidates:
        if bi in used_bt or ri in used_real:
            continue
        used_bt.add(bi)
        used_real.add(ri)
        matched.append((bt_trades[bi], real_trades[ri]))

    bt_only = [bt for bi, bt in enumerate(bt_trades) if bi not in used_bt]
    real_only = [rt for ri, rt in enumerate(real_trades) if ri not in used_real]
    return matched, bt_only, real_only


def _compare_csv_path(csv_path, tf_name, suffix):
    stem, ext = (csv_path.rsplit(".", 1) if "." in csv_path else (csv_path, "csv"))
    return f"{stem}_{tf_name}_{suffix}.{ext}"


def _write_csv(path, rows, fieldnames):
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"เขียน {len(rows)} แถวลง {path}")


def run_compare(all_bt_trades, start_bkk, end_bkk, args):
    print("\n\n===== เทียบกับของจริงจาก bot.log (--compare) =====")
    real_trades_all = _fetch_real_trades(args.compare_profile_dir, start_bkk, end_bkk,
                                          args.compare_comment_prefix)
    print(f"อ่าน bot.log จาก {args.compare_profile_dir} ได้ {len(real_trades_all)} ไม้จริง "
          f"ในช่วง {start_bkk} - {end_bkk}")

    bt_trades = [{
        "tf": t["tf"], "direction": t["direction"], "entry": float(t["entry"]),
        "sl": t.get("sl"), "tp": t.get("tp"),
        "open_time": datetime.strptime(t["entry_time"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=BKK),
        "close_time": datetime.strptime(t["exit_time"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=BKK),
        "profit": float(t["profit"]), "outcome": t.get("outcome"),
    } for t in all_bt_trades]

    tf_list = sorted({t["tf"] for t in bt_trades} | {t["tf"] for t in real_trades_all})
    compare_fields = ["TF", "Direction", "BT_Open_Time", "MT5_Open_Time", "BT_Entry", "MT5_Entry",
                       "BT_SL", "MT5_SL", "BT_TP", "MT5_TP", "BT_Close_Time", "MT5_Close_Time",
                       "BT_Profit", "MT5_Profit", "MT5_Ticket", "MT5_Reason"]
    real_fields = ["Ticket", "TF", "Direction", "Open_Time", "Close_Time", "Entry", "SL", "TP",
                   "Profit", "Reason"]
    bt_fields = ["TF", "Direction", "Open_Time", "Close_Time", "Entry", "SL", "TP", "Profit", "Outcome"]

    grand_matched = grand_bt_only = grand_real_only = 0
    for tf_name in tf_list:
        bt_tf = [t for t in bt_trades if t["tf"] == tf_name]
        real_tf = [t for t in real_trades_all if t["tf"] == tf_name]
        matched, bt_only, real_only = _compare_trades(bt_tf, real_tf, args.compare_tolerance)
        grand_matched += len(matched)
        grand_bt_only += len(bt_only)
        grand_real_only += len(real_only)

        print(f"\n[{tf_name}] backtest={len(bt_tf)} จริง={len(real_tf)} "
              f"matched={len(matched)} bt_only={len(bt_only)} real_only={len(real_only)}")

        compare_rows = [{
            "TF": tf_name, "Direction": bt["direction"],
            "BT_Open_Time": bt["open_time"].strftime("%Y-%m-%d %H:%M:%S"),
            "MT5_Open_Time": rt["open_time"].strftime("%Y-%m-%d %H:%M:%S"),
            "BT_Entry": round(bt["entry"], 2), "MT5_Entry": round(rt["entry"], 2),
            "BT_SL": bt["sl"], "MT5_SL": round(rt["sl"], 2),
            "BT_TP": bt["tp"], "MT5_TP": round(rt["tp"], 2),
            "BT_Close_Time": bt["close_time"].strftime("%Y-%m-%d %H:%M:%S"),
            "MT5_Close_Time": rt["close_time"].strftime("%Y-%m-%d %H:%M:%S"),
            "BT_Profit": round(bt["profit"], 2), "MT5_Profit": round(rt["profit"], 2),
            "MT5_Ticket": rt["ticket"], "MT5_Reason": rt["reason"],
        } for bt, rt in matched]
        real_only_rows = [{
            "Ticket": rt["ticket"], "TF": rt["tf"], "Direction": rt["direction"],
            "Open_Time": rt["open_time"].strftime("%Y-%m-%d %H:%M:%S"),
            "Close_Time": rt["close_time"].strftime("%Y-%m-%d %H:%M:%S"),
            "Entry": round(rt["entry"], 2), "SL": round(rt["sl"], 2), "TP": round(rt["tp"], 2),
            "Profit": round(rt["profit"], 2), "Reason": rt["reason"],
        } for rt in real_only]
        bt_only_rows = [{
            "TF": bt["tf"], "Direction": bt["direction"],
            "Open_Time": bt["open_time"].strftime("%Y-%m-%d %H:%M:%S"),
            "Close_Time": bt["close_time"].strftime("%Y-%m-%d %H:%M:%S"),
            "Entry": round(bt["entry"], 2), "SL": bt["sl"], "TP": bt["tp"],
            "Profit": round(bt["profit"], 2), "Outcome": bt["outcome"],
        } for bt in bt_only]
        real_rows = [{
            "Ticket": rt["ticket"], "TF": rt["tf"], "Direction": rt["direction"],
            "Open_Time": rt["open_time"].strftime("%Y-%m-%d %H:%M:%S"),
            "Close_Time": rt["close_time"].strftime("%Y-%m-%d %H:%M:%S"),
            "Entry": round(rt["entry"], 2), "SL": round(rt["sl"], 2), "TP": round(rt["tp"], 2),
            "Profit": round(rt["profit"], 2), "Reason": rt["reason"],
        } for rt in real_tf]

        _write_csv(_compare_csv_path(args.csv, tf_name, "compare"), compare_rows, compare_fields)
        _write_csv(_compare_csv_path(args.csv, tf_name, "mt5_real"), real_rows, real_fields)
        _write_csv(_compare_csv_path(args.csv, tf_name, "mt5_not_match"), real_only_rows, real_fields)
        _write_csv(_compare_csv_path(args.csv, tf_name, "backtest_not_match"), bt_only_rows, bt_fields)

        if matched:
            bt_sum = sum(bt["profit"] for bt, _ in matched)
            real_sum = sum(rt["profit"] for _, rt in matched)
            print(f"  รวม P&L คู่ matched — backtest: {bt_sum:.2f} | จริง: {real_sum:.2f}")

    print(f"\n===== รวมทุก TF: matched={grand_matched} bt_only={grand_bt_only} "
          f"real_only={grand_real_only} =====")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--start", help="BKK ISO datetime เริ่ม backtest (เช่น 2026-06-01)")
    parser.add_argument("--end", help="BKK ISO datetime สิ้นสุด backtest; default = ตอนนี้")
    parser.add_argument("--days", type=int, help="จำนวนวันย้อนหลังจาก --end (ใช้แทน --start ได้)")
    parser.add_argument("--tf", choices=tuple(TF_MAP) + ("all",), default="M15",
                         help="timeframe เดียว หรือ 'all' เพื่อรันทุก timeframe แล้วสรุปเทียบกัน")
    parser.add_argument("--spread", type=float, default=0.20)
    parser.add_argument("--balance", type=float, default=100.0,
                         help="ยอดเงินสมมติ (USD) ใช้คำนวณ lot อัตโนมัติ = balance/10000 "
                              "(100->0.01, 1000->0.10, 10000->1.00, 100000->10.00) ใส่ --lot เพื่อ override ค่านี้")
    parser.add_argument("--lot", type=float, default=None,
                         help="ขนาด lot คงที่ (ถ้าไม่ใส่ จะคำนวณจาก --balance อัตโนมัติ)")
    parser.add_argument("--cfg-json", default="{}",
                         help="JSON object ส่งเข้า cfg ของ detect_s420 (เช่น TP_RATE/EW_RATE/SL_RATE)")
    parser.add_argument("--csv", default=os.path.join(_HERE, "s420_trades.csv"),
                         help="path ไฟล์ CSV ผลลัพธ์ (default = s420_trades.csv ในโฟลเดอร์นี้ ไม่ใช่ CWD)")
    parser.add_argument("--debug-bkk",
                         help="BKK ISO datetime ของแท่งที่อยาก print state เต็ม (X,A,B,C,D/ratios/bull-bear) "
                              "เช่น 2026-08-06T16:00:00")
    parser.add_argument("--order-type", choices=("market", "limit"), default="limit",
                         help="limit = วาง pending order ที่ fib_ew รอราคาแตะจริง (default — "
                              "ยืนยันแล้วว่าดีกว่า market ทุก TF/ช่วงเวลาที่ทดสอบ) | "
                              "market = เข้าที่ราคาเปิดแท่งถัดไปทันที")
    parser.add_argument("--no-parallel", action="store_true",
                         help="ปิดการคำนวณสัญญาณแบบขนานหลาย process (default เปิดอยู่ เร็วกว่า "
                              "sequential มากบน M1/M5 ที่ lookback ใหญ่) ใช้ตอน debug/เทียบผลเท่านั้น")
    parser.add_argument("--jobs", type=int, default=None,
                         help="จำนวน process ที่ใช้คำนวณสัญญาณขนาน (default = cpu_count()-2)")
    parser.add_argument("--compare", action="store_true",
                         help="หลัง backtest เสร็จ อ่าน logs/bot.log ของ profile จริง (default = "
                              "profiles/demo/demo-iux-2101183586, terminal ที่รัน S420 live) "
                              "ดึงไม้จริงมาเทียบกับไม้ backtest (จับคู่ด้วยทิศ/ราคา/เวลาใกล้เคียง) "
                              "เขียนไฟล์ {csv}_{TF}_compare/mt5_real/mt5_not_match/backtest_not_match.csv")
    parser.add_argument("--compare-profile-dir",
                         default=os.path.join(_ROOT, "profiles", "demo", "demo-iux-2101183586"),
                         help="path โฟลเดอร์ profile ที่มี profile.env ของ terminal จริงที่จะเทียบ")
    parser.add_argument("--compare-comment-prefix", default="S420",
                         help="กรอง deal ที่มี comment ขึ้นต้น/มีคำนี้เท่านั้น (default S420)")
    parser.add_argument("--compare-tolerance", type=float, default=1.0,
                         help="ระยะห่างราคาสูงสุด (USD) ที่ยังนับว่า match กัน (default 1.0)")
    parser.add_argument("--unblocked", action="store_true",
                         help="รันซ้ำอีกรอบแบบไม่จำกัดไม้ซ้อนต่อ TF (max_concurrent=999 แทน --cap) "
                             "แล้วเขียนผลลง {csv}_{TF}_unblocked.csv แยกจากไฟล์หลัก — ใช้ดูว่า "
                             "'ถ้าไม่มี cap กันไม้ซ้อนเลย' จะออกไม้ได้กี่ไม้/P&L เท่าไหร่ เทียบกับตอนที่ไม้เก่า "
                             "ค้างเปิดอยู่บน live แล้วบล็อกสัญญาณใหม่ทุกครั้ง (ดู log DEMO_PORTFOLIO_SKIP cap=1)")
    parser.add_argument("--cap", type=int, default=None,
                         help="จำนวนไม้ (position+pending รวมกัน) สูงสุดที่เปิดพร้อมกันได้ต่อ TF "
                             "ไม่ใส่ (default) = ดึงจาก config.demo_portfolio_max_pos_per_leg('S420-J_<TF>') "
                             "อัตโนมัติต่อ TF ตรงกับ live เป๊ะ (รองรับ --tf all ที่แต่ละ TF cap ไม่เท่ากันด้วย) "
                             "ใส่เลขเองเพื่อทดสอบเปรียบเทียบ (เช่น --cap 999 = ไม่จำกัด)")
    parser.add_argument("--no-mql5-sync", action="store_true",
                         help="ปิดการ copy CSV ไปที่ MQL5\\Files ของ terminal 3586 อัตโนมัติ (default เปิดอยู่ "
                             "ให้ indicator mql5/backtest_S420.mq5 เห็นผลใหม่ทันที) ใช้ตอนรัน sweep รัวๆ "
                             "หลายรอบไม่อยากให้ copy ทับถี่เกินไป")
    parser.add_argument("--no-duplicate-tp-sl", action="store_true",
                         help="ตัดไม้ที่คู่ TP/SL ซ้ำกับไม้ก่อนหน้าออก (entry ต่างกันได้ แต่ TP/SL เดียวกัน "
                             "ถือว่าซ้ำ) เก็บไว้แค่ไม้แรกสุดของแต่ละคู่ (tp, sl) — ใช้ดูผลถ้าตัด order "
                             "ที่ระดับ TP/SL ซ้ำกันทิ้ง")
    args = parser.parse_args()

    if args.start and args.days:
        parser.error("ใส่ได้แค่ --start หรือ --days อย่างใดอย่างหนึ่ง ไม่ใช่ทั้งคู่")

    lot = args.lot if args.lot is not None else args.balance / 10000.0
    print(f"lot={lot:.2f}" + (f" (คำนวณจาก --balance={args.balance:g})" if args.lot is None else " (ระบุตรงผ่าน --lot)"))

    end_bkk = parse_bkk(args.end)
    if args.start:
        start_bkk = parse_bkk(args.start)
    elif args.days:
        start_bkk = end_bkk - timedelta(days=args.days)
    else:
        start_bkk = end_bkk - timedelta(days=DEFAULT_DAYS)

    if start_bkk >= end_bkk:
        parser.error("--start ต้องมาก่อน --end")

    try:
        detector_cfg = json.loads(args.cfg_json)
        if not isinstance(detector_cfg, dict):
            raise ValueError("cfg must be a JSON object")
    except (json.JSONDecodeError, ValueError) as exc:
        parser.error(f"invalid --cfg-json: {exc}")

    debug_bkk = parse_bkk(args.debug_bkk) if args.debug_bkk else None
    tf_list = tuple(TF_MAP) if args.tf == "all" else (args.tf,)

    results = []
    all_bt_trades = []
    for tf_name in tf_list:
        cap = args.cap if args.cap is not None else config.demo_portfolio_max_pos_per_leg(f"S420-J_{tf_name}")
        print(f"\n===== TF={tf_name} ===== (cap={cap}{'  ' + ('ระบุเอง' if args.cap is not None else 'จาก config live')})")
        try:
            summary, trades = backtest(tf_name, args.spread, lot, start_bkk, end_bkk, detector_cfg, debug_bkk,
                                        order_type=args.order_type, parallel=not args.no_parallel, n_workers=args.jobs,
                                        max_concurrent=cap)
        except RuntimeError as exc:
            print(f"ข้าม TF={tf_name}: {exc}")
            continue
        if args.no_duplicate_tp_sl:
            before_count = len(trades)
            trades = dedupe_tp_sl(trades)
            summary = _summarize(trades, tf_name, args.order_type, start_bkk, end_bkk, args.spread, lot,
                                  summary["signals"])
            print(f"[no-duplicate-tp-sl] ตัดไม้ TP/SL ซ้ำออก {before_count - len(trades)} ไม้ "
                  f"(เหลือ {len(trades)} จาก {before_count})")
        print(summary)
        for t in trades:
            t["tf"] = tf_name
        all_bt_trades.extend(trades)

        csv_path = _csv_path_for_tf(args.csv, tf_name)  # ต่อท้าย TF เสมอ ไม่ว่าจะรันกี่ TF ก็ตาม
        with open(csv_path, "w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=(trades[0].keys() if trades else (
                "entry_time", "exit_time", "direction", "entry", "sl", "tp",
                "outcome", "profit", "pattern", "reason", "entry_time_raw", "exit_time_raw",
                "signal_time", "signal_time_raw",
            )))
            writer.writeheader()
            writer.writerows(trades)
        print(f"เขียน {len(trades)} ไม้ลง {csv_path}")
        if not args.no_mql5_sync:
            _sync_csv_to_mql5(csv_path)

        win_rate_str = f"{summary['win_rate']:.2f}%" if summary["win_rate"] is not None else "N/A"
        print("-" * 40)
        print(f"P&L        : {summary['net_profit']:.2f} USD")
        print(f"Win Rate   : {win_rate_str}")
        print(f"Win/Order  : {summary['wins']}/{summary['closed']}")
        print("-" * 40)
        results.append((tf_name, summary))

        if args.unblocked:
            try:
                unb_summary, unb_trades = backtest(tf_name, args.spread, lot, start_bkk, end_bkk, detector_cfg,
                                                    debug_bkk, order_type=args.order_type,
                                                    parallel=not args.no_parallel, n_workers=args.jobs,
                                                    max_concurrent=999)
            except RuntimeError as exc:
                print(f"ข้าม unblocked TF={tf_name}: {exc}")
            else:
                if args.no_duplicate_tp_sl:
                    unb_before = len(unb_trades)
                    unb_trades = dedupe_tp_sl(unb_trades)
                    unb_summary = _summarize(unb_trades, tf_name, args.order_type, start_bkk, end_bkk,
                                              args.spread, lot, unb_summary["signals"])
                    print(f"[unblocked][no-duplicate-tp-sl] ตัดไม้ TP/SL ซ้ำออก {unb_before - len(unb_trades)} ไม้ "
                          f"(เหลือ {len(unb_trades)} จาก {unb_before})")
                unb_csv_path = _compare_csv_path(args.csv, tf_name, "unblocked")
                with open(unb_csv_path, "w", newline="", encoding="utf-8") as handle:
                    writer = csv.DictWriter(handle, fieldnames=(unb_trades[0].keys() if unb_trades else (
                        "entry_time", "exit_time", "direction", "entry", "sl", "tp",
                        "outcome", "profit", "pattern", "reason", "entry_time_raw", "exit_time_raw",
                        "signal_time", "signal_time_raw",
                    )))
                    writer.writeheader()
                    writer.writerows(unb_trades)
                print(f"[unblocked] {tf_name}: signals={unb_summary['signals']} closed={unb_summary['closed']} "
                      f"(ปกติ={summary['closed']}) net_profit={unb_summary['net_profit']:.2f} "
                      f"(ปกติ={summary['net_profit']:.2f}) max_drawdown={unb_summary['max_drawdown']:.2f} "
                      f"(ปกติ={summary['max_drawdown']:.2f})")
                print(f"เขียน {len(unb_trades)} ไม้ลง {unb_csv_path}")

    if len(tf_list) > 1:
        print("\n===== สรุปเทียบทุก TF =====")
        header = f"{'TF':<6}{'P&L':>12}{'WinRate':>10}{'Win/Order':>12}{'PF':>10}{'MaxDD':>10}"
        print(header)
        for tf_name, summary in results:
            wr = f"{summary['win_rate']:.1f}%" if summary["win_rate"] is not None else "N/A"
            wo = f"{summary['wins']}/{summary['closed']}"
            if summary["profit_factor"] is None:
                pf = "N/A"
            elif summary["profit_factor"] == float("inf"):
                pf = "inf"
            else:
                pf = f"{summary['profit_factor']:.2f}"
            print(f"{tf_name:<6}{summary['net_profit']:>12.2f}{wr:>10}{wo:>12}{pf:>10}{summary['max_drawdown']:>10.2f}")

    if args.compare:
        run_compare(all_bt_trades, start_bkk, end_bkk, args)


if __name__ == "__main__":
    main()
