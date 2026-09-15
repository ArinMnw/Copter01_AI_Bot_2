import argparse
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from datetime import datetime, timedelta, timezone
from sim_strategy_backtest import backtest, parse_bkk, BKK

def get_session(dt_str):
    hour = datetime.fromisoformat(dt_str).hour
    if 5 <= hour < 14:
        return 'Asia'
    elif 14 <= hour < 19:
        return 'London'
    else:
        return 'NewYork'

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--day", type=int, default=365)
    parser.add_argument("--start")
    parser.add_argument("--end")
    parser.add_argument("--compare", action="store_true")
    
    args = parser.parse_args()

    tfs = ['M1', 'M5', 'M15', 'M30', 'H1', 'H4', 'D1']
    
    months = max(1, args.day // 30)
    end_bkk = parse_bkk(args.end)
    
    print(f"==================================================")
    print(f"Backtesting S20.15 for {args.day} days (~{months} months)")
    print(f"Timeframes: {', '.join(tfs)}")
    if args.start:
        print(f"Start: {args.start}")
    print(f"End: {end_bkk.isoformat()}")
    if args.compare:
        print(f"Compare: Enabled")
    print(f"==================================================")
        
    for tf in tfs:
        print(f"\n[ TF: {tf} ]")
        try:
            summary, trades = backtest(
                strategy_id=2015,
                months=months,
                tf_name=tf,
                spread=0.20,
                lot=0.01,
                end_bkk=end_bkk,
                lookback=300
            )
            print(summary)
            
            # Session Analysis
            session_stats = {
                'Asia': {'trades': 0, 'wins': 0, 'pnl': 0.0},
                'London': {'trades': 0, 'wins': 0, 'pnl': 0.0},
                'NewYork': {'trades': 0, 'wins': 0, 'pnl': 0.0}
            }
            
            for trade in trades:
                session = get_session(trade["signal_time"])
                session_stats[session]['trades'] += 1
                if trade["profit"] > 0:
                    session_stats[session]['wins'] += 1
                session_stats[session]['pnl'] += trade["profit"]
                
            print("--- Session Analysis ---")
            for session, stats in session_stats.items():
                win_rate = (stats['wins'] / stats['trades'] * 100) if stats['trades'] > 0 else 0
                print(f"  {session:<8}: Trades={stats['trades']:<4} | WinRate={win_rate:>5.2f}% | PnL={stats['pnl']:>8.2f} USD")
                
        except Exception as e:
            print(f"Error on {tf}: {e}")

if __name__ == "__main__":
    main()
