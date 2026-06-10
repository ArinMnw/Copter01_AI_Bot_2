# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')

import argparse
import MetaTrader5 as mt5
from datetime import datetime, timezone, timedelta
import config
import json
import os

BKK = timezone(timedelta(hours=getattr(config, "TZ_OFFSET", 7)))

# Parse arguments
parser = argparse.ArgumentParser(description='Check S10 details for a specific parent bar')
parser.add_argument('--tf', type=str, required=True,
                    help='HTF timeframe of the parent candle (e.g. H4, H12, D1, H1, M30, M15)')
parser.add_argument('--time', type=str, required=True,
                    help='Parent bar open time in Bangkok timezone (YYYY-MM-DD HH:MM)')
parser.add_argument('--symbol', type=str, required=False,
                    help='Symbol to check (e.g. XAUUSD.iux). Defaults to config.SYMBOL')
args = parser.parse_args()

# Import sim_s10_backtest to get timezone offset logic and simulation engine
import sim_s10_backtest
from sim_s10_backtest import backtest_tf, TF_MAP, to_bkk, TF_SECONDS, sync_strategy10_runtime_config
import strategy10
from strategy10 import strategy_10, _armed_states, reset_mtf_state, _HTF_TO_LTF

HTF_CONSTANTS = {
    "D1":  mt5.TIMEFRAME_D1,
    "H12": mt5.TIMEFRAME_H12,
    "H4":  mt5.TIMEFRAME_H4,
    "H1":  mt5.TIMEFRAME_H1,
    "M30": mt5.TIMEFRAME_M30,
    "M15": mt5.TIMEFRAME_M15,
}

def parse_bkk_dt(dt_str: str) -> datetime:
    for fmt in ('%Y-%m-%dT%H:%M:%S', '%Y-%m-%d %H:%M:%S', '%Y-%m-%dT%H:%M', '%Y-%m-%d %H:%M'):
        try:
            return datetime.strptime(dt_str, fmt)
        except ValueError:
            continue
    raise ValueError(f'Invalid datetime format: {dt_str}. Use YYYY-MM-DD HH:MM')


def mt5_range_dt_from_ts(ts: int) -> datetime:
    dt = to_bkk(ts)
    return datetime(dt.year, dt.month, dt.day, dt.hour, dt.minute, dt.second, tzinfo=BKK)

