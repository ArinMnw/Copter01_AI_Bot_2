# Fork ของ run_backtest_sim.py — เก็บไฟล์ต้นฉบับไว้ตามเดิม (พี่ขอ 2026-08-05) ไฟล์นี้แก้ 2 บั๊ก
# scoped เฉพาะ LTS_AVENGERS_ULTRA_SAFE (AUS) / LTS_AVENGERS_HIGH_RISK (AHR) / LTS44
# (เพิ่ม LTS44 เข้ามา 2026-08-07 — เจอว่าติดบั๊ก compounding-double-scale ตัวเดียวกัน แม้ไม่มี
# duplicate leg ก็ตาม เพราะ weight ต่อ leg สูงถึง 690 อยู่แล้ว):
#   1. compounding-equity คูณ leg["weight"] ซ้ำอีกชั้นใน run_lts_af_backtest (ของเดิมเอา pnl_usd
#      ที่ทบต้นจาก sim_s31_backtest มาคูณ weight อีกที ทำให้ backtest ได้ P&L หลักสิบล้าน) — แก้เป็น
#      lot คงที่ (MIN_LOT x weight x scale, ไม่ทบต้น) ตรงกับสูตร live (demo_portfolio.py:_af_order_volume)
#   2. duplicate leg ในไฟล์ weight ต้นฉบับ (lts_avengers_*_weights.txt มี leg สัญญาณเดียวกันซ้ำ
#      กันหลายสิบครั้ง จากบั๊กใน lts_auto_ladder_log.md/lts_optimize_worst_day.py) — dedupe ในหน่วยความจำ
#      ตอนรัน (ไม่แก้ไฟล์ weight ต้นฉบับ) รวม leg signature เดียวกันบวก weight เข้าด้วยกัน (LTS44 ไม่มี
#      leg ซ้ำอยู่แล้ว ขั้นตอนนี้เป็น no-op สำหรับ LTS44)
# พร้อมจำลอง broker aggregate exposure cap (SYMBOL_VOLUME_LIMIT ~100 lot/ทิศทาง) ที่ของเดิมไม่มี
# หมายเหตุ: hour-bug fix (_post_filter_raw_signal_hour) และ Smart-Cutloss/Momentum-Stall overlay
# (_apply_lts_exit_overlay) ยัง scope เฉพาะ AUS/AHR เหมือนเดิม — ยังไม่มีหลักฐานว่า LTS44 มีปัญหา
# broker clock drift แบบเดียวกัน ไม่ได้ขยายไปโดยไม่จำเป็น
# พอร์ตอื่นนอกจาก AUS/AHR/LTS44 พฤติกรรมเหมือน run_backtest_sim.py ทุกอย่าง ไม่กระทบ
import os
import sys
import csv
import json
import re
import argparse
import subprocess
import pandas as pd
import numpy as np
import MetaTrader5 as mt5
import itertools
from datetime import datetime, timezone, timedelta
from collections import defaultdict

# Add root directory to sys.path so we can import modules from it
root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.append(root_dir)
# Also append dirname(__file__) for local imports
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

import config
config.IN_BACKTEST = True
import demo_portfolio as dp

# Core imports for S84/S86 backtests (used in AF and LTS portfolios)
from sim_s84_backtest import run_single as run_s84
from sim_s86_backtest import run_single as run_s86
from sim_s62_backtest import _atr_series
from optimize_s72_vs_demo_portfolio import DEFAULT_SPREAD
from optimize_s75_champion_formula import _simulate_leg
from ambfix_sweep2 import _post_filter_raw, _invert_raw
from optimize_s88_allin4s_fast import OVERLAY_CFG

# Standard sim modules (P13, P16, P18)
import sim_s30_backtest as s30sim
import sim_s31_backtest as s31sim
import sim_s34_backtest as s34sim
import sim_s36_backtest as s36sim
import sim_s37_backtest as s37sim
import sim_s38_backtest as s38sim
import sim_s39_backtest as s39sim
import sim_s40_backtest as s40sim
import sim_s41_backtest as s41sim
import sim_s42_backtest as s42sim
import sim_s44_backtest as s44sim
import sim_s45_backtest as s45sim
import sim_s46_backtest as s46sim
import sim_s47_backtest as s47sim
import sim_s49_backtest as s49sim
import sim_s51_backtest as s51sim
import sim_s56_backtest as s56sim
import sim_s96_backtest as s96sim

GLOBAL_RAW_TRADES_CACHE = {}
# เก็บ raw trade ที่ simulated circuit breaker (OVERLAY_CFG) ตัดทิ้งไป ต่อ portfolio — ใช้แค่
# สำหรับ "อธิบาย" compare report ว่า mismatch แถวไหนเกิดจาก CB จำลอง ไม่ได้เอาไปแก้ตัวเลข
# P&L ของ backtest หลักเลย (ตามที่พี่ย้ำว่า backtest ต้องไม่ลดลง — ใช้ compare report เพื่อ diagnose
# เท่านั้น ไม่แตะ simulate_equity_substream/OVERLAY_CFG ของจริง)
CB_SKIPPED_TRADES = {}
# path ของ profile จริงที่ connect ล่าสุด (ตั้งใน connect_to_actual_profile_for_portfolio)
# ใช้อ่าน demo_portfolio_state.json (cb_state จริง) มาแปะอธิบายใน compare report
LAST_MATCHED_PROFILE_DIR = None
import pickle
CACHE_FILE = os.path.abspath(os.path.join(os.path.dirname(__file__), "raw_trades_cache.pkl"))
DISK_CACHE_ENABLED = (
    "--no-cache" not in sys.argv
    and "--start" not in sys.argv
    and "--end" not in sys.argv
)

def _cache_key_has_date_scope(k):
    """Return True for cache keys tied to a CLI --start/--end range."""
    if not isinstance(k, tuple):
        return False
    if len(k) == 6:
        return k[4] is not None or k[5] is not None
    if len(k) == 5:
        return k[3] is not None or k[4] is not None
    if len(k) == 4:
        return k[2] is not None or k[3] is not None
    return False

def save_disk_cache():
    if not DISK_CACHE_ENABLED:
        return
    try:
        os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
        # Filter cache: do not save keys with start_str or end_str to disk
        clean_cache = {}
        for k, v in GLOBAL_RAW_TRADES_CACHE.items():
            if not _cache_key_has_date_scope(k):
                clean_cache[k] = v
        with open(CACHE_FILE, "wb") as f:
            pickle.dump(clean_cache, f)
    except Exception as e:
        print(f"⚠️ Failed to save disk cache: {e}")

def load_disk_cache():
    global GLOBAL_RAW_TRADES_CACHE
    if not DISK_CACHE_ENABLED:
        print("Disk cache disabled for this run.")
        return
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "rb") as f:
                GLOBAL_RAW_TRADES_CACHE = pickle.load(f)
            GLOBAL_RAW_TRADES_CACHE = {
                k: v for k, v in GLOBAL_RAW_TRADES_CACHE.items()
                if not _cache_key_has_date_scope(k)
            }
            print(f"Loaded {len(GLOBAL_RAW_TRADES_CACHE)} items from disk cache.")
        except Exception as e:
            print(f"⚠️ Failed to load disk cache: {e}")

load_disk_cache()

# Mapping for standard letters (A-S)
_SIM_MODULES = {
    "A": s31sim, "B": s34sim, "C": s36sim, "D": s37sim, "E": s38sim, "F": s39sim,
    "G": s40sim, "H": s41sim, "I": s42sim, "K": s44sim, "L": s45sim, "M": s46sim,
    "N": s47sim, "P": s49sim, "Q": s51sim, "R": s56sim, "S": s96sim
}

# Single strategy mappings (T-X) to their standalone scripts
SINGLE_STRATEGY_SCRIPTS = {
    "T": ("S101", "sim_s101_backtest.py"),
    "U": ("S102", "sim_s102_backtest.py"),
    "V": ("S105", "sim_s105_backtest.py"),
    "W": ("S106", "sim_s106_backtest.py"),
    "X": ("S111", "sim_s111_backtest.py"),
}

# Recommended starting balance for each portfolio (default to 1000.0 if not specified)
PORTFOLIO_BALANCES = {
    "P13": 1000.0,
    "P16": 1500.0,
    "P18": 2500.0,
    "18-Way": 2500.0,
    "AF22": 1000.0,
    "AF34": 1500.0,
    "AF47": 2000.0,
    "LTS44": 500.0,
    "LTS890": 10000.0,
    "LTS999": 1000.0,
    "LTS_AVENGERS_BASE": 50000.0,
    "LTS_AVENGERS_P34": 100000.0,
    "LTS_AVENGERS_HIGH_RISK": 300000.0,
    "LTS_AVENGERS_ULTRA_SAFE": 5000.0,
    "LTS_AVENGERS_HIGH_FREQ": 8000.0,
    "S101": 2000.0,
    "S102": 2000.0,
    "S105": 2000.0,
    "S106": 2000.0,
    "S111": 2000.0,
}

# Mapping aliases to canonical dp.PORTFOLIOS keys
ALIASES = {
    "18-Way": "P18",
    "LTS_AVB": "LTS_AVENGERS_BASE",
    "LTS_AP34": "LTS_AVENGERS_P34",
    "LTS_AHR": "LTS_AVENGERS_HIGH_RISK",
    "LTS_AUS": "LTS_AVENGERS_ULTRA_SAFE",
    "LTS_AHF": "LTS_AVENGERS_HIGH_FREQ",
}

def is_portfolio_match(p1, p2):
    c1 = ALIASES.get(p1, p1)
    c2 = ALIASES.get(p2, p2)
    return (p1 == p2) or (c1 == c2) or (p1 == c2) or (c1 == p2)

def fetch_bars_range(symbol, tf_str, days, start_str=None, end_str=None, extra_bars=400):
    if start_str:
        def parse_date(s):
            for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
                try:
                    return datetime.strptime(s.strip(), fmt)
                except ValueError:
                    pass
            raise ValueError(f"Time data '{s}' does not match formats YYYY-MM-DD, YYYY-MM-DD HH:MM, or YYYY-MM-DD HH:MM:SS")
            
        start_dt = parse_date(start_str)
        
        import pytz
        bkk = pytz.timezone("Asia/Bangkok")
        start_dt = bkk.localize(start_dt)
        
        if end_str:
            end_dt = parse_date(end_str)
            if len(end_str.strip()) <= 10:
                end_dt = end_dt + timedelta(days=1)
            end_dt = bkk.localize(end_dt)
        else:
            end_dt = datetime.now(bkk)
        
        # Convert tf_str to minutes per bar to calculate start_fetch properly based on extra_bars
        tf_mins = {
            "M1": 1,
            "M5": 5,
            "M15": 15,
            "M30": 30,
            "H1": 60,
            "H4": 240,
            "H8": 480,
            "D1": 1440
        }
        mins_per_bar = tf_mins.get(tf_str, 15)
        # Multiply by 1.5 to account for weekends/non-trading hours
        total_mins_needed = int(extra_bars * mins_per_bar * 1.5)
        start_fetch = start_dt - timedelta(minutes=total_mins_needed)
        
        tf_map = {
            "M1": mt5.TIMEFRAME_M1,
            "M5": mt5.TIMEFRAME_M5,
            "M15": mt5.TIMEFRAME_M15,
            "M30": mt5.TIMEFRAME_M30,
            "H1": mt5.TIMEFRAME_H1
        }
        mt5_tf = tf_map.get(tf_str, mt5.TIMEFRAME_M5)
        rates = mt5.copy_rates_range(symbol, mt5_tf, start_fetch, end_dt)
        return rates
    else:
        return s30sim.fetch_bars(symbol, tf_str, days, extra_bars=extra_bars)

def format_ts_to_bkk(ts):
    if not ts or ts == "-":
        return "-"
    bkk_tz = timezone(timedelta(hours=7))
    return datetime.fromtimestamp(int(ts), tz=timezone.utc).astimezone(bkk_tz).strftime('%d-%m-%Y %H:%M:%S')

COMPARE_COLS = [
    "SIM_Open_Time", "MT5_Open_Time", "SIM_Close_Time", "MT5_Close_Time",
    "SIM_Leg", "SIM_TF", "MT5_TF", "SIM_Type", "MT5_Type", "SIM_Entry", "MT5_Entry",
    "MT5_Close_Price", "SIM_SL", "MT5_SL", "SIM_TP", "MT5_TP", "SIM_Lot",
    "MT5_Volume", "SIM_P&L", "MT5_P&L", "SIM_Balance", "MT5_Balance",
    "MT5_Comment", "MT5_Position_ID", "Matched", "Match_Detail", "SIM_Reason",
    "MT5_Reason", "Sim_point", "MT5_point"
]

def save_compare_and_splits(compare_rows, output_dir, portfolio_name):
    """เซฟ 3 ไฟล์จาก compare_rows ชุดเดียว (ต้องคำนวณ SIM_Balance/MT5_Balance ตามลำดับเวลา
    ของทุกแถวมาก่อนแล้ว):
    - {portfolio}_compare.csv          : เฉพาะ Matched=True เท่านั้น (order ที่ตรงกันจริง)
    - {portfolio}_mt5_not_match.csv     : MT5 มี order แต่ backtest ไม่มีคู่
    - {portfolio}_backtest_not_match.csv: backtest มี trade แต่ MT5 ไม่มีคู่
    แทน split_compare_mismatches.py แบบแยกสคริปต์ — เรียกครั้งเดียวจบในตัว run_backtest_sim.py"""
    matched_rows, mt5_rows, bt_rows = [], [], []
    for row in compare_rows:
        if row.get("Matched") is True:
            matched_rows.append(row)
            continue
        mt5_open = (row.get("MT5_Open_Time") or "")
        sim_open = (row.get("SIM_Open_Time") or "")
        if mt5_open and not sim_open:
            mt5_rows.append(row)
        elif sim_open and not mt5_open:
            bt_rows.append(row)

    compare_path = os.path.join(output_dir, f"{portfolio_name}_compare.csv")
    pd.DataFrame(matched_rows, columns=COMPARE_COLS).to_csv(compare_path, index=False, encoding="utf-8")
    print(f"Saved: {compare_path} ({len(matched_rows)} matched rows)")

    mt5_path = os.path.join(output_dir, f"{portfolio_name}_mt5_not_match.csv")
    pd.DataFrame(mt5_rows, columns=COMPARE_COLS).to_csv(mt5_path, index=False, encoding="utf-8")
    print(f"Saved: {mt5_path} ({len(mt5_rows)} rows)")

    bt_path = os.path.join(output_dir, f"{portfolio_name}_backtest_not_match.csv")
    pd.DataFrame(bt_rows, columns=COMPARE_COLS).to_csv(bt_path, index=False, encoding="utf-8")
    print(f"Saved: {bt_path} ({len(bt_rows)} rows)")

