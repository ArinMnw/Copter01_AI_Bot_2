import backtest_S20_6_runner_mt5 as runner
import MetaTrader5 as mt5

days_list = [30, 60, 90, 120, 180]
for d in days_list:
    print(f"\n======================================")
    print(f"   BACKTEST FOR {d} DAYS")
    print(f"======================================")
    runner.run_backtest(days=d, tf_input="all", sid_target="20.6", compound_pct=2.0)

mt5.shutdown()
