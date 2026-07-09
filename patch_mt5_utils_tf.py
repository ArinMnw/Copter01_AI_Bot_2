import re

def patch_mt5_utils():
    with open("mt5_utils.py", "r", encoding="utf-8") as f:
        content = f.read()
        
    old_code = '''        import ml_scoring
        from config import SYMBOL
        regime = ml_scoring.detect_market_regime(SYMBOL, tf)'''
        
    new_code = '''        import ml_scoring
        from config import SYMBOL
        import mt5_worker as mt5
        
        # Convert string to int if necessary
        mt5_tf = tf
        if isinstance(tf, str):
            tf_clean = tf.strip("[]").split("_")[0] # handle "[M15_H1]" -> "M15"
            tf_map = {
                "M1": mt5.TIMEFRAME_M1, "M5": mt5.TIMEFRAME_M5, "M15": mt5.TIMEFRAME_M15,
                "M30": mt5.TIMEFRAME_M30, "H1": mt5.TIMEFRAME_H1, "H4": mt5.TIMEFRAME_H4,
                "D1": mt5.TIMEFRAME_D1, "W1": mt5.TIMEFRAME_W1, "MN1": mt5.TIMEFRAME_MN1
            }
            mt5_tf = tf_map.get(tf_clean, mt5.TIMEFRAME_M15)
            
        regime = ml_scoring.detect_market_regime(SYMBOL, mt5_tf)'''
        
    content = content.replace(old_code, new_code)
    
    with open("mt5_utils.py", "w", encoding="utf-8") as f:
        f.write(content)

if __name__ == "__main__":
    patch_mt5_utils()
