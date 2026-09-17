# -*- coding: utf-8 -*-
"""s20_compare_engine.py
Official 100% Verifiable Compare Engine for S20 Institutional Strategies
(S20.18, S20.19, S20.20, S20.21, S20.22, S20.24, S20.28, S20.301, S20.302, S20.303, S20.304).

Generates the 7 core CSV reports matching LTS_AUS3 specification:
1. {portfolio}_trades.csv            : All backtest simulated trades
2. {portfolio}_daily.csv             : Backtest daily performance summary
3. {portfolio}_monthly.csv           : Backtest monthly performance summary
4. {portfolio}_mt5_real.csv          : All closed real trades extracted from MT5 History Deals
5. {portfolio}_compare.csv           : Matched trades only (Matched=True) with detailed side-by-side metrics
6. {portfolio}_mt5_not_match.csv     : Real MT5 trades that had no matching backtest trade
7. {portfolio}_backtest_not_match.csv: Backtest trades that were not found in MT5 history
"""

import os
import sys
import re
import time
import pandas as pd
from datetime import datetime, timezone, timedelta
import MetaTrader5 as mt5

BKK_TZ = timezone(timedelta(hours=7))

COMPARE_COLS = [
    "SIM_Open_Time", "MT5_Open_Time", "SIM_Close_Time", "MT5_Close_Time",
    "SIM_Leg", "SIM_TF", "MT5_TF", "SIM_Type", "MT5_Type", "SIM_Entry", "MT5_Entry",
    "MT5_Close_Price", "SIM_SL", "MT5_SL", "SIM_TP", "MT5_TP", "SIM_Lot",
    "MT5_Volume", "SIM_P&L", "MT5_P&L", "SIM_Balance", "MT5_Balance",
    "MT5_Comment", "MT5_Position_ID", "Matched", "Match_Detail", "SIM_Reason",
    "MT5_Reason", "Sim_point", "MT5_point"
]

MT5_REAL_COLS = [
    "Time (BKK)", "Close Time", "Leg", "TF", "Type",
    "Entry", "Exit", "Lot", "P&L", "Outcome"
]


def format_ts_to_bkk(ts, fmt="%Y-%m-%d %H:%M:%S"):
    if not ts or ts == "-":
        return "-"
    try:
        return datetime.fromtimestamp(int(ts), tz=timezone.utc).astimezone(BKK_TZ).strftime(fmt)
    except Exception:
        return str(ts)


def connect_profile_mt5(profile_name="demo-iux-2101183586", root_dir=None):
    """Connect to MT5 terminal belonging to the specified profile."""
    if root_dir is None:
        root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

    # Try matching profile in profiles/demo or profiles/real
    matched_profile_dir = None
    for sub in ["demo", "real"]:
        cand = os.path.join(root_dir, "profiles", sub, profile_name)
        if os.path.isdir(cand):
            matched_profile_dir = cand
            break

    # If profile name was given as account login like 3586 or 2101183586
    if not matched_profile_dir:
        for sub in ["demo", "real"]:
            base = os.path.join(root_dir, "profiles", sub)
            if os.path.exists(base):
                for p in os.listdir(base):
                    if profile_name in p:
                        matched_profile_dir = os.path.join(base, p)
                        break
            if matched_profile_dir:
                break

    if not matched_profile_dir:
        print(f"⚠️ Profile directory for '{profile_name}' not found under profiles/demo or profiles/real.")
        return False

    env_path = os.path.join(matched_profile_dir, "profile.env")
    env_data = {}
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    env_data[k.strip()] = v.strip().strip('"').strip("'")

    rel_path = env_data.get("MT5_PATH", "mt5\\terminal64.exe")
    abs_path = os.path.abspath(os.path.join(matched_profile_dir, rel_path))
    portable = env_data.get("MT5_PORTABLE", "true").lower() == "true"
    login = int(env_data.get("MT5_LOGIN", "0"))

    connected = False
    for attempt in range(3):
        mt5.shutdown()
        time.sleep(0.5)
        if mt5.initialize(path=abs_path, portable=portable, timeout=30000):
            connected = True
            break

    if not connected:
        print(f"❌ Failed to initialize MT5 at {abs_path}: {mt5.last_error()}")
        return False

    acc_info = mt5.account_info()
    if acc_info is not None and login > 0 and acc_info.login == login:
        return True

    # Login if not already logged in
    password = env_data.get("MT5_PASSWORD", "")
    server = env_data.get("MT5_SERVER", "")
    if login > 0:
        if mt5.login(login, password, server):
            return True
        else:
            print(f"❌ mt5.login failed for {login}: {mt5.last_error()}")
            return False

    return True


