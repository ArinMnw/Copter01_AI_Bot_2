import os
import sys
import csv
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
import pickle
CACHE_FILE = os.path.abspath(os.path.join(os.path.dirname(__file__), "raw_trades_cache.pkl"))

def save_disk_cache():
    try:
        os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
        # Filter cache: do not save keys with start_str or end_str to disk
        clean_cache = {}
        for k, v in GLOBAL_RAW_TRADES_CACHE.items():
            has_date = False
            if len(k) == 5:
                if k[3] is not None or k[4] is not None:
                    has_date = True
            elif len(k) == 4:
                if k[2] is not None or k[3] is not None:
                    has_date = True
            if not has_date:
                clean_cache[k] = v
        with open(CACHE_FILE, "wb") as f:
            pickle.dump(clean_cache, f)
    except Exception as e:
        print(f"⚠️ Failed to save disk cache: {e}")

def load_disk_cache():
    global GLOBAL_RAW_TRADES_CACHE
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "rb") as f:
                GLOBAL_RAW_TRADES_CACHE = pickle.load(f)
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

# Mapping aliases
ALIASES = {
    "18-Way": "P18",
    "LTS_AVB": "LTS_AVENGERS_BASE",
    "LTS_AP34": "LTS_AVENGERS_P34",
    "LTS_AHR": "LTS_AVENGERS_HIGH_RISK",
    "LTS_AUS": "LTS_AVENGERS_ULTRA_SAFE",
    "LTS_AHF": "LTS_AVENGERS_HIGH_FREQ",
}

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
        
        tf_multiplier = {"M1": 1, "M5": 2, "M15": 5, "M30": 8}
        lookback_days = tf_multiplier.get(tf_str, 5)
        start_fetch = start_dt - timedelta(days=lookback_days)
        
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
                    fill_dt = datetime.strptime(row["fill_time"], "%Y-%m-%d %H:%M")
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