def save_reports(portfolio_name, trades, start_balance, output_dir):
    """คำนวณ Balance และสร้างไฟล์ trades, daily, monthly CSV"""
    os.makedirs(output_dir, exist_ok=True)
    
    # Sort trades chronologically
    trades.sort(key=lambda x: x.get("fill_time_ts", 0))
    
    # 1. Trades CSV
    running_balance = start_balance
    trades_rows = []
    for t in trades:
        pnl = t.get("pnl_usd", 0.0)
        running_balance += pnl
        trades_rows.append({
            "Time (BKK)": format_ts_to_bkk(t.get("fill_time_ts")),
            "Close Time": format_ts_to_bkk(t.get("exit_time_ts")),
            "Leg": t.get("leg", portfolio_name),
            "TF": t.get("tf", "M5"),
            "Type": t.get("signal", ""),
            "Entry": round(t.get("entry", 0.0), 2),
            "SL": round(t.get("sl", 0.0), 2),
            "TP": round(t.get("tp", 0.0), 2),
            "Lot": round(t.get("lot", 0.01), 2),
            "P&L": round(pnl, 2),
            "Balance": round(running_balance, 2),
            "Outcome": t.get("outcome", "")
        })
        
    trades_path = os.path.join(output_dir, f"{portfolio_name}_trades.csv")
    if trades_rows:
        df_trades = pd.DataFrame(trades_rows)
        df_trades.to_csv(trades_path, index=False, encoding="utf-8")
        print(f"Saved: {trades_path} ({len(trades_rows)} trades)")
    else:
        # Create empty placeholder file
        with open(trades_path, "w", newline="", encoding="utf-8") as f:
            f.write("Time (BKK),Close Time,Leg,TF,Type,Entry,SL,TP,Lot,P&L,Balance,Outcome\n")
        print(f"Saved empty placeholder: {trades_path}")
        
    # 2. Daily CSV
    daily_records = []
    if trades_rows:
        df = pd.DataFrame(trades_rows)
        df['date'] = df['Time (BKK)'].apply(lambda x: x.split(" ")[0] if x != "-" else "-")
        # filter out empty dates
        df = df[df['date'] != "-"]
        
        running_daily_balance = start_balance
        for d, grp in df.groupby('date', sort=False):
            tp = (grp['Outcome'] == 'TP').sum()
            sl = (grp['Outcome'] == 'SL').sum()
            net = grp['P&L'].sum()
            running_daily_balance += net
            wr = tp / (tp + sl) * 100 if tp + sl > 0 else 0.0
            daily_records.append({
                "Date": d,
                "Trades": len(grp),
                "Win": tp,
                "Loss": sl,
                "Net Profit": round(net, 2),
                "Win Rate (%)": round(wr, 2),
                "Balance": round(running_daily_balance, 2)
            })
            
    daily_path = os.path.join(output_dir, f"{portfolio_name}_daily.csv")
    if daily_records:
        pd.DataFrame(daily_records).to_csv(daily_path, index=False, encoding="utf-8")
        print(f"Saved: {daily_path}")
    else:
        with open(daily_path, "w", newline="", encoding="utf-8") as f:
            f.write("Date,Trades,Win,Loss,Net Profit,Win Rate (%),Balance\n")
        print(f"Saved empty placeholder: {daily_path}")
        
    # 3. Monthly CSV
    monthly_records = []
    if trades_rows and daily_records:
        df = pd.DataFrame(trades_rows)
        df['month'] = df['Time (BKK)'].apply(lambda x: "-".join(x.split(" ")[0].split("-")[1:][::-1]) if x != "-" else "-")
        df = df[df['month'] != "-"]
        
        running_monthly_balance = start_balance
        for m, grp in df.groupby('month', sort=False):
            tp = (grp['Outcome'] == 'TP').sum()
            sl = (grp['Outcome'] == 'SL').sum()
            net = grp['P&L'].sum()
            running_monthly_balance += net
            wr = tp / (tp + sl) * 100 if tp + sl > 0 else 0.0
            monthly_records.append({
                "Month": m,
                "Trades": len(grp),
                "Win": tp,
                "Loss": sl,
                "Net Profit": round(net, 2),
                "Win Rate (%)": round(wr, 2),
                "Balance": round(running_monthly_balance, 2)
            })
            
    monthly_path = os.path.join(output_dir, f"{portfolio_name}_monthly.csv")
    if monthly_records:
        pd.DataFrame(monthly_records).to_csv(monthly_path, index=False, encoding="utf-8")
        print(f"Saved: {monthly_path}")
    else:
        with open(monthly_path, "w", newline="", encoding="utf-8") as f:
            f.write("Month,Trades,Win,Loss,Net Profit,Win Rate (%),Balance\n")
        print(f"Saved empty placeholder: {monthly_path}")

def run_standard_blend_backtest(portfolio_name, days, spread, start_str=None, end_str=None, scale=1.0):
    """รัน backtest สำหรับ P13, P16, P18 โดยการจำลองแต่ละขาและดึงรายการไม้เทรด"""
    actual_name = ALIASES.get(portfolio_name, portfolio_name)
    keys = dp.PORTFOLIOS[actual_name]
    
    # Fetch price bars
    entry_bars = fetch_bars_range(config.SYMBOL, "M5", days, start_str, end_str, extra_bars=600)
    htf_bars = fetch_bars_range(config.SYMBOL, "M15", days, start_str, end_str, extra_bars=200)
    
    if entry_bars is None or len(entry_bars) == 0:
        print(f"❌ Fetch M5 bars failed for standard blend: {portfolio_name}")
        return []
        
    all_trades = []
    
    global GLOBAL_RAW_TRADES_CACHE
    
    for key in keys:
        if key in _SIM_MODULES:
            label, _, cfg, _, _ = dp._LEG_DEFS[key]
            sim = _SIM_MODULES[key]
            
            cache_key = (f"std_{key}", days, spread, start_str, end_str)
            if cache_key in GLOBAL_RAW_TRADES_CACHE:
                raw = GLOBAL_RAW_TRADES_CACHE[cache_key]
                print(f"Retrieved standard leg {key} ({label}) from cache.")
            else:
                print(f"Simulating standard leg {key} ({label})...")
                # Run simulation on this leg
                if sim == s96sim:
                    raw = sim.run_single(entry_bars, None, cfg, days, spread)
                else:
                    raw = sim.run_single(entry_bars, htf_bars, cfg, days, spread)
                GLOBAL_RAW_TRADES_CACHE[cache_key] = raw
                save_disk_cache()
                
            if sim == s96sim:
                twp = raw
            else:
                twp, eq = s31sim.simulate_equity_substream(raw, cfg, s31sim.START_EQUITY)
            
            for t in twp:
                trade_dict = {
                    "fill_time_ts": t.get("fill_time_ts"),
                    "exit_time_ts": t.get("exit_time_ts"),
                    "signal": t.get("signal"),
                    "entry": t.get("entry"),
                    "sl": t.get("sl"),
                    "tp": t.get("tp"),
                    "lot": t.get("lot", 0.01) * scale,
                    "pnl_usd": t.get("pnl_usd", 0.0) * scale,
                    "outcome": t.get("outcome", ""),
                    "leg": f"{portfolio_name}-{key}",
                    "tf": cfg.get("ENTRY_TF", "M5")
                }
                all_trades.append(trade_dict)
                
        elif key in SINGLE_STRATEGY_SCRIPTS:
            # Standalone single strategy used as part of P18 blend
            name, script = SINGLE_STRATEGY_SCRIPTS[key]
            
            cache_key = (f"script_{key}", days, start_str, end_str)
            if cache_key in GLOBAL_RAW_TRADES_CACHE:
                script_trades = GLOBAL_RAW_TRADES_CACHE[cache_key]
                print(f"Retrieved composite single leg {key} ({name}) from cache.")
                for t in script_trades:
                    scaled_t = dict(t)
                    scaled_t["lot"] = t["lot"] * scale
                    scaled_t["pnl_usd"] = t["pnl_usd"] * scale
                    scaled_t["leg"] = f"{portfolio_name}-{name}"
                    all_trades.append(scaled_t)
            else:
                print(f"Simulating composite single leg {key} ({name}) via script subprocess...")
                temp_prefix = f"temp_blend_{portfolio_name.lower()}_{name.lower()}"
                try:
                    script_path = os.path.join(os.path.dirname(__file__), script)
                    cmd = [sys.executable, script_path]
                    if start_str:
                        cmd.extend(["--start", start_str])
                        if end_str:
                            cmd.extend(["--end", end_str])
                    else:
                        cmd.extend(["--days", str(days)])
                    cmd.extend(["--out-prefix", temp_prefix])
                    
                    subprocess.run(
                        cmd,
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True
                    )
                    temp_csv = f"{temp_prefix}_trades.csv"
                    cached_list = []
                    if os.path.exists(temp_csv):
                        df = pd.read_csv(temp_csv)
                        for _, row in df.iterrows():
                            try:
                                fill_dt = datetime.strptime(row["fill_time"], "%Y-%m-%d %H:%M")
                                fill_ts = int(fill_dt.timestamp())
                                exit_dt = datetime.strptime(row["exit_time"], "%Y-%m-%d %H:%M")
                                exit_ts = int(exit_dt.timestamp())
                            except Exception:
                                fill_ts = 0
                                exit_ts = 0
                                
                            t_dict = {
                                "fill_time_ts": fill_ts,
                                "exit_time_ts": exit_ts,
                                "signal": row["dir"],
                                "entry": row["entry"],
                                "sl": row["sl"],
                                "tp": row["tp"],
                                "lot": 0.01,
                                "pnl_usd": row["profit"],
                                "outcome": row["outcome"],
                                "leg": f"{portfolio_name}-{name}",
                                "tf": "M5"
                            }
                            cached_list.append(t_dict)
                            
                            # Append scaled to all_trades
                            scaled_t = dict(t_dict)
                            scaled_t["lot"] = 0.01 * scale
                            scaled_t["pnl_usd"] = row["profit"] * scale
                            all_trades.append(scaled_t)
                            
                        # Cache the base list
                        GLOBAL_RAW_TRADES_CACHE[cache_key] = cached_list
                        save_disk_cache()
                        
                        # clean up
                        os.remove(temp_csv)
                        daily_temp = f"{temp_prefix}_daily.csv"
                        if os.path.exists(daily_temp):
                            os.remove(daily_temp)
                except Exception as e:
                    print(f"⚠️ Failed to run composite script {script}: {e}")
                
    return all_trades

def run_single_strategy_backtest(portfolio_name, days, start_str=None, end_str=None, scale=1.0):
    """รัน backtest สำหรับ S101, S102, S105, S106, S111 โดยเรียกผ่าน Script Subprocess"""
    leg_key = None
    for k, v in dp._LEG_DEFS.items():
        if v[0].split(" ")[0] == portfolio_name:
            leg_key = k
            break
            
    if not leg_key:
        for k, v in SINGLE_STRATEGY_SCRIPTS.items():
            if v[0] == portfolio_name:
                leg_key = k
                break
                
    if not leg_key or leg_key not in SINGLE_STRATEGY_SCRIPTS:
        print(f"❌ Could not find standalone script for strategy: {portfolio_name}")
        return []
        
    name, script = SINGLE_STRATEGY_SCRIPTS[leg_key]
    print(f"Running standalone script backtest for {portfolio_name} ({script})...")
    
    temp_prefix = f"temp_standalone_{portfolio_name.lower()}"
    trades = []
    try:
        script_path = os.path.join(os.path.dirname(__file__), script)
        cmd = [sys.executable, script_path]
        if start_str:
            cmd.extend(["--start", start_str])
            if end_str:
                cmd.extend(["--end", end_str])
        else:
            cmd.extend(["--days", str(days)])
        cmd.extend(["--out-prefix", temp_prefix])
        
        subprocess.run(cmd, check=True)
        temp_csv = f"{temp_prefix}_trades.csv"
        if os.path.exists(temp_csv):
            df = pd.read_csv(temp_csv)
            for _, row in df.iterrows():
                try:
                    # บาง standalone script (s105/s106/s111) เขียน column ชื่อ "time" แทน
                    # "fill_time" (ต่างจาก s101/s102) — รองรับทั้งสองชื่อกันไม่ให้เวลากลายเป็น 0
                    # แล้วโดนกรองทิ้งหมดทุกเทรด (เจอบั๊กจริง 2026-07-27 ตอนกู้ไฟล์คืน)
                    fill_time_str = row["fill_time"] if "fill_time" in row else row["time"]
                    fill_dt = datetime.strptime(fill_time_str, "%Y-%m-%d %H:%M")
                    fill_ts = int(fill_dt.timestamp())
                    exit_dt = datetime.strptime(row["exit_time"], "%Y-%m-%d %H:%M")
                    exit_ts = int(exit_dt.timestamp())
                except Exception:
                    fill_ts = 0
                    exit_ts = 0
                    
                trades.append({
                    "fill_time_ts": fill_ts,
                    "exit_time_ts": exit_ts,
                    "signal": row["dir"],
                    "entry": row["entry"],
                    "sl": row["sl"],
                    "tp": row["tp"],
                    "lot": 0.01 * scale,
                    "pnl_usd": row["profit"] * scale,
                    "outcome": row["outcome"],
                    "leg": portfolio_name,
                    "tf": "M5"
                })
            # Clean up
            os.remove(temp_csv)
            daily_temp = f"{temp_prefix}_daily.csv"
            if os.path.exists(daily_temp):
                os.remove(daily_temp)
    except Exception as e:
        print(f"❌ Standalone script {script} execution failed: {e}")
        
    return trades

# ดีเลย์ประมวลผลจริงของ live (แท่งปิด -> ดึงบาร์ -> detect pattern -> ส่ง ARM คำสั่ง pending)
# วัดได้จริงจาก log DEMO_PORTFOLIO_PENDING_ARM ~3 วิหลังแท่งปิดเสมอ (เจอเคสจริง 2026-07-22
# leg LTS_AVENGERS_ULTRA_SAFE_910: ราคาแตะระดับ fill แค่วูบเดียวตรงวินาทีแรกที่แท่งเปิด (ก่อน
# ARM ทัน 3 วิ) แล้วร่วงกลับ ไม่เคยแตะอีกเลยตลอดหน้าต่าง 5 แท่ง — backtest แบบเดิมที่เช็คจาก
# high/low ทั้งแท่งนับว่า fill ทั้งที่ live ไม่มีทางทันจริง ทำให้ P&L backtest สูงเกินจริงเป็นระบบ)
LIVE_ARM_DELAY_SEC = 3


def _tick_fill_check(symbol, direction, entry, spread, window_start_ts, window_end_ts):
    """เช็คจาก tick (bid) จริงว่าราคาแตะระดับ fill ไหม ในช่วงเวลาที่ live จะเห็นได้จริงเท่านั้น
    (เริ่มนับหลัง LIVE_ARM_DELAY_SEC ไปแล้ว) คืนค่า epoch ของ tick แรกที่ fill, False ถ้ามี tick
    data ครบแต่ไม่แตะเลย, หรือ None ถ้าไม่มี tick history ให้เช็ค (ต้อง fallback เป็น bar-based)"""
    try:
        start_dt = datetime.fromtimestamp(int(window_start_ts), tz=timezone.utc)
        end_dt = datetime.fromtimestamp(int(window_end_ts), tz=timezone.utc)
        ticks = mt5.copy_ticks_range(symbol, start_dt, end_dt, mt5.COPY_TICKS_ALL)
        if ticks is None or len(ticks) == 0:
            return None
        for t in ticks:
            bid = float(t["bid"])
            if bid <= 0:
                continue
            if direction == "BUY" and bid <= entry - spread:
                return int(t["time"])
            if direction == "SELL" and bid >= entry + spread:
                return int(t["time"])
        return False
    except Exception:
        return None