def fetch_mt5_real_trades(date_from, date_to, target_sids=None, symbol_filter=None):
    """Fetch closed trades from MT5 history deals and orders within date range."""
    wide_date_from = date_from - timedelta(days=10)
    deals = mt5.history_deals_get(wide_date_from, date_to) or []
    orders = mt5.history_orders_get(wide_date_from - timedelta(days=5), date_to) or []

    order_sl_map = {}
    order_tp_map = {}
    for o in orders:
        if o.sl > 0:
            order_sl_map[o.position_id] = o.sl
            order_sl_map[o.ticket] = o.sl
        if o.tp > 0:
            order_tp_map[o.position_id] = o.tp
            order_tp_map[o.ticket] = o.tp

    entry_deals = {d.position_id: d for d in deals if d.entry == mt5.DEAL_ENTRY_IN}
    start_ts = date_from.timestamp()

    # Normalization helper for sids
    sid_tokens = []
    if target_sids:
        for s in target_sids:
            s_str = str(s).strip()
            sid_tokens.extend([f"S{s_str}", f"_{s_str}", f"S{s_str.replace('.', '_')}", s_str])

    mt5_trades = []
    mt5_real_rows = []

    for d in deals:
        if d.time < start_ts:
            continue
        if d.entry not in (mt5.DEAL_ENTRY_OUT, 3):  # 3 = Close by
            continue
        if d.position_id not in entry_deals:
            continue

        din = entry_deals[d.position_id]
        comment = din.comment or ""

        # Filter by strategy ID if specified
        if sid_tokens:
            if not any(token in comment for token in sid_tokens):
                continue

        # Filter by symbol if specified
        if symbol_filter and din.symbol not in symbol_filter:
            continue

        trade_type = "BUY" if din.type == mt5.DEAL_TYPE_BUY else "SELL"
        profit = float(d.profit) + float(d.swap) + float(d.commission)

        entry_dt_bkk = datetime.fromtimestamp(din.time, tz=timezone.utc).astimezone(BKK_TZ)
        exit_dt_bkk = datetime.fromtimestamp(d.time, tz=timezone.utc).astimezone(BKK_TZ)
        outcome = "TP" if profit > 0 else "SL"

        # Parse TF from comment (e.g. M5_S20.304 -> M5)
        tf = "M5"
        m_tf = re.match(r'^([A-Za-z0-9]+)_', comment)
        if m_tf and m_tf.group(1).upper() in ("M1", "M5", "M15", "M30", "H1", "H4", "D1"):
            tf = m_tf.group(1).upper()

        sl_val = order_sl_map.get(din.position_id, 0.0) or order_sl_map.get(din.order, 0.0)
        tp_val = order_tp_map.get(din.position_id, 0.0) or order_tp_map.get(din.order, 0.0)

        mt5_real_rows.append({
            "Time (BKK)": entry_dt_bkk.strftime('%Y-%m-%d %H:%M:%S'),
            "Close Time": exit_dt_bkk.strftime('%Y-%m-%d %H:%M:%S'),
            "Leg": comment if comment else f"Pos {d.position_id}",
            "TF": tf,
            "Type": trade_type,
            "Entry": round(din.price, 4),
            "Exit": round(d.price, 4),
            "Lot": round(d.volume, 2),
            "P&L": round(profit, 2),
            "Outcome": outcome
        })

        mt5_trades.append({
            "dt": entry_dt_bkk.replace(tzinfo=None),
            "close_dt": exit_dt_bkk.replace(tzinfo=None),
            "symbol": din.symbol,
            "tf": tf,
            "type": trade_type,
            "entry": din.price,
            "close_price": d.price,
            "sl": sl_val,
            "tp": tp_val,
            "volume": d.volume,
            "pnl": profit,
            "comment": comment,
            "position_id": d.position_id,
            "outcome": outcome,
            "mt5_reason": getattr(d, "comment", "")
        })

    return mt5_trades, mt5_real_rows


