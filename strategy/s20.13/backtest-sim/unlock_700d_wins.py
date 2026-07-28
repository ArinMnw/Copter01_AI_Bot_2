import MetaTrader5 as mt5
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from strategy20_13_22 import compute_indicators_df, evaluate_bar, get_fuel_multiplier
import config

def audit_individual_filters(days=700, symbol="XAUUSD.iux", compound=1.5):
    path = r'd:\Project\Copter01_AI_Bot_2\profiles\demo\demo-iux-2101114448\mt5\terminal64.exe'
    if not mt5.initialize(path=path): return
    end_time = datetime.now()
    start_time = end_time - timedelta(days=days)
    rates = mt5.copy_rates_range(symbol, mt5.TIMEFRAME_H1, start_time, end_time)
    
    df_master = compute_indicators_df(rates)
    df_master['upper_wick'] = df_master['high'] - np.maximum(df_master['open'], df_master['close'])
    df_master['lower_wick'] = np.minimum(df_master['open'], df_master['close']) - df_master['low']
    df_master['upper_wick_pct'] = df_master['upper_wick'] / (df_master['range'] + 0.0001)
    df_master['lower_wick_pct'] = df_master['lower_wick'] / (df_master['range'] + 0.0001)
    df_master['dist_ema50'] = df_master['close'] - df_master['ema_50']
    df_master['dist_ema200'] = df_master['close'] - df_master['ema_200']
    df_master['hour'] = df_master['time_dt'].dt.hour

    # Let's see all base PA setup bars (Engulfing + Sweep) without ANY BUY or SELL feature filters!
    pa_bars = []
    for idx in range(100, len(rates) - 10):
        current_bar = df_master.iloc[idx]
        prev_bar = df_master.iloc[idx - 1]
        lookback_bars = df_master.iloc[idx - 14 : idx - 3]
        local_low = lookback_bars['low'].min()
        local_high = lookback_bars['high'].max()
        recent_3 = df_master.iloc[idx - 3 : idx]
        
        cur_range = current_bar['high'] - current_bar['low']
        is_strong_range = cur_range >= (0.8 * current_bar['atr'])
        if not is_strong_range: continue
        
        hour = current_bar['time_dt'].hour
        if hour in [12, 13, 23, 0, 8, 9]: continue # Basic time traps
        
        # Check BUY PA
        sweep_buy = recent_3['low'].min() < local_low
        engulf_buy = current_bar['close'] > prev_bar['high']
        instant_sweep_buy = current_bar['low'] < local_low and current_bar['close'] > prev_bar['high']
        if (sweep_buy and engulf_buy) or instant_sweep_buy:
            if hour in [2, 19, 17]: continue
            if current_bar['rsi'] < 35: continue
            sweep_bottom = min(recent_3['low'].min(), current_bar['low'])
            sl = sweep_bottom - config.SL_BUFFER(current_bar['atr'])
            tp = sweep_bottom + current_bar['atr'] * 2.6 * np.sqrt(720/60)
            pa_bars.append((idx, "BUY", current_bar['close'], sl, tp, current_bar))
            continue
            
        # Check SELL PA
        sweep_sell = recent_3['high'].max() > local_high
        engulf_sell = current_bar['close'] < prev_bar['low']
        instant_sweep_sell = current_bar['high'] > local_high and current_bar['close'] < prev_bar['low']
        if (sweep_sell and engulf_sell) or instant_sweep_sell:
            if current_bar['rsi'] > 60: continue
            sweep_top = max(recent_3['high'].max(), current_bar['high'])
            sl = sweep_top + config.SL_BUFFER(current_bar['atr'])
            tp = sweep_top - current_bar['atr'] * 2.6 * np.sqrt(1440/60)
            pa_bars.append((idx, "SELL", current_bar['close'], sl, tp, current_bar))

    print(f"Total raw PA setups found in 700 days: {len(pa_bars)}")
    
    # Now let's evaluate each raw PA setup's future outcome (WIN, LOSS, BE)!
    outcomes = []
    for idx, signal, entry, sl, tp, cur in pa_bars:
        future_rates = rates[idx+1:]
        be_trig = entry + ((tp - entry) * 0.4) if signal == "BUY" else entry - ((entry - tp) * 0.4)
        be_act = False
        outcome = "OPEN"
        for f_bar in future_rates:
            if signal == "BUY":
                if f_bar['low'] <= sl:
                    outcome = "BE" if be_act else "LOSS"; break
                elif f_bar['high'] >= tp:
                    outcome = "WIN"; break
                if not be_act and f_bar['high'] >= be_trig: be_act = True; sl = entry
            elif signal == "SELL":
                if f_bar['high'] >= sl:
                    outcome = "BE" if be_act else "LOSS"; break
                elif f_bar['low'] <= tp:
                    outcome = "WIN"; break
                if not be_act and f_bar['low'] <= be_trig: be_act = True; sl = entry
        outcomes.append((idx, signal, outcome, cur))
        
    df_out = pd.DataFrame([{"idx": idx, "signal": sig, "outcome": out, **cur.to_dict()} for idx, sig, out, cur in outcomes])
    print(f"Raw PA Outcomes -> Wins: {len(df_out[df_out['outcome']=='WIN'])}, Losses: {len(df_out[df_out['outcome']=='LOSS'])}, BE: {len(df_out[df_out['outcome']=='BE'])}")
    
    df_out.to_csv("700d_raw_pa_outcomes.csv", index=False)
    print("Saved to 700d_raw_pa_outcomes.csv")
    mt5.shutdown()

if __name__ == "__main__":
    audit_individual_filters()
