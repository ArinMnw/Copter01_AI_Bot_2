$days = 30, 60, 90, 120, 150, 365, 700
foreach ($d in $days) {
    python strategy/s20.14/backtest-sim/fast_backtest.py --days $d --tf all --compound 2
}