def run_diagnostics():
    if not mt5.initialize():
        print('MT5 init failed:', mt5.last_error())
        return

    # Reset config to defaults and load config state from bot_state
    import importlib
    importlib.reload(config)
    restore_info = config.restore_runtime_state()
    
    # Set symbol
    state_symbol = ""
    try:
        if os.path.exists(config.STATE_FILE):
            with open(config.STATE_FILE, "r", encoding="utf-8") as f:
                state_symbol = str((json.load(f) or {}).get("symbol", "") or "")
    except Exception:
        state_symbol = ""
    symbol = args.symbol or state_symbol or config.SYMBOL
    config.set_runtime_symbol(symbol)
    sim_s10_backtest.SYMBOL = symbol
    sync_strategy10_runtime_config()

    htf_tf = args.tf.upper()
    if htf_tf not in _HTF_TO_LTF:
        print(f"❌ Error: Timeframe '{args.tf}' is not a valid HTF timeframe.")
        print(f"Supported HTFs: {list(_HTF_TO_LTF.keys())}")
        mt5.shutdown()
        return

    ltf_tf = _HTF_TO_LTF[htf_tf]
    ltf_val = TF_MAP[ltf_tf]

    parent_bkk = parse_bkk_dt(args.time)
    parent_time_str = parent_bkk.strftime('%Y-%m-%d %H:%M')

    print(f'Symbol         : {symbol}')
    print(f'Restore        : {restore_info}')
    print(f'HTF Timeframe  : {htf_tf}')
    print(f'LTF Timeframe  : {ltf_tf}')
    print(f'Parent BKK Time: {parent_time_str}')
    print(f'S10 Settings   : active_strategies[10]={config.active_strategies.get(10, False)}')
    print(f'                 CRT_BAR_MODE={getattr(config, "CRT_BAR_MODE", "2bar")} | CRT_WAIT_HTF_CLOSE={getattr(config, "CRT_WAIT_HTF_CLOSE", False)}')
    print(f'                 PDFIBOPLUS_ENABLED={getattr(config, "PDFIBOPLUS_ENABLED", True)} | PD_SKIP_SIDS=9,10,13,14,15,16')
    print('=' * 65)

    if not config.active_strategies.get(10, False):
        print("❌ S10 is disabled (OFF) in config! Skip diagnostics.")
        mt5.shutdown()
        return

    # Fetch HTF rates around the parent bar (fetch 5000 candles to make sure we cover historical range)
    htf_const = HTF_CONSTANTS[htf_tf]
    print(f"Fetching HTF ({htf_tf}) rates from MT5...")
    htf_rates = mt5.copy_rates_from_pos(symbol, htf_const, 0, 5000)
    if htf_rates is None or len(htf_rates) == 0:
        print(f"❌ Failed to fetch HTF rates for symbol {symbol}")
        mt5.shutdown()
        return

    # Find the parent candle
    pi = None
    for idx, r in enumerate(htf_rates):
        if to_bkk(r['time']).strftime('%Y-%m-%d %H:%M') == parent_time_str:
            pi = idx
            break

    if pi is None:
        first_bkk = to_bkk(htf_rates[0]['time']).strftime('%Y-%m-%d %H:%M')
        last_bkk = to_bkk(htf_rates[-1]['time']).strftime('%Y-%m-%d %H:%M')
        print(f"❌ Parent candle at {parent_time_str} not found in HTF data.")
        print(f"Available HTF ({htf_tf}) range in history: {first_bkk} to {last_bkk}")
        mt5.shutdown()
        return

    parent = htf_rates[pi]
    p_open  = float(parent["open"])
    p_high  = float(parent["high"])
    p_low   = float(parent["low"])
    p_close = float(parent["close"])
    p_range = p_high - p_low
    p_body = abs(p_close - p_open)
    p_body_pct = (p_body / p_range if p_range > 0 else 0) * 100

    from strategy10 import crt_min_range_price
    min_range = crt_min_range_price()
    min_body_pct = getattr(config, "CRT_PARENT_MIN_BODY_PCT", 0.50) * 100

    print(f"\n--- Parent Candle Diagnostics ({htf_tf}) ---")
    print(f"Time (BKK) : {parent_time_str}")
    print(f"Open       : {p_open:.2f}")
    print(f"High       : {p_high:.2f}")
    print(f"Low        : {p_low:.2f}")
    print(f"Close      : {p_close:.2f}")
    print(f"Range      : {p_range:.2f} (Required >= {min_range:.2f}) -> {'✅ PASS' if p_range >= min_range else '❌ FAIL'}")
    print(f"Body Pct   : {p_body_pct:.1f}% (Required >= {min_body_pct:.1f}%) -> {'✅ PASS' if p_body_pct >= min_body_pct else '❌ FAIL'}")

    # Check setup validity on parent bar
    parent_valid = (p_range >= min_range) and (p_body_pct >= min_body_pct)
    if not parent_valid:
        print("\n❌ Setup failed: Parent bar does not meet range or body constraints. No setup possible.")
        mt5.shutdown()
        return

    # Scan forward from the parent candle to find potential sweep candles on HTF
    print(f"\n--- Subsequent HTF Sweep Scan ---")
    sweeps_found = []
    
    # We only scan up to 15 bars after parent to find sweep, similar to live
    scan_limit = min(pi + 15, len(htf_rates))
    for si in range(pi + 1, scan_limit):
        sweep = htf_rates[si]
        sweep_bkk = to_bkk(sweep['time']).strftime('%Y-%m-%d %H:%M')
        
        rates_slice = [
            {'time': int(r['time']), 'open': float(r['open']), 'high': float(r['high']), 'low': float(r['low']), 'close': float(r['close'])}
            for r in htf_rates[:si+1]
        ]
        
        res = strategy10._strategy_10_htf(rates_slice)
        
        if res.get("signal") in ("BUY", "SELL"):
            candles = res.get("candles", [])
            # Check if the detected parent bar is indeed our target parent bar
            if len(candles) > 0 and int(candles[0].get("time", 0)) == int(parent["time"]):
                sweeps_found.append((si, sweep, res))
                print(f"  [{sweep_bkk}] ✅ Setup Armed! Signal: {res['signal']} | Sweep Depth: {res.get('reason', '').split('depth:')[1].split(' ')[0] if 'depth:' in res.get('reason','') else 'n/a'}")
                print(f"    Reason: {res['reason'].replace(chr(10), ' | ')}")
        else:
            # Custom diagnosis for why this si candle isn't a sweep of our parent
            s_open  = float(sweep["open"])
            s_high  = float(sweep["high"])
            s_low   = float(sweep["low"])
            s_close = float(sweep["close"])
            min_depth = p_range * float(config.CRT_SWEEP_DEPTH_PCT)

            print(f"  [{sweep_bkk}] Checking as potential sweep:")
            if s_low < p_low:
                if p_close >= p_open:
                    print(f"    ❌ Invalid BUY sweep: Parent candle is not RED (close={p_close:.2f} >= open={p_open:.2f}).")
                elif s_close <= p_low:
                    print(f"    ❌ Invalid BUY sweep: Close ({s_close:.2f}) did not close back inside parent low ({p_low:.2f}).")
                elif (p_low - s_low) < min_depth:
                    print(f"    ❌ Invalid BUY sweep: Sweep depth ({p_low - s_low:.2f}) is shallower than required ({min_depth:.2f}).")
                else:
                    print(f"    ❌ Invalid BUY sweep: Failed intermediate high/low broken or internal checks.")
            elif s_high > p_high:
                if p_close <= p_open:
                    print(f"    ❌ Invalid SELL sweep: Parent candle is not GREEN (close={p_close:.2f} <= open={p_open:.2f}).")
                elif s_close >= p_high:
                    print(f"    ❌ Invalid SELL sweep: Close ({s_close:.2f}) did not close back inside parent high ({p_high:.2f}).")
                elif (s_high - p_high) < min_depth:
                    print(f"    ❌ Invalid SELL sweep: Sweep depth ({s_high - p_high:.2f}) is shallower than required ({min_depth:.2f}).")
                else:
                    print(f"    ❌ Invalid SELL sweep: Failed intermediate high/low broken or internal checks.")
            else:
                print(f"    ❌ Did not sweep parent boundaries (H:{p_high:.2f}, L:{p_low:.2f} | Sweep H:{s_high:.2f}, L:{s_low:.2f}).")

    if not sweeps_found:
        print("\n❌ No valid sweep candles found after the parent candle in HTF history.")
        mt5.shutdown()
        return

    # Choose the first valid sweep to run diagnostics on
    si, sweep, res = sweeps_found[0]
    sweep_time = int(sweep["time"])
    direction = res["signal"]

    # Mock copy_rates_from_pos to speed up the backtest by limiting the data range to parent_time +- 2.5 days
    orig_copy_rates_from_pos = mt5.copy_rates_from_pos
    
    TF_DURATIONS = {
        mt5.TIMEFRAME_M1: 60,
        mt5.TIMEFRAME_M5: 300,
        mt5.TIMEFRAME_M15: 900,
        mt5.TIMEFRAME_M30: 1800,
        mt5.TIMEFRAME_H1: 3600,
        mt5.TIMEFRAME_H4: 14400,
        mt5.TIMEFRAME_H12: 43200,
        mt5.TIMEFRAME_D1: 86400,
    }

    def mock_copy_rates_from_pos(sym, tf, position, count):
        tf_secs = TF_DURATIONS.get(tf, 60)
        lookback_bars = 2000 if tf_secs < 3600 else 500
        start_ts = int(parent['time']) - lookback_bars * tf_secs
        end_ts = int(parent['time']) + int(2.5 * 86400)

        return mt5.copy_rates_range(sym, tf, mt5_range_dt_from_ts(start_ts), mt5_range_dt_from_ts(end_ts))

    mt5.copy_rates_from_pos = mock_copy_rates_from_pos

    try:
        # Run the backtest using sim_s10_backtest to get actual trade results
        # We set sim start to 1 day before parent to build HHLL and run the backtest
        print(f"\nRunning backtest simulation starting from parent time - 1 day...")
        parent_utc = datetime.fromtimestamp(parent['time'], tz=timezone.utc)
        sim_s10_backtest.SINCE = parent_utc - timedelta(days=1)
        
        # Execute simulation
        all_trades = backtest_tf(ltf_tf, ltf_val)
    finally:
        # Restore original function
        mt5.copy_rates_from_pos = orig_copy_rates_from_pos
    
    # Filter trades belonging to this parent candle
    parent_trades = [t for t in all_trades if t.get('s10_parent_time') == int(parent['time'])]
    if parent_trades:
        print(f"\n🎉 Simulation found {len(parent_trades)} trade(s) for this parent candle:")
        grand_total = 0.0
        ltf_of_htf = _HTF_TO_LTF.get(htf_tf, "")
        tf_display = f"{htf_tf} ({ltf_of_htf})" if ltf_of_htf else htf_tf
        
        for idx, t in enumerate(parent_trades):
            et = t['entry_time'].strftime('%Y-%m-%d %H:%M')
            ct = t['close_time'].strftime('%Y-%m-%d %H:%M') if t['close_type'] not in ('OPEN', 'OPEN_PENDING') else 'OPEN'
            pnl_s = f'{"+" if t["pnl"]>=0 else ""}{t["pnl"]:.2f}'

            print(f"\n--- Trade #{idx+1} ---")
            print(f"  [{tf_display}] {et} {t['signal']} [{t.get('pattern', 'S10')}]")
            print(f"  Entry  = {t['entry']:.2f} | SL = {t['sl']:.2f} | TP = {t['tp']:.2f}")
            close_label = t['close_type']
            if close_label == 'PD_FAIL':
                close_label = 'PD_FILL_FAIL' if t.get('pd_result') == 'FAIL' else 'PD_PENDING_FAIL'
            print(f"  Result -> {close_label} @ {t.get('close_price', 0):.2f} [{ct}]  PnL={pnl_s} USD")
            
            if t.get('cancel_reason'):
                print(f"  Cancel Reason: {t['cancel_reason']}")

            print(f"  HTF Details:")
            print(f"    HTF TF = {htf_tf} | Bar Mode = {t.get('s10_bar_mode', '2bar')}")
            print(f"    Parent Bar: High = {p_high:.2f}, Low = {p_low:.2f}, Range = {p_range:.2f} | Time = {parent_time_str}")
            print(f"    Sweep Time: {to_bkk(sweep_time).strftime('%d-%m %H:%M')}")

            m1_p = t.get('s10_m1_price')
            m1_t = t.get('s10_m1_time')
            m2_p = t.get('s10_m2_price')
            m2_t = t.get('s10_m2_time')
            m3_p = t.get('s10_m3_price')
            m3_t = t.get('s10_m3_time')
            print(f"  Models Info:")
            print(f"    Model 1 (OB.open): {f'{m1_p:.2f}' if m1_p is not None else 'n/a'} @ {m1_t or 'n/a'}")
            print(f"    Model 2 (FVG 98%): {f'{m2_p:.2f}' if m2_p is not None else 'n/a'} @ {m2_t or 'n/a'}")
            print(f"    Model 3 (MSS)    : {f'{m3_p:.2f}' if m3_p is not None else 'n/a'} @ {m3_t or 'n/a'}")

            # PD Fibo Plus details
            pd_val = t.get('pd_result')
            if pd_val:
                fibo_pct = t.get('pd_fibo_pct')
                pd_round = t.get('pd_round', 1)
                pd_fibo_str = f" ({fibo_pct:.1f}%)" if fibo_pct is not None else ""
                print(f"  PD Fibo Plus:")
                print(f"    PD Result: {pd_val}{pd_fibo_str} [Round {pd_round}]")
                if t.get('pd_h') is not None and t.get('pd_l') is not None:
                    h_t = to_bkk(t['pd_h_time']).strftime('%d-%m %H:%M') if t.get('pd_h_time') else '?'
                    l_t = to_bkk(t['pd_l_time']).strftime('%d-%m %H:%M') if t.get('pd_l_time') else '?'
                    print(f"    PD Range : H = {t['pd_h']:.2f} [{h_t}] | L = {t['pd_l']:.2f} [{l_t}]")
    if not parent_trades:
        print("\nℹ️ No trades/orders were generated in backtest for this parent candle. Performing trigger checks...")
        # Diagnose why it didn't trigger
        # Fetch LTF rates around the armed window
        ltf_secs = TF_SECONDS[ltf_tf]
        htf_secs = TF_SECONDS[htf_tf]
        start_ltf = parent['time'] - 100 * ltf_secs
        end_ltf = sweep_time + 2 * htf_secs
        
        ltf_rates_raw = mt5.copy_rates_range(
            symbol,
            ltf_val,
            mt5_range_dt_from_ts(start_ltf),
            mt5_range_dt_from_ts(end_ltf),
        )
        if ltf_rates_raw is None or len(ltf_rates_raw) == 0:
            print(f"❌ Failed to fetch LTF ({ltf_tf}) rates for details check.")
        else:
            ltf_bars = [
                {'time': int(r['time']), 'open': float(r['open']), 'high': float(r['high']), 'low': float(r['low']), 'close': float(r['close'])}
                for r in ltf_rates_raw
            ]
            
            # Reconstruct armed state
            state = {
                "direction":      direction,
                "sl_target":      float(res["sl"]),
                "tp_target":      float(res["tp"]),
                "armed_at":       int(sweep_time),
                "htf_tf":         htf_tf,
                "ltf_tf":         ltf_tf,
                "candles":        res.get("candles", []),
                "pattern_base":   res.get("pattern", ""),
                "pre_arm":        False,
                "fired_tickets":  [],
                "awaiting_choch": False,
                "fire_count":     0,
            }
            
            # Find the index of sweep_time in ltf_bars
            sweep_idx = next((i for i, b in enumerate(ltf_bars) if b['time'] >= sweep_time), None)
            
            if sweep_idx is None:
                print(f"❌ Sweep time {to_bkk(sweep_time)} not found in LTF bars.")
            else:
                backward_mode = getattr(config, "CRT_WAIT_HTF_CLOSE", False)
                
                # Check phase 1 failed push
                p1_idx = strategy10._find_phase1_failed_push(ltf_bars, direction, sweep_time, p_high, p_low, backward=backward_mode)
                
                print(f"\n--- LTF Trigger Breakdown ---")
                if p1_idx is not None:
                    p1_bar = ltf_bars[p1_idx]
                    print(f"  - Phase 1 (failed-push) : ✅ FOUND at {to_bkk(p1_bar['time']).strftime('%Y-%m-%d %H:%M')} (Close = {p1_bar['close']:.2f})")
                    
                    # Calculate models
                    m1_entry = strategy10._calc_model1_ob(ltf_bars, p1_idx + 1, direction, sweep_time)
                    m2_entry = strategy10._calc_model2_fvg(ltf_bars, p1_idx + 1, direction)
                    m3_entry = strategy10._calc_model3_mss(ltf_bars, p1_idx, direction, sweep_time)
                    
                    m3_val = m3_entry[0] if m3_entry is not None else None
                    print(f"  - Model 1 (OB.open)     : {'FOUND = ' + f'{m1_entry:.2f}' if m1_entry is not None else '❌ NOT FOUND'}")
                    print(f"  - Model 2 (FVG 98%)     : {'FOUND = ' + f'{m2_entry:.2f}' if m2_entry is not None else '❌ NOT FOUND'}")
                    print(f"  - Model 3 (MSS)         : {'FOUND = ' + f'{m3_val:.2f}' if m3_val is not None else '❌ NOT FOUND'}")
                    
                    if m1_entry is None or m2_entry is None:
                        print(f"  - ❌ Trigger Blocked    : Both Model 1 AND Model 2 must be found to trigger.")
                    else:
                        sl = float(state["sl_target"])
                        m1_ok, m1_dist, m1_min = strategy10._sl_distance_ok(direction, m1_entry, sl)
                        m2_ok, m2_dist, m2_min = strategy10._sl_distance_ok(direction, m2_entry, sl)
                        print(f"  - Model 1 SL Distance   : Actual = {m1_dist:.2f}, Required >= {m1_min:.2f} ({'✅ OK' if m1_ok else '❌ TOO TIGHT'})")
                        print(f"  - Model 2 SL Distance   : Actual = {m2_dist:.2f}, Required >= {m2_min:.2f} ({'✅ OK' if m2_ok else '❌ TOO TIGHT'})")
                        if not m1_ok or not m2_ok:
                            print(f"  - ❌ Trigger Blocked    : Fails minimum SL distance guard.")
                else:
                    print(f"  - Phase 1 (failed-push) : ❌ NOT FOUND")
                    print(f"    (LTF bars did not produce a red bar closing below parent low for BUY, or green bar closing above parent high for SELL).")

    mt5.shutdown()

if __name__ == '__main__':
    run_diagnostics()
