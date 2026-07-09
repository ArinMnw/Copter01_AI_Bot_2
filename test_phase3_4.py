import ml_scoring
import trailing
import config
from datetime import datetime
import MetaTrader5 as mt5

def test_ml_scoring():
    print("=== Testing Phase 3 (ML Scoring Quant Features) ===")
    if not mt5.initialize():
        print("MT5 init failed")
        return
        
    symbol = config.SYMBOL
    time_bkk = datetime.now()
    
    print(f"Fetching features for {symbol}...")
    try:
        features = ml_scoring.extract_features(symbol, mt5.TIMEFRAME_M15, "BUY", 2000.0, time_bkk)
        print("✅ Features extracted successfully:")
        for k, v in features.items():
            print(f"  - {k}: {v:.4f}" if isinstance(v, float) else f"  - {k}: {v}")
            
        score = ml_scoring.predict_success_probability(features)
        print(f"✅ ML Score prediction: {score:.2f} ({(score*100):.1f}%)")
        
    except Exception as e:
        print(f"❌ Error during ML testing: {e}")
        
    mt5.shutdown()

def test_trailing():
    print("\n=== Testing Phase 4 (Dynamic Exits) ===")
    has_cutloss = hasattr(trailing, 'check_smart_cutloss')
    has_atr = hasattr(trailing, 'check_atr_trailing')
    
    if has_cutloss:
        print("✅ Smart Cut-loss function (check_smart_cutloss) is implemented.")
    else:
        print("❌ Smart Cut-loss missing.")
        
    if has_atr:
        print("✅ ATR Trailing function (check_atr_trailing) is implemented.")
    else:
        print("❌ ATR Trailing missing.")

if __name__ == "__main__":
    test_ml_scoring()
    test_trailing()
