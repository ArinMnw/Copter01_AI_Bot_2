import asyncio
import pandas as pd
import MetaTrader5 as mt5
import config
from mt5_utils import get_dynamic_volume
import ml_scoring

def test_dynamic_lot():
    print("="*50)
    print("🚀 TEST PHASE 3: Dynamic Lot Sizing")
    print("="*50)
    tf = "M15"
    base_lot = 0.10 # changed to 0.10 to see scaling clearly
    symbol = 'XAUUSD.iux'
    
    regime = ml_scoring.detect_market_regime(symbol, mt5.TIMEFRAME_M15)
    print(f"[Regime] {regime}")
    
    vol_buy = get_dynamic_volume(tf, "BUY", base_lot)
    print(f"Base Lot: {base_lot} | Signal: BUY  | Dynamic Lot: {vol_buy} (Expected: 0.15 if Strong BUY, else 0.05)")
    
    vol_sell = get_dynamic_volume(tf, "SELL", base_lot)
    print(f"Base Lot: {base_lot} | Signal: SELL | Dynamic Lot: {vol_sell} (Expected: 0.15 if Strong SELL, else 0.05)")

def test_momentum_stall():
    print("\n" + "="*50)
    print("🛡️ TEST PHASE 4: Momentum Stall (Dry-Run)")
    print("="*50)
    
    symbol = 'XAUUSD.iux'
    rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M15, 0, 10)
    if rates is None or len(rates) < 5:
        print("Failed to get rates from MT5")
        return
        
    df = pd.DataFrame(rates)
    recent_highs = df['high'].iloc[-6:-1]
    recent_lows = df['low'].iloc[-6:-1]
    
    print("Recent 5 M15 Highs:")
    print(recent_highs.tolist())
    print("Recent 5 M15 Lows:")
    print(recent_lows.tolist())
    
    last_3_highs = list(recent_highs.iloc[-3:])
    if last_3_highs[0] >= last_3_highs[1] >= last_3_highs[2]:
        print("🚨 Momentum Stall Exit [BUY] Triggered! (Lower highs detected)")
    else:
        print("✅ Momentum Stall Exit [BUY] NOT Triggered (Highs are fine)")
        
    last_3_lows = list(recent_lows.iloc[-3:])
    if last_3_lows[0] <= last_3_lows[1] <= last_3_lows[2]:
        print("🚨 Momentum Stall Exit [SELL] Triggered! (Higher lows detected)")
    else:
        print("✅ Momentum Stall Exit [SELL] NOT Triggered (Lows are fine)")

async def main():
    if not mt5.initialize():
        print("MT5 Init failed")
        return
        
    mt5.symbol_select("XAUUSD.iux", True)
    
    test_dynamic_lot()
    test_momentum_stall()
    
    mt5.shutdown()

if __name__ == "__main__":
    asyncio.run(main())
