import argparse
import MetaTrader5 as mt5
from datetime import datetime, timedelta, timezone
import pandas as pd
import config
from strategy20_7 import strategy_20_7
import itertools

def to_bkk(ts):
    return datetime.fromtimestamp(ts, tz=timezone.utc) + timedelta(hours=7)

def simulate_trades(formatted_rates, tf, target_pts, atr_mult, risk_percent, initial_cap=1000):
    balance = initial_cap
    trades = 0
    wins = 0
    losses = 0
    
    # Store temporary config values
    orig_s20_7 = getattr(config, "S20_7_ENABLED", False)
    config.S20_7_ENABLED = True
    
    for i in range(50, len(formatted_rates)):
        if balance <= 0:
            break
            
        slice_rates = formatted_rates[i-50:i]
        
        # We need to temporarily patch strategy_20_7 or we can just calculate sl/tp here
        # Actually strategy_20_7 uses hardcoded 14.0 for target_points_usd and 1.5 for ATR.
        # Let's call it to get the signal and entry, but override sl/tp.
        res = strategy_20_7(slice_rates, tf=tf, dt_bkk=to_bkk(slice_rates[-1]['time']))
        
        if res.get("signal") in ("BUY", "SELL"):
            sig = res["signal"]
            entry = res["entry"]
            
            # Recalculate SL and TP based on parameters
            from mt5_utils import calc_atr
            atr = calc_atr(slice_rates[:-1], 14) or 1.0
            sl_dist = atr * atr_mult
            sl = entry - sl_dist if sig == "BUY" else entry + sl_dist
            tp = entry + target_pts if sig == "BUY" else entry - target_pts
            
            triggered = False
            trade_result = None
            
            for j in range(i, len(formatted_rates)):
                future_bar = formatted_rates[j]
                
                if not triggered:
                    if sig == "BUY" and future_bar['low'] <= entry:
                        triggered = True
                    elif sig == "SELL" and future_bar['high'] >= entry:
                        triggered = True
                
                if triggered:
                    if sig == "BUY":
                        if future_bar['low'] <= sl:
                            trade_result = "LOSS"
                            break
                        if future_bar['high'] >= tp:
                            trade_result = "WIN"
                            break
                    else:
                        if future_bar['high'] >= sl:
                            trade_result = "LOSS"
                            break
                        if future_bar['low'] <= tp:
                            trade_result = "WIN"
                            break
                            
            if trade_result:
                trades += 1
                # Risk calculation
                risk_amount = balance * (risk_percent / 100.0)
                pts_sl = abs(entry - sl)
                
                # 1 standard lot = 1 USD per point for XAUUSD (if point=0.01)
                # Actually MT5 gold 1 standard lot (volume 1.0) means 1 tick (0.01) = 1 USD
                # 1 pt (e.g. 2400.00 to 2401.00 = 100 ticks = $100).
                # Wait, if entry=2400, sl=2397. pts_sl = 3.0 = 300 ticks.
                # If we lose 3.0 pts at 1.0 lot, we lose $300.
                lot_size = risk_amount / (pts_sl * 100) if pts_sl > 0 else 0.01
                # Cap lot size to a realistic max for $1000-$5000 account (e.g. max leverage 1:500, max lot = balance / 500)
                max_lot = balance / 500.0
                if lot_size > max_lot: lot_size = max_lot
                if lot_size < 0.01: lot_size = 0.01
                
                if trade_result == "WIN":
                    wins += 1
                    pts_win = abs(tp - entry)
                    balance += (pts_win * 100) * lot_size
                else:
                    losses += 1
                    balance -= (pts_sl * 100) * lot_size
    
    config.S20_7_ENABLED = orig_s20_7
    return balance, trades, wins, losses

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=30)
    args = parser.parse_args()
    
    if not mt5.initialize():
        print("initialize() failed")
        return
        
    symbol = config.SYMBOL
    tfs = ["M5", "M15"]
    
    bars_per_day = {"M5": 288, "M15": 96}
    
    print(f"--- Optimizing S20.7 to hit $1000/day on {symbol} ---")
    
    target_pts_list = [10.0, 14.0, 20.0]
    atr_mult_list = [1.0, 1.5, 2.0]
    risk_list = [5.0, 10.0]
    
    best_results = []
    
    for tf in tfs:
        mt5_tf = mt5.TIMEFRAME_M5 if tf == "M5" else mt5.TIMEFRAME_M15
        num_bars = bars_per_day[tf] * args.days + 50
        
        rates = mt5.copy_rates_from_pos(symbol, mt5_tf, 0, num_bars)
        if rates is None or len(rates) < 50:
            continue
            
        formatted_rates = [{"time": r['time'], "open": r['open'], "high": r['high'], "low": r['low'], "close": r['close']} for r in rates]
        
        best_bal = 0
        best_params = None
        best_stats = None
        
        for t_pts, a_mult, risk in itertools.product(target_pts_list, atr_mult_list, risk_list):
            bal, tr, w, l = simulate_trades(formatted_rates, tf, t_pts, a_mult, risk)
            if bal > best_bal:
                best_bal = bal
                best_params = (t_pts, a_mult, risk)
                best_stats = (tr, w, l)
                
        if best_params:
            tr, w, l = best_stats
            wr = (w/tr*100) if tr > 0 else 0
            daily_profit = (best_bal - 1000) / args.days
            print(f"[{tf}] Best Params -> TP:{best_params[0]}pt, ATRx{best_params[1]}, Risk:{best_params[2]}%")
            print(f"      Trades: {tr}, WinRate: {wr:.1f}%")
            print(f"      Final Balance: ${best_bal:.2f} (Avg ${daily_profit:.2f}/day)")
            best_results.append({
                "TF": tf, "Params": best_params, "DailyProfit": daily_profit, "WR": wr
            })

    mt5.shutdown()
    
    print("\n--- Summary: Can we hit $1000/day? ---")
    total_daily = sum(r["DailyProfit"] for r in best_results)
    if total_daily >= 1000:
        print(f"✅ YES! Combined Daily Profit: ${total_daily:.2f}")
    else:
        print(f"❌ NO. Combined Daily Profit: ${total_daily:.2f}. Needs more leverage or better win rate.")

if __name__ == "__main__":
    main()
