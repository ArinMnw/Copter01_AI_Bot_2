# -*- coding: utf-8 -*-
"""test_fx_eurusd.py
Exploratory institutional test for Major Forex Pairs: EURUSD.iux, GBPUSD.iux, USDJPY.iux
"""
import sys
import os
import bisect
import numpy as np
import pandas as pd
from datetime import datetime, timezone, timedelta
import MetaTrader5 as mt5

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from goal_s20_53_to_100 import init_mt5, run_simulation
from run_master_s20_marathon_201_to_300 import compute_marathon_300_synergies, make_stages

def run_pair_sim(symbol, tp_r=13.43, stages=None):
    if stages is None:
        stages = make_stages(55)

    sinfo = mt5.symbol_info(symbol)
    digits = sinfo.digits
    point = sinfo.point
    contract_size = sinfo.trade_contract_size
    tick_val = sinfo.trade_tick_value
    
    # 0.01 lot dollar value per 1.0 price unit
    # For EURUSD: 0.01 * 100,000 = 1,000 USD per 1.0 price change
    # For USDJPY: 0.01 * 100,000 / price JPY = tick_val per point / tick
    if "JPY" in symbol:
        point_val = (contract_size * 0.01) / 154.0 # ~$6.49 USD per 1.0 JPY move (0.01 lot)
    else:
        point_val = (contract_size * 0.01) # 1,000.0 USD per 1.0 move for EURUSD / GBPUSD

    now = datetime.now(timezone.utc)
    start_dt = now - timedelta(days=365)

    rates = {tf: mt5.copy_rates_range(symbol, getattr(mt5, f"TIMEFRAME_{tf}"), start_dt, now) for tf in ['H4','H3','H2','H1','M30','M20','M15','M12']}
    m5_bars = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M5, 0, 75000)
    m5_times = [int(r['time']) for r in m5_bars]
    m5_len = len(m5_bars)

    dfs = {tf: compute_marathon_300_synergies(r) for tf, r in rates.items()}

    # Extract setups adapted to FX point/digits
    setups = []
    min_atr = 2.0 * point # relative min ATR instead of 0.05
    min_sl_buf = 2.0 * point

    for tf, df_tf in dfs.items():
        for cur in df_tf.to_dict('records'):
            if pd.isna(cur['atr']) or cur['atr'] <= min_atr or cur['range'] < 0.45 * cur['atr'] or cur['vol_ratio'] < 1.11:
                continue

            swept_low = (cur['low'] <= cur['swing_low_12']) or (cur['low'] <= cur['asian_low']) or \
                        (not pd.isna(cur.get('fvg_bull_zone')) and cur['low'] <= cur['fvg_bull_zone']) or \
                        (not pd.isna(cur.get('fibo_discount_382')) and cur['low'] <= cur['fibo_discount_382']) or \
                        (not pd.isna(cur.get('val_proxy')) and cur['low'] <= cur['val_proxy']) or \
                        (not pd.isna(cur.get('pdl')) and cur['low'] <= cur['pdl']) or \
                        cur['swept_htf_low'] or cur['is_spring']
            swept_high = (cur['high'] >= cur['swing_high_12']) or (cur['high'] >= cur['asian_high']) or \
                         (not pd.isna(cur.get('fvg_bear_zone')) and cur['high'] >= cur['fvg_bear_zone']) or \
                         (not pd.isna(cur.get('fibo_premium_618')) and cur['high'] >= cur['fibo_premium_618']) or \
                         (not pd.isna(cur.get('vah_proxy')) and cur['high'] >= cur['vah_proxy']) or \
                         (not pd.isna(cur.get('pdh')) and cur['high'] >= cur['pdh']) or \
                         cur['swept_htf_high'] or cur['is_utad']

            bull_ob = cur['bull_ob_zone']; bear_ob = cur['bear_ob_zone']
            ob_mitigated_bull = (not pd.isna(bull_ob) and cur['low'] <= bull_ob)
            ob_mitigated_bear = (not pd.isna(bear_ob) and cur['high'] >= bear_ob)
            bpr_tap_bull = (cur['has_bpr'] and cur['low'] <= cur['bpr_high'] and cur['high'] >= cur['bpr_low'])
            bpr_tap_bear = (cur['has_bpr'] and cur['high'] >= cur['bpr_low'] and cur['low'] <= cur['bpr_high'])
            is_abs_buy = cur['is_absorption_buy']; is_abs_sell = cur['is_absorption_sell']
            ifvg_buy = cur['ifvg_tap_buy']; ifvg_sell = cur['ifvg_tap_sell']
            bb_buy = (not pd.isna(cur.get('breaker_bull_zone')) and cur['low'] <= cur['breaker_bull_zone'])
            bb_sell = (not pd.isna(cur.get('breaker_bear_zone')) and cur['high'] >= cur['breaker_bear_zone'])
            is_overlap = cur['is_ldn_ny_overlap']

            has_wick_buy = (cur['lower_wick_pct'] >= 0.14) or (cur['lower_wick'] >= 1.1 * cur['body'])
            has_wick_sell = (cur['upper_wick_pct'] >= 0.14) or (cur['upper_wick'] >= 1.1 * cur['body'])
            closed_high = cur['close'] >= (cur['low'] + 0.45 * cur['range'])
            closed_low = cur['close'] <= (cur['high'] - 0.45 * cur['range'])
            is_comp = cur['compression_ratio'] <= 0.70

            sig = "BUY" if ((swept_low or ob_mitigated_bull or bpr_tap_bull or is_abs_buy or ifvg_buy or bb_buy) and has_wick_buy and closed_high) else \
                  ("SELL" if ((swept_high or ob_mitigated_bear or bpr_tap_bear or is_abs_sell or ifvg_sell or bb_sell) and has_wick_sell and closed_low) else None)

            if sig:
                is_hc = (ob_mitigated_bull if sig == "BUY" else ob_mitigated_bear) or \
                        (bpr_tap_bull if sig == "BUY" else bpr_tap_bear) or \
                        (is_abs_buy if sig == "BUY" else is_abs_sell) or \
                        (ifvg_buy if sig == "BUY" else ifvg_sell) or \
                        (bb_buy if sig == "BUY" else bb_sell)

                sl_mult = (0.188 - 0.002 if is_overlap else 0.188) if is_hc else (0.190 if is_comp else 0.195)
                sl_buf = max(sl_mult * cur['atr'], min_sl_buf)
                active_depth = 0.121 if is_hc else (0.124 if is_comp else 0.125)

                entry = round(cur['low'] + (active_depth * cur['lower_wick']), digits) if sig == "BUY" else round(cur['high'] - (active_depth * cur['upper_wick']), digits)
                sl = round(cur['low'] - sl_buf, digits) if sig == "BUY" else round(cur['high'] + sl_buf, digits)
                risk = entry - sl if sig == "BUY" else sl - entry

                if risk > 0:
                    setups.append({"time": int(cur['time']), "signal": sig, "entry": entry, "sl": sl, "risk": risk, "atr": cur['atr'], "tf": tf})

    setups = sorted(setups, key=lambda x: x['time'])
    print(f"[{symbol}] Total Raw Setups generated: {len(setups)}")

    # Sim execution with proper digits and stage ratchet locking
    be_trigger = 0.8
    busy_until = 0
    trades = 0; wins = 0; bes = 0; losses = 0
    total_pnl = 0.0
    peak = 0.0; max_dd = 0.0
    monthly_stats = {}

    for s in setups:
        s_time = s['time']
        if s_time < busy_until:
            continue
        m5_start = bisect.bisect_right(m5_times, s_time)
        if m5_start >= m5_len:
            continue

        entry = s['entry']
        sl = s['sl']
        risk = s['risk']
        sig = s['signal']

        filled = False; fill_idx = -1
        for i in range(m5_start, min(m5_start + 12, m5_len)):
            b = m5_bars[i]
            if sig == 'BUY' and b['low'] <= entry:
                filled = True; fill_idx = i; break
            elif sig == 'SELL' and b['high'] >= entry:
                filled = True; fill_idx = i; break

        if not filled:
            continue

        tp = round(entry + (tp_r * risk), digits) if sig == "BUY" else round(entry - (tp_r * risk), digits)
        be_target = round(entry + (be_trigger * risk), digits) if sig == "BUY" else round(entry - (be_trigger * risk), digits)

        stage_levels = []
        for trig, amt in stages:
            t_price = round(entry + (trig * risk), digits) if sig == "BUY" else round(entry - (trig * risk), digits)
            s_price = round(entry + (amt * risk), digits) if sig == "BUY" else round(entry - (amt * risk), digits)
            stage_levels.append((t_price, s_price))

        current_sl = sl
        be_active = False
        active_stage_idx = -1
        trade_pnl = 0.0
        outcome = None
        exit_time = m5_bars[fill_idx]['time']
        m_key = datetime.fromtimestamp(exit_time, tz=timezone.utc).strftime('%Y-%m')

        for k in range(fill_idx + 1, min(fill_idx + 288, m5_len)):
            b = m5_bars[k]
            exit_time = b['time']

            if sig == "BUY":
                if b['low'] <= current_sl:
                    if active_stage_idx >= 0:
                        outcome = "WIN"
                        trade_pnl = (stage_levels[active_stage_idx][1] - entry) * point_val
                    elif be_active:
                        outcome = "BE"; trade_pnl = 0.0
                    else:
                        outcome = "LOSS"; trade_pnl = -risk * point_val
                    break

                if b['high'] >= tp:
                    outcome = "WIN"; trade_pnl = (tp - entry) * point_val
                    break

                for s_idx in range(len(stage_levels) - 1, -1, -1):
                    t_price, s_price = stage_levels[s_idx]
                    if b['high'] >= t_price:
                        if s_idx > active_stage_idx:
                            active_stage_idx = s_idx
                            current_sl = max(current_sl, s_price)
                        break

                if active_stage_idx == -1 and b['high'] >= be_target:
                    be_active = True
                    current_sl = max(current_sl, entry)

            else:  # SELL
                if b['high'] >= current_sl:
                    if active_stage_idx >= 0:
                        outcome = "WIN"
                        trade_pnl = (entry - stage_levels[active_stage_idx][1]) * point_val
                    elif be_active:
                        outcome = "BE"; trade_pnl = 0.0
                    else:
                        outcome = "LOSS"; trade_pnl = -risk * point_val
                    break

                if b['low'] <= tp:
                    outcome = "WIN"; trade_pnl = (entry - tp) * point_val
                    break

                for s_idx in range(len(stage_levels) - 1, -1, -1):
                    t_price, s_price = stage_levels[s_idx]
                    if b['low'] <= t_price:
                        if s_idx > active_stage_idx:
                            active_stage_idx = s_idx
                            current_sl = min(current_sl, s_price)
                        break

                if active_stage_idx == -1 and b['low'] <= be_target:
                    be_active = True
                    current_sl = min(current_sl, entry)

        if outcome is None:
            final_b = m5_bars[min(fill_idx + 288, m5_len - 1)]
            final_c = final_b['close']
            exit_time = final_b['time']
            pnl_pts = (final_c - entry) if sig == "BUY" else (entry - final_c)
            trade_pnl = pnl_pts * point_val
            if trade_pnl > 0.001: outcome = "WIN"
            elif trade_pnl < -0.001: outcome = "LOSS"
            else: outcome = "BE"

        busy_until = exit_time
        trades += 1
        total_pnl += trade_pnl
        if outcome == "WIN": wins += 1
        elif outcome == "BE": bes += 1
        else: losses += 1

        if total_pnl > peak: peak = total_pnl
        dd = peak - total_pnl
        if dd > max_dd: max_dd = dd

        if m_key not in monthly_stats:
            monthly_stats[m_key] = {"trades": 0, "wins": 0, "bes": 0, "losses": 0, "pnl": 0.0}
        monthly_stats[m_key]["trades"] += 1
        if outcome == "WIN": monthly_stats[m_key]["wins"] += 1
        elif outcome == "BE": monthly_stats[m_key]["bes"] += 1
        else: monthly_stats[m_key]["losses"] += 1
        monthly_stats[m_key]["pnl"] += trade_pnl

    wr = wins / trades * 100 if trades else 0
    nlr = (wins + bes) / trades * 100 if trades else 0
    print(f"[{symbol}] RESULTS: Trades={trades} | Wins={wins} | BEs={bes} | Losses={losses} | WR={wr:.1f}% | NLR={nlr:.1f}% | Net PnL=${total_pnl:,.2f} | MaxDD=${max_dd:.2f}")
    return {
        "symbol": symbol, "trades": trades, "wins": wins, "bes": bes, "losses": losses,
        "wr": wr, "nlr": nlr, "pnl": total_pnl, "max_dd": max_dd, "monthly_stats": monthly_stats
    }

def main():
    if not init_mt5():
        print("MT5 Failed")
        return

    pairs = ['EURUSD.iux', 'GBPUSD.iux', 'USDJPY.iux']
    for p in pairs:
        mt5.symbol_select(p, True)

    results = {}
    for p in pairs:
        results[p] = run_pair_sim(p)

    mt5.shutdown()

    print("\n" + "=" * 90)
    print(" SUMMARY FOREX BENCHMARK (STRICT 0.01 LOT)")
    print("=" * 90)
    for p, r in results.items():
        print(f"Pair: {p:12} | Trades: {r['trades']:5} | WR: {r['wr']:5.1f}% | NLR: {r['nlr']:5.1f}% | Net PnL: ${r['pnl']:10,.2f} | MaxDD: ${r['max_dd']:6.2f}")

if __name__ == '__main__':
    main()
