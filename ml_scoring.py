import os
import json
import random
from datetime import datetime

try:
    from sklearn.ensemble import RandomForestClassifier
    import numpy as np
    import joblib
    ML_AVAILABLE = True
except ImportError:
    ML_AVAILABLE = False

MODEL_PATH = "ml_model.pkl"
_model = None

def _load_model():
    global _model
    if ML_AVAILABLE and os.path.exists(MODEL_PATH):
        try:
            _model = joblib.load(MODEL_PATH)
        except Exception as e:
            print(f"[ML Scoring] Error loading model: {e}")
            try:
                from bot_log import log_error
                log_error("ML_SCORING_ERROR", f"load model: {type(e).__name__}: {e}")
            except Exception:
                pass

def extract_features(symbol, tf, signal, current_price, time_bkk):
    """
    Extract basic + advanced features for ML model.
    Fetches real RSI, ATR, EMA distance, Z-Score, BB Width, and ADX from MT5.
    """
    import mt5_worker as mt5
    import pandas as pd
    import numpy as np
    
    rsi_val, atr_val, ema_dist = 50.0, 20.0, 0.0
    z_score, bb_width, adx_val = 0.0, 1.0, 25.0
    
    if mt5.terminal_info() is not None:
        rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M15, 0, 100)
        if rates is not None and len(rates) > 80:
            df = pd.DataFrame(rates)
            
            # 1. RSI
            delta = df['close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            rsi_series = 100 - (100 / (1 + rs))
            
            # 2. ATR
            high_low = df['high'] - df['low']
            high_close = np.abs(df['high'] - df['close'].shift())
            low_close = np.abs(df['low'] - df['close'].shift())
            true_range = np.max(pd.concat([high_low, high_close, low_close], axis=1), axis=1)
            atr_series = true_range.rolling(14).mean()
            
            # 3. EMA Dist
            ema_series = df['close'].ewm(span=50, adjust=False).mean()
            
            # 4. Z-Score (20 period)
            sma_20 = df['close'].rolling(20).mean()
            std_20 = df['close'].rolling(20).std()
            z_score_series = (df['close'] - sma_20) / std_20
            
            # 5. Bollinger Band Width
            upper_bb = sma_20 + (2 * std_20)
            lower_bb = sma_20 - (2 * std_20)
            bb_width_series = (upper_bb - lower_bb) / sma_20
            
            # 6. ADX (14 period)
            plus_dm = df['high'].diff()
            minus_dm = df['low'].shift() - df['low']
            plus_dm = np.where((plus_dm > minus_dm) & (plus_dm > 0), plus_dm, 0.0)
            minus_dm = np.where((minus_dm > plus_dm) & (minus_dm > 0), minus_dm, 0.0)
            
            tr14 = true_range.rolling(14).sum()
            plus_di14 = 100 * (pd.Series(plus_dm).rolling(14).sum() / tr14)
            minus_di14 = 100 * (pd.Series(minus_dm).rolling(14).sum() / tr14)
            dx = 100 * (np.abs(plus_di14 - minus_di14) / (plus_di14 + minus_di14))
            adx_series = dx.rolling(14).mean()
            
            # Extract latest
            rsi_val = float(rsi_series.iloc[-1])
            atr_val = float(atr_series.iloc[-1])
            ema_dist = float(df['close'].iloc[-1] - ema_series.iloc[-1])
            z_score = float(z_score_series.iloc[-1])
            bb_width = float(bb_width_series.iloc[-1])
            adx_val = float(adx_series.iloc[-1])
            
            if np.isnan(rsi_val): rsi_val = 50.0
            if np.isnan(atr_val): atr_val = 20.0
            if np.isnan(ema_dist): ema_dist = 0.0
            if np.isnan(z_score): z_score = 0.0
            if np.isnan(bb_width): bb_width = 1.0
            if np.isnan(adx_val): adx_val = 25.0

    return {
        "hour_of_day": time_bkk.hour,
        "is_buy": 1 if signal.upper() == "BUY" else 0,
        "is_sell": 1 if signal.upper() == "SELL" else 0,
        "rsi_approx": rsi_val,
        "atr_approx": atr_val,
        "ema_dist": ema_dist,
        "z_score": z_score,
        "bb_width": bb_width,
        "adx_val": adx_val
    }

def predict_success_probability(features: dict) -> float:
    """
    Returns a probability score (0.0 to 1.0) of this setup being successful.
    """
    global _model
    if not ML_AVAILABLE:
        import random
        return random.uniform(0.4, 0.9)
        
    if _model is None:
        _load_model()
        
    if _model is None:
        return 0.55
        
    try:
        feature_values = [
            features.get("hour_of_day", 12),
            features.get("is_buy", 0),
            features.get("is_sell", 0),
            features.get("rsi_approx", 50.0),
            features.get("atr_approx", 20.0),
            features.get("ema_dist", 0.0),
            features.get("z_score", 0.0),
            features.get("bb_width", 1.0),
            features.get("adx_val", 25.0)
        ]
        
        prob = _model.predict_proba([feature_values])[0][1]
        return float(prob)
    except Exception as e:
        print(f"[ML Scoring] Prediction error: {e}")
        try:
            from bot_log import log_error
            log_error("ML_SCORING_ERROR", f"predict: {type(e).__name__}: {e}")
        except Exception:
            pass
        return 0.5

def score_signal(symbol, tf, signal, current_price, time_bkk):
    """
    Helper function to extract features and return probability score.
    Used by strategy_af.py
    """
    features = extract_features(symbol, tf, signal, current_price, time_bkk)
    return predict_success_probability(features)

def train_dummy_model():
    """
    Creates a dummy RandomForest model for demonstration.
    Run this once to create the ml_model.pkl file.
    """
    if not ML_AVAILABLE:
        print("Please 'pip install scikit-learn numpy joblib' first.")
        return
        
    print("Training dummy ML model with new features...")
    X = []
    y = []
    for _ in range(1000):
        hour = random.randint(0, 23)
        is_buy = random.choice([0, 1])
        is_sell = 1 - is_buy
        rsi = random.uniform(10, 90)
        atr = random.uniform(5, 60)
        ema_dist = random.uniform(-500, 500)
        z_score = random.uniform(-3.0, 3.0)
        bb_width = random.uniform(0.001, 0.02)
        adx_val = random.uniform(10, 60)
        
        success = 0
        if is_buy and rsi < 40 and z_score < -1: success = 1
        if is_sell and rsi > 60 and z_score > 1: success = 1
        if random.random() < 0.2: success = 1 - success
        
        X.append([hour, is_buy, is_sell, rsi, atr, ema_dist, z_score, bb_width, adx_val])
        y.append(success)
        
    clf = RandomForestClassifier(n_estimators=100, max_depth=5, random_state=42)
    clf.fit(X, y)
    joblib.dump(clf, MODEL_PATH)
    print(f"Model trained and saved to {MODEL_PATH}")

# Attempt to load model on module import
_load_model()

def train_from_mt5_history(days=30):
    """
    Train the ML model using real historical data from MT5.
    """
    if not ML_AVAILABLE:
        print("[ML Scoring] scikit-learn is not installed. Skipping training.")
        return False
        
    try:
        import mt5_worker as mt5
        import pandas as pd
        import numpy as np
        import config
        from datetime import timezone, timedelta
        
        if not mt5.initialize():
            print("[ML Scoring] MT5 initialize failed.")
            return False
            
        tz = timezone(timedelta(hours=7)) # BKK
        end_time = datetime.now(tz)
        start_time = end_time - timedelta(days=days)
        
        history_deals = mt5.history_deals_get(start_time, end_time)
        if not history_deals:
            print("[ML Scoring] No history deals found to train.")
            return False
            
        print(f"[ML Scoring] Found {len(history_deals)} deals. Fetching historical rates...")
        
        rates_start = start_time - timedelta(days=5)
        rates = mt5.copy_rates_range(config.SYMBOL, mt5.TIMEFRAME_M15, rates_start, end_time)
        df_rates = pd.DataFrame()
        if rates is not None and len(rates) > 0:
            df_rates = pd.DataFrame(rates)
            df_rates['time'] = pd.to_datetime(df_rates['time'], unit='s')
            df_rates.set_index('time', inplace=True)
            
            delta = df_rates['close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            df_rates['rsi'] = 100 - (100 / (1 + rs))
            
            high_low = df_rates['high'] - df_rates['low']
            high_close = np.abs(df_rates['high'] - df_rates['close'].shift())
            low_close = np.abs(df_rates['low'] - df_rates['close'].shift())
            true_range = np.max(pd.concat([high_low, high_close, low_close], axis=1), axis=1)
            df_rates['atr'] = true_range.rolling(14).mean()
            df_rates['ema50'] = df_rates['close'].ewm(span=50, adjust=False).mean()
            
            sma_20 = df_rates['close'].rolling(20).mean()
            std_20 = df_rates['close'].rolling(20).std()
            df_rates['z_score'] = (df_rates['close'] - sma_20) / std_20
            df_rates['bb_width'] = (4 * std_20) / sma_20
            
            plus_dm = df_rates['high'].diff()
            minus_dm = df_rates['low'].shift() - df_rates['low']
            plus_dm = np.where((plus_dm > minus_dm) & (plus_dm > 0), plus_dm, 0.0)
            minus_dm = np.where((minus_dm > plus_dm) & (minus_dm > 0), minus_dm, 0.0)
            tr14 = true_range.rolling(14).sum()
            plus_di14 = 100 * (pd.Series(plus_dm).rolling(14).sum() / tr14)
            minus_di14 = 100 * (pd.Series(minus_dm).rolling(14).sum() / tr14)
            dx = 100 * (np.abs(plus_di14 - minus_di14) / (plus_di14 + minus_di14))
            df_rates['adx'] = dx.rolling(14).mean()
            
            df_rates.bfill(inplace=True)

        df = pd.DataFrame(list(history_deals), columns=history_deals[0]._asdict().keys())
        df['time'] = pd.to_datetime(df['time'], unit='s')
        
        # Build position_id -> sid map from IN deals
        pos_sid_map = {}
        for _, row in df[df['entry'] == mt5.DEAL_ENTRY_IN].iterrows():
            pos_id = row['position_id']
            comment = str(row.get('comment', ''))
            sid = 0
            if "LTS" in comment:
                try:
                    sid = int(comment.split("LTS")[1].split("_")[0])
                except:
                    pass
            elif "_S" in comment:
                try:
                    sid = int(comment.split("_S")[1].split("_")[0])
                except:
                    pass
            pos_sid_map[pos_id] = sid
            
        df_out = df[df['entry'] == mt5.DEAL_ENTRY_OUT].copy()
        
        X, y = [], []
        for _, row in df_out.iterrows():
            pos_id = row['position_id']
            sid = pos_sid_map.get(pos_id, 0)
            
            # Filter for LTS only
            if sid < 80:
                continue

            hour = row['time'].hour
            is_buy = 1 if row['type'] == mt5.DEAL_TYPE_SELL else 0
            is_sell = 1 if row['type'] == mt5.DEAL_TYPE_BUY else 0
            success = 1 if row['profit'] > 0 else 0
            
            rsi_val, atr_val, ema_dist = 50.0, 20.0, 0.0
            z_score, bb_width, adx_val = 0.0, 1.0, 25.0
            
            if not df_rates.empty:
                idx = df_rates.index.get_indexer([row['time']], method='pad')[0]
                if idx >= 0:
                    r = df_rates.iloc[idx]
                    rsi_val = float(r.get('rsi', 50.0))
                    atr_val = float(r.get('atr', 20.0))
                    ema_dist = float(r.get('close', 0.0) - r.get('ema50', 0.0))
                    z_score = float(r.get('z_score', 0.0))
                    bb_width = float(r.get('bb_width', 1.0))
                    adx_val = float(r.get('adx', 25.0))
            
            X.append([hour, is_buy, is_sell, rsi_val, atr_val, ema_dist, z_score, bb_width, adx_val])
            y.append(success)
            
        print(f"[ML Scoring] Training RandomForest on {len(X)} historical trades...")
        if len(X) < 5:
            print("[ML Scoring] Not enough LTS trades to train (need at least 5).")
            return False
            
        clf = RandomForestClassifier(n_estimators=100, max_depth=5, random_state=42)
        clf.fit(X, y)
        joblib.dump(clf, MODEL_PATH)
        
        global _model
        _model = clf
        print(f"[ML Scoring] Model successfully trained and saved to {MODEL_PATH}")
        return True
    except Exception as e:
        print(f"[ML Scoring] Error during training: {e}")
        return False

def detect_market_regime(symbol: str, tf: int) -> dict:
    """
    Detects if the market is in a strong trend or ranging.
    Returns: {"is_strong_trend": bool, "trend_direction": "BUY" | "SELL" | None, "adx": float}
    """
    import mt5_worker as mt5
    import pandas as pd
    import numpy as np
    
    result = {"is_strong_trend": False, "trend_direction": None, "adx": 0.0}
    
    if mt5.terminal_info() is None:
        return result
        
    rates = mt5.copy_rates_from_pos(symbol, tf, 0, 100)
    if rates is None or len(rates) < 50:
        return result
        
    df = pd.DataFrame(rates)
    
    # Calculate ADX (14)
    high_low = df['high'] - df['low']
    high_close = np.abs(df['high'] - df['close'].shift())
    low_close = np.abs(df['low'] - df['close'].shift())
    true_range = np.max(pd.concat([high_low, high_close, low_close], axis=1), axis=1)
    
    plus_dm = df['high'].diff()
    minus_dm = df['low'].shift() - df['low']
    plus_dm = np.where((plus_dm > minus_dm) & (plus_dm > 0), plus_dm, 0.0)
    minus_dm = np.where((minus_dm > plus_dm) & (minus_dm > 0), minus_dm, 0.0)
    
    tr14 = true_range.rolling(14).sum()
    plus_di14 = 100 * (pd.Series(plus_dm).rolling(14).sum() / tr14)
    minus_di14 = 100 * (pd.Series(minus_dm).rolling(14).sum() / tr14)
    dx = 100 * (np.abs(plus_di14 - minus_di14) / (plus_di14 + minus_di14))
    adx_series = dx.rolling(14).mean()
    
    current_adx = float(adx_series.iloc[-1])
    if np.isnan(current_adx):
        return result
        
    # Calculate EMA 50 to determine direction
    ema50 = df['close'].ewm(span=50, adjust=False).mean()
    current_close = df['close'].iloc[-1]
    
    direction = "BUY" if current_close > ema50.iloc[-1] else "SELL"
    
    # ADX > 25 is typically considered a strong trend
    is_strong = current_adx > 25.0
    
    return {
        "is_strong_trend": is_strong,
        "trend_direction": direction if is_strong else None,
        "adx": current_adx
    }
