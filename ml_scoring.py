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

def extract_features(symbol, tf, signal, current_price, time_bkk):
    """
    Extract basic features for ML model.
    Fetches real RSI, ATR, and EMA distance from MT5.
    """
    import mt5_worker as mt5
    import pandas as pd
    import numpy as np
    
    rsi_val, atr_val, ema_dist = 50.0, 20.0, 0.0
    
    if mt5.terminal_info() is not None:
        rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M15, 0, 60)
        if rates is not None and len(rates) > 50:
            df = pd.DataFrame(rates)
            
            delta = df['close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            rsi_series = 100 - (100 / (1 + rs))
            
            high_low = df['high'] - df['low']
            high_close = np.abs(df['high'] - df['close'].shift())
            low_close = np.abs(df['low'] - df['close'].shift())
            true_range = np.max(pd.concat([high_low, high_close, low_close], axis=1), axis=1)
            atr_series = true_range.rolling(14).mean()
            
            ema_series = df['close'].ewm(span=50, adjust=False).mean()
            
            rsi_val = float(rsi_series.iloc[-1])
            atr_val = float(atr_series.iloc[-1])
            ema_dist = float(df['close'].iloc[-1] - ema_series.iloc[-1])
            
            if np.isnan(rsi_val): rsi_val = 50.0
            if np.isnan(atr_val): atr_val = 20.0
            if np.isnan(ema_dist): ema_dist = 0.0

    return {
        "hour_of_day": time_bkk.hour,
        "is_buy": 1 if signal.upper() == "BUY" else 0,
        "is_sell": 1 if signal.upper() == "SELL" else 0,
        "rsi_approx": rsi_val,
        "atr_approx": atr_val,
        "ema_dist": ema_dist
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
            features.get("rsi_approx", 50),
            features.get("atr_approx", 20),
            features.get("ema_dist", 0)
        ]
        
        prob = _model.predict_proba([feature_values])[0][1]
        return float(prob)
    except Exception as e:
        print(f"[ML Scoring] Prediction error: {e}")
        return 0.5

def train_dummy_model():
    """
    Creates a dummy RandomForest model for demonstration.
    Run this once to create the ml_model.pkl file.
    """
    if not ML_AVAILABLE:
        print("Please 'pip install scikit-learn numpy joblib' first.")
        return
        
    print("Training ML model on historical data...")
    X = []
    y = []
    # Generate 1000 dummy rows
    for _ in range(1000):
        hour = random.randint(0, 23)
        is_buy = random.choice([0, 1])
        is_sell = 1 - is_buy
        rsi = random.uniform(10, 90)
        atr = random.uniform(5, 60)
        
        # Create a fake logic: Buy is better when RSI is low, Sell when RSI is high
        success = 0
        if is_buy and rsi < 40: success = 1
        if is_sell and rsi > 60: success = 1
        # Add noise
        if random.random() < 0.2: success = 1 - success
        
        X.append([hour, is_buy, is_sell, rsi, atr])
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
            
        print(f"[ML Scoring] Found {len(history_deals)} deals. Fetching historical rates for features...")
        
        # Fetch OHLC data for the period + extra 5 days for indicators window
        rates_start = start_time - timedelta(days=5)
        rates = mt5.copy_rates_range(config.SYMBOL, mt5.TIMEFRAME_M15, rates_start, end_time)
        df_rates = pd.DataFrame()
        if rates is not None and len(rates) > 0:
            df_rates = pd.DataFrame(rates)
            df_rates['time'] = pd.to_datetime(df_rates['time'], unit='s')
            df_rates.set_index('time', inplace=True)
            
            # Calculate Indicators
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
            
            # Fill NaNs
            df_rates.bfill(inplace=True)

        df = pd.DataFrame(list(history_deals), columns=history_deals[0]._asdict().keys())
        df['time'] = pd.to_datetime(df['time'], unit='s')
        
        # We only want closed positions (OUT deals)
        df_out = df[df['entry'] == mt5.DEAL_ENTRY_OUT].copy()
        
        if len(df_out) < 10:
            print("[ML Scoring] Not enough closed trades to train the model.")
            return False
            
        X = []
        y = []
        
        for _, row in df_out.iterrows():
            hour = row['time'].hour
            is_buy = 1 if row['type'] == mt5.DEAL_TYPE_SELL else 0
            is_sell = 1 if row['type'] == mt5.DEAL_TYPE_BUY else 0
            
            success = 1 if row['profit'] > 0 else 0
            
            rsi_val, atr_val, ema_dist = 50.0, 20.0, 0.0
            
            # Lookup historical indicators
            if not df_rates.empty:
                # Find closest index
                idx = df_rates.index.get_indexer([row['time']], method='pad')[0]
                if idx >= 0:
                    rsi_val = float(df_rates.iloc[idx]['rsi'])
                    atr_val = float(df_rates.iloc[idx]['atr'])
                    ema_dist = float(df_rates.iloc[idx]['close'] - df_rates.iloc[idx]['ema50'])
            
            X.append([hour, is_buy, is_sell, rsi_val, atr_val, ema_dist])
            y.append(success)
            
        print(f"[ML Scoring] Training RandomForest on {len(X)} historical trades...")
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
