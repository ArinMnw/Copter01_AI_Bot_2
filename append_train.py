with open('ml_scoring.py', 'a') as f:
    f.write('''
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
        
        df_out = df[df['entry'] == mt5.DEAL_ENTRY_OUT].copy()
        
        X, y = [], []
        for _, row in df_out.iterrows():
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
''')