def run_s9x_generic(bars, detect_fn, tf, cfg, spread):
    """Simulates standalone S95-S111 strategies bar-by-bar for the blend backtester."""
    trades = []
    n = len(bars)
    lookback = 300
    if n < lookback + 10:
        return []
        
    last_trade_idx = -100
    cooldown = 5
    
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
            
        # Check if filled within 5 bars
        fill_idx = None
        for j in range(i + 1, min(i + 6, n)):
            h, l = float(bars[j]['high']), float(bars[j]['low'])
            if (direction == "BUY" and l <= entry - spread) or (direction == "SELL" and h >= entry + spread):
                fill_idx = j
                break
                
        if fill_idx is None:
            continue
            
        # Simulate outcome
        outcome = None
        exit_price = None
        exit_idx = None
        
        for j in range(fill_idx, n):
            h, l = float(bars[j]['high']), float(bars[j]['low'])
            if direction == "BUY":
                if l <= sl:
                    outcome = "SL"
                    exit_price = sl
                    exit_idx = j
                    break
                if h >= tp:
                    outcome = "TP"
                    exit_price = tp
                    exit_idx = j
                    break
            else:
                if h >= sl:
                    outcome = "SL"
                    exit_price = sl
                    exit_idx = j
                    break
                if l <= tp:
                    outcome = "TP"
                    exit_price = tp
                    exit_idx = j
                    break
                    
        if outcome is None or exit_idx is None:
            continue
            
        last_trade_idx = i
        diff = (exit_price - entry) if direction == "BUY" else (entry - exit_price)
        pnl = diff - spread
        
        trades.append({
            "outcome": outcome,
            "signal_time_ts": int(bars[i]["time"]),
            "fill_time_ts": int(bars[fill_idx]["time"]),
            "exit_time_ts": int(bars[exit_idx]["time"]),
            "entry": round(entry, 2),
            "tp": round(tp, 2),
            "sl": round(sl, 2),
            "exit_price": round(exit_price, 2),
            "risk_distance": round(risk_distance, 4),
            "diff_usd_per_001lot": round(pnl, 4),
            "spread": spread,
            "reason": "S9X",
        })
        
    return trades

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
        
    print(f"Simulating {len(legs)} legs for {portfolio_name}...")
    
    global GLOBAL_RAW_TRADES_CACHE
    unique_bases = set((leg["family"], leg["cfg_idx"]) for leg in legs)
    
    # 1. Fetch bars and cache raw trades for unique base configs
    from optimize_s88_allin4s_fast import _make_s84, _make_s86, _grid_s84, _grid_s86, TF_EXTRA_BARS
    
    for fam, cfg_idx in unique_bases:
        cache_key = (fam, cfg_idx, days, start_str, end_str)
        if cache_key in GLOBAL_RAW_TRADES_CACHE:
            continue
            
        # Find if any leg matching (fam, cfg_idx) is is_s9x
        leg = next((l for l in legs if l["family"] == fam and l["cfg_idx"] == cfg_idx), None)
        is_s9x = leg.get("is_s9x", False) if leg else False
        
        if is_s9x:
            detect_fn = leg["detect_fn"]
            cfg = leg["cfg"]
            tf = cfg["ENTRY_TF"]
            
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
        tf = cfg["ENTRY_TF"]
        
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
    for leg in legs:
        cache_key = (leg["family"], leg["cfg_idx"], days, start_str, end_str)
        raw = GLOBAL_RAW_TRADES_CACHE.get(cache_key)
        if not raw:
            continue
            
        rd_min = leg.get("rd_min")
        rd_max = leg.get("rd_max")
        rd_band = "all" if (rd_min is None or rd_max is None) else f"{rd_min:.1f}-{rd_max:.1f}"
        filtered_raw = _post_filter_raw(raw, rd_band, leg.get("hour"))
        if leg.get("mode") == "inverse":
            filtered_raw = _invert_raw(filtered_raw)
            
        _twp, _eq, by_day = _simulate_leg(filtered_raw, OVERLAY_CFG)
        
        # Determine TF
        if leg.get("is_s9x"):
            tf = leg["cfg"]["ENTRY_TF"]
        else:
            maker = _make_s84 if leg["family"] == "s84" else _make_s86
            grid = _grid_s84("micro") if leg["family"] == "s84" else _grid_s86("micro")
            all_vals = list(itertools.product(*grid))
            cfg_vals = all_vals[leg["cfg_idx"]]
            tf = maker(cfg_vals)["ENTRY_TF"]
        
        for t in _twp:
            t_scaled = {
                "fill_time_ts": t.get("fill_time_ts"),
                "exit_time_ts": t.get("exit_time_ts"),
                "signal": t.get("signal"),
                "entry": t.get("entry"),
                "sl": t.get("sl"),
                "tp": t.get("tp"),
                "lot": t.get("lot", 0.01) * leg["weight"] * scale,
                "pnl_usd": t.get("pnl_usd", 0.0) * leg["weight"] * scale,
                "outcome": t.get("outcome", ""),
                "leg": leg["label"],
                "tf": tf
            }
            all_portfolio_trades.append(t_scaled)
            
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
            if "2101114448" in p or "exness" in p.lower(): # exclude 4448 and exness profiles to avoid deadlocks
                continue
            env_path = os.path.join(p_dir, "profile.env")
            env_data = parse_env_file(env_path)
            active_pf = env_data.get("DEMO_PORTFOLIO_ACTIVE", "")
            active_pfs = [ALIASES.get(x.strip(), x.strip()) for x in active_pf.split(",") if x.strip()]
            if normalized_pf in active_pfs:
                matched_profile_dir = p_dir
                matched_profile_name = p
                matched_env = env_data
                break
        if matched_profile_dir:
            break
            
    # 2. If no match, default to main profile: demo-iux-2101182459
    main_profile_name = "demo-iux-2101182459"
    main_profile_dir = os.path.join(demo_profiles_dir, main_profile_name)
    
    if matched_profile_dir:
        print(f"📌 [Profile Match] Portfolio '{portfolio_name}' matches active profile '{matched_profile_name}'")
        target_dir = matched_profile_dir
        target_env = matched_env
    else:
        print(f"📌 [Profile Match] No profile matches portfolio '{portfolio_name}'. Defaulting to main profile '{main_profile_name}'")
        target_dir = main_profile_dir
        target_env = parse_env_file(os.path.join(main_profile_dir, "profile.env"))
        
    # 3. Apply settings
    if target_env:
        # Resolve absolute MT5 path
        rel_path = target_env.get("MT5_PATH", "mt5\\terminal64.exe")
        abs_path = os.path.abspath(os.path.join(target_dir, rel_path))
        
        # Write to environment variables for subprocesses
        os.environ["MT5_PATH"] = abs_path
        os.environ["MT5_PORTABLE"] = target_env.get("MT5_PORTABLE", "true")
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
        config.MT5_PORTABLE = target_env.get("MT5_PORTABLE", "true").lower() == "true"
        config.MT5_LOGIN = int(target_env.get("MT5_LOGIN", "0"))
        config.MT5_PASSWORD = target_env.get("MT5_PASSWORD", "")
        config.MT5_SERVER = target_env.get("MT5_SERVER", "")
        if env_symbol:
            config.SYMBOL = env_symbol
        if env_candidates:
            config.SYMBOL_CANDIDATES = env_candidates
            
        print(f"   Using MT5 Terminal: {config.MT5_PATH}")
        print(f"   Account Details: Login={config.MT5_LOGIN}, Server={config.MT5_SERVER}, Symbol={config.SYMBOL}")
    else:
        print(f"   ⚠️ Warning: Could not load target profile environment settings.")

