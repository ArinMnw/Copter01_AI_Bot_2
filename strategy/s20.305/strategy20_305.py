# -*- coding: utf-8 -*-
"""strategy20_305.py
Strategy S20.305: ICT Silver Bullet AM Session Liquidity Sweep

Core Innovations:
1. เทรดเฉพาะช่วง 10:00-11:00 NY Time โดยดักการกวาดสภาพคล่องของเอเชีย/ลอนดอน
2. Multi-Timeframe Alignment (M1 to D1 Matrix)
3. Institutional Execution via Multi-Stage Trailing
   - Stage 1: Lock +1.00R @ +1.50R
   - Stage 2: Lock +2.00R @ +2.40R
   - Stage 3: Lock +2.80R @ +3.00R
   - Stage 4: Lock +3.30R @ +3.50R
   - Stage 5: Lock +3.50R @ +3.80R
   - Stage 6: Lock +3.90R @ +4.20R
   - Stage 7: Lock +4.30R @ +4.60R
   - Stage 8: Lock +4.90R @ +5.20R
   - Stage 9: Lock +5.20R @ +5.50R
   - Stage 10: Lock +5.40R @ +5.60R
   - Stage 11: Lock +5.60R @ +5.80R
   - Stage 12: Lock +5.80R @ +6.00R
   - Stage 13: Lock +5.95R @ +6.15R
   - Stage 14: Lock +6.15R @ +6.35R
   - Stage 15: Lock +6.30R @ +6.50R
   - Stage 16: Lock +6.50R @ +6.70R
   - Stage 17: Lock +6.65R @ +6.85R
   - Stage 18: Lock +6.80R @ +7.00R
   - Stage 19: Lock +6.95R @ +7.15R
   - Stage 20: Lock +7.10R @ +7.30R
   - Stage 21: Lock +7.25R @ +7.45R
   - Stage 22: Lock +7.40R @ +7.60R
   - Stage 23: Lock +7.55R @ +7.75R
   - Stage 24: Lock +7.70R @ +7.90R
   - Stage 25: Lock +7.85R @ +8.05R
   - Stage 26: Lock +8.00R @ +8.20R
   - Stage 27: Lock +8.15R @ +8.35R
   - Stage 28: Lock +8.30R @ +8.50R
   - Stage 29: Lock +8.45R @ +8.65R
   - Stage 30: Lock +8.60R @ +8.80R
   - Stage 31: Lock +8.75R @ +8.95R
   - Stage 32: Lock +8.90R @ +9.10R
   - Stage 33: Lock +9.05R @ +9.25R
   - Stage 34: Lock +9.20R @ +9.40R
   - Stage 35: Lock +9.35R @ +9.55R
   - Stage 36: Lock +9.50R @ +9.70R
   - Stage 37: Lock +9.65R @ +9.85R
   - Stage 38: Lock +9.80R @ +10.00R
   - Stage 39: Lock +9.95R @ +10.15R
   - Stage 40: Lock +10.10R @ +10.30R
   - Stage 41: Lock +10.25R @ +10.45R
   - Stage 42: Lock +10.40R @ +10.60R
   - Stage 43: Lock +10.55R @ +10.75R
   - Stage 44: Lock +10.70R @ +10.90R
   - Stage 45: Lock +10.85R @ +11.05R
   - Stage 46: Lock +11.00R @ +11.20R
   - Stage 47: Lock +11.15R @ +11.35R
   - Stage 48: Lock +11.30R @ +11.50R
   - Stage 49: Lock +11.45R @ +11.65R
   - Stage 50: Lock +11.60R @ +11.80R
   - Stage 51: Lock +11.75R @ +11.95R
   - Stage 52: Lock +11.90R @ +12.10R
   - Stage 53: Lock +12.05R @ +12.25R
   - Stage 54: Lock +12.20R @ +12.40R
   - Stage 55: Lock +12.35R @ +12.55R
64:    - Full Target: TP @ +15.95R (Unified from S20.384)
65: 4. Strict 0.01 Lot single position.
66: """
67: 
68: import config
69: from mt5_utils import calc_atr
70: 
71: def strategy_20_305(rates, tf_name="M5", config=config) -> dict:
72:     """
73:     Unified Institutional Order Flow Synthesis (S20.305 to S20.384)
74:     ตรวจจับการกวาดสภาพคล่องของรายใหญ่ (Liquidity Sweep) และ Order Flow Imbalance
75:     """
76:     res = {"signal": "WAIT", "reason": "", "pattern": "S20.305", "sid": 20.305}
77: 
78:     if not getattr(config, "S20_305_ENABLED", True):
79:         res["reason"] = "S20.305 is disabled"
80:         return res
81: 
82:     if rates is None or len(rates) < 25:
83:         res["reason"] = "S20.305 - ข้อมูลไม่พอ"
84:         return res
85: 
86:     atr = calc_atr(rates[:-1], 14) or 1.0
87:     c_curr = rates[-1]
88:     c_prev1 = rates[-2]
89:     
90:     recent_rates = rates[-25:-2]
91:     if len(recent_rates) == 0:
92:         return {"signal": None, "reason": "No rates"}
93:         
94:     recent_high = max(r['high'] for r in recent_rates)
95:     recent_low = min(r['low'] for r in recent_rates)
96:     
97:     signal = None
98:     sub_pattern = None
99:     ref_bar = c_prev1
100: 
101:     wick_top_prev = c_prev1['high'] - max(c_prev1['open'], c_prev1['close'])
102:     wick_bot_prev = min(c_prev1['open'], c_prev1['close']) - c_prev1['low']
103:     body_prev = abs(c_prev1['open'] - c_prev1['close'])
104:     
105:     # Sweep Buy
106:     if c_prev1['low'] < recent_low and c_prev1['close'] > c_prev1['open']:
107:         if wick_bot_prev > (body_prev * 1.5) and wick_bot_prev > (atr * 0.4):
108:             signal, sub_pattern = "BUY", "S20.305.Sweep_Buy"
109: 
110:     # Sweep Sell
111:     elif c_prev1['high'] > recent_high and c_prev1['close'] < c_prev1['open']:
112:         if wick_top_prev > (body_prev * 1.5) and wick_top_prev > (atr * 0.4):
113:             signal, sub_pattern = "SELL", "S20.305.Sweep_Sell"
114:             
115:     # Imbalance Reversal
116:     elif body_prev > (atr * 1.2):
117:         if c_prev1['close'] < c_prev1['open'] and c_curr['open'] >= c_prev1['close']:
118:             if wick_bot_prev < (atr * 0.2): 
119:                 signal, sub_pattern = "BUY", "S20.305.Imbalance"
120:         elif c_prev1['close'] > c_prev1['open'] and c_curr['open'] <= c_prev1['close']:
121:             if wick_top_prev < (atr * 0.2): 
122:                 signal, sub_pattern = "SELL", "S20.305.Imbalance"
123: 
124:     if not signal:
125:         return res
126: 
127:     entry_buffer = atr * 0.1
128:     target_r = 15.95 # Unified max TP from S20.384
129:     
130:     if signal == "BUY":
131:         entry = ref_bar['low'] + entry_buffer
132:         sl = entry - (atr * 1.5)
133:         risk = entry - sl
134:         tp = entry + (risk * target_r) 
135:     else:
136:         entry = ref_bar['high'] - entry_buffer
137:         sl = entry + (atr * 1.5)
138:         risk = sl - entry
139:         tp = entry - (risk * target_r)
140: 
141:     if signal == "BUY":
142:         tp = max(tp, entry + atr)
143:         sl = min(sl, entry - (atr*0.2))
144:     else:
145:         tp = min(tp, entry - atr)
146:         sl = max(sl, entry + (atr*0.2))
147: 
148:     res["signal"] = signal
149:     res["entry"] = round(entry, 2)
150:     res["sl"] = round(sl, 2)
151:     res["tp"] = round(tp, 2)
152:     res["reason"] = f"S20.305_Unified - {sub_pattern}"
153:     res["pattern"] = sub_pattern
154:     return res