def run_s20_compare(
    portfolio_name,
    backtest_trades,
    start_balance,
    output_dir,
    start_dt,
    end_dt,
    target_sids=None,
    symbols_to_run=None,
    profile_name="demo-iux-2101183586",
    time_tolerance_sec=900,
    price_tolerance_usd=1.0,
    root_dir=None
):
    """Run full matching comparison between backtest simulated trades and MT5 real trades.
    Generates 4 compare CSV files:
    - {portfolio}_mt5_real.csv
    - {portfolio}_compare.csv (Matched=True)
    - {portfolio}_mt5_not_match.csv
    - {portfolio}_backtest_not_match.csv
    """
    os.makedirs(output_dir, exist_ok=True)
    print(f"\n" + "=" * 115)
    print(f" 🔍 S20 INSTITUTIONAL COMPARE ENGINE: {portfolio_name} vs MT5 ({profile_name})")
    print("=" * 115)

    if not connect_profile_mt5(profile_name, root_dir=root_dir):
        print(f"   ℹ️ Skipping MT5 real trade match: Could not connect to profile '{profile_name}'.")
        # Save empty MT5 real CSV and unmatched compare rows
        mt5_path = os.path.join(output_dir, f"{portfolio_name}_mt5_real.csv")
        pd.DataFrame([], columns=MT5_REAL_COLS).to_csv(mt5_path, index=False, encoding="utf-8")
        return

    # Convert backtest trades to standardized comparison records
    bt_compare_list = []
    for bt in backtest_trades:
        open_ts = bt.get("fill_time_ts", 0)
        close_ts = bt.get("exit_time_ts", 0)
        open_dt = datetime.fromtimestamp(open_ts, tz=timezone.utc).astimezone(BKK_TZ).replace(tzinfo=None)
        close_dt = datetime.fromtimestamp(close_ts, tz=timezone.utc).astimezone(BKK_TZ).replace(tzinfo=None)
        bt_compare_list.append({
            "open_dt": open_dt,
            "close_dt": close_dt,
            "symbol": bt.get("symbol", "XAUUSD.iux"),
            "tf": bt.get("tf", "M5"),
            "type": bt.get("signal", ""),
            "entry": bt.get("entry", 0.0),
            "sl": bt.get("sl", 0.0),
            "tp": bt.get("tp", 0.0),
            "lot": bt.get("lot", 0.01),
            "pnl": bt.get("pnl_usd", 0.0),
            "outcome": bt.get("outcome", ""),
            "leg_name": bt.get("leg", portfolio_name),
            "sid": bt.get("sid", None)
        })

    # Fetch MT5 history trades
    mt5_trades, mt5_real_rows = fetch_mt5_real_trades(
        date_from=start_dt,
        date_to=end_dt,
        target_sids=target_sids,
        symbol_filter=symbols_to_run
    )

    mt5.shutdown()

    # Save 1. MT5 Real CSV
    mt5_real_path = os.path.join(output_dir, f"{portfolio_name}_mt5_real.csv")
    df_mt5_real = pd.DataFrame(mt5_real_rows, columns=MT5_REAL_COLS)
    df_mt5_real.to_csv(mt5_real_path, index=False, encoding="utf-8")
    print(f"Saved: {mt5_real_path} ({len(mt5_real_rows)} real trades from MT5)")

    # Matching logic: Global optimal assignment to prevent greedy trade stealing
    compare_rows = []

    # 1. Collect all valid candidate pairings
    candidates = []
    for bt_idx, bt in enumerate(bt_compare_list):
        for mt_idx, mt in enumerate(mt5_trades):
            if mt["symbol"] != bt["symbol"] or mt["type"] != bt["type"]:
                continue
            if mt["tf"] != bt["tf"]:
                continue
            time_diff = abs((mt["dt"] - bt["open_dt"]).total_seconds())
            if time_diff > time_tolerance_sec:
                continue

            price_diff = abs(float(mt["entry"]) - float(bt["entry"]))
            pt_threshold = price_tolerance_usd
            if "XAU" in mt["symbol"].upper():
                pt_threshold = 0.80
            elif "XAG" in mt["symbol"].upper():
                pt_threshold = 0.15
            elif "JPY" in mt["symbol"].upper():
                pt_threshold = 0.20
            else:
                pt_threshold = 0.0020

            if price_diff > pt_threshold:
                continue

            # Prioritize price accuracy heavily (price diff in points), then time closeness
            score = (price_diff * 50.0) + (time_diff / 60.0)
            candidates.append((score, bt_idx, mt_idx))

    # Sort candidate pairs by score ascending (exact match / best score first)
    candidates.sort(key=lambda x: x[0])

    matched_bt = set()
    matched_mt = set()
    bt_to_mt = {}

    for score, bt_idx, mt_idx in candidates:
        if bt_idx in matched_bt or mt_idx in matched_mt:
            continue
        matched_bt.add(bt_idx)
        matched_mt.add(mt_idx)
        bt_to_mt[bt_idx] = mt5_trades[mt_idx]

    unmatched_mt5 = [mt for idx, mt in enumerate(mt5_trades) if idx not in matched_mt]

    for bt_idx, bt in enumerate(bt_compare_list):
        matched = bt_to_mt.get(bt_idx)
        if matched:
            sim_exit = bt["tp"] if bt["outcome"] == "TP" else bt["sl"]
            sim_diff = (sim_exit - bt["entry"]) if bt["type"] == "BUY" else (bt["entry"] - sim_exit)
            sim_pt = round(sim_diff * 100, 1) if bt["entry"] and sim_exit else ""

            mt5_diff = (matched["close_price"] - matched["entry"]) if matched["type"] == "BUY" else (matched["entry"] - matched["close_price"])
            mt5_pt = round(mt5_diff * 100, 1) if matched["entry"] and matched["close_price"] else ""

            compare_rows.append({
                "SIM_Open_Time": bt["open_dt"].strftime('%Y-%m-%d %H:%M:%S'),
                "MT5_Open_Time": matched["dt"].strftime('%Y-%m-%d %H:%M:%S'),
                "SIM_Close_Time": bt["close_dt"].strftime('%Y-%m-%d %H:%M:%S'),
                "MT5_Close_Time": matched["close_dt"].strftime('%Y-%m-%d %H:%M:%S'),
                "SIM_Leg": bt["leg_name"],
                "SIM_TF": bt["tf"],
                "MT5_TF": matched["tf"],
                "SIM_Type": bt["type"],
                "MT5_Type": matched["type"],
                "SIM_Entry": round(bt["entry"], 4),
                "MT5_Entry": round(matched["entry"], 4),
                "MT5_Close_Price": round(matched["close_price"], 4),
                "SIM_SL": round(bt["sl"], 4),
                "MT5_SL": round(matched["sl"], 4) if matched["sl"] else "",
                "SIM_TP": round(bt["tp"], 4),
                "MT5_TP": round(matched["tp"], 4) if matched["tp"] else "",
                "SIM_Lot": round(bt["lot"], 2),
                "MT5_Volume": round(matched["volume"], 2),
                "SIM_P&L": round(bt["pnl"], 2),
                "MT5_P&L": round(matched["pnl"], 2),
                "SIM_Balance": "",
                "MT5_Balance": "",
                "MT5_Comment": matched["comment"],
                "MT5_Position_ID": matched["position_id"],
                "Matched": True,
                "Match_Detail": "matched",
                "SIM_Reason": bt["outcome"],
                "MT5_Reason": matched.get("mt5_reason", ""),
                "Sim_point": sim_pt,
                "MT5_point": mt5_pt
            })
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
                "SIM_Entry": round(bt["entry"], 4),
                "MT5_Entry": "",
                "MT5_Close_Price": "",
                "SIM_SL": round(bt["sl"], 4),
                "MT5_SL": "",
                "SIM_TP": round(bt["tp"], 4),
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
                "Match_Detail": "BACKTEST_ONLY",
                "SIM_Reason": bt["outcome"],
                "MT5_Reason": "",
                "Sim_point": sim_pt,
                "MT5_point": ""
            })

    # Add remaining unmatched MT5 trades
    for mt in unmatched_mt5:
        mt5_diff = (mt["close_price"] - mt["entry"]) if mt["type"] == "BUY" else (mt["entry"] - mt["close_price"])
        mt5_pt = round(mt5_diff * 100, 1) if mt["entry"] and mt["close_price"] else ""

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
            "MT5_Entry": round(mt["entry"], 4),
            "MT5_Close_Price": round(mt["close_price"], 4),
            "SIM_SL": "",
            "MT5_SL": round(mt["sl"], 4) if mt["sl"] else "",
            "SIM_TP": "",
            "MT5_TP": round(mt["tp"], 4) if mt["tp"] else "",
            "SIM_Lot": "",
            "MT5_Volume": round(mt["volume"], 2),
            "SIM_P&L": "",
            "MT5_P&L": round(mt["pnl"], 2),
            "SIM_Balance": "",
            "MT5_Balance": "",
            "MT5_Comment": mt["comment"],
            "MT5_Position_ID": mt["position_id"],
            "Matched": False,
            "Match_Detail": "MT5_ONLY",
            "SIM_Reason": "No matching backtest signal found",
            "MT5_Reason": mt.get("mt5_reason", ""),
            "Sim_point": "",
            "MT5_point": mt5_pt
        })

    # Sort all rows chronologically and compute running balances
    if compare_rows:
        def sort_key(row):
            t = row["SIM_Open_Time"] or row["MT5_Open_Time"]
            return datetime.strptime(t, '%Y-%m-%d %H:%M:%S')

        compare_rows.sort(key=sort_key)

        sim_running = start_balance
        mt5_running = start_balance
        for r in compare_rows:
            if r["SIM_P&L"] != "":
                sim_running += r["SIM_P&L"]
                r["SIM_Balance"] = round(sim_running, 2)
            if r["MT5_P&L"] != "":
                mt5_running += r["MT5_P&L"]
                r["MT5_Balance"] = round(mt5_running, 2)

    # Split into matched, mt5_not_match, and backtest_not_match
    matched_rows = []
    mt5_not_match_rows = []
    bt_not_match_rows = []

    for r in compare_rows:
        if r.get("Matched") is True:
            matched_rows.append(r)
        elif r.get("MT5_Open_Time") and not r.get("SIM_Open_Time"):
            mt5_not_match_rows.append(r)
        elif r.get("SIM_Open_Time") and not r.get("MT5_Open_Time"):
            bt_not_match_rows.append(r)

    # Save 2. Compare CSV (Matched=True only)
    compare_path = os.path.join(output_dir, f"{portfolio_name}_compare.csv")
    pd.DataFrame(matched_rows, columns=COMPARE_COLS).to_csv(compare_path, index=False, encoding="utf-8")
    print(f"Saved: {compare_path} ({len(matched_rows)} matched rows)")

    # Save 3. MT5 Not Match CSV
    mt5_not_match_path = os.path.join(output_dir, f"{portfolio_name}_mt5_not_match.csv")
    pd.DataFrame(mt5_not_match_rows, columns=COMPARE_COLS).to_csv(mt5_not_match_path, index=False, encoding="utf-8")
    print(f"Saved: {mt5_not_match_path} ({len(mt5_not_match_rows)} MT5-only rows)")

    # Save 4. Backtest Not Match CSV
    bt_not_match_path = os.path.join(output_dir, f"{portfolio_name}_backtest_not_match.csv")
    pd.DataFrame(bt_not_match_rows, columns=COMPARE_COLS).to_csv(bt_not_match_path, index=False, encoding="utf-8")
    print(f"Saved: {bt_not_match_path} ({len(bt_not_match_rows)} Backtest-only rows)")

    # Print Summary
    total_sim = len(bt_compare_list)
    total_mt5 = len(mt5_trades)
    matched_cnt = len(matched_rows)
    match_rate = (matched_cnt / total_sim * 100) if total_sim > 0 else 0.0

    print("-" * 115)
    print(f" 📊 COMPARE VERIFICATION SUMMARY: {portfolio_name}")
    print(f" Total Backtest Simulated Trades: {total_sim}")
    print(f" Total MT5 Real Closed Trades:    {total_mt5}")
    print(f" ✅ Matched Trades (100% Valid):  {matched_cnt} ({match_rate:.1f}% Match Rate)")
    print(f" ⚠️ Backtest Missed in MT5:       {len(bt_not_match_rows)}")
    print(f" ⚠️ MT5 Trades Not in Backtest:   {len(mt5_not_match_rows)}")
    print("=" * 115 + "\n")
