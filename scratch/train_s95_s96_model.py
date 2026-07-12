import sys
import os
import pandas as pd
import numpy as np
import MetaTrader5 as mt5
from datetime import datetime
from sklearn.ensemble import RandomForestClassifier
import joblib

sys.path.append(os.path.abspath('.'))
import config
from sim_s30_backtest import fetch_bars
import strategy95
import strategy96
import ml_scoring

print("Fetching 180 days of data for training...")
config.mt5_initialize(mt5)
all_bars = fetch_bars('XAUUSD.iux', 'M5', 180, extra_bars=400)
if all_bars is None or len(all_bars) == 0:
    sys.exit("No bars fetched.")

cfg_s95 = {"CONFIRMATION_TYPE": "htf_trend", "RSI_FILTER_ENABLED": True, "RSI_BUY_MIN": 40.0, "RSI_SELL_MAX": 60.0, "TIME_FILTER_ENABLED": True, "PD_ZONE_FILTER_ENABLED": True, "ML_FILTER_ENABLED": False}
cfg_s96 = {"CONFIRMATION_TYPE": "htf_trend", "RSI_FILTER_ENABLED": True, "RSI_BUY_MIN": 40.0, "RSI_SELL_MAX": 60.0, "TIME_FILTER_ENABLED": True, "PD_ZONE_FILTER_ENABLED": False, "ML_FILTER_ENABLED": False}

X = []
y = []

print("Simulating trades to build ML dataset...")
for i in range(200, len(all_bars)-1):
    slice_ = all_bars[i-199:i+1]
    dt_bkk = datetime.fromtimestamp(slice_[-1]['time'])
    
    # Process S95
    sig95 = strategy95.detect_s95(slice_, tf='M5', dt_bkk=dt_bkk, cfg=cfg_s95)
    if sig95 and sig95.get('signal') in ['BUY', 'SELL']:
        entry = sig95['entry']
        sl, tp = sig95['sl'], sig95['tp']
        outcome = 'OPEN'
        for j in range(i+1, len(all_bars)):
            h, l = all_bars[j]['high'], all_bars[j]['low']
            if sig95['signal'] == 'BUY':
                if l <= sl: outcome = 0; break
                elif h >= tp: outcome = 1; break
            else:
                if h >= sl: outcome = 0; break
                elif l <= tp: outcome = 1; break
        
        if outcome != 'OPEN':
            features = ml_scoring.extract_features('XAUUSD.iux', 'M5', sig95['signal'], entry, dt_bkk, historical_rates=slice_)
            fv = [features.get("hour_of_day", 12), features.get("is_buy", 0), features.get("is_sell", 0),
                  features.get("rsi_approx", 50.0), features.get("atr_approx", 20.0), features.get("ema_dist", 0.0),
                  features.get("z_score", 0.0), features.get("bb_width", 1.0), features.get("adx_val", 25.0)]
            X.append(fv)
            y.append(outcome)

    # Process S96
    sig96 = strategy96.detect_s96(slice_, tf='M5', dt_bkk=dt_bkk, cfg=cfg_s96)
    if sig96 and sig96.get('signal') in ['BUY', 'SELL']:
        entry = sig96['entry']
        sl, tp = sig96['sl'], sig96['tp']
        outcome = 'OPEN'
        for j in range(i+1, len(all_bars)):
            h, l = all_bars[j]['high'], all_bars[j]['low']
            if sig96['signal'] == 'BUY':
                if l <= sl: outcome = 0; break
                elif h >= tp: outcome = 1; break
            else:
                if h >= sl: outcome = 0; break
                elif l <= tp: outcome = 1; break
        
        if outcome != 'OPEN':
            features = ml_scoring.extract_features('XAUUSD.iux', 'M5', sig96['signal'], entry, dt_bkk, historical_rates=slice_)
            fv = [features.get("hour_of_day", 12), features.get("is_buy", 0), features.get("is_sell", 0),
                  features.get("rsi_approx", 50.0), features.get("atr_approx", 20.0), features.get("ema_dist", 0.0),
                  features.get("z_score", 0.0), features.get("bb_width", 1.0), features.get("adx_val", 25.0)]
            X.append(fv)
            y.append(outcome)

print(f"Extracted {len(X)} trades for training. Training model...")
if len(X) > 0:
    clf = RandomForestClassifier(n_estimators=100, max_depth=5, random_state=42)
    clf.fit(X, y)
    joblib.dump(clf, 'ml_model.pkl')
    print(f"Model saved to ml_model.pkl. Training Accuracy: {clf.score(X, y)*100:.2f}%")
else:
    print("No trades found to train.")

mt5.shutdown()
