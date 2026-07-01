import argparse
import sys, os
import copy
from datetime import datetime, timedelta, timezone

sys.path.append(os.path.join(os.path.dirname(__file__), "strategy", "s20.11"))
from strategy20_11 import strategy_20_11

import mt5_worker as mt5

# Override config if needed
import config
config.S20_11_ENABLED = True
for tf in config.S20_11_TF_ENABLED:
    config.S20_11_TF_ENABLED[tf] = True

def parse_args():
    parser = argparse.ArgumentParser(description="Backtest S20.11 Candle Strength")
    parser.add_argument("--tf", type=str, default="all", help="Timeframe (e.g. M1, M5, all)")
    parser.add_argument("--symbol", type=str, default="", help="Symbol (default: profile SYMBOL)")
    parser.add_argument("--days", type=int, default=0, help="Days to backtest (0 = run multiple)")
    parser.add_argument("--compound", type=float, default=2.0, help="Risk percentage for compounding (default 2)")
    return parser.parse_args()

def main():
    args = parse_args()
    
    if not config.mt5_initialize(mt5, resolve=False):
        print("MT5 initialize failed")
        return

    args.symbol = config.profile_symbol(args.symbol or config.SYMBOL, mt5, set_runtime=True)
    mt5.symbol_select(args.symbol, True)
    info = mt5.symbol_info(args.symbol)
    if not info:
        print(f"Symbol {args.symbol} not found")
        return
        
    point = info.point
    spread = info.spread * point
    
    tfs = {
        "M1": mt5.TIMEFRAME_M1,
        "M5": mt5.TIMEFRAME_M5,
        "M15": mt5.TIMEFRAME_M15,
        "M30": mt5.TIMEFRAME_M30,
        "H1": mt5.TIMEFRAME_H1,
        "H4": mt5.TIMEFRAME_H4,
        "H12": mt5.TIMEFRAME_H12,
        "D1": mt5.TIMEFRAME_D1,
    }
    
    if args.tf != "all":
        tfs = {args.tf: tfs[args.tf]}
        
    if args.days > 0:
        days_list = [args.days]
    else:
        days_list = [30, 60, 90, 120, 180]
    
    for days in days_list:
        results = []
        
        end_time = datetime.now()
        start_time = end_time - timedelta(days=days)
        
        # Lot calculation based on 2% risk of $1000 balance
        balance = 1000.0
        risk_pct = args.compound / 100.0
        contract_size = info.trade_contract_size if info.trade_contract_size > 0 else 100.0
        
        print(f"\n--- Running Backtest S20.11 for {days} days ---")
        
        for tf_name, tf_code in tfs.items():
            rates = mt5.copy_rates_range(args.symbol, tf_code, start_time, end_time)
            if rates is None or len(rates) < 50:
                results.append((tf_name, 0, 0, 0, 0.0, "-", 0.0))
                continue
                
            trades = 0
            wins = 0
            losses = 0
            net_pl = 0.0
            patterns = {}
            
            # Simulate bar by bar
            total_bars = len(rates) - 1
            for i in range(40, total_bars):
                if i % 5000 == 0:
                    print(f"  [{tf_name}] Processing bar {i}/{total_bars}...")
                sub_rates = rates[:i+1]
                res = strategy_20_11(sub_rates, tf_name)
                
                if res and res.get("signal") in ("BUY", "SELL"):
                    sig = res["signal"]
                    entry = res["entry"]
                    sl = res["sl"]
                    tp = res["tp"]
                    pattern = res["pattern"]
                    
                    trade_pnl = 0.0
                    trade_result = None
                    
                    sl_dist = abs(entry - sl)
                    if sl_dist == 0: sl_dist = 1.0
                    risk_amt = balance * risk_pct
                    lot = risk_amt / (sl_dist * contract_size)
                    lot = max(0.01, round(lot, 2))
                    
                    for j in range(i+1, min(len(rates), i+2000)):
                        c = rates[j]
                        if sig == "BUY":
                            if c['low'] <= sl:
                                trade_result = "LOSS"
                                exec_price = sl - spread
                                trade_pnl = -(entry - exec_price) * contract_size * lot
                                break
                            elif c['high'] >= tp:
                                trade_result = "WIN"
                                exec_price = tp - spread
                                trade_pnl = (exec_price - entry) * contract_size * lot
                                break
                        else: # SELL
                            if c['high'] >= sl:
                                trade_result = "LOSS"
                                exec_price = sl + spread
                                trade_pnl = -(exec_price - entry) * contract_size * lot
                                break
                            elif c['low'] <= tp:
                                trade_result = "WIN"
                                exec_price = tp + spread
                                trade_pnl = (entry - exec_price) * contract_size * lot
                                break
                                
                    if trade_result:
                        trades += 1
                        balance += trade_pnl
                        net_pl += trade_pnl
                        patterns[pattern] = patterns.get(pattern, 0) + 1
                        
                        if trade_result == "WIN":
                            wins += 1
                        else:
                            losses += 1
                            
            win_rate = (wins / trades * 100.0) if trades > 0 else 0.0
            most_pattern = max(patterns, key=patterns.get) if patterns else "-"
            results.append((tf_name, trades, wins, losses, win_rate, most_pattern, net_pl))
            
        print(f"\n| กรอบเวลา (Timeframe) | จำนวนการเข้าเทรดทั้งหมด (Trades) | เคสที่ชนะ (Win) | เคสที่แพ้ (Loss) | อัตราแพ้ชนะ (Win Rate %) | แนวราคา/ระดับสัญญาณเทคนิคอลที่เข้าบ่อยที่สุด | ผลรวมกำไรขาดทุนสุทธิ (Net P&L ($)) |")
        print(f"|---|---|---|---|---|---|---|")
        
        total_trades = 0
        total_wins = 0
        total_losses = 0
        total_net = 0.0
        
        for r in results:
            tf_name, tr, w, l, wr, pat, net = r
            print(f"| **{tf_name}** | {tr} | {w} | {l} | {wr:.1f}% | {pat} | {net:,.2f} |")
            total_trades += tr
            total_wins += w
            total_losses += l
            total_net += net
            
        total_wr = (total_wins / total_trades * 100.0) if total_trades > 0 else 0.0
        print(f"| **สรุปรวมทุก TF** | {total_trades} | {total_wins} | {total_losses} | {total_wr:.1f}% | - | {total_net:,.2f} |")
        
    mt5.shutdown()

if __name__ == "__main__":
    main()
