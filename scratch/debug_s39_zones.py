import sys
sys.path.insert(0, ".")
import MetaTrader5 as mt5
import config
from strategy39 import S39_DEFAULTS, _calc_atr, _find_active_zone
import sim_s30_backtest as s30sim

mt5.initialize()
days = 60
entry_bars = s30sim.fetch_bars(config.SYMBOL, "M5", days, extra_bars=200)
print(f"n bars={len(entry_bars)}")

for base_atr_mult, impulse_atr_mult in [(0.5, 1.2), (0.7, 1.0), (1.0, 0.8), (1.5, 0.6)]:
    cfg = dict(S39_DEFAULTS)
    cfg.update(BASE_ATR_MULT=base_atr_mult, IMPULSE_ATR_MULT=impulse_atr_mult)
    found = 0
    win_size = cfg["MAX_ZONE_AGE_BARS"] + cfg["BASE_BARS"] + 30
    for j in range(win_size + 5, len(entry_bars) - 1, 5):
        window = entry_bars[max(0, j - win_size):j]
        atr = _calc_atr(window, 14)
        if not atr:
            continue
        z = _find_active_zone(window, atr, cfg)
        if z:
            found += 1
    print(f"base_atr={base_atr_mult} impulse_atr={impulse_atr_mult} -> zones found in sample: {found}")
mt5.shutdown()
