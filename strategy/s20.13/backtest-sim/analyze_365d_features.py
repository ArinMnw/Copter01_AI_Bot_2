import MetaTrader5 as mt5
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from strategy20_13_19 import strategy_20_13_19

def run_feature_analysis():
    path = r'd:\Project\Copter01_AI_Bot_2\profiles\demo\demo-iux-2101114448\mt5\terminal64.exe'
    if not mt5.initialize(path=path):
        print("MT5 initialize failed")
        return
        
    end = datetime.now()
    start = end - timedelta(days=365)
    rates = mt5.copy_rates_range("XAUUSD.iux", mt5.TIMEFRAME_H1, start, end)
    if rates is None or len(rates) == 0:
        print("Failed to get rates")
        mt5.shutdown()
        return

    all_trades_log = []
    closed = True
    signal = None
    entry = 0.0
    sl = 0.0
    tp = 0.0
    be_active = False
    be_trigger = 0.0
    open_i = 0
    trade_features = {}

    for i in range(100, len(rates) - 1):
        slice_rates = rates[:i]
        res = strategy_20_13_19(pd.DataFrame(slice_rates), tf="H1")
        
        if closed and res.get("signal") in ["BUY", "SELL"]:
            signal = res["signal"]
            entry = res["entry"]
            sl = res["sl"]
            tp = res["tp"]
            
            df_slice = pd.DataFrame(slice_rates)
            high_low = df_slice['high'] - df_slice['low']
            high_close = np.abs(df_slice['high'] - df_slice['close'].shift())
            low_close = np.abs(df_slice['low'] - df_slice['close'].shift())
            tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
            atr = tr.rolling(window=14).mean().iloc[-1]
            cur = df_slice.iloc[-1]
            
            delta = df_slice['close'].diff()
            gain14 = (delta.where(delta > 0, 0)).rolling(14).mean()
            loss14 = (-delta.where(delta < 0, 0)).rolling(14).mean()
            rsi14 = 100 - (100 / (1 + (gain14/loss14))).iloc[-1]
            
            gain7 = (delta.where(delta > 0, 0)).rolling(7).mean()
            loss7 = (-delta.where(delta < 0, 0)).rolling(7).mean()
            rsi7 = 100 - (100 / (1 + (gain7/loss7))).iloc[-1]
            
            sma20 = df_slice['close'].rolling(20).mean().iloc[-1]
            std20 = df_slice['close'].rolling(20).std().iloc[-1]
            z_score = (cur['close'] - sma20) / (std20 + 0.0001)
            
            plus_dm = df_slice['high'].diff()
            minus_dm = df_slice['low'].shift() - df_slice['low']
            plus_dm = np.where((plus_dm > minus_dm) & (plus_dm > 0), plus_dm, 0.0)
            minus_dm = np.where((minus_dm > plus_dm) & (minus_dm > 0), minus_dm, 0.0)
            tr14 = tr.rolling(14).sum()
            plus_di14 = 100 * (pd.Series(plus_dm).rolling(14).sum() / tr14)
            minus_di14 = 100 * (pd.Series(minus_dm).rolling(14).sum() / tr14)
            dx = 100 * (np.abs(plus_di14 - minus_di14) / (plus_di14 + minus_di14))
            adx = dx.rolling(14).mean().iloc[-1]
            di_diff = (plus_di14 - minus_di14).iloc[-1]
            
            range_val = cur['high'] - cur['low']
            body_val = abs(cur['close'] - cur['open'])
            body_pct = body_val / (range_val + 0.0001)
            atr_pct = (atr / cur['close']) * 100.0
            
            vol_ma20 = df_slice['tick_volume'].rolling(20).mean().iloc[-1]
            vol_ratio = cur['tick_volume'] / (vol_ma20 + 1.0)
            
            ema50 = df_slice['close'].ewm(span=50, adjust=False).mean().iloc[-1]
            ema200 = df_slice['close'].ewm(span=200, adjust=False).mean().iloc[-1]
            dist_ema50 = cur['close'] - ema50
            dist_ema200 = cur['close'] - ema200
            
            dt = datetime.fromtimestamp(cur['time']) + timedelta(hours=7)
            
            trade_features = {
                "time": dt.strftime('%Y-%m-%d %H:%M'),
                "hour": dt.hour,
                "dayofweek": dt.weekday(),
                "type": signal,
                "rsi14": rsi14,
                "rsi7": rsi7,
                "adx": adx,
                "di_diff": di_diff,
                "z_score": z_score,
                "atr_pct": atr_pct,
                "body_pct": body_pct,
                "vol_ratio": vol_ratio,
                "dist_ema50": dist_ema50,
                "dist_ema200": dist_ema200
            }
            
            be_trigger = entry + (abs(entry - sl) * 1.0) if signal == "BUY" else entry - (abs(entry - sl) * 1.0)
            be_active = False
            closed = False
            open_i = i
            
        elif not closed:
            cur_bar = rates[i]
            future_high = cur_bar['high']
            future_low = cur_bar['low']
            
            if signal == "BUY":
                if future_low <= sl:
                    trade_features["reason"] = "BE" if be_active else "SL"
                    all_trades_log.append(trade_features)
                    closed = True
                elif future_high >= tp:
                    trade_features["reason"] = "TP"
                    all_trades_log.append(trade_features)
                    closed = True
                elif not be_active and future_high >= be_trigger:
                    be_active = True
                    sl = entry
            elif signal == "SELL":
                if future_high >= sl:
                    trade_features["reason"] = "BE" if be_active else "SL"
                    all_trades_log.append(trade_features)
                    closed = True
                elif future_low <= tp:
                    trade_features["reason"] = "TP"
                    all_trades_log.append(trade_features)
                    closed = True
                elif not be_active and future_low <= be_trigger:
                    be_active = True
                    sl = entry

    mt5.shutdown()
    df_out = pd.DataFrame(all_trades_log)
    df_out.to_csv("trades_365d_features.csv", index=False)
    print("Saved trades_365d_features.csv with", len(df_out), "rows.")
    print("Breakdown:")
    print(pd.crosstab(df_out['type'], df_out['reason']))

if __name__ == "__main__":
    run_feature_analysis()
