import MetaTrader5 as mt5
import config
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config
from datetime import datetime, timezone, timedelta

config.mt5_initialize(mt5)
config.restore_runtime_state()

SYMBOL = config.SYMBOL
tf_val = mt5.TIMEFRAME_M5

start_dt = datetime(2026, 5, 29, 12, 0)
end_dt = datetime(2026, 5, 30, 6, 0)

rates = mt5.copy_rates_range(SYMBOL, tf_val, start_dt, end_dt)
import sim_s10_backtest
from sim_s10_backtest import to_bkk

bkk_rates = []
if rates is not None:
    for r in rates:
        bkk_dt = to_bkk(r['time'])
        # Compare as UTC to match the timezone of to_bkk (which is UTC + offset added as timedelta)
        if bkk_dt <= datetime(2026, 5, 30, 2, 0, tzinfo=timezone.utc):
            bkk_rates.append(r)

parent_high = 4570.46
parent_low = 4512.72
direction = "SELL"
armed_at_dt = datetime(2026, 5, 29, 22, 0, tzinfo=timezone.utc)

armed_at = None
for r in bkk_rates:
    if to_bkk(r['time']) == armed_at_dt:
        armed_at = r['time']
        break

print(f"Total rates up to 02:00 BKK: {len(bkk_rates)}")
print(f"armed_at (22:00 BKK): {armed_at} (BKK: {to_bkk(armed_at) if armed_at else 'None'})")

if armed_at and bkk_rates:
    from strategy10 import _find_phase1_failed_push, _calc_model1_ob, _calc_model2_fvg, _calc_model3_mss
    
    # 1. FORWARD SEARCH
    def find_phase1_forward(rates, direction, armed_at, p_high, p_low):
        for i in range(1, len(rates)):
            if int(rates[i]["time"]) <= armed_at:
                continue
            bo = float(rates[i]["open"])
            bc = float(rates[i]["close"])
            if direction == "BUY" and bc < bo and bc < p_low:
                return i
            if direction == "SELL" and bc > bo and bc > p_high:
                return i
        return None

    p1_f = find_phase1_forward(bkk_rates, direction, armed_at, parent_high, parent_low)
    m3_f = _calc_model3_mss(bkk_rates, p1_f, direction, armed_at) if p1_f else None
    
    m1_f = None
    m2_f = None
    if p1_f:
        for idx in range(p1_f + 1, len(bkk_rates)):
            if m1_f is None:
                v = _calc_model1_ob(bkk_rates, idx, direction, armed_at)
                if v is not None:
                    m1_f = (v, idx)
            if m2_f is None:
                v = _calc_model2_fvg(bkk_rates, idx, direction)
                if v is not None:
                    m2_f = (v, idx)

    print("FORWARD:")
    print(f"  Phase 1: idx={p1_f} @ {to_bkk(bkk_rates[p1_f]['time']) if p1_f else 'None'}")
    print(f"  Model 1: {m1_f[0] if m1_f else 'None'} @ {to_bkk(bkk_rates[m1_f[1]]['time']) if m1_f else 'None'}")
    print(f"  Model 2: {m2_f[0] if m2_f else 'None'} @ {to_bkk(bkk_rates[m2_f[1]]['time']) if m2_f else 'None'}")
    print(f"  Model 3: {m3_f if m3_f else 'None'}")

    # 2. BACKWARD SEARCH (Searching backwards from the end of rates down to armed_at)
    def find_phase1_backward(rates, direction, armed_at, p_high, p_low):
        for i in range(len(rates) - 1, -1, -1):
            if int(rates[i]["time"]) <= armed_at:
                break
            bo = float(rates[i]["open"])
            bc = float(rates[i]["close"])
            if direction == "BUY" and bc < bo and bc < p_low:
                return i
            if direction == "SELL" and bc > bo and bc > p_high:
                return i
        return None

    p1_b = find_phase1_backward(bkk_rates, direction, armed_at, parent_high, parent_low)
    m3_b = _calc_model3_mss(bkk_rates, p1_b, direction, armed_at) if p1_b else None
    
    m1_b = None
    m2_b = None
    if p1_b:
        for idx in range(len(bkk_rates) - 1, p1_b, -1):
            if m1_b is None:
                v = _calc_model1_ob(bkk_rates, idx, direction, armed_at)
                if v is not None:
                    m1_b = (v, idx)
            if m2_b is None:
                v = _calc_model2_fvg(bkk_rates, idx, direction)
                if v is not None:
                    m2_b = (v, idx)

    print("\nBACKWARD (Lookback from end):")
    print(f"  Phase 1: idx={p1_b} @ {to_bkk(bkk_rates[p1_b]['time']) if p1_b else 'None'}")
    print(f"  Model 1: {m1_b[0] if m1_b else 'None'} @ {to_bkk(bkk_rates[m1_b[1]]['time']) if m1_b else 'None'}")
    print(f"  Model 2: {m2_b[0] if m2_b else 'None'} @ {to_bkk(bkk_rates[m2_b[1]]['time']) if m2_b else 'None'}")
    print(f"  Model 3: {m3_b if m3_b else 'None'}")

mt5.shutdown()
