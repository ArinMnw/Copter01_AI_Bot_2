import subprocess
import sys
import os

sys.stdout.reconfigure(encoding='utf-8')

portfolios_days = {
    "P13": 550,
    "P16": 550,
    "18-Way": 550,
    "AF22": 365,
    "AF34": 365,
    "AF47": 365,
    "LTS44": 550,
    "LTS890": 550,
    "LTS999": 550,
    "LTS_AVENGERS_BASE": 420,
    "LTS_AVENGERS_P34": 420,
    "LTS_AVENGERS_HIGH_RISK": 550,
    "LTS_AVENGERS_ULTRA_SAFE": 550,
    "LTS_AVENGERS_HIGH_FREQ": 550,
    "S101": 550,
    "S102": 550,
    "S105": 550,
    "S106": 550,
    "S111": 550,
}

def main():
    print("🏁 Starting to run all demo portfolios backtests...")
    for pf, days in portfolios_days.items():
        print(f"\n==================================================")
        print(f"🚀 Running subprocess: run_backtest_sim.py for {pf} ({days} days)")
        print(f"==================================================")
        try:
            script_path = os.path.join("strategy", "demo_portfolio", "backtest-sim", "run_backtest_sim.py")
            subprocess.run(
                [sys.executable, script_path, "--portfolio", pf, "--days", str(days)],
                check=True
            )
        except Exception as e:
            print(f"❌ Error running backtest for {pf}: {e}")
            
    print("\n🎉 Completed all demo portfolios backtests!")

if __name__ == "__main__":
    main()