def run_s9x_generic(bars, detect_fn, tf, cfg, spread, symbol=None, cooldown=5):
    """Simulates standalone S95-S111 (และตระกูล S1xx/S2xx ที่ผ่าน is_s9x) bar-by-bar สำหรับ
    blend backtester — cooldown=5 (แท่ง) เป็น default เดิม ไม่ตรงกับ live (live ใช้
    af_raw_cooldown_active ซึ่ง fallback เป็น MIN_GAP_BARS=1 เพราะ cfg ของ S9x leg ที่สร้างใน
    strategy_lts.py ไม่เคยกำหนด MIN_GAP_BARS ไว้) verify ตรงๆ 2026-08-04: raw detect_s96 บน
    bars จริงให้สัญญาณห่างกันแค่ 1 แท่งบ่อยมาก (เช่น 1785798900->1785799800->1785800700
    ติดกันเป๊ะ) ตรงกับราคา/เวลาที่ live ยิงจริงเป๊ะทุกจุด — cooldown=5 ของ backtest เลยตัดทิ้ง
    ~80% ของสัญญาณที่ live เก็บได้จริง พารามิเตอร์นี้เปิดให้ override เฉพาะจุดเรียกใน
    run_lts_af_backtest (LTS_AVENGERS_ULTRA_SAFE/HIGH_RISK เท่านั้น) ไม่กระทบพอร์ตอื่นที่ยังใช้
    default 5 เดิม"""
    if symbol is None:
        symbol = config.SYMBOL
    trades = []
    n = len(bars)
    lookback = 300
    if n < lookback + 10:
        return []

    last_trade_idx = -100

    for i in range(lookback, n - 2):
        if i - last_trade_idx < cooldown:
            continue
            
        rates_slice = bars[i - lookback + 1: i + 1]
        dt_bkk = config.mt5_ts_to_bkk(int(rates_slice[-1]["time"]))
        
        try:
            # S9X detect_fn expects: bars, tf, dt_bkk, cfg
            res = detect_fn(rates_slice, tf=tf, dt_bkk=dt_bkk, cfg=cfg)
        except TypeError:
            try:
                res = detect_fn(rates_slice, tf=tf, dt_bkk=dt_bkk)
            except Exception:
                continue
        except Exception:
            continue
            
        if not res or res.get("signal") not in ("BUY", "SELL"):
            continue
            
        direction = res["signal"]
        entry = float(res["entry"])
        sl = float(res["sl"])
        tp = float(res["tp"])
        
        risk_distance = abs(entry - sl)
        if risk_distance <= 0:
            continue
            
        # Check fill+outcome ทั้งสองทิศทางแยกกันอิสระ — leg DIRECT ใช้ entry+spread (ราคาขึ้น)
        # ส่วน leg INVERSE ของสัญญาณเดียวกันจะเทรดสวนทาง (BUY<->SELL, สลับ sl/tp) แต่ entry เดิม
        # ซึ่งไลฟ์เช็คเงื่อนไข fill ตาม "ทิศหลัง invert" เอง (ดู strategy_lts.py detect_lts) คือ
        # รอราคา "ลง" ไปแตะ entry-spread แทน — ทิศตรงข้ามกับ DIRECT เป๊ะ (เจอเคสจริง 2026-07-22:
        # leg 910 DIRECT ไม่ fill เพราะราคาไม่ขึ้น แต่ leg 911 INVERSE ของสัญญาณเดียวกัน fill จริง
        # เพราะราคาร่วงลงแรง — ถ้าเช็ค fill แค่ทิศเดียวแล้วแชร์ผลให้ทั้งคู่ จะพัง leg ใดเสมอ)
        window_start_ts = int(bars[i + 1]["time"]) + LIVE_ARM_DELAY_SEC
        window_end_ts = int(bars[min(i + 5, n - 1)]["time"])

        def _resolve(dirn, sl_v, tp_v):
            tick_result = _tick_fill_check(symbol, dirn, entry, spread, window_start_ts, window_end_ts)
            fidx = None
            if tick_result is None:
                for j in range(i + 1, min(i + 6, n)):
                    h, l = float(bars[j]['high']), float(bars[j]['low'])
                    if (dirn == "BUY" and l <= entry - spread) or (dirn == "SELL" and h >= entry + spread):
                        fidx = j
                        break
            elif tick_result is not False:
                fill_ts = tick_result
                for j in range(i + 1, min(i + 6, n)):
                    bar_start = int(bars[j]["time"])
                    bar_end = int(bars[j + 1]["time"]) if j + 1 < n else bar_start + 10 ** 9
                    if bar_start <= fill_ts < bar_end:
                        fidx = j
                        break
                if fidx is None:
                    fidx = min(i + 5, n - 1)
            if fidx is None:
                return None

            outc = None
            exit_p = None
            exit_i = None
            for j in range(fidx, n):
                h, l = float(bars[j]['high']), float(bars[j]['low'])
                if dirn == "BUY":
                    if l <= sl_v:
                        outc, exit_p, exit_i = "SL", sl_v, j
                        break
                    if h >= tp_v:
                        outc, exit_p, exit_i = "TP", tp_v, j
                        break
                else:
                    if h >= sl_v:
                        outc, exit_p, exit_i = "SL", sl_v, j
                        break
                    if l <= tp_v:
                        outc, exit_p, exit_i = "TP", tp_v, j
                        break
            if outc is None or exit_i is None:
                return None

            diff = (exit_p - entry) if dirn == "BUY" else (entry - exit_p)
            pnl = diff - spread
            return {
                "signal": dirn,
                "outcome": outc,
                "signal_time_ts": int(bars[i]["time"]),
                "fill_time_ts": int(bars[fidx]["time"]),
                "exit_time_ts": int(bars[exit_i]["time"]),
                "entry": round(entry, 2),
                "tp": round(tp_v, 2),
                "sl": round(sl_v, 2),
                "exit_price": round(exit_p, 2),
                "risk_distance": round(abs(entry - sl_v), 4),
                "diff_usd_per_001lot": round(pnl, 4),
                "spread": spread,
                "reason": "S9X",
            }

        direct_record = _resolve(direction, sl, tp)
        inverse_direction = "SELL" if direction == "BUY" else "BUY"
        inverse_record = _resolve(inverse_direction, tp, sl)

        if direct_record is None and inverse_record is None:
            continue

        last_trade_idx = i
        if direct_record is not None:
            direct_record["inverse"] = inverse_record
            trades.append(direct_record)
        elif inverse_record is not None:
            # DIRECT ไม่ fill แต่ INVERSE fill — ยังต้องเก็บไว้ให้ leg inverse ใช้ได้
            # (ทำเครื่องหมาย direct=None ไว้ให้ _invert_raw_s9x รู้ว่าไม่มี direct trade จริง)
            trades.append({"signal": None, "inverse": inverse_record, "_direct_only_placeholder": True})

    return trades

def _clean_s9x_direct(raw):
    """เอา trade record ของ run_s9x_generic มาใช้ในทาง DIRECT — ตัด placeholder ที่มีแต่
    inverse fill (signal=None, ไม่มี direct trade จริง) ทิ้ง และลบ field 'inverse' ที่แนบมา"""
    out = []
    for t in raw:
        if t.get("_direct_only_placeholder"):
            continue
        clean = {k: v for k, v in t.items() if k != "inverse"}
        out.append(clean)
    return out


def _invert_raw_s9x(raw):
    """เอา trade record ของ run_s9x_generic มาใช้ในทาง INVERSE — ใช้ผล fill/outcome ที่คำนวณ
    แยกอิสระไว้แล้วในฟิลด์ 'inverse' (เพราะทิศ fill ของ inverse ตรงข้ามกับ direct เป๊ะ ไม่ใช่แค่
    กลับ signal/sl/tp ของ direct trade เฉยๆ — ดู docstring ใน run_s9x_generic) ข้ามรายการที่
    inverse ไม่ fill เลย"""
    out = []
    for t in raw:
        inv = t.get("inverse")
        if inv is None:
            continue
        out.append(inv)
    return out


# ── ทำไมมีฟังก์ชันนี้แยกจาก ambfix_sweep2._post_filter_raw ──────────────────────────
# _post_filter_raw ตัวจริง (ambfix_sweep2.py) เช็ค hour filter จาก trade["fill_time_ts"]
# (เวลาที่ order เข้าจริง = แท่งถัดจาก signal) แต่ live (apply_af_filters ใน strategy_af.py)
# เช็ค hour จาก entry_ts ที่เป็นเวลา "แท่ง signal" ตรงๆ — สำหรับ M30/H1 ที่ signal เกิดใกล้ขอบ
# ชั่วโมง (เช่น signal 16:30 → fill 17:00) จะทำให้ hour bucket เพี้ยนไป 1 ชม. จาก signal จริง
# (เจอจริง 2026-07-31: leg S84c5505/c6017/c4369 RD5.0-7.0_H16 — sim ตัดทิ้งเพราะ fill_time_ts
# ตกที่ hour=17 ทั้งที่ signal จริงเกิด hour=16 ตรง H16 พอดี ทำให้ live ยิง order จริงแต่ sim ไม่เจอ)
# แก้เฉพาะจุดนี้ ไม่แตะ ambfix_sweep2._post_filter_raw ตัวจริง (ไฟล์กลางที่พอร์ตอื่น/sweep tool
# ใช้ร่วมกัน) เพื่อไม่ให้กระทบผล backtest ของพอร์ตอื่นเลย — ใช้ฟังก์ชันนี้เฉพาะ
# LTS_AVENGERS_ULTRA_SAFE/HIGH_RISK เท่านั้น (ดูจุดเรียกใน run_lts_af_backtest)
LTS_AUS_AHR_SETUP_PROFILE_DIR = None
_LTS_AUS_AHR_SERVER_TZ_HISTORY_CACHE = None  # (profile_dir, history_dict)
_LTS_AUS_AHR_LOG_HOUR_GROUND_TRUTH_CACHE = None  # (profile_dir, {entry_ts: hour})

_LOG_BAR_SNAPSHOT_RE = re.compile(r"DEMO_PORTFOLIO_BAR_SNAPSHOT \| (\S+) raw_signal=\S+ entry_ts=(\d+)")
_LOG_SKIP_HOUR_RE = re.compile(r"DEMO_PORTFOLIO_SKIP \| (\S+) skipped - hour (\d+) !=")
_LOG_SIGNAL_HOUR_RE = re.compile(r"DEMO_PORTFOLIO_SIGNAL \| (\S+) .*? h=(\d+)")


def _load_lts_aus_ahr_log_hour_ground_truth():
    """Parse bot.log ของโปรไฟล์ที่ตรงกับ portfolio นี้จริง (Exness สำหรับ LTS_AUS, IUX สำหรับ
    LTS_AHR) เพื่อดึง "hour ที่ live daemon คำนวณจริง ณ ตอนนั้น" ต่อ entry_ts ต่อสัญญาณ — วิธีนี้
    เท่านั้นที่แม่น 100% เพราะ MT5_SERVER_TZ ของโบรกเกอร์นี้ขยับได้แม้ภายในวันเดียวกัน (เจอจริง
    2026-08-03: server clock ของ Exness ขยับจาก -1 เป็น 0 ภายในไม่กี่ชม. ระหว่างที่กำลัง debug
    เรื่องนี้อยู่ — ยืนยันด้วยการเทียบเวลาบนหน้าจอ MT5 ตรงๆ) ทำให้ "ค่า offset เดียวทั้ง run" ไม่ว่า
    จะมาจาก tick สด ณ ตอนรัน backtest หรือจาก mt5_server_tz_history.json (debounce ล่าช้า) ก็ผิด
    ได้เสมอสำหรับบางช่วงของวัน อ่าน log ตรงๆ จึงถูกต้องเสมอ เพราะเป็นค่าที่ live คำนวณไว้จริง ณ
    วินาทีนั้นเป๊ะ ไม่ต้องเดา — ใช้ได้เฉพาะช่วงที่มี DEMO_PORTFOLIO_BAR_SNAPSHOT log แล้วเท่านั้น
    (เริ่มบันทึกตั้งแต่ 2026-07-31) ก่อนหน้านั้น fallback ไปที่ history file/default ตามเดิม
    ขอบเขต: ใช้เฉพาะ LTS_AUS/LTS_AHR ผ่าน _post_filter_raw_signal_hour"""
    global _LTS_AUS_AHR_LOG_HOUR_GROUND_TRUTH_CACHE
    profile_dir = LTS_AUS_AHR_SETUP_PROFILE_DIR
    if (_LTS_AUS_AHR_LOG_HOUR_GROUND_TRUTH_CACHE is not None
            and _LTS_AUS_AHR_LOG_HOUR_GROUND_TRUTH_CACHE[0] == profile_dir):
        return _LTS_AUS_AHR_LOG_HOUR_GROUND_TRUTH_CACHE[1]

    mapping = {}
    if profile_dir:
        log_path = os.path.join(profile_dir, "logs", "bot.log")
        try:
            pending_entry_ts_by_leg = {}
            with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    if "DEMO_PORTFOLIO_BAR_SNAPSHOT" in line:
                        m = _LOG_BAR_SNAPSHOT_RE.search(line)
                        if m:
                            pending_entry_ts_by_leg[m.group(1)] = int(m.group(2))
                        continue
                    if "DEMO_PORTFOLIO_SKIP" in line:
                        m = _LOG_SKIP_HOUR_RE.search(line)
                        if m:
                            leg_id, hour = m.group(1), int(m.group(2))
                            entry_ts = pending_entry_ts_by_leg.get(leg_id)
                            if entry_ts is not None:
                                mapping[entry_ts] = hour
                        continue
                    if "DEMO_PORTFOLIO_SIGNAL" in line:
                        m = _LOG_SIGNAL_HOUR_RE.search(line)
                        if m:
                            leg_id, hour = m.group(1), int(m.group(2))
                            entry_ts = pending_entry_ts_by_leg.get(leg_id)
                            if entry_ts is not None:
                                mapping[entry_ts] = hour
        except Exception:
            mapping = {}
    _LTS_AUS_AHR_LOG_HOUR_GROUND_TRUTH_CACHE = (profile_dir, mapping)
    return mapping


def _derive_latest_server_tz_from_log():
    """ย้อนคำนวณ MT5_SERVER_TZ จาก entry_ts->hour ล่าสุดใน log ground truth (ดู
    _load_lts_aus_ahr_log_hour_ground_truth) — ใช้สำหรับกรอง trade ตามช่วง --start/--end
    (ดู _true_utc_fill_ts) ซึ่งมักอ้างอิงเวลาใกล้ "ตอนนี้" อยู่แล้ว server_tz ล่าสุดที่ log จริง
    บันทึกไว้จึงแม่นกว่า mt5_server_tz_history.json ที่มี debounce ล่าช้าหลายนาที (เจอจริง
    2026-08-04: history file ของ IUX ยังค้างที่ 0 จากหลายวันก่อน ทั้งที่ log ล่าสุดยืนยัน server_tz
    จริงตอนนี้ = +1 ทำให้ trade ใกล้ขอบ --end โดนกรองผิดถ้าใช้ history file เฉยๆ)
    สูตร: naive_hour (สมมติ server_tz=0) - live_hour ที่บันทึกจริง = server_tz (ปรับ wraparound
    ข้ามเที่ยงคืน ±24 ชม.)"""
    mapping = _load_lts_aus_ahr_log_hour_ground_truth()
    if not mapping:
        return None
    latest_ts = max(mapping.keys())
    live_hour = mapping[latest_ts]
    naive_hour = (datetime.fromtimestamp(latest_ts, tz=timezone.utc) + timedelta(hours=config.TZ_OFFSET)).hour
    diff = naive_hour - live_hour
    if diff > 12:
        diff -= 24
    elif diff < -12:
        diff += 24
    return diff


def _load_lts_aus_ahr_server_tz_history():
    """โหลด mt5_server_tz_history.json ของโปรไฟล์ที่ตรงกับ portfolio นี้จริง — ใช้เป็น fallback
    รอง เมื่อ _load_lts_aus_ahr_log_hour_ground_truth ไม่มีข้อมูลของช่วงเวลานั้น (เช่น ก่อน
    2026-07-31 ที่ยังไม่มี BAR_SNAPSHOT log)"""
    global _LTS_AUS_AHR_SERVER_TZ_HISTORY_CACHE
    profile_dir = LTS_AUS_AHR_SETUP_PROFILE_DIR
    if _LTS_AUS_AHR_SERVER_TZ_HISTORY_CACHE is not None and _LTS_AUS_AHR_SERVER_TZ_HISTORY_CACHE[0] == profile_dir:
        return _LTS_AUS_AHR_SERVER_TZ_HISTORY_CACHE[1]
    history = {}
    if profile_dir:
        hist_path = os.path.join(profile_dir, "mt5_server_tz_history.json")
        try:
            with open(hist_path, "r", encoding="utf-8") as f:
                history = {str(k): int(v) for k, v in json.load(f).items()}
        except Exception:
            history = {}
    _LTS_AUS_AHR_SERVER_TZ_HISTORY_CACHE = (profile_dir, history)
    return history


