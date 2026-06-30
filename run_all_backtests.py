import subprocess
import sys
import io

sys.stdout.reconfigure(encoding='utf-8')

def run_backtest(days):
    print(f"\n==============================================")
    print(f"       BACKTEST FOR {days} DAYS")
    print(f"==============================================")
    cmd = [sys.executable, "sim_s20_8_backtest.py", "--days", str(days)]
    # Stream the command output directly to console
    subprocess.run(cmd)

if __name__ == "__main__":
    days_list = [30, 60, 90, 120, 180]
    for d in days_list:
        run_backtest(d)
    
    print("\nMulti-timeframe backtest complete!")