def main():
    parser = argparse.ArgumentParser(description="Unified Backtest Simulation for all Demo Portfolios")
    parser.add_argument("--portfolio", default="all", help="Portfolio name (e.g. LTS999, P13, S101, all)")
    parser.add_argument("--days", type=int, default=550, help="Number of days to backtest (default: 550)")
    parser.add_argument("--start", type=str, default=None, help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end", type=str, default=None, help="End date (YYYY-MM-DD)")
    parser.add_argument("--balance", type=float, default=None, help="Custom starting balance")
    parser.add_argument("--scale", type=float, default=1.0, help="Custom lot/PnL scale factor (default: 1.0)")
    parser.add_argument("--spread", type=float, default=0.20, help="Spread to apply (default: 0.20)")
    parser.add_argument("--out-dir", default=os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "excel")), help="Output directory for CSV files")
    args = parser.parse_args()
    
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
            days = portfolio_days.get(pf, args.days) if args.portfolio == "all" else args.days
            
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
                
            # Post-filter trades based on custom start / end timestamps
            if args.start:
                def parse_date(s):
                    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
                        try:
                            return datetime.strptime(s.strip(), fmt)
                        except ValueError:
                            pass
                    raise ValueError(f"Time data '{s}' does not match formats YYYY-MM-DD, YYYY-MM-DD HH:MM, or YYYY-MM-DD HH:MM:SS")
                    
                import pytz
                bkk = pytz.timezone("Asia/Bangkok")
                start_dt = bkk.localize(parse_date(args.start))
                start_ts = int(start_dt.timestamp())
                trades = [t for t in trades if t.get("fill_time_ts", 0) >= start_ts]
                
                if args.end:
                    end_dt = parse_date(args.end)
                    if len(args.end.strip()) <= 10:
                        end_dt = end_dt + timedelta(days=1)
                    end_dt = bkk.localize(end_dt)
                    end_ts = int(end_dt.timestamp())
                    trades = [t for t in trades if t.get("fill_time_ts", 0) <= end_ts]
                    
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
            
    finally:
        mt5.shutdown()
        print("\nMT5 Shutdown completed.")

if __name__ == "__main__":
    main()