def _bkk_hour_server_tz_aware(ts_int):
    """แปลง MT5 server timestamp -> ชั่วโมง Bangkok แบบเดียวกับที่ live คำนวณจริง
    (config.mt5_ts_to_bkk ตอน IN_BACKTEST=True จะข้ามการปรับ MT5_SERVER_TZ ไปเลย ใช้แค่
    +TZ_OFFSET ตรงๆ) ทำให้ backtest กับ live คำนวณชั่วโมงของแท่งเดียวกันต่างกันได้เต็มๆ 1 ชั่วโมง
    ทุกครั้งที่ broker server clock เพี้ยนไปจาก 0 (เจอจริง 2026-08-03: signal เดียวกันเป๊ะ sim
    บอก hour 10 แต่ live บอก hour 11) — ลอง fix ด้วย offset เดียวทั้ง run มาสองรอบ (tick สด /
    history file) แต่พบว่า MT5_SERVER_TZ ของโบรกเกอร์นี้ขยับได้แม้ภายในวันเดียวกัน ทำให้ offset
    เดียวไม่พอสำหรับ window ที่ยาวหลายชั่วโมง จึงเปลี่ยนมาอ่าน hour ที่ live คำนวณจริงต่อสัญญาณ
    ตรงๆ จาก bot.log (ดู _load_lts_aus_ahr_log_hour_ground_truth) แม่นที่สุดเพราะไม่ต้องเดา
    offset เลย — ถ้าไม่มี log ของช่วงนั้น (ก่อน 2026-07-31) fallback ไปที่ server_tz history file
    แล้วค่อย default สุดท้าย ขอบเขต: ใช้เฉพาะ LTS_AUS/LTS_AHR ผ่าน _post_filter_raw_signal_hour"""
    ts_int = int(ts_int)
    ground_truth = _load_lts_aus_ahr_log_hour_ground_truth()
    if ts_int in ground_truth:
        return ground_truth[ts_int]

    history = _load_lts_aus_ahr_server_tz_history()
    utc_dt = datetime.fromtimestamp(ts_int, tz=timezone.utc)
    date_key = utc_dt.strftime("%Y-%m-%d")
    server_tz = config.MT5_SERVER_TZ
    for k in sorted(history.keys(), reverse=True):
        if k <= date_key:
            server_tz = history[k]
            break
    return (utc_dt + timedelta(hours=config.TZ_OFFSET - server_tz)).hour


def _post_filter_raw_signal_hour(raw, rd_band, fill_hour):
    out = []
    rd_min, rd_max = 0.0, 0.0
    if rd_band != "all":
        parts = rd_band.split("-")
        rd_min, rd_max = float(parts[0]), float(parts[1])
    for trade in raw:
        if rd_band != "all":
            rd = float(trade.get("risk_distance", 0.0))
            if rd < rd_min or rd > rd_max:
                continue
        if fill_hour is not None and fill_hour >= 0:
            hour = _bkk_hour_server_tz_aware(int(trade["signal_time_ts"]))
            if hour != fill_hour:
                continue
        out.append(trade)
    return out


_LTS_AUS_AHR_EXIT_OVERLAY_BARS_CACHE = {}  # (tf, days, start_str, end_str) -> (bars, closes, highs, lows, ema20, ema50, ts_to_idx)
_LTS_AUS_AHR_EXIT_OVERLAY_TRADE_CACHE = {}  # (tf, days, start_str, end_str, fill_ts, direction, entry, exit_ts) -> triggered or None


def _ewm_series(values, span):
    """ewm(span=X, adjust=False) เวอร์ชัน pure-python — สูตรเดียวกับ pandas.Series.ewm ที่ live
    ใช้จริงใน demo_portfolio.py (_check_lts_position_exits) alpha = 2/(span+1)"""
    if not values:
        return []
    alpha = 2.0 / (span + 1.0)
    out = [float(values[0])]
    for i in range(1, len(values)):
        out.append(alpha * float(values[i]) + (1 - alpha) * out[-1])
    return out


def _apply_lts_exit_overlay(trades, tf, portfolio_name, days, start_str, end_str):
    """จำลอง Smart Cut-loss + Momentum Stall Exit (live-only overlay ที่ปิดไม้ก่อนถึง SL/TP
    เดิม) ให้ backtest — ตรรกะ COPY ตรงจาก demo_portfolio.py:_check_lts_position_exits (ที่ live
    ใช้จริง) ไม่ใช่เดา:
      Smart Cut-loss ต่อแท่งปิด: BUY เช็ค close<ema50 และ ema20<ema50 (Death Cross),
      SELL เช็ค close>ema50 และ ema20>ema50 (Golden Cross) — EMA20/50 จาก close ของ TF เดียวกับ
      leg นั้น (ewm span=20/50, adjust=False)
      Momentum Stall (เช็คถ้า Smart Cut-loss ไม่ทำงานก่อน): กำไร >= 150 pts (mult=100 สำหรับ
      XAUUSD) แล้ว 5 แท่งก่อนหน้าไม่ทำ high/low ใหม่

    เจอจริง 2026-08-04: ticket 568028532 (leg S96 M15) ปิดจริงด้วย Smart Cut-loss ที่ -244 USD
    ไม่ใช่ SL/TP เดิมเลย — backtest เดิมไม่จำลองส่วนนี้เลยทำให้ order แทบทุกตัวที่โดนกลไกนี้ไม่ match
    กับ live (ยืนยันด้วย log: SMART_CUTLOSS 14 + MOMENTUM_STALL 25 ครั้งใน AHR, 22+28 ใน AUS —
    ใกล้เคียงจำนวน order ไม่ match ทั้งหมดที่เจอมาตลอดเซสชัน)

    ข้อจำกัด: EMA คำนวณต่อเนื่องทั้งช่วง bars ที่ fetch มา (ไม่ใช่ re-window 60 แท่งล่าสุดทุกครั้ง
    แบบ live) — หลัง warmup ~30 แท่งค่าจะลู่เข้าใกล้กันมาก ความต่างเล็กน้อยที่ขอบเป็นข้อจำกัดที่
    ยอมรับได้ของการประมาณ ราคาที่ปิดใช้ close ของแท่งที่ trigger (live ปิดที่ market ไม่กี่วินาที
    หลังจากนั้น ราคาจริงอาจต่างจากนี้เล็กน้อย)

    ขอบเขต: เรียกเฉพาะ LTS_AUS/LTS_AHR จาก run_lts_af_backtest เท่านั้น — cache 2 ชั้น (bars/EMA
    ต่อ tf, และผลลัพธ์ต่อ trade จริง) เพราะ leg หลายร้อยตัวใน unique_base เดียวกัน (เช่น RD-band
    ต่างกัน) มักได้ raw trade ชุดเดียวกันมาเรียกซ้ำ — ไม่ cache จะ walk-forward bar-by-bar ซ้ำ
    เดิมหลายสิบ-หลายร้อยรอบต่อ trade จริง 1 ตัว (เจอจริง 2026-08-04: ทำให้รัน 550 วันช้าลงมาก)"""
    smart_cut_on = config.SMART_CUTLOSS_ENABLED.get(portfolio_name, False)
    mom_stall_on = config.MOMENTUM_STALL_EXIT_ENABLED.get(portfolio_name, False)
    if not smart_cut_on and not mom_stall_on:
        return trades
    if not trades:
        return trades

    bars_key = (tf, days, start_str, end_str)
    cached = _LTS_AUS_AHR_EXIT_OVERLAY_BARS_CACHE.get(bars_key)
    if cached is None:
        bars = fetch_bars_range(config.SYMBOL, tf, days, start_str, end_str, extra_bars=700)
        if bars is None or len(bars) < 60:
            cached = ()
        else:
            closes = [float(b["close"]) for b in bars]
            highs = [float(b["high"]) for b in bars]
            lows = [float(b["low"]) for b in bars]
            ema20 = _ewm_series(closes, 20)
            ema50 = _ewm_series(closes, 50)
            ts_to_idx = {int(b["time"]): i for i, b in enumerate(bars)}
            cached = (bars, closes, highs, lows, ema20, ema50, ts_to_idx)
        _LTS_AUS_AHR_EXIT_OVERLAY_BARS_CACHE[bars_key] = cached
    if not cached:
        return trades
    bars, closes, highs, lows, ema20, ema50, ts_to_idx = cached
    n = len(bars)
    mult = 100.0  # XAUUSD points (เหมือน demo_portfolio.py:_check_lts_position_exits)

    out = []
    for t in trades:
        direction = t.get("signal")
        fill_ts = t.get("fill_time_ts")
        exit_ts = t.get("exit_time_ts")
        entry = t.get("entry")
        if direction not in ("BUY", "SELL") or fill_ts is None or entry is None:
            out.append(t)
            continue
        fill_idx = ts_to_idx.get(int(fill_ts))
        if fill_idx is None or fill_idx < 55:
            out.append(t)
            continue

        entry = float(entry)
        trade_key = bars_key + (int(fill_ts), direction, round(entry, 4),
                                 int(exit_ts) if exit_ts is not None else None)
        if trade_key in _LTS_AUS_AHR_EXIT_OVERLAY_TRADE_CACHE:
            triggered = _LTS_AUS_AHR_EXIT_OVERLAY_TRADE_CACHE[trade_key]
        else:
            triggered = None
            for j in range(fill_idx + 1, n):
                bar_ts = int(bars[j]["time"])
                if exit_ts is not None and bar_ts > int(exit_ts):
                    break
                closed_price = closes[j]
                if smart_cut_on:
                    e20, e50 = ema20[j], ema50[j]
                    if direction == "BUY" and closed_price < e50 and e20 < e50:
                        triggered = (bar_ts, closed_price)
                        break
                    if direction == "SELL" and closed_price > e50 and e20 > e50:
                        triggered = (bar_ts, closed_price)
                        break
                if mom_stall_on and j >= fill_idx + 5:
                    profit_points = (closed_price - entry) * mult
                    if direction == "SELL":
                        profit_points = -profit_points
                    if profit_points >= 150:
                        recent_highs = highs[j - 5:j]
                        recent_lows = lows[j - 5:j]
                        is_stalled = (
                            closed_price < max(recent_highs) if direction == "BUY"
                            else closed_price > min(recent_lows)
                        )
                        if is_stalled:
                            triggered = (bar_ts, closed_price)
                            break
            _LTS_AUS_AHR_EXIT_OVERLAY_TRADE_CACHE[trade_key] = triggered

        if triggered is None:
            out.append(t)
            continue

        exit_bar_ts, exit_price = triggered
        spread = float(t.get("spread", 0.0))
        diff = (exit_price - entry) if direction == "BUY" else (entry - exit_price)
        new_t = dict(t)
        new_t["exit_time_ts"] = exit_bar_ts
        new_t["exit_price"] = round(exit_price, 2)
        new_t["outcome"] = "SMART_EXIT"
        new_t["diff_usd_per_001lot"] = round(diff - spread, 4)
        out.append(new_t)
    return out


def _apply_aggregate_exposure_cap_scoped(trades, aggregate_cap=100.0):
    """จำลอง SYMBOL_VOLUME_LIMIT (aggregate exposure รวมทุก position ที่เปิดพร้อมกันในทิศทาง
    เดียวกัน ห้ามเกิน cap) ที่ broker บังคับจริง — เดินเวลาไปตามลำดับ entry/exit จริงของทุก trade
    รวมกัน ถ้า trade ไหนเปิดแล้วจะดันยอดรวมทิศทางเดียวกันเกิน cap ให้ reject ทิ้งทั้งไม้ (ยืนยันจาก
    log จริง — broker ปฏิเสธทั้งไม้ ไม่ partial fill) เรียกใช้เฉพาะ AUS/AHR เท่านั้น (ดู
    run_lts_af_backtest) พอร์ตอื่นไม่กระทบ"""
    events = []
    for i, t in enumerate(trades):
        fill_ts = t.get("fill_time_ts")
        exit_ts = t.get("exit_time_ts")
        if fill_ts is None or exit_ts is None:
            continue
        events.append((int(fill_ts), 1, i))
        events.append((int(exit_ts), 0, i))
    events.sort(key=lambda e: (e[0], e[1]))  # exits (kind=0) ก่อน entries (kind=1) เวลาเดียวกัน

    buy_exposure = 0.0
    sell_exposure = 0.0
    accepted = [False] * len(trades)
    open_lot = [0.0] * len(trades)

    for _ts, kind, i in events:
        t = trades[i]
        direction = t.get("signal")
        lot = float(t.get("lot", 0.0))
        if kind == 0:
            if accepted[i]:
                if direction == "BUY":
                    buy_exposure -= open_lot[i]
                else:
                    sell_exposure -= open_lot[i]
        else:
            if direction == "BUY":
                if buy_exposure + lot <= aggregate_cap:
                    buy_exposure += lot
                    accepted[i] = True
                    open_lot[i] = lot
            elif direction == "SELL":
                if sell_exposure + lot <= aggregate_cap:
                    sell_exposure += lot
                    accepted[i] = True
                    open_lot[i] = lot

    return [t for i, t in enumerate(trades) if accepted[i]]


