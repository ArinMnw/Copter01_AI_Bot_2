import ml_scoring
import strategy95
import mt5_worker as mt5
from config import SYMBOL
import pandas as pd

def test_regime_detection():
    print("=== Testing Regime Detection ===")
    if not mt5.initialize():
        print("MT5 init failed")
        return
        
    try:
        regime = ml_scoring.detect_market_regime(SYMBOL, mt5.TIMEFRAME_M15)
        print(f"Regime for {SYMBOL} M15:")
        print(f"Is Strong Trend: {regime['is_strong_trend']}")
        print(f"Trend Direction: {regime['trend_direction']}")
        print(f"ADX: {regime['adx']:.2f}")
    except Exception as e:
        print(f"Error testing regime: {e}")
        
    mt5.shutdown()

def test_strategy_95():
    print("\n=== Testing Strategy 95 (Liquidity Sweep) ===")
    if not mt5.initialize():
        return
        
    try:
        rates = mt5.copy_rates_from_pos(SYMBOL, mt5.TIMEFRAME_M15, 0, 100)
        if rates is not None and len(rates) > 0:
            result = strategy95.strategy_95(rates, tf="M15")
            print("S95 Result:")
            for k, v in result.items():
                if k == 'candles': continue
                print(f"  {k}: {v}")
    except Exception as e:
        print(f"Error testing S95: {e}")
        
    mt5.shutdown()

if __name__ == "__main__":
    test_regime_detection()
    test_strategy_95()
