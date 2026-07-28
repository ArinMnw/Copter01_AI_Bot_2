import sys
import os

with open(r'd:\Project\Copter01_AI_Bot_2\strategy\s20.13\strategy20_13_15.py', 'r', encoding='utf-8') as f:
    text = f.read()

text = text.replace('strategy_20_13_15', 'strategy_20_13_17')
text = text.replace('S20.13.15', 'S20.13.17')

# Add advanced features to DataFrame
advanced = '''    df['rsi'] = 100 - (100 / (1 + rs))

    # Z-Score
    sma_20 = df['close'].rolling(20).mean()
    std_20 = df['close'].rolling(20).std()
    df['z_score'] = (df['close'] - sma_20) / std_20
    
    # ADX
    plus_dm = df['high'].diff()
    minus_dm = df['low'].shift() - df['low']
    plus_dm = np.where((plus_dm > minus_dm) & (plus_dm > 0), plus_dm, 0.0)
    minus_dm = np.where((minus_dm > plus_dm) & (minus_dm > 0), minus_dm, 0.0)
    tr14 = tr.rolling(14).sum()
    plus_di14 = 100 * (pd.Series(plus_dm).rolling(14).sum() / tr14)
    minus_di14 = 100 * (pd.Series(minus_dm).rolling(14).sum() / tr14)
    dx = 100 * (np.abs(plus_di14 - minus_di14) / (plus_di14 + minus_di14))
    df['adx'] = dx.rolling(14).mean()'''

text = text.replace("    df['rsi'] = 100 - (100 / (1 + rs))", advanced)

# Add filter before returning BUY/SELL
filter_buy = '''        if current_bar['z_score'] > 0.0 and current_bar['adx'] > 30.0:
            return {"signal": "WAIT", "reason": f"BUY Trend/Z Block (Z={current_bar['z_score']:.2f}, ADX={current_bar['adx']:.1f})"}
        sl = sweep_bottom - config.SL_BUFFER(current_bar['atr'])'''

filter_sell = '''        if (current_bar['z_score'] < 0.0 and current_bar['adx'] > 50.0) or (current_bar['close'] - current_bar['ema_50'] > 100.0):
            return {"signal": "WAIT", "reason": f"SELL Trend/Z Block (Z={current_bar['z_score']:.2f}, ADX={current_bar['adx']:.1f})"}
        sl = sweep_top + config.SL_BUFFER(current_bar['atr'])'''

text = text.replace("        sl = sweep_bottom - config.SL_BUFFER(current_bar['atr'])", filter_buy)
text = text.replace("        sl = sweep_top + config.SL_BUFFER(current_bar['atr'])", filter_sell)

with open(r'd:\Project\Copter01_AI_Bot_2\strategy\s20.13\strategy20_13_17.py', 'w', encoding='utf-8') as f:
    f.write(text)