def run_lts_af_backtest(portfolio_name, days, start_str=None, end_str=None, scale=1.0):
    """รัน backtest สำหรับ AF และ LTS portfolios โดยจำลอง S84/S86 แต่ละตัวและผสมตาม Weight"""
    actual_name = ALIASES.get(portfolio_name, portfolio_name)
    keys = dp.PORTFOLIOS[actual_name]
    
    legs = []
    for k in keys:
        if k in dp.AF_DEFS:
            legs.append(dp.AF_DEFS[k])
            
    if not legs:
        print(f"❌ No valid legs found in AF_DEFS for portfolio: {portfolio_name}")
        return []

    if actual_name in ("LTS_AVENGERS_ULTRA_SAFE", "LTS_AVENGERS_HIGH_RISK", "LTS44"):
        # เจอจริง 2026-08-05: ไฟล์ weight ต้นฉบับ (lts_avengers_*_weights.txt) มี leg สัญญาณ
        # เดียวกัน (family/cfg_idx/tf/mode/rd_band/hour เหมือนกันเป๊ะ) ซ้ำกันหลายสิบครั้ง (ตัวแย่
        # สุดซ้ำ 66 ครั้ง) จากบั๊กใน pipeline สร้าง ladder เดิม (lts_auto_ladder_log.md ไม่มี
        # exclusion check ตอนเลือก leg ถัดไป) — dedupe ตรงนี้ในหน่วยความจำ (ไม่แก้ไฟล์ weight จริง)
        # รวม leg signature เดียวกันเป็น 1 leg บวก weight เข้าด้วยกัน (LTS44 เช็คแล้วไม่มี leg ซ้ำ
        # อยู่แล้ว 2026-08-07 — ใส่ไว้เผื่ออนาคต ไม่กระทบผลลัพธ์ปัจจุบัน)
        _n_before = len(legs)
        _merged = {}
        for leg in legs:
            sig = (leg["family"], leg["cfg_idx"], leg["cfg"]["ENTRY_TF"], leg.get("mode"),
                   leg.get("rd_min"), leg.get("rd_max"), leg.get("hour"))
            if sig in _merged:
                _merged[sig]["weight"] += leg["weight"]
            else:
                _merged[sig] = dict(leg)
        legs = list(_merged.values())
        print(f"   [dedup] {portfolio_name}: {_n_before} legs -> {len(legs)} unique (duplicate signatures merged, weight summed)")

    print(f"Simulating {len(legs)} legs for {portfolio_name}...")
    
    global GLOBAL_RAW_TRADES_CACHE
    unique_bases = set((leg["family"], leg["cfg_idx"], leg["cfg"]["ENTRY_TF"]) for leg in legs)
    
    # 1. Fetch bars and cache raw trades for unique base configs
    from optimize_s88_allin4s_fast import _make_s84, _make_s86, _grid_s84, _grid_s86, TF_EXTRA_BARS

    _ub_total = len(unique_bases)
    for _ub_i, (fam, cfg_idx, tf) in enumerate(sorted(unique_bases), 1):
        cache_key = (fam, cfg_idx, tf, days, start_str, end_str)
        if cache_key in GLOBAL_RAW_TRADES_CACHE:
            print(f"  [{_ub_i}/{_ub_total}] {fam}c{cfg_idx} {tf} (cached, skip)", flush=True)
            continue
        print(f"  [{_ub_i}/{_ub_total}] {fam}c{cfg_idx} {tf} — fetching bars & detecting...", flush=True)

        # Find if any leg matching (fam, cfg_idx, tf) is is_s9x
        leg = next((l for l in legs if l["family"] == fam and l["cfg_idx"] == cfg_idx and l["cfg"]["ENTRY_TF"] == tf), None)
        is_s9x = leg.get("is_s9x", False) if leg else False
        
        if is_s9x:
            detect_fn = leg["detect_fn"]
            cfg = leg["cfg"]
            
            bars = fetch_bars_range(config.SYMBOL, tf, days, start_str, end_str, extra_bars=700)
            if bars is None or len(bars) == 0:
                print(f"❌ Failed to fetch {tf} bars for standalone leg {fam}")
                GLOBAL_RAW_TRADES_CACHE[cache_key] = []
                save_disk_cache()
                continue
                
            raw = run_s9x_generic(bars, detect_fn, tf, cfg, DEFAULT_SPREAD)
            GLOBAL_RAW_TRADES_CACHE[cache_key] = raw
            save_disk_cache()
            continue
            
        grid = _grid_s84("micro") if fam == "s84" else _grid_s86("micro")
        all_vals = list(itertools.product(*grid))
        cfg_vals = all_vals[cfg_idx]
        
        maker = _make_s84 if fam == "s84" else _make_s86
        runner = run_s84 if fam == "s84" else run_s86
        cfg = maker(cfg_vals)
        
        bars = fetch_bars_range(config.SYMBOL, tf, days, start_str, end_str, extra_bars=TF_EXTRA_BARS.get(tf, 700))
        if bars is None or len(bars) == 0:
            print(f"❌ Failed to fetch {tf} bars for base config {fam}c{cfg_idx}")
            GLOBAL_RAW_TRADES_CACHE[cache_key] = []
            save_disk_cache()
            continue
            
        run_cfg = dict(cfg)
        run_cfg["_ATR14"] = _atr_series(bars, 14)
        run_cfg["_DT_BKK"] = [config.mt5_ts_to_bkk(int(b["time"])) for b in bars]
        
        raw = runner(bars, run_cfg, days, DEFAULT_SPREAD)
        GLOBAL_RAW_TRADES_CACHE[cache_key] = raw
        save_disk_cache()
        
    # 2. Filter, Invert, Scale and Combine trades
    all_portfolio_trades = []
    CB_SKIPPED_TRADES[portfolio_name] = []
    for leg in legs:
        cache_key = (leg["family"], leg["cfg_idx"], leg["cfg"]["ENTRY_TF"], days, start_str, end_str)
        raw = GLOBAL_RAW_TRADES_CACHE.get(cache_key)
        if not raw:
            continue
            
        rd_min = leg.get("rd_min")
        rd_max = leg.get("rd_max")
        rd_band = "all" if (rd_min is None or rd_max is None) else f"{rd_min:.1f}-{rd_max:.1f}"
        if actual_name in ("LTS_AVENGERS_ULTRA_SAFE", "LTS_AVENGERS_HIGH_RISK"):
            filtered_raw = _post_filter_raw_signal_hour(raw, rd_band, leg.get("hour"))
        else:
            filtered_raw = _post_filter_raw(raw, rd_band, leg.get("hour"))
        if leg.get("is_s9x"):
            # run_s9x_generic คำนวณ fill/outcome ของ direct กับ inverse แยกอิสระต่อกันไว้แล้ว
            # (ทิศ fill ตรงข้ามกันจริง ไม่ใช่แค่กลับเครื่องหมาย) ห้ามใช้ _invert_raw ทั่วไป
            if leg.get("mode") == "inverse":
                filtered_raw = _invert_raw_s9x(filtered_raw)
            else:
                filtered_raw = _clean_s9x_direct(filtered_raw)
        elif leg.get("mode") == "inverse":
            filtered_raw = _invert_raw(filtered_raw)

        # Determine TF (ย้ายขึ้นมาก่อน _simulate_leg เพื่อใช้ fetch bars สำหรับ exit overlay)
        if leg.get("is_s9x"):
            tf = leg["cfg"]["ENTRY_TF"]
        else:
            maker = _make_s84 if leg["family"] == "s84" else _make_s86
            grid = _grid_s84("micro") if leg["family"] == "s84" else _grid_s86("micro")
            all_vals = list(itertools.product(*grid))
            cfg_vals = all_vals[leg["cfg_idx"]]
            tf = maker(cfg_vals)["ENTRY_TF"]

        if actual_name in ("LTS_AVENGERS_ULTRA_SAFE", "LTS_AVENGERS_HIGH_RISK"):
            filtered_raw = _apply_lts_exit_overlay(filtered_raw, tf, actual_name, days, start_str, end_str)

        _twp, _eq, by_day = _simulate_leg(filtered_raw, OVERLAY_CFG)

        # เก็บ raw trade ที่ simulated circuit breaker (OVERLAY_CFG) ตัดทิ้งไป — ไม่กระทบ
        # _twp/all_portfolio_trades ที่ใช้คำนวณ P&L จริงเลย ใช้แค่ diagnose ใน compare report
        if OVERLAY_CFG.get("DD_CONTROL") == "circuit_breaker":
            _twp_ts = {int(x["fill_time_ts"]) for x in _twp}
            for rt in filtered_raw:
                if int(rt["fill_time_ts"]) not in _twp_ts:
                    CB_SKIPPED_TRADES[portfolio_name].append({
                        "leg_key": leg["key"],
                        "fill_time_ts": int(rt["fill_time_ts"]),
                        "signal": rt.get("signal"),
                        "entry": rt.get("entry"),
                    })

        # เจอจริง 2026-08-05: สูตรเดิม (lot/pnl_usd จาก _twp คูณ leg["weight"] ซ้ำอีกชั้น) เอา $
        # pnl ที่ sim_s31_backtest คำนวณมาจาก equity substream ที่ทบต้นอยู่แล้ว (START_EQUITY=1000)
        # ไปคูณด้วย weight (หลักร้อย-หลักหมื่น) ซ้ำอีกที ทำให้ backtest ได้ P&L หลักสิบล้าน ทั้งที่
        # live เทรดจริงไม่มีทางเป็นแบบนี้ — live (demo_portfolio.py:_af_order_volume) คำนวณ lot จาก
        # MIN_LOT(0.01) คงที่ x weight x scale เท่านั้น ไม่เคยทบต้น เปลี่ยนตรงนี้ให้ตรงกับ live จริง
        # (ใช้ diff_usd_per_001lot/spread ดิบจาก raw signal แทน lot/pnl_usd ที่ผ่าน compounding sim
        # มาแล้ว) — scope เฉพาะ AUS/AHR/LTS44 (2026-08-07 เพิ่ม LTS44 เข้ามาด้วย เจอ weight สูงถึง
        # 690 ต่อ leg ติดบั๊กเดียวกันแม้ไม่มี leg ซ้ำ) พอร์ตอื่นพฤติกรรมเดิมทุกอย่าง
        use_fixed_lot = actual_name in ("LTS_AVENGERS_ULTRA_SAFE", "LTS_AVENGERS_HIGH_RISK", "LTS44")
        if use_fixed_lot:
            base_raw = 0.01  # MIN_LOT คงที่ ไม่ทบต้น (Phase 3/dynamic lot ไม่มีผลต่อ backtest อยู่แล้ว)
            real_cap = config.DEMO_PORTFOLIO_AF_MAX_LOT.get(actual_name, 0.0) or 20.0
            fixed_lot = max(0.01, min(base_raw * leg["weight"] * scale, real_cap))
            fixed_lot_001_units = fixed_lot / 0.01

        for t in _twp:
            if use_fixed_lot:
                spread = float(t.get("spread", 0.0))
                diff = float(t.get("diff_usd_per_001lot", 0.0))
                lot_val = fixed_lot
                pnl_val = (diff - spread) * fixed_lot_001_units
            else:
                lot_val = t.get("lot", 0.01) * leg["weight"] * scale
                pnl_val = t.get("pnl_usd", 0.0) * leg["weight"] * scale
            t_scaled = {
                "fill_time_ts": t.get("fill_time_ts"),
                "exit_time_ts": t.get("exit_time_ts"),
                "signal": t.get("signal"),
                "entry": t.get("entry"),
                "sl": t.get("sl"),
                "tp": t.get("tp"),
                "exit_price": t.get("exit_price"),  # เฉพาะ trade ที่ผ่าน _apply_lts_exit_overlay (SMART_EXIT)
                "lot": lot_val,
                "pnl_usd": pnl_val,
                "outcome": t.get("outcome", ""),
                "leg": leg["label"],
                "tf": tf
            }
            all_portfolio_trades.append(t_scaled)

    if actual_name in ("LTS_AVENGERS_ULTRA_SAFE", "LTS_AVENGERS_HIGH_RISK", "LTS44"):
        all_portfolio_trades = _apply_aggregate_exposure_cap_scoped(all_portfolio_trades, aggregate_cap=100.0)

    return all_portfolio_trades


