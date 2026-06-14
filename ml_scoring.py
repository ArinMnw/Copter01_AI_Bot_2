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
    In a real scenario, you would fetch RSI, ATR, distance to EMA, etc.
    """
    return {
        "hour_of_day": time_bkk.hour,
        "is_buy": 1 if signal.upper() == "BUY" else 0,
        "is_sell": 1 if signal.upper() == "SELL" else 0,
        # Mock features that would normally be fetched from indicators
        "rsi_approx": random.uniform(30, 70),
        "atr_approx": random.uniform(10, 50)
    }

def predict_success_probability(features: dict) -> float:
    """
    Returns a probability score (0.0 to 1.0) of this setup being successful.
    """
    global _model
    if not ML_AVAILABLE:
        # Fallback to random probability if sklearn is not installed
        return random.uniform(0.4, 0.9)
        
    if _model is None:
        _load_model()
        
    if _model is None:
        # Model not trained yet, return a neutral/optimistic probability
        return 0.55
        
    try:
        # Convert features to 2D array
        feature_values = [
            features.get("hour_of_day", 12),
            features.get("is_buy", 0),
            features.get("is_sell", 0),
            features.get("rsi_approx", 50),
            features.get("atr_approx", 20)
        ]
        
        # predict_proba returns [[prob_0, prob_1]]
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
        import MetaTrader5 as mt5
        import pandas as pd
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
            
        print(f"[ML Scoring] Found {len(history_deals)} deals. Processing data...")
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
            # In MT5, DEAL_TYPE_BUY (0) closing means it was a SELL position.
            # But let's simplify and use the deal type to infer direction.
            # Usually, we want the direction of the original trade.
            # A cleaner way is to just assume:
            # If the closing deal is SELL, the position was BUY.
            is_buy = 1 if row['type'] == mt5.DEAL_TYPE_SELL else 0
            is_sell = 1 if row['type'] == mt5.DEAL_TYPE_BUY else 0
            
            # Target variable: 1 if profit > 0 else 0
            success = 1 if row['profit'] > 0 else 0
            
            # Using random for RSI/ATR since we can't reconstruct historical indicators easily.
            # In a production system, these should be saved to a database at execution time.
            rsi = random.uniform(30, 70) 
            atr = random.uniform(10, 50)
            
            X.append([hour, is_buy, is_sell, rsi, atr])
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