def setup_mt5_for_portfolio(portfolio_name):
    # Normalize portfolio name
    normalized_pf = ALIASES.get(portfolio_name, portfolio_name)
    
    # Locate directories
    demo_profiles_dir = os.path.join(root_dir, "profiles", "demo")
    real_profiles_dir = os.path.join(root_dir, "profiles", "real")
    
    matched_profile_dir = None
    matched_profile_name = None
    matched_env = {}
    
    def parse_env_file(env_path):
        data = {}
        if os.path.exists(env_path):
            try:
                with open(env_path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line or line.startswith("#") or "=" not in line:
                            continue
                        k, v = line.split("=", 1)
                        data[k.strip()] = v.strip().strip('"').strip("'")
            except Exception:
                pass
        return data

    # 1. Scan profiles for a matching portfolio
    for root in [demo_profiles_dir, real_profiles_dir]:
        if not os.path.exists(root):
            continue
        for p in os.listdir(root):
            p_dir = os.path.join(root, p)
            if not os.path.isdir(p_dir):
                continue
            if "2101114448" in p or "2101182458" in p: # exclude 4448 and 2458 profiles per rules
                continue
            env_path = os.path.join(p_dir, "profile.env")
            env_data = parse_env_file(env_path)
            active_pf = env_data.get("DEMO_PORTFOLIO_ACTIVE", "")
            active_pfs = [x.strip() for x in active_pf.split(",") if x.strip()]
            for apf in active_pfs:
                if is_portfolio_match(apf, portfolio_name):
                    matched_profile_dir = p_dir
                    matched_profile_name = p
                    matched_env = env_data
                    break
            if matched_profile_dir:
                break
        if matched_profile_dir:
            break
            
    # 2. If no match, default to main profile for market OHLC bar data
    main_profile_name = "demo-iux-2101182459"
    main_profile_dir = os.path.join(demo_profiles_dir, main_profile_name)
    
    if matched_profile_dir:
        print(f"📌 [Profile Match] Portfolio '{portfolio_name}' matches active profile '{matched_profile_name}'")
        target_dir = matched_profile_dir
        target_env = matched_env
    else:
        print(f"📌 [Profile Match] No active profile runs portfolio '{portfolio_name}'. Using main profile '{main_profile_name}' for OHLC bar data.")
        target_dir = main_profile_dir
        target_env = parse_env_file(os.path.join(main_profile_dir, "profile.env"))

    # เก็บ target_dir ไว้ใช้อ่าน mt5_server_tz_history.json ของโปรไฟล์นี้โดยตรง (ดู
    # _bkk_hour_server_tz_aware) — ไฟล์ history ถูก scope ต่อโปรไฟล์ (config.PROFILE_DIR)
    # ไม่ใช่ตัวเดียวกันข้ามบัญชี ต่างจาก path ที่ config มองเห็นตอนรันสคริปต์นี้แบบ standalone
    # (PROFILE_ACTIVE=False เลยได้ path fallback ที่ root ซึ่งไม่มีใครเขียนจริง)
    global LTS_AUS_AHR_SETUP_PROFILE_DIR
    LTS_AUS_AHR_SETUP_PROFILE_DIR = target_dir

    # 3. Apply settings
    if target_env:
        # Resolve absolute MT5 path
        rel_path = target_env.get("MT5_PATH", "mt5\\terminal64.exe")
        abs_path = os.path.abspath(os.path.join(target_dir, rel_path))
        portable = target_env.get("MT5_PORTABLE", "true").lower() == "true"
        
        # Write to environment variables for subprocesses
        os.environ["MT5_PATH"] = abs_path
        os.environ["MT5_PORTABLE"] = "true" if portable else "false"
        os.environ["MT5_LOGIN"] = target_env.get("MT5_LOGIN", "0")
        os.environ["MT5_PASSWORD"] = target_env.get("MT5_PASSWORD", "")
        os.environ["MT5_SERVER"] = target_env.get("MT5_SERVER", "")
        
        env_symbol = target_env.get("SYMBOL", "")
        if env_symbol:
            os.environ["SYMBOL"] = env_symbol
        env_candidates = target_env.get("SYMBOL_CANDIDATES", "")
        if env_candidates:
            os.environ["SYMBOL_CANDIDATES"] = env_candidates
            
        # Update config attributes in memory for the current process
        config.MT5_PATH = abs_path
        config.MT5_PORTABLE = portable
        config.MT5_LOGIN = int(target_env.get("MT5_LOGIN", "0"))
        config.MT5_PASSWORD = target_env.get("MT5_PASSWORD", "")
        config.MT5_SERVER = target_env.get("MT5_SERVER", "")
        if env_symbol:
            config.SYMBOL = env_symbol
        if env_candidates:
            config.SYMBOL_CANDIDATES = env_candidates
            
        print(f"   Using MT5 Terminal: {config.MT5_PATH}")
        print(f"   Account Details: Login={config.MT5_LOGIN}, Server={config.MT5_SERVER}, Symbol={config.SYMBOL}")

        # ── scoped profile.env behavioral override (เฉพาะ LTS_AUS/LTS_AHR) ──────────
        # `import config` เกิดที่บรรทัดบนสุดของไฟล์นี้ (ก่อน setup_mt5_for_portfolio ถูกเรียก
        # ด้วยซ้ำ) ทำให้ config.py อ่านค่า default hardcode เสมอ ไม่เคยเห็น override เฉพาะ
        # โปรไฟล์จาก profile.env เลย (เช่น DEMO_PORTFOLIO_CB_ENABLED_*, DYNAMIC_LOT_ENABLED_*)
        # เจอจริง 2026-08-04: profile.env ของ IUX ตั้ง DEMO_PORTFOLIO_CB_ENABLED_LTS_AVENGERS_
        # HIGH_RISK=true ไว้ แต่ config.DEMO_PORTFOLIO_CB_ENABLED อ่านได้ False เสมอ (default
        # เดิมเป็น True เฉพาะ ULTRA_SAFE) ทำให้ backtest จำลอง CB ผิดเปิด/ปิดสำหรับ AHR มาตลอด
        # ตั้งค่าย้อนหลังตรงนี้เข้า config dict โดยตรง (เหมือนที่ config.py เองทำตอน import แต่
        # runtime) — เขียนเฉพาะ key ของ LTS_AUS/LTS_AHR เท่านั้น ไม่กระทบพอร์ตอื่นเลย
        if normalized_pf in ("LTS_AVENGERS_ULTRA_SAFE", "LTS_AVENGERS_HIGH_RISK"):
            def _env_bool_from(env_val, default):
                if env_val is None or env_val == "":
                    return default
                return str(env_val).strip().lower() == "true"

            def _env_float_from(env_val, default):
                if env_val is None or env_val == "":
                    return default
                try:
                    return float(env_val)
                except ValueError:
                    return default

            config.DEMO_PORTFOLIO_CB_ENABLED[normalized_pf] = _env_bool_from(
                target_env.get("DEMO_PORTFOLIO_CB_ENABLED_" + normalized_pf),
                config.DEMO_PORTFOLIO_CB_ENABLED.get(normalized_pf, False),
            )
            config.DYNAMIC_LOT_ENABLED[normalized_pf] = _env_bool_from(
                target_env.get("DYNAMIC_LOT_ENABLED_" + normalized_pf),
                config.DYNAMIC_LOT_ENABLED.get(normalized_pf, False),
            )
            config.DEMO_PORTFOLIO_WEIGHT_ENABLED[normalized_pf] = _env_bool_from(
                target_env.get("DEMO_PORTFOLIO_WEIGHT_ENABLED_" + normalized_pf),
                config.DEMO_PORTFOLIO_WEIGHT_ENABLED.get(normalized_pf, False),
            )
            config.DEMO_PORTFOLIO_WEIGHT_SCALE[normalized_pf] = _env_float_from(
                target_env.get("DEMO_PORTFOLIO_WEIGHT_SCALE_" + normalized_pf),
                config.DEMO_PORTFOLIO_WEIGHT_SCALE.get(normalized_pf, 1.0),
            )
            config.DEMO_PORTFOLIO_AF_MAX_LOT[normalized_pf] = _env_float_from(
                target_env.get("DEMO_PORTFOLIO_AF_MAX_LOT_" + normalized_pf),
                config.DEMO_PORTFOLIO_AF_MAX_LOT.get(normalized_pf, 0.0),
            )
            config.SMART_CUTLOSS_ENABLED[normalized_pf] = _env_bool_from(
                target_env.get("SMART_CUTLOSS_ENABLED_" + normalized_pf),
                config.SMART_CUTLOSS_ENABLED.get(normalized_pf, False),
            )
            config.MOMENTUM_STALL_EXIT_ENABLED[normalized_pf] = _env_bool_from(
                target_env.get("MOMENTUM_STALL_EXIT_ENABLED_" + normalized_pf),
                config.MOMENTUM_STALL_EXIT_ENABLED.get(normalized_pf, False),
            )
            print(
                f"   [profile.env override] CB_ENABLED={config.DEMO_PORTFOLIO_CB_ENABLED[normalized_pf]} "
                f"DYNAMIC_LOT={config.DYNAMIC_LOT_ENABLED[normalized_pf]} "
                f"WEIGHT_ENABLED={config.DEMO_PORTFOLIO_WEIGHT_ENABLED[normalized_pf]} "
                f"WEIGHT_SCALE={config.DEMO_PORTFOLIO_WEIGHT_SCALE[normalized_pf]} "
                f"MAX_LOT={config.DEMO_PORTFOLIO_AF_MAX_LOT[normalized_pf]} "
                f"SMART_CUTLOSS={config.SMART_CUTLOSS_ENABLED[normalized_pf]} "
                f"MOMENTUM_STALL={config.MOMENTUM_STALL_EXIT_ENABLED[normalized_pf]}"
            )
    else:
        print(f"   ⚠️ Warning: Could not load target profile environment settings.")

def connect_to_actual_profile_for_portfolio(portfolio_name):
    demo_profiles_dir = os.path.join(root_dir, "profiles", "demo")
    real_profiles_dir = os.path.join(root_dir, "profiles", "real")
    
    matched_profile_dir = None
    matched_env = {}
    
    def parse_env_file(env_path):
        data = {}
        if os.path.exists(env_path):
            try:
                with open(env_path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line or line.startswith("#") or "=" not in line:
                            continue
                        k, v = line.split("=", 1)
                        data[k.strip()] = v.strip().strip('"').strip("'")
            except Exception:
                pass
        return data

    for root in [demo_profiles_dir, real_profiles_dir]:
        if not os.path.exists(root):
            continue
        for p in os.listdir(root):
            p_dir = os.path.join(root, p)
            if not os.path.isdir(p_dir) or "2101114448" in p or "2101182458" in p:
                continue
            env_path = os.path.join(p_dir, "profile.env")
            env_data = parse_env_file(env_path)
            active_pf = env_data.get("DEMO_PORTFOLIO_ACTIVE", "")
            active_pfs = [x.strip() for x in active_pf.split(",") if x.strip()]
            for apf in active_pfs:
                if is_portfolio_match(apf, portfolio_name):
                    matched_profile_dir = p_dir
                    matched_env = env_data
                    break
            if matched_profile_dir:
                break
        if matched_profile_dir:
            break
            
    if not matched_profile_dir:
        # NO profile is currently running this portfolio active in DEMO_PORTFOLIO_ACTIVE!
        return False

    global LAST_MATCHED_PROFILE_DIR
    LAST_MATCHED_PROFILE_DIR = matched_profile_dir

    # Initialize and login using the matched profile's local terminal path
    rel_path = matched_env.get("MT5_PATH", "mt5\\terminal64.exe")
    abs_path = os.path.abspath(os.path.join(matched_profile_dir, rel_path))
    portable = matched_env.get("MT5_PORTABLE", "true").lower() == "true"
    login = int(matched_env.get("MT5_LOGIN", "0"))
    
    import time
    connected = False
    for attempt in range(4):
        mt5.shutdown()
        time.sleep(1.0)
        if mt5.initialize(path=abs_path, portable=portable, timeout=30000):
            connected = True
            break
            
    if connected:
        try:
            info = mt5.account_info()
        except Exception:
            info = None
        if info is not None and login > 0 and int(getattr(info, "login", 0) or 0) == login:
            # Already connected to correct account, skip login to avoid IPC conflicts/timeouts
            return True
        else:
            # Login only if not already logged in to the correct account
            password = matched_env.get("MT5_PASSWORD", "")
            server = matched_env.get("MT5_SERVER", "")
            if login > 0:
                if mt5.login(login, password, server):
                    return True
                else:
                    print(f"   ❌ mt5.login failed for {portfolio_name} ({login}): {mt5.last_error()}")
            else:
                return True
            
    mt5.shutdown()
    print(f"   ❌ Connection failed to terminal {abs_path} for {portfolio_name}: {mt5.last_error()}")
    return False

def generate_mt5_and_compare_reports(portfolio_name, backtest_trades, start_str, end_str, days, output_dir):
    # 1. Calculate date_from and date_to
    if start_str:
        def parse_date(s):
            for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
                try:
                    return datetime.strptime(s.strip(), fmt)
                except ValueError:
                    pass
            raise ValueError(f"Time data '{s}' does not match formats")
        import pytz
        bkk = pytz.timezone("Asia/Bangkok")
        date_from = bkk.localize(parse_date(start_str)).astimezone(timezone.utc)
        if end_str:
            date_to = bkk.localize(parse_date(end_str)).astimezone(timezone.utc)
        else:
            date_to = datetime.now(timezone.utc) + timedelta(days=1)
    else:
        # Align with midnight of the start date in BKK timezone (UTC+7) to match backtest range
        bkk_tz = timezone(timedelta(hours=7))
        now_bkk = datetime.now(bkk_tz)
        start_bkk = now_bkk - timedelta(days=days)
        start_bkk = start_bkk.replace(hour=0, minute=0, second=0, microsecond=0)
        date_from = start_bkk.astimezone(timezone.utc)
        date_to = datetime.now(timezone.utc) + timedelta(days=1)
        
    # 2. Get active magic numbers for this portfolio
    actual_pf = ALIASES.get(portfolio_name, portfolio_name)
    strict_backtest_match = actual_pf in ("LTS_AVENGERS_ULTRA_SAFE", "LTS_AVENGERS_HIGH_RISK")
    sub_pfs = [x.strip() for x in actual_pf.split(",") if x.strip()]
    target_magics = []
    for pf in sub_pfs:
        try:
            magic = dp._portfolio_magic(pf)
            target_magics.append(magic)
        except Exception:
            pass

    # Prepare backtest compare list
    bt_compare_list = []
    for t in backtest_trades:
        open_ts = t["fill_time_ts"]
        close_ts = t["exit_time_ts"]
        open_dt = datetime.fromtimestamp(open_ts, tz=timezone.utc).astimezone(timezone(timedelta(hours=7)))
        close_dt = datetime.fromtimestamp(close_ts, tz=timezone.utc).astimezone(timezone(timedelta(hours=7)))
        bt_compare_list.append({
            "open_dt": open_dt.replace(tzinfo=None),
            "close_dt": close_dt.replace(tzinfo=None),
            "type": t["signal"],
            "entry": t["entry"],
            "sl": t["sl"],
            "tp": t["tp"],
            "lot": t["lot"],
            "pnl": t["pnl_usd"],
            "outcome": t["outcome"],
            "leg_name": t.get("leg", portfolio_name),
            "tf": t.get("tf", "M5")
        })
        
    # 3. Connect to the actual profile
    if not connect_to_actual_profile_for_portfolio(portfolio_name):
        print(f"   ℹ️ Skipping MT5 real trade match: No active MT5 profile running portfolio '{portfolio_name}'")
        # Save empty MT5 real CSV
        mt5_path = os.path.join(output_dir, f"{portfolio_name}_mt5_real.csv")
        with open(mt5_path, "w", newline="", encoding="utf-8") as f:
            f.write("Time (BKK),Close Time,Leg,TF,Type,Entry,Exit,Lot,P&L,Outcome\n")
            
        # Write clean SIM-only compare report
        compare_rows = []
        for bt in bt_compare_list:
            # SMART_EXIT (Smart Cut-loss/Momentum Stall overlay ของ LTS_AUS/LTS_AHR) ปิดที่ราคา
            # จริงไม่ใช่ SL/TP เดิม — ใช้ exit_price ที่เก็บไว้แทน (ดู _apply_lts_exit_overlay)
            if bt["outcome"] == "SMART_EXIT" and bt.get("exit_price") is not None:
                sim_exit = bt["exit_price"]
            else:
                sim_exit = bt["tp"] if bt["outcome"] == "TP" else bt["sl"]
            sim_diff = (sim_exit - bt["entry"]) if bt["type"] == "BUY" else (bt["entry"] - sim_exit)
            sim_pt = round(sim_diff * 100, 1) if bt["entry"] and sim_exit else ""
            compare_rows.append({
                "SIM_Open_Time": bt["open_dt"].strftime('%Y-%m-%d %H:%M:%S'),
                "MT5_Open_Time": "",
                "SIM_Close_Time": bt["close_dt"].strftime('%Y-%m-%d %H:%M:%S'),
                "MT5_Close_Time": "",
                "SIM_Leg": bt["leg_name"],
                "SIM_TF": bt["tf"],
                "MT5_TF": "",
                "SIM_Type": bt["type"],
                "MT5_Type": "",
                "SIM_Entry": round(bt["entry"], 2),
                "MT5_Entry": "",
                "MT5_Close_Price": "",
                "SIM_SL": round(bt["sl"], 2),
                "MT5_SL": "",
                "SIM_TP": round(bt["tp"], 2),
                "MT5_TP": "",
                "SIM_Lot": round(bt["lot"], 2),
                "MT5_Volume": "",
                "SIM_P&L": round(bt["pnl"], 2),
                "MT5_P&L": "",
                "SIM_Balance": "",
                "MT5_Balance": "",
                "MT5_Comment": "",
                "MT5_Position_ID": "",
                "Matched": False,
                "Match_Detail": "NO_ACTIVE_PROFILE",
                "SIM_Reason": bt["outcome"],
                "MT5_Reason": "",
                "Sim_point": sim_pt,
                "MT5_point": ""
            })
            
        if compare_rows:
            def sort_key(row):
                t = row["SIM_Open_Time"] or row["MT5_Open_Time"]
                return datetime.strptime(t, '%Y-%m-%d %H:%M:%S')
            compare_rows.sort(key=sort_key)
            start_balance = PORTFOLIO_BALANCES.get(portfolio_name, 1000.0)
            sim_running_balance = start_balance
            for r in compare_rows:
                if r["SIM_P&L"] != "":
                    sim_running_balance += r["SIM_P&L"]
                    r["SIM_Balance"] = round(sim_running_balance, 2)
        save_compare_and_splits(compare_rows, output_dir, portfolio_name)
        return
        
    # 4. Fetch deals from history (lookback 10 days wider to find entry deals for positions closed in the range)
    wide_date_from = date_from - timedelta(days=10)
    deals = mt5.history_deals_get(wide_date_from, date_to)
    
    # Fetch historical orders to map SL/TP (since deals do not contain sl/tp fields)
    orders = mt5.history_orders_get(wide_date_from - timedelta(days=5), date_to)
    order_sl_map = {}
    order_tp_map = {}
    if orders:
        for o in orders:
            order_sl_map[o.ticket] = o.sl
            order_tp_map[o.ticket] = o.tp
            pid = o.position_id
            if pid:
                if o.sl > 0:
                    order_sl_map[pid] = o.sl
                if o.tp > 0:
                    order_tp_map[pid] = o.tp

    mt5_compare_list = []
    mt5_rows = []
    
    if deals:
        entry_deals = {d.position_id: d for d in deals if d.entry == mt5.DEAL_ENTRY_IN}
        start_ts = date_from.timestamp()
        for d in deals:
            # Match exits that closed within the requested date range (including Close By exit type 3)
            if d.time >= start_ts and d.entry in (mt5.DEAL_ENTRY_OUT, 3) and d.position_id in entry_deals:
                d_in = entry_deals[d.position_id]
                if strict_backtest_match and d_in.time < start_ts:
                    continue
                # Filter by symbol and magic (check both exit and entry deal to support Close By with magic 0)
                if "XAUUSD" in d.symbol and (d.magic in target_magics or d_in.magic in target_magics):
                    trade_type = "BUY" if d_in.type == mt5.DEAL_TYPE_BUY else "SELL"
                    profit = float(d.profit) + float(d.swap) + float(d.commission)
                    
                    bkk_tz = timezone(timedelta(hours=7))
                    entry_dt_bkk = datetime.fromtimestamp(d_in.time, tz=timezone.utc).astimezone(bkk_tz)
                    exit_dt_bkk = datetime.fromtimestamp(d.time, tz=timezone.utc).astimezone(bkk_tz)
                    
                    outcome = "TP" if profit > 0 else "SL"
                    
                    # Parse TF from comment (e.g. M15-LTS_AUS_913 -> M15)
                    real_tf = "M5"
                    if d_in.comment:
                        parts = d_in.comment.split("-")
                        if parts and parts[0] in ("M1", "M5", "M15", "M30", "H1", "H4", "D1"):
                            real_tf = parts[0]
                            
                    row = {
                        "Time (BKK)": entry_dt_bkk.strftime('%d-%m-%Y %H:%M:%S'),
                        "Close Time": exit_dt_bkk.strftime('%d-%m-%Y %H:%M:%S'),
                        "Leg": d_in.comment if d_in.comment else f"Magic {d.magic}",
                        "TF": real_tf,
                        "Type": trade_type,
                        "Entry": round(d_in.price, 2),
                        "Exit": round(d.price, 2),
                        "Lot": round(d.volume, 2),
                        "P&L": round(profit, 2),
                        "Outcome": outcome
                    }
                    mt5_rows.append(row)
                    
                    mt5_compare_list.append({
                        "dt": entry_dt_bkk.replace(tzinfo=None),
                        "close_dt": exit_dt_bkk.replace(tzinfo=None),
                        "type": trade_type,
                        "tf": real_tf,
                        "entry": d_in.price,
                        "close_price": d.price,
                        "sl": order_sl_map.get(d_in.order, 0.0) or order_sl_map.get(d_in.position_id, 0.0),
                        "tp": order_tp_map.get(d_in.order, 0.0) or order_tp_map.get(d_in.position_id, 0.0),
                        "volume": d.volume,
                        "pnl": profit,
                        "comment": d_in.comment if d_in.comment else getattr(d, "comment", ""),
                        "position_id": d.position_id,
                        "outcome": outcome,
                        "mt5_reason": getattr(d, "comment", "")
                    })
                    
    # Save mt5 real CSV
    mt5_path = os.path.join(output_dir, f"{portfolio_name}_mt5_real.csv")
    if mt5_rows:
        df_mt5 = pd.DataFrame(mt5_rows)
        df_mt5.to_csv(mt5_path, index=False, encoding="utf-8")
        print(f"Saved: {mt5_path} ({len(mt5_rows)} real trades)")
    else:
        with open(mt5_path, "w", newline="", encoding="utf-8") as f:
            f.write("Time (BKK),Close Time,Leg,TF,Type,Entry,Exit,Lot,P&L,Outcome\n")
        print(f"Saved empty MT5 real: {mt5_path}")
        
    # 5. Run matching comparison
    bt_compare_list = []
    bkk_tz = timezone(timedelta(hours=7))
    for bt in backtest_trades:
        bt_open_dt = datetime.fromtimestamp(bt.get("fill_time_ts", 0), tz=timezone.utc).astimezone(bkk_tz).replace(tzinfo=None)
        bt_close_dt = datetime.fromtimestamp(bt.get("exit_time_ts", 0), tz=timezone.utc).astimezone(bkk_tz).replace(tzinfo=None)
        bt_compare_list.append({
            "open_dt": bt_open_dt,
            "close_dt": bt_close_dt,
            "tf": bt.get("tf", "M5"),
            "type": bt.get("signal", ""),
            "entry": bt.get("entry", 0.0),
            "sl": bt.get("sl", 0.0),
            "tp": bt.get("tp", 0.0),
            "lot": bt.get("lot", 0.01),
            "pnl": bt.get("pnl_usd", 0.0),
            "outcome": bt.get("outcome", ""),
            "exit_price": bt.get("exit_price"),  # เฉพาะ trade ที่ผ่าน _apply_lts_exit_overlay (SMART_EXIT)
            "leg_name": bt.get("leg", "")
        })
        
    import re
    def extract_leg_idx(name):
        if not name:
            return None
        m = re.search(r'LTS_AVENGERS_[A-Z_]+_([0-9]+)\b', name)
        if m:
            return int(m.group(1))
        m = re.search(r'(?:LTS_AUS_|LTS-AUS-|_|\b)([0-9]{1,4})\b', name)
        if m:
            return int(m.group(1))
        return None

    strict_time_tolerance_sec = 30
    strict_price_tolerance = 0.05

    def _get_time_diff(bt, mt):
        bt_leg = extract_leg_idx(bt["leg_name"])
        is_s9x_leg = bt_leg >= 900 if bt_leg is not None else False
        if is_s9x_leg:
            bt_tf_mins = {"M15": 15, "M30": 30, "H1": 60}.get(bt["tf"], 15)
            mt_dt_aligned = mt["dt"] - timedelta(minutes=mt["dt"].minute % bt_tf_mins, seconds=mt["dt"].second)
            return abs((mt_dt_aligned - bt["open_dt"]).total_seconds())
        return abs((mt["dt"] - bt["open_dt"]).total_seconds())

    def _strict_mismatch_reason(bt, mt):
        reasons = []
        time_diff = _get_time_diff(bt, mt)
        if time_diff > strict_time_tolerance_sec:
            reasons.append(f"open_time_diff={time_diff:.0f}s")
        if mt["tf"] != bt["tf"]:
            reasons.append(f"tf {bt['tf']}!={mt['tf']}")
        if mt["type"] != bt["type"]:
            reasons.append(f"type {bt['type']}!={mt['type']}")
        if mt["sl"] and abs(float(mt["sl"]) - float(bt["sl"])) > strict_price_tolerance:
            reasons.append(f"sl_diff={abs(float(mt['sl']) - float(bt['sl'])):.2f}")
        elif not mt["sl"]:
            reasons.append("mt5_sl_missing")
        if mt["tp"] and abs(float(mt["tp"]) - float(bt["tp"])) > strict_price_tolerance:
            reasons.append(f"tp_diff={abs(float(mt['tp']) - float(bt['tp'])):.2f}")
        elif not mt["tp"]:
            reasons.append("mt5_tp_missing")
        return "; ".join(reasons)

    compare_rows = []
    mismatch_mt5 = list(mt5_compare_list)
    
    # Matching pass
    for bt in bt_compare_list:
        matched = None
        bt_leg = extract_leg_idx(bt["leg_name"])
        
        # Pass 1: Strict match by Leg Index + Timeframe + Direction
        if bt_leg is not None:
            for mt in mismatch_mt5:
                mt_leg = extract_leg_idx(mt["comment"])
                if mt_leg is not None and mt_leg == bt_leg and mt["type"] == bt["type"] and mt["tf"] == bt["tf"]:
                    time_diff = _get_time_diff(bt, mt)
                    if strict_backtest_match:
                        sl_ok = mt["sl"] and abs(float(mt["sl"]) - float(bt["sl"])) <= strict_price_tolerance
                        tp_ok = mt["tp"] and abs(float(mt["tp"]) - float(bt["tp"])) <= strict_price_tolerance
                        if time_diff <= strict_time_tolerance_sec and sl_ok and tp_ok:
                            matched = mt
                            break
                    elif time_diff <= 21600: # Within 6 hours
                        matched = mt
                        break
                        
        # Pass 2: Fallback match by Timeframe + Type + Proximity (time <= 3 hours, price <= 15 USD)
        if not matched and not strict_backtest_match:
            for mt in mismatch_mt5:
                mt_leg = extract_leg_idx(mt["comment"])
                # Explicitly forbid matching if both have leg indices and they are different!
                if bt_leg is not None and mt_leg is not None and bt_leg != mt_leg:
                    continue
                time_diff = _get_time_diff(bt, mt)
                price_diff = abs(mt["entry"] - bt["entry"])
                if mt["type"] == bt["type"] and mt["tf"] == bt["tf"] and price_diff <= 15.0 and time_diff <= 10800:
                    matched = mt
                    break
                    
        if matched:
            # Sim point calculation (exit at TP if outcome is TP, else SL)
            # SMART_EXIT (Smart Cut-loss/Momentum Stall overlay ของ LTS_AUS/LTS_AHR) ปิดที่ราคา
            # จริงไม่ใช่ SL/TP เดิม — ใช้ exit_price ที่เก็บไว้แทน (ดู _apply_lts_exit_overlay)
            if bt["outcome"] == "SMART_EXIT" and bt.get("exit_price") is not None:
                sim_exit = bt["exit_price"]
            else:
                sim_exit = bt["tp"] if bt["outcome"] == "TP" else bt["sl"]
            sim_diff = (sim_exit - bt["entry"]) if bt["type"] == "BUY" else (bt["entry"] - sim_exit)
            sim_pt = round(sim_diff * 100, 1) if bt["entry"] and sim_exit else ""
            
            # MT5 point calculation
            mt5_diff = (matched["close_price"] - matched["entry"]) if matched["type"] == "BUY" else (matched["entry"] - matched["close_price"])
            mt5_pt = round(mt5_diff * 100, 1) if matched["entry"] and matched["close_price"] else ""
            
            compare_rows.append({
                "SIM_Open_Time": bt["open_dt"].strftime('%Y-%m-%d %H:%M:%S'),
                "MT5_Open_Time": matched["dt"].strftime('%Y-%m-%d %H:%M:%S'),
                "SIM_Close_Time": bt["close_dt"].strftime('%Y-%m-%d %H:%M:%S'),
                "MT5_Close_Time": matched["close_dt"].strftime('%Y-%m-%d %H:%M:%S'),
                "SIM_Leg": bt["leg_name"],
                "SIM_TF": bt["tf"],
                "MT5_TF": bt["tf"], # Use SIM_TF for MT5_TF if matched
                "SIM_Type": bt["type"],
                "MT5_Type": matched["type"],
                "SIM_Entry": round(bt["entry"], 2),
                "MT5_Entry": round(matched["entry"], 2),
                "MT5_Close_Price": round(matched["close_price"], 2),
                "SIM_SL": round(bt["sl"], 2),
                "MT5_SL": round(matched["sl"], 2) if matched["sl"] else "",
                "SIM_TP": round(bt["tp"], 2),
                "MT5_TP": round(matched["tp"], 2) if matched["tp"] else "",
                "SIM_Lot": round(bt["lot"], 2),
                "MT5_Volume": round(matched["volume"], 2),
                "SIM_P&L": round(bt["pnl"], 2),
                "MT5_P&L": round(matched["pnl"], 2),
                "SIM_Balance": "",
                "MT5_Balance": "",
                "MT5_Comment": matched["comment"],
                "MT5_Position_ID": matched["position_id"],
                "Matched": True,
                "Match_Detail": "strict" if strict_backtest_match else "matched",
                "SIM_Reason": bt["outcome"],
                "MT5_Reason": matched.get("mt5_reason", ""),
                "Sim_point": sim_pt,
                "MT5_point": mt5_pt
            })
            mismatch_mt5.remove(matched)
        else:
            near_reason = ""
            if strict_backtest_match:
                nearest = None
                nearest_score = None
                for mt in mismatch_mt5:
                    mt_leg = extract_leg_idx(mt["comment"])
                    if bt_leg is not None and mt_leg is not None and bt_leg != mt_leg:
                        continue
                    score = abs((mt["dt"] - bt["open_dt"]).total_seconds())
                    if mt["tf"] != bt["tf"]:
                        score += 3600
                    if mt["type"] != bt["type"]:
                        score += 3600
                    if nearest is None or score < nearest_score:
                        nearest = mt
                        nearest_score = score
                if nearest is not None:
                    near_reason = _strict_mismatch_reason(bt, nearest)
            
            # Sim point calculation
            # SMART_EXIT (Smart Cut-loss/Momentum Stall overlay ของ LTS_AUS/LTS_AHR) ปิดที่ราคา
            # จริงไม่ใช่ SL/TP เดิม — ใช้ exit_price ที่เก็บไว้แทน (ดู _apply_lts_exit_overlay)
            if bt["outcome"] == "SMART_EXIT" and bt.get("exit_price") is not None:
                sim_exit = bt["exit_price"]
            else:
                sim_exit = bt["tp"] if bt["outcome"] == "TP" else bt["sl"]
            sim_diff = (sim_exit - bt["entry"]) if bt["type"] == "BUY" else (bt["entry"] - sim_exit)
            sim_pt = round(sim_diff * 100, 1) if bt["entry"] and sim_exit else ""
            
            compare_rows.append({
                "SIM_Open_Time": bt["open_dt"].strftime('%Y-%m-%d %H:%M:%S'),
                "MT5_Open_Time": "",
                "SIM_Close_Time": bt["close_dt"].strftime('%Y-%m-%d %H:%M:%S'),
                "MT5_Close_Time": "",
                "SIM_Leg": bt["leg_name"],
                "SIM_TF": bt["tf"],
                "MT5_TF": "",
                "SIM_Type": bt["type"],
                "MT5_Type": "",
                "SIM_Entry": round(bt["entry"], 2),
                "MT5_Entry": "",
                "MT5_Close_Price": "",
                "SIM_SL": round(bt["sl"], 2),
                "MT5_SL": "",
                "SIM_TP": round(bt["tp"], 2),
                "MT5_TP": "",
                "SIM_Lot": round(bt["lot"], 2),
                "MT5_Volume": "",
                "SIM_P&L": round(bt["pnl"], 2),
                "MT5_P&L": "",
                "SIM_Balance": "",
                "MT5_Balance": "",
                "MT5_Comment": "",
                "MT5_Position_ID": "",
                "Matched": False,
                "Match_Detail": near_reason,
                "SIM_Reason": bt["outcome"],
                "MT5_Reason": "",
                "Sim_point": sim_pt,
                "MT5_point": ""
            })
            
    # เตรียมข้อมูล cb-desync สำหรับอธิบาย MT5_ONLY ที่แท้จริงเกิดจาก simulated circuit breaker
    # (OVERLAY_CFG) ตัดทิ้ง ไม่ใช่ backtest หา pattern ไม่เจอจริงๆ — ไม่แตะตัวเลข P&L ใดๆ เลย
    _cb_skipped_by_leg = {}
    for rt in CB_SKIPPED_TRADES.get(portfolio_name, []):
        leg_num = extract_leg_idx(rt["leg_key"])
        if leg_num is not None:
            _cb_skipped_by_leg.setdefault(leg_num, []).append(rt["fill_time_ts"])

    _real_cb_state = {}
    if LAST_MATCHED_PROFILE_DIR:
        try:
            state_path = os.path.join(LAST_MATCHED_PROFILE_DIR, "demo_portfolio_state.json")
            with open(state_path, "r", encoding="utf-8") as f:
                _real_cb_state = json.load(f).get("cb_state", {})
        except Exception:
            _real_cb_state = {}

    def _cb_desync_note(mt):
        """ถ้า MT5_ONLY แถวนี้ตรงกับ raw trade ที่ simulated CB ตัดทิ้งไป (leg เดียวกัน,
        เวลาใกล้กันภายใน 6 ชม.) ให้คืน note พร้อมสถานะ cb_state จริงของ leg นั้น — ไม่งั้นคืน None"""
        leg_num = extract_leg_idx(mt["comment"])
        if leg_num is None or leg_num not in _cb_skipped_by_leg:
            return None
        # mt["dt"] เป็น BKK-naive (tzinfo ถูก strip แล้ว) — ต้องแปะ tzinfo=BKK ก่อนเรียก .timestamp()
        # ไม่งั้น Python จะตีความเป็น local timezone ของเครื่องที่รัน (ผิดถ้าเครื่องไม่ได้ตั้ง BKK)
        mt_ts = mt["dt"].replace(tzinfo=timezone(timedelta(hours=7))).timestamp()
        if not any(abs(mt_ts - ts) <= 21600 for ts in _cb_skipped_by_leg[leg_num]):
            return None
        leg_key_guess = f"{ALIASES.get(portfolio_name, portfolio_name)}_{leg_num}"
        cb = _real_cb_state.get(leg_key_guess, {})
        return (
            f"cb_desync: simulated CB (550d) ตัดทิ้ง แต่บัญชีจริง cooldown_remaining="
            f"{cb.get('cooldown_remaining', '?')} consec_loss={cb.get('consec_loss', '?')} ตอนนี้"
        )

    for mt in mismatch_mt5:
        # MT5 point calculation
        mt5_diff = (mt["close_price"] - mt["entry"]) if mt["type"] == "BUY" else (mt["entry"] - mt["close_price"])
        mt5_pt = round(mt5_diff * 100, 1) if mt["entry"] and mt["close_price"] else ""

        cb_note = _cb_desync_note(mt)
        match_detail = "MT5_ONLY_CB_DESYNC" if cb_note else "MT5_ONLY"
        sim_reason = cb_note if cb_note else "ไม่มี SIM คู่ — backtest ไม่เจอ pattern นี้"

        compare_rows.append({
            "SIM_Open_Time": "",
            "MT5_Open_Time": mt["dt"].strftime('%Y-%m-%d %H:%M:%S'),
            "SIM_Close_Time": "",
            "MT5_Close_Time": mt["close_dt"].strftime('%Y-%m-%d %H:%M:%S'),
            "SIM_Leg": "",
            "SIM_TF": "",
            "MT5_TF": mt["tf"],
            "SIM_Type": "",
            "MT5_Type": mt["type"],
            "SIM_Entry": "",
            "MT5_Entry": round(mt["entry"], 2),
            "MT5_Close_Price": round(mt["close_price"], 2),
            "SIM_SL": "",
            "MT5_SL": round(mt["sl"], 2) if mt["sl"] else "",
            "SIM_TP": "",
            "MT5_TP": round(mt["tp"], 2) if mt["tp"] else "",
            "SIM_Lot": "",
            "MT5_Volume": round(mt["volume"], 2),
            "SIM_P&L": "",
            "MT5_P&L": round(mt["pnl"], 2),
            "SIM_Balance": "",
            "MT5_Balance": "",
            "MT5_Comment": mt["comment"],
            "MT5_Position_ID": mt["position_id"],
            "Matched": False,
            "Match_Detail": match_detail,
            "SIM_Reason": sim_reason,
            "MT5_Reason": mt.get("mt5_reason", ""),
            "Sim_point": "",
            "MT5_point": mt5_pt
        })
        
    if compare_rows:
        def sort_key(row):
            t = row["SIM_Open_Time"] or row["MT5_Open_Time"]
            return datetime.strptime(t, '%Y-%m-%d %H:%M:%S')
        compare_rows.sort(key=sort_key)

        start_balance = PORTFOLIO_BALANCES.get(portfolio_name, 1000.0)
        sim_running_balance = start_balance
        mt5_running_balance = start_balance

        for r in compare_rows:
            if r["SIM_P&L"] != "":
                sim_running_balance += r["SIM_P&L"]
                r["SIM_Balance"] = round(sim_running_balance, 2)
            else:
                r["SIM_Balance"] = ""

            if r["MT5_P&L"] != "":
                mt5_running_balance += r["MT5_P&L"]
                r["MT5_Balance"] = round(mt5_running_balance, 2)
            else:
                r["MT5_Balance"] = ""
    save_compare_and_splits(compare_rows, output_dir, portfolio_name)
        
    # Cleanup connection to return to safe state if possible
    mt5.shutdown()

def run_compare_only_flow(portfolio_name, args):
    name_lower = portfolio_name.lower()
    if name_lower.startswith("p"):
        sub = "p"
    elif name_lower.startswith("s"):
        sub = "s"
    elif name_lower.startswith("af"):
        sub = "af"
    elif name_lower.startswith("lts"):
        sub = "lts"
    else:
        sub = "others"
    pf_out_dir = os.path.join(args.out_dir, sub)
    
    bt_trades = []
    trades_path = os.path.join(pf_out_dir, f"{portfolio_name}_trades.csv")
    if os.path.exists(trades_path):
        try:
            with open(trades_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    def bkk_to_ts(time_str):
                        if not time_str or time_str == "-":
                            return 0
                        dt = datetime.strptime(time_str, "%d-%m-%Y %H:%M:%S")
                        bkk_tz = timezone(timedelta(hours=7))
                        dt = dt.replace(tzinfo=bkk_tz)
                        return int(dt.timestamp())
                        
                    bt_trades.append({
                        "fill_time_ts": bkk_to_ts(row.get("Time (BKK)")),
                        "exit_time_ts": bkk_to_ts(row.get("Close Time")),
                        "tf": row.get("TF", "M5"),
                        "signal": row.get("Type", ""),
                        "entry": float(row.get("Entry") or 0.0),
                        "sl": float(row.get("SL") or 0.0),
                        "tp": float(row.get("TP") or 0.0),
                        "lot": float(row.get("Lot") or 0.01),
                        "pnl_usd": float(row.get("P&L") or 0.0),
                        "outcome": row.get("Outcome", ""),
                        "leg": row.get("Leg", "")
                    })
        except Exception as e:
            print(f"   ⚠️ Error parsing trades.csv for compare only: {e}")
            
    portfolio_days = {
        "P13": 550, "P16": 550, "18-Way": 550, "P18": 550,
        "AF22": 365, "AF34": 365, "AF47": 365,
        "LTS44": 550, "LTS890": 550, "LTS999": 550,
        "LTS_AVENGERS_BASE": 420, "LTS_AVENGERS_P34": 420,
        "LTS_AVENGERS_HIGH_RISK": 550, "LTS_AVENGERS_ULTRA_SAFE": 550, "LTS_AVENGERS_HIGH_FREQ": 550,
        "S101": 550, "S102": 550, "S105": 550, "S106": 550, "S111": 550
    }
    has_custom_range = "--days" in sys.argv or "--start" in sys.argv or "--end" in sys.argv
    days = portfolio_days.get(portfolio_name, args.days) if not has_custom_range else args.days

    # โหลด CB_SKIPPED_TRADES ที่ parent process เซฟไว้ (subprocess นี้คนละ memory space)
    cb_skip_path = os.path.join(pf_out_dir, f"{portfolio_name}_cb_skipped.json")
    if os.path.exists(cb_skip_path):
        try:
            with open(cb_skip_path, "r", encoding="utf-8") as f:
                CB_SKIPPED_TRADES[portfolio_name] = json.load(f)
        except Exception as e:
            print(f"   ⚠️ Failed to load cb_skipped cache: {e}")

    generate_mt5_and_compare_reports(portfolio_name, bt_trades, args.start, args.end, days, pf_out_dir)

def main():
    parser = argparse.ArgumentParser(description="Unified Backtest Simulation for all Demo Portfolios")
    parser.add_argument("--portfolio", default="all", help="Portfolio name (e.g. LTS999, P13, S101, all)")
    parser.add_argument("--days", type=int, default=550, help="Number of days to backtest (default: 550)")
    parser.add_argument("--start", type=str, default=None, help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end", type=str, default=None, help="End date (YYYY-MM-DD)")
    parser.add_argument("--balance", type=float, default=None, help="Custom starting balance")
    parser.add_argument("--scale", type=float, default=1.0, help="Custom lot/PnL scale factor (default: 1.0)")
    parser.add_argument("--spread", type=float, default=0.20, help="Spread to apply (default: 0.20)")
    parser.add_argument("--out-dir", default=os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "excel_fixed")), help="Output directory for CSV files (แยกจาก run_backtest_sim.py ต้นฉบับ กัน CSV ทับกัน)")
    parser.add_argument("--compare-only", type=str, default=None, help="Internal use: run compare report in separate process")
    parser.add_argument("--no-cache", action="store_true", help="Do not load or save raw trades disk cache")
    args = parser.parse_args()
    
    if args.compare_only:
        run_compare_only_flow(args.compare_only, args)
        sys.exit(0)
    
    # Select portfolios
    if args.portfolio == "all":
        portfolios = list(dp.PORTFOLIOS.keys())
    else:
        target = args.portfolio
        actual = ALIASES.get(target, target)
        if actual not in dp.PORTFOLIOS:
            print(f"❌ Portfolio name '{target}' not found in demo_portfolio.PORTFOLIOS")
            sys.exit(1)
        portfolios = [actual]
        
    try:
        for pf in portfolios:
            actual_pf = ALIASES.get(pf, pf)
            
            # Ensure previous connection is closed to change profile safely
            mt5.shutdown()
            GLOBAL_RAW_TRADES_CACHE.clear()
            
            # Match and configure MT5 profile
            setup_mt5_for_portfolio(pf)
            
            # Ensure MT5 is initialized (subprocesses might shut it down)
            if not config.mt5_initialize(mt5):
                print(f"❌ MT5 re-initialization failed for {pf}: {mt5.last_error()}")
                sys.exit(1)

            
            portfolio_days = {
                "P13": 550, "P16": 550, "18-Way": 550, "P18": 550,
                "AF22": 365, "AF34": 365, "AF47": 365,
                "LTS44": 550, "LTS890": 550, "LTS999": 550,
                "LTS_AVENGERS_BASE": 420, "LTS_AVENGERS_P34": 420,
                "LTS_AVENGERS_HIGH_RISK": 550, "LTS_AVENGERS_ULTRA_SAFE": 550, "LTS_AVENGERS_HIGH_FREQ": 550,
                "S101": 550, "S102": 550, "S105": 550, "S106": 550, "S111": 550
            }
            # If the user did not specify any custom range arguments (--days, --start, --end), use portfolio default days.
            has_custom_range = "--days" in sys.argv or "--start" in sys.argv or "--end" in sys.argv
            days = portfolio_days.get(pf, args.days) if not has_custom_range else args.days
            
            # Print execution info
            if args.start:
                end_str = args.end if args.end else "Now"
                print(f"\n==================================================")
                print(f"🏁 RUNNING BACKTEST FOR: {pf} (Range: {args.start} to {end_str} | scale={args.scale})")
                print(f"==================================================")
            else:
                print(f"\n==================================================")
                print(f"🏁 RUNNING BACKTEST FOR: {pf} ({days} days | scale={args.scale})")
                print(f"==================================================")
            
            balance = args.balance if args.balance is not None else PORTFOLIO_BALANCES.get(pf, 1000.0)
            
            trades = []
            if pf in ["P13", "P16", "P18", "18-Way"]:
                trades = run_standard_blend_backtest(pf, days, args.spread, args.start, args.end, args.scale)
            elif pf in ["S101", "S102", "S105", "S106", "S111"]:
                trades = run_single_strategy_backtest(pf, days, args.start, args.end, args.scale)
            elif actual_pf.startswith("LTS") or actual_pf.startswith("AF"):
                trades = run_lts_af_backtest(pf, days, args.start, args.end, args.scale)
            else:
                print(f"⚠️ Unknown portfolio type for: {pf}")
                continue
                
            # Shutdown MT5 connection as soon as bar fetching is done to release IPC locks for subprocesses
            mt5.shutdown()
            
            # Post-filter trades based on custom start / end timestamps or days range
            import pytz
            bkk = pytz.timezone("Asia/Bangkok")
            
            def parse_date(s):
                for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
                    try:
                        return datetime.strptime(s.strip(), fmt)
                    except ValueError:
                        pass
                raise ValueError(f"Time data '{s}' does not match formats YYYY-MM-DD, YYYY-MM-DD HH:MM, or YYYY-MM-DD HH:MM:SS")
                
            if args.start:
                start_dt = bkk.localize(parse_date(args.start))
                start_ts = int(start_dt.timestamp())
            else:
                # Limit trades to the last N days (midnight BKK of start day)
                now_bkk = datetime.now(bkk)
                start_dt = now_bkk - timedelta(days=days)
                start_dt = start_dt.replace(hour=0, minute=0, second=0, microsecond=0)
                start_ts = int(start_dt.timestamp())

            # fill_time_ts ของ trade คือ raw MT5 epoch (server wall clock แปะป้ายเป็น UTC) ไม่ใช่
            # true UTC ตรงๆ — เทียบตรงๆ กับ start_ts/end_ts (ซึ่งแปลงจาก BKK wall-clock ที่พี่พิมพ์
            # ด้วย pytz แบบถูกต้องเป๊ะ) จะเพี้ยนไปตาม MT5_SERVER_TZ ของวันนั้น (เจอจริง 2026-08-04:
            # IUX server_tz=+1 ทำให้ trade ที่ fill จริงตอน BKK 10:52 ถูกกรองทิ้งไปทั้งที่ --end
            # ตั้งไว้ 11:00 — เพราะ raw fill_time_ts เพี้ยนไปเกิน end_ts) แก้เฉพาะ LTS_AUS/LTS_AHR
            # โดยแปลง fill_time_ts เป็น true UTC ก่อนเทียบ ใช้ server_tz history เดียวกับที่ fix
            # เรื่อง hour bucket ไปแล้ว ไม่กระทบพอร์ตอื่น (ยังเทียบ raw ตรงๆ เหมือนเดิม)
            def _true_utc_fill_ts(fill_ts):
                if actual_pf not in ("LTS_AVENGERS_ULTRA_SAFE", "LTS_AVENGERS_HIGH_RISK"):
                    return fill_ts
                # เชื่อ server_tz ที่ย้อนคำนวณจาก log จริงล่าสุดก่อน (สดกว่า history file
                # ที่มี debounce ล่าช้า — ดู _derive_latest_server_tz_from_log) fallback ไป
                # history file ถ้า log ยังไม่มีข้อมูล (เช่น รันช่วงก่อน 2026-07-31)
                derived = _derive_latest_server_tz_from_log()
                if derived is not None:
                    return int(fill_ts) - derived * 3600
                history = _load_lts_aus_ahr_server_tz_history()
                utc_dt = datetime.fromtimestamp(int(fill_ts), tz=timezone.utc)
                date_key = utc_dt.strftime("%Y-%m-%d")
                server_tz = config.MT5_SERVER_TZ
                for k in sorted(history.keys(), reverse=True):
                    if k <= date_key:
                        server_tz = history[k]
                        break
                return int(fill_ts) - server_tz * 3600

            trades = [t for t in trades if _true_utc_fill_ts(t.get("fill_time_ts", 0)) >= start_ts]

            if args.end:
                end_dt = parse_date(args.end)
                if len(args.end.strip()) <= 10:
                    end_dt = end_dt + timedelta(days=1)
                end_dt = bkk.localize(end_dt)
                end_ts = int(end_dt.timestamp())
                trades = [t for t in trades if _true_utc_fill_ts(t.get("fill_time_ts", 0)) <= end_ts]
                    
            print(f"Processing reports for {pf} (found {len(trades)} trades)...")
            
            # Resolve subfolder path (lts, af, p, s)
            name_lower = pf.lower()
            if name_lower.startswith("p") or name_lower.startswith("18") or pf == "18-Way":
                sub = "p"
            elif name_lower.startswith("s"):
                sub = "s"
            elif name_lower.startswith("af"):
                sub = "af"
            elif name_lower.startswith("lts"):
                sub = "lts"
            else:
                sub = "others"
            
            pf_out_dir = os.path.join(args.out_dir, sub)
            save_reports(pf, trades, balance, pf_out_dir)
            # เซฟ CB_SKIPPED_TRADES ลงดิสก์ — compare report รันเป็น subprocess แยก (คนละ process
            # memory) ต้องส่งข้อมูลนี้ผ่านไฟล์ ไม่ใช่ตัวแปร module-level เฉยๆ (อ่านคืนใน
            # run_compare_only_flow ด้านล่าง)
            if pf in CB_SKIPPED_TRADES:
                os.makedirs(pf_out_dir, exist_ok=True)
                cb_skip_path = os.path.join(pf_out_dir, f"{pf}_cb_skipped.json")
                try:
                    with open(cb_skip_path, "w", encoding="utf-8") as f:
                        json.dump(CB_SKIPPED_TRADES[pf], f)
                except Exception as e:
                    print(f"   ⚠️ Failed to save cb_skipped cache: {e}")
            # Generate MT5 real trades and comparison CSV files via separate subprocess to avoid path-switching deadlocks
            print(f"   Generating MT5 real trades and compare reports for {pf}...")
            cmd = [sys.executable, __file__, "--compare-only", pf, "--days", str(days), "--out-dir", args.out_dir]
            if args.start:
                cmd += ["--start", args.start]
            if args.end:
                cmd += ["--end", args.end]
            subprocess.run(cmd)
            
    finally:
        mt5.shutdown()
        print("\nMT5 Shutdown completed.")

if __name__ == "__main__":
    main()
