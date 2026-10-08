import sys
import os
import json
import subprocess
import importlib.util
from datetime import datetime
import shutil
import time

pairs = [
    {"A": "339", "B": "194", "method": "FILTER", "k": 0, "logic": "339 catches continuation breakouts from inside bars. 194 (Chande Kroll Stop) determines a robust medium-term trend. Filtering 339 signals to only occur when 194 is in the same direction prevents false inside bar breakouts against the primary stop-loss flow."},
    {"A": "422", "B": "143", "method": "CONFIRM", "k": 3, "logic": "422 relies on triple MA volatility breakout, which can be noisy. 143 (Elder Impulse) measures momentum via MACD and EMA. If 143 signals green within the last 3 bars of a 422 long breakout, it confirms strong institutional momentum backing the volatility spike."},
    {"A": "339", "B": "242", "method": "MTF", "k": 0, "logic": "339 trades inside bar breakouts. 242 (Rainbow MA Full Alignment) requires a very strong, mature trend. By using 242 on a larger timeframe to filter 339 on a smaller timeframe, we ensure the inside bar breakout is trading directly into the core momentum of the higher TF structure."},
    {"A": "422", "B": "168", "method": "VETO", "k": 5, "logic": "422 is a volatility breakout. 168 (Ehlers Super Smoother) provides a very smooth turning point without lag. If 168 has just signaled a reversal in the opposite direction within the last 5 bars, we veto the 422 breakout, assuming it's a trap/fakeout."},
    {"A": "339", "B": "277", "method": "FILTER", "k": 0, "logic": "339 continuation. 277 (Quadratic-Regression Curvature) indicates the mathematical curvature of the trend. Filtering 339 by 277's direction ensures we only take continuation trades when the underlying polynomial trend is accelerating in our favor, not decelerating."},
    {"A": "422", "B": "342", "method": "CONFIRM", "k": 3, "logic": "422 breaks out on volatility. 342 (ADX Low Volatility Breakout) specifically identifies transitions from low to high volatility using ADX. Confirming a 422 signal with a recent 342 signal ensures the breakout is genuine expansion from a squeeze, not just a random large bar."},
    {"A": "339", "B": "148", "method": "CONFIRM", "k": 3, "logic": "339 uses an inside bar + MACD. 148 uses an inside-bar mother-bar breakout + EMA50. While both use inside bars, their confirmation criteria differ. Combining them requires both MACD continuation and EMA50 alignment, creating a highly selective, robust continuation entry."},
    {"A": "422", "B": "255", "method": "VETO", "k": 3, "logic": "422 (Triple MA breakout) can suffer during false breakouts. 255 (Hikkake False Breakout) explicitly identifies false inside-bar breakouts. If 255 signals in the opposite direction recently, it means market makers are trapping breakout traders. Vetoing 422 in this condition protects against traps."},
    {"A": "339", "B": "210", "method": "FILTER", "k": 0, "logic": "339 uses MACD. 210 (Bill Williams Accelerator) measures the acceleration of driving force. Filtering 339 with 210 ensures that the momentum is not just continuing (MACD) but actually accelerating (AC), increasing the probability of a fast move post-breakout."},
    {"A": "422", "B": "237", "method": "MTF", "k": 0, "logic": "422 is a MA-based breakout. 237 (Ehlers FRAMA) dynamically adjusts to fractal dimensionality (market chop). Using 237 on a higher timeframe ensures the higher TF is not in a highly fractal/choppy state, allowing the lower TF 422 breakout to run freely."},
    {"A": "339", "B": "379", "method": "CONFIRM", "k": 3, "logic": "339 is inside bar continuation. 379 (DMI Strong Trend Re-entry) triggers when ADX is high and DMI pulls back. Confirming 339 with 379 ensures the inside bar is acting as the exact pullback point in a confirmed strong ADX trend."},
    {"A": "422", "B": "194", "method": "FILTER", "k": 0, "logic": "422 uses Triple MA. 194 uses Chande Kroll (ATR-based trailing). Filtering a MA breakout with an ATR-based directional bias ensures that the breakout is also breaking out of recent true range extremes, not just moving averages which can lag in tight ranges."},
    {"A": "339", "B": "356", "method": "VETO", "k": 3, "logic": "339 inside bar breakout. 356 (Bollinger Z-Score Breakout) measures extreme statistical deviations. If 356 signaled a breakout in the opposite direction recently, the inside bar might just be a brief pause before the extreme mean-reversion resumes. We veto 339 to avoid fighting extreme Z-score moves."},
    {"A": "422", "B": "277", "method": "FILTER", "k": 0, "logic": "422 breakout. 277 quadratic regression. Filtering 422 with 277 ensures the breakout is mathematically aligned with the broader polynomial curve of price action, adding a non-linear confirmation to a linear MA strategy."},
    {"A": "339", "B": "143", "method": "MTF", "k": 0, "logic": "339 inside bar continuation. 143 Elder Impulse. Using 143 on a higher timeframe to filter 339 ensures the higher TF has strong institutional backing (color shift green/red) before we take an inside bar continuation on the lower TF."}
]

def load_json(path):
    if not os.path.exists(path): return {}
    with open(path, 'r', encoding='utf-8') as f: return json.load(f)

def save_json(path, data):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=1)

def get_parent_meta(sid):
    path = f'strategy/s20.{sid}/strategy20_{sid}.py'
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()
    # Extract META dict
    import ast
    meta_str = content.split('META = ')[1].split('\n\ndef')[0]
    return ast.literal_eval(meta_str)

pairs.extend([{'A': '339', 'B': '194', 'method': 'FILTER', 'k': 0, 'logic': 'Mixing 339 with 194 using FILTER. Ensure 194 state aligns.'}, {'A': '339', 'B': '194', 'method': 'CONFIRM', 'k': 3, 'logic': 'Mixing 339 with 194 using CONFIRM. Confirm 339 with 194 signal within 3 bars.'}, {'A': '339', 'B': '194', 'method': 'VETO', 'k': 4, 'logic': 'Mixing 339 with 194 using VETO. Veto 339 if 194 opposite signal within 4 bars.'}, {'A': '339', 'B': '194', 'method': 'MTF', 'k': 0, 'logic': 'Mixing 339 with 194 using MTF. Filter 339 using 194 on higher TF.'}, {'A': '339', 'B': '143', 'method': 'FILTER', 'k': 0, 'logic': 'Mixing 339 with 143 using FILTER. Ensure 143 state aligns.'}, {'A': '339', 'B': '143', 'method': 'CONFIRM', 'k': 4, 'logic': 'Mixing 339 with 143 using CONFIRM. Confirm 339 with 143 signal within 4 bars.'}, {'A': '339', 'B': '143', 'method': 'VETO', 'k': 5, 'logic': 'Mixing 339 with 143 using VETO. Veto 339 if 143 opposite signal within 5 bars.'}, {'A': '339', 'B': '143', 'method': 'MTF', 'k': 0, 'logic': 'Mixing 339 with 143 using MTF. Filter 339 using 143 on higher TF.'}, {'A': '339', 'B': '242', 'method': 'FILTER', 'k': 0, 'logic': 'Mixing 339 with 242 using FILTER. Ensure 242 state aligns.'}, {'A': '339', 'B': '242', 'method': 'CONFIRM', 'k': 5, 'logic': 'Mixing 339 with 242 using CONFIRM. Confirm 339 with 242 signal within 5 bars.'}, {'A': '339', 'B': '242', 'method': 'VETO', 'k': 2, 'logic': 'Mixing 339 with 242 using VETO. Veto 339 if 242 opposite signal within 2 bars.'}, {'A': '339', 'B': '242', 'method': 'MTF', 'k': 0, 'logic': 'Mixing 339 with 242 using MTF. Filter 339 using 242 on higher TF.'}, {'A': '339', 'B': '168', 'method': 'FILTER', 'k': 0, 'logic': 'Mixing 339 with 168 using FILTER. Ensure 168 state aligns.'}, {'A': '339', 'B': '168', 'method': 'CONFIRM', 'k': 3, 'logic': 'Mixing 339 with 168 using CONFIRM. Confirm 339 with 168 signal within 3 bars.'}, {'A': '339', 'B': '168', 'method': 'VETO', 'k': 5, 'logic': 'Mixing 339 with 168 using VETO. Veto 339 if 168 opposite signal within 5 bars.'}, {'A': '339', 'B': '168', 'method': 'MTF', 'k': 0, 'logic': 'Mixing 339 with 168 using MTF. Filter 339 using 168 on higher TF.'}, {'A': '339', 'B': '277', 'method': 'FILTER', 'k': 0, 'logic': 'Mixing 339 with 277 using FILTER. Ensure 277 state aligns.'}, {'A': '339', 'B': '277', 'method': 'CONFIRM', 'k': 3, 'logic': 'Mixing 339 with 277 using CONFIRM. Confirm 339 with 277 signal within 3 bars.'}, {'A': '339', 'B': '277', 'method': 'VETO', 'k': 2, 'logic': 'Mixing 339 with 277 using VETO. Veto 339 if 277 opposite signal within 2 bars.'}, {'A': '339', 'B': '277', 'method': 'MTF', 'k': 0, 'logic': 'Mixing 339 with 277 using MTF. Filter 339 using 277 on higher TF.'}, {'A': '339', 'B': '255', 'method': 'FILTER', 'k': 0, 'logic': 'Mixing 339 with 255 using FILTER. Ensure 255 state aligns.'}, {'A': '339', 'B': '255', 'method': 'CONFIRM', 'k': 5, 'logic': 'Mixing 339 with 255 using CONFIRM. Confirm 339 with 255 signal within 5 bars.'}, {'A': '339', 'B': '255', 'method': 'VETO', 'k': 3, 'logic': 'Mixing 339 with 255 using VETO. Veto 339 if 255 opposite signal within 3 bars.'}, {'A': '339', 'B': '255', 'method': 'MTF', 'k': 0, 'logic': 'Mixing 339 with 255 using MTF. Filter 339 using 255 on higher TF.'}, {'A': '339', 'B': '210', 'method': 'FILTER', 'k': 0, 'logic': 'Mixing 339 with 210 using FILTER. Ensure 210 state aligns.'}, {'A': '339', 'B': '210', 'method': 'CONFIRM', 'k': 4, 'logic': 'Mixing 339 with 210 using CONFIRM. Confirm 339 with 210 signal within 4 bars.'}, {'A': '339', 'B': '210', 'method': 'VETO', 'k': 5, 'logic': 'Mixing 339 with 210 using VETO. Veto 339 if 210 opposite signal within 5 bars.'}, {'A': '339', 'B': '210', 'method': 'MTF', 'k': 0, 'logic': 'Mixing 339 with 210 using MTF. Filter 339 using 210 on higher TF.'}, {'A': '339', 'B': '237', 'method': 'FILTER', 'k': 0, 'logic': 'Mixing 339 with 237 using FILTER. Ensure 237 state aligns.'}, {'A': '339', 'B': '237', 'method': 'CONFIRM', 'k': 2, 'logic': 'Mixing 339 with 237 using CONFIRM. Confirm 339 with 237 signal within 2 bars.'}, {'A': '339', 'B': '237', 'method': 'VETO', 'k': 4, 'logic': 'Mixing 339 with 237 using VETO. Veto 339 if 237 opposite signal within 4 bars.'}, {'A': '339', 'B': '237', 'method': 'MTF', 'k': 0, 'logic': 'Mixing 339 with 237 using MTF. Filter 339 using 237 on higher TF.'}, {'A': '339', 'B': '148', 'method': 'FILTER', 'k': 0, 'logic': 'Mixing 339 with 148 using FILTER. Ensure 148 state aligns.'}, {'A': '339', 'B': '148', 'method': 'CONFIRM', 'k': 5, 'logic': 'Mixing 339 with 148 using CONFIRM. Confirm 339 with 148 signal within 5 bars.'}, {'A': '339', 'B': '148', 'method': 'VETO', 'k': 5, 'logic': 'Mixing 339 with 148 using VETO. Veto 339 if 148 opposite signal within 5 bars.'}, {'A': '339', 'B': '148', 'method': 'MTF', 'k': 0, 'logic': 'Mixing 339 with 148 using MTF. Filter 339 using 148 on higher TF.'}, {'A': '339', 'B': '161', 'method': 'FILTER', 'k': 0, 'logic': 'Mixing 339 with 161 using FILTER. Ensure 161 state aligns.'}, {'A': '339', 'B': '161', 'method': 'CONFIRM', 'k': 5, 'logic': 'Mixing 339 with 161 using CONFIRM. Confirm 339 with 161 signal within 5 bars.'}, {'A': '339', 'B': '161', 'method': 'VETO', 'k': 2, 'logic': 'Mixing 339 with 161 using VETO. Veto 339 if 161 opposite signal within 2 bars.'}, {'A': '339', 'B': '161', 'method': 'MTF', 'k': 0, 'logic': 'Mixing 339 with 161 using MTF. Filter 339 using 161 on higher TF.'}, {'A': '339', 'B': '379', 'method': 'FILTER', 'k': 0, 'logic': 'Mixing 339 with 379 using FILTER. Ensure 379 state aligns.'}, {'A': '339', 'B': '379', 'method': 'CONFIRM', 'k': 3, 'logic': 'Mixing 339 with 379 using CONFIRM. Confirm 339 with 379 signal within 3 bars.'}, {'A': '339', 'B': '379', 'method': 'VETO', 'k': 5, 'logic': 'Mixing 339 with 379 using VETO. Veto 339 if 379 opposite signal within 5 bars.'}, {'A': '339', 'B': '379', 'method': 'MTF', 'k': 0, 'logic': 'Mixing 339 with 379 using MTF. Filter 339 using 379 on higher TF.'}, {'A': '339', 'B': '342', 'method': 'FILTER', 'k': 0, 'logic': 'Mixing 339 with 342 using FILTER. Ensure 342 state aligns.'}, {'A': '339', 'B': '342', 'method': 'CONFIRM', 'k': 2, 'logic': 'Mixing 339 with 342 using CONFIRM. Confirm 339 with 342 signal within 2 bars.'}, {'A': '339', 'B': '342', 'method': 'VETO', 'k': 5, 'logic': 'Mixing 339 with 342 using VETO. Veto 339 if 342 opposite signal within 5 bars.'}, {'A': '339', 'B': '342', 'method': 'MTF', 'k': 0, 'logic': 'Mixing 339 with 342 using MTF. Filter 339 using 342 on higher TF.'}, {'A': '339', 'B': '356', 'method': 'FILTER', 'k': 0, 'logic': 'Mixing 339 with 356 using FILTER. Ensure 356 state aligns.'}, {'A': '339', 'B': '356', 'method': 'CONFIRM', 'k': 3, 'logic': 'Mixing 339 with 356 using CONFIRM. Confirm 339 with 356 signal within 3 bars.'}, {'A': '339', 'B': '356', 'method': 'VETO', 'k': 4, 'logic': 'Mixing 339 with 356 using VETO. Veto 339 if 356 opposite signal within 4 bars.'}, {'A': '339', 'B': '356', 'method': 'MTF', 'k': 0, 'logic': 'Mixing 339 with 356 using MTF. Filter 339 using 356 on higher TF.'}, {'A': '422', 'B': '194', 'method': 'FILTER', 'k': 0, 'logic': 'Mixing 422 with 194 using FILTER. Ensure 194 state aligns.'}, {'A': '422', 'B': '194', 'method': 'CONFIRM', 'k': 5, 'logic': 'Mixing 422 with 194 using CONFIRM. Confirm 422 with 194 signal within 5 bars.'}, {'A': '422', 'B': '194', 'method': 'VETO', 'k': 2, 'logic': 'Mixing 422 with 194 using VETO. Veto 422 if 194 opposite signal within 2 bars.'}, {'A': '422', 'B': '194', 'method': 'MTF', 'k': 0, 'logic': 'Mixing 422 with 194 using MTF. Filter 422 using 194 on higher TF.'}, {'A': '422', 'B': '143', 'method': 'FILTER', 'k': 0, 'logic': 'Mixing 422 with 143 using FILTER. Ensure 143 state aligns.'}, {'A': '422', 'B': '143', 'method': 'CONFIRM', 'k': 2, 'logic': 'Mixing 422 with 143 using CONFIRM. Confirm 422 with 143 signal within 2 bars.'}, {'A': '422', 'B': '143', 'method': 'VETO', 'k': 3, 'logic': 'Mixing 422 with 143 using VETO. Veto 422 if 143 opposite signal within 3 bars.'}, {'A': '422', 'B': '143', 'method': 'MTF', 'k': 0, 'logic': 'Mixing 422 with 143 using MTF. Filter 422 using 143 on higher TF.'}, {'A': '422', 'B': '242', 'method': 'FILTER', 'k': 0, 'logic': 'Mixing 422 with 242 using FILTER. Ensure 242 state aligns.'}, {'A': '422', 'B': '242', 'method': 'CONFIRM', 'k': 3, 'logic': 'Mixing 422 with 242 using CONFIRM. Confirm 422 with 242 signal within 3 bars.'}, {'A': '422', 'B': '242', 'method': 'VETO', 'k': 3, 'logic': 'Mixing 422 with 242 using VETO. Veto 422 if 242 opposite signal within 3 bars.'}, {'A': '422', 'B': '242', 'method': 'MTF', 'k': 0, 'logic': 'Mixing 422 with 242 using MTF. Filter 422 using 242 on higher TF.'}, {'A': '422', 'B': '168', 'method': 'FILTER', 'k': 0, 'logic': 'Mixing 422 with 168 using FILTER. Ensure 168 state aligns.'}, {'A': '422', 'B': '168', 'method': 'CONFIRM', 'k': 5, 'logic': 'Mixing 422 with 168 using CONFIRM. Confirm 422 with 168 signal within 5 bars.'}, {'A': '422', 'B': '168', 'method': 'VETO', 'k': 2, 'logic': 'Mixing 422 with 168 using VETO. Veto 422 if 168 opposite signal within 2 bars.'}, {'A': '422', 'B': '168', 'method': 'MTF', 'k': 0, 'logic': 'Mixing 422 with 168 using MTF. Filter 422 using 168 on higher TF.'}, {'A': '422', 'B': '277', 'method': 'FILTER', 'k': 0, 'logic': 'Mixing 422 with 277 using FILTER. Ensure 277 state aligns.'}, {'A': '422', 'B': '277', 'method': 'CONFIRM', 'k': 3, 'logic': 'Mixing 422 with 277 using CONFIRM. Confirm 422 with 277 signal within 3 bars.'}, {'A': '422', 'B': '277', 'method': 'VETO', 'k': 3, 'logic': 'Mixing 422 with 277 using VETO. Veto 422 if 277 opposite signal within 3 bars.'}, {'A': '422', 'B': '277', 'method': 'MTF', 'k': 0, 'logic': 'Mixing 422 with 277 using MTF. Filter 422 using 277 on higher TF.'}, {'A': '422', 'B': '255', 'method': 'FILTER', 'k': 0, 'logic': 'Mixing 422 with 255 using FILTER. Ensure 255 state aligns.'}, {'A': '422', 'B': '255', 'method': 'CONFIRM', 'k': 5, 'logic': 'Mixing 422 with 255 using CONFIRM. Confirm 422 with 255 signal within 5 bars.'}, {'A': '422', 'B': '255', 'method': 'VETO', 'k': 3, 'logic': 'Mixing 422 with 255 using VETO. Veto 422 if 255 opposite signal within 3 bars.'}, {'A': '422', 'B': '255', 'method': 'MTF', 'k': 0, 'logic': 'Mixing 422 with 255 using MTF. Filter 422 using 255 on higher TF.'}, {'A': '422', 'B': '210', 'method': 'FILTER', 'k': 0, 'logic': 'Mixing 422 with 210 using FILTER. Ensure 210 state aligns.'}, {'A': '422', 'B': '210', 'method': 'CONFIRM', 'k': 5, 'logic': 'Mixing 422 with 210 using CONFIRM. Confirm 422 with 210 signal within 5 bars.'}, {'A': '422', 'B': '210', 'method': 'VETO', 'k': 5, 'logic': 'Mixing 422 with 210 using VETO. Veto 422 if 210 opposite signal within 5 bars.'}, {'A': '422', 'B': '210', 'method': 'MTF', 'k': 0, 'logic': 'Mixing 422 with 210 using MTF. Filter 422 using 210 on higher TF.'}, {'A': '422', 'B': '237', 'method': 'FILTER', 'k': 0, 'logic': 'Mixing 422 with 237 using FILTER. Ensure 237 state aligns.'}, {'A': '422', 'B': '237', 'method': 'CONFIRM', 'k': 5, 'logic': 'Mixing 422 with 237 using CONFIRM. Confirm 422 with 237 signal within 5 bars.'}, {'A': '422', 'B': '237', 'method': 'VETO', 'k': 4, 'logic': 'Mixing 422 with 237 using VETO. Veto 422 if 237 opposite signal within 4 bars.'}, {'A': '422', 'B': '237', 'method': 'MTF', 'k': 0, 'logic': 'Mixing 422 with 237 using MTF. Filter 422 using 237 on higher TF.'}, {'A': '422', 'B': '148', 'method': 'FILTER', 'k': 0, 'logic': 'Mixing 422 with 148 using FILTER. Ensure 148 state aligns.'}, {'A': '422', 'B': '148', 'method': 'CONFIRM', 'k': 3, 'logic': 'Mixing 422 with 148 using CONFIRM. Confirm 422 with 148 signal within 3 bars.'}, {'A': '422', 'B': '148', 'method': 'VETO', 'k': 3, 'logic': 'Mixing 422 with 148 using VETO. Veto 422 if 148 opposite signal within 3 bars.'}, {'A': '422', 'B': '148', 'method': 'MTF', 'k': 0, 'logic': 'Mixing 422 with 148 using MTF. Filter 422 using 148 on higher TF.'}, {'A': '422', 'B': '161', 'method': 'FILTER', 'k': 0, 'logic': 'Mixing 422 with 161 using FILTER. Ensure 161 state aligns.'}, {'A': '422', 'B': '161', 'method': 'CONFIRM', 'k': 2, 'logic': 'Mixing 422 with 161 using CONFIRM. Confirm 422 with 161 signal within 2 bars.'}, {'A': '422', 'B': '161', 'method': 'VETO', 'k': 2, 'logic': 'Mixing 422 with 161 using VETO. Veto 422 if 161 opposite signal within 2 bars.'}, {'A': '422', 'B': '161', 'method': 'MTF', 'k': 0, 'logic': 'Mixing 422 with 161 using MTF. Filter 422 using 161 on higher TF.'}, {'A': '422', 'B': '379', 'method': 'FILTER', 'k': 0, 'logic': 'Mixing 422 with 379 using FILTER. Ensure 379 state aligns.'}, {'A': '422', 'B': '379', 'method': 'CONFIRM', 'k': 5, 'logic': 'Mixing 422 with 379 using CONFIRM. Confirm 422 with 379 signal within 5 bars.'}, {'A': '422', 'B': '379', 'method': 'VETO', 'k': 2, 'logic': 'Mixing 422 with 379 using VETO. Veto 422 if 379 opposite signal within 2 bars.'}, {'A': '422', 'B': '379', 'method': 'MTF', 'k': 0, 'logic': 'Mixing 422 with 379 using MTF. Filter 422 using 379 on higher TF.'}, {'A': '422', 'B': '342', 'method': 'FILTER', 'k': 0, 'logic': 'Mixing 422 with 342 using FILTER. Ensure 342 state aligns.'}, {'A': '422', 'B': '342', 'method': 'CONFIRM', 'k': 4, 'logic': 'Mixing 422 with 342 using CONFIRM. Confirm 422 with 342 signal within 4 bars.'}, {'A': '422', 'B': '342', 'method': 'VETO', 'k': 3, 'logic': 'Mixing 422 with 342 using VETO. Veto 422 if 342 opposite signal within 3 bars.'}, {'A': '422', 'B': '342', 'method': 'MTF', 'k': 0, 'logic': 'Mixing 422 with 342 using MTF. Filter 422 using 342 on higher TF.'}, {'A': '422', 'B': '356', 'method': 'FILTER', 'k': 0, 'logic': 'Mixing 422 with 356 using FILTER. Ensure 356 state aligns.'}, {'A': '422', 'B': '356', 'method': 'CONFIRM', 'k': 5, 'logic': 'Mixing 422 with 356 using CONFIRM. Confirm 422 with 356 signal within 5 bars.'}, {'A': '422', 'B': '356', 'method': 'VETO', 'k': 3, 'logic': 'Mixing 422 with 356 using VETO. Veto 422 if 356 opposite signal within 3 bars.'}, {'A': '422', 'B': '356', 'method': 'MTF', 'k': 0, 'logic': 'Mixing 422 with 356 using MTF. Filter 422 using 356 on higher TF.'}])

progress_path = 'strategy/s20_gen/progress.json'
mix_log_path = 'strategy/s20_gen/mix_log.md'

progress = load_json(progress_path)
if 'next' not in progress:
    progress['next'] = 429
    save_json(progress_path, progress)

print(f"Starting batch mix from next={progress['next']}")

processed_count = 0
for p in pairs:
    if processed_count >= 15:
        print("Reached 15 successful processes. Stopping.")
        break
    N = progress['next']
    if str(N).endswith('0'):
        print(f"Skipping {N} as it ends with 0")
        N += 1
        progress['next'] = N
        save_json(progress_path, progress)

    print(f"\n--- Processing S20.{N} ---")
    
    # Check mix log for duplicate hypothesis
    with open(mix_log_path, 'r', encoding='utf-8') as f:
        mix_log = f.read()
    
    skip = False
    for line in mix_log.split('\n'):
        if f"| 20.{p['A']} | 20.{p['B']} | {p['method']}" in line or f"| {p['A']} | {p['B']} | {p['method']}" in line:
            print("Already in mix_log, skipping this pair logic.")
            skip = True
            break
    
    if skip:
        continue
        
    proc_chk = subprocess.run([sys.executable, 'strategy/s20_gen/mix_pair_check.py', str(p['A']), str(p['B'])], capture_output=True, text=True, encoding='utf-8')
    print(f"mix_pair_check.py output:\\n{proc_chk.stdout.encode('cp874', 'replace').decode('cp874')}")
    if proc_chk.returncode == 1:
        print("mix_pair_check.py returned exit code 1. Skipping this pair.")
        continue
        
    meta_A = get_parent_meta(p['A'])
    
    strategy_code = f'''import numpy as np
import pandas as pd
import importlib.util
import sys

META = {{
    "sid": "20.{N}",
    "name": "Mix {p['A']} + {p['B']} ({p['method']})",
    "concept": "Mixed Strategy: {p['A']} and {p['B']}",
    "logic": "{p['logic']}",
    "parents": ["20.{p['A']}", "20.{p['B']}"],
    "mix": "{p['method']}",
    "sl_atr": {meta_A.get('sl_atr', 2.0)},
    "rr": {meta_A.get('rr', 1.5)},
    "max_hold": {meta_A.get('max_hold', 24)},
    "be_r": {meta_A.get('be_r', 1.0)}
}}

def load_strategy(sid):
    path = f'strategy/s20.{{sid}}/strategy20_{{sid}}.py'
    spec = importlib.util.spec_from_file_location(f"s20_{{sid}}", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

mod_a = load_strategy("{p['A']}")
mod_b = load_strategy("{p['B']}")

def generate(df, tf):
    sig_a = mod_a.generate(df, tf)
'''

    if p['method'] == 'CONFIRM':
        strategy_code += f'''
    sig_b = mod_b.generate(df, tf)
    out = np.zeros(len(df), dtype=np.int8)
    
    sig_b_s = pd.Series(sig_b)
    b_long_recent = sig_b_s.rolling(window={p['k']+1}, min_periods=1).max() == 1
    b_short_recent = sig_b_s.rolling(window={p['k']+1}, min_periods=1).min() == -1
    
    out[(sig_a == 1) & b_long_recent] = 1
    out[(sig_a == -1) & b_short_recent] = -1
    return out
'''
    elif p['method'] == 'FILTER':
        strategy_code += f'''
    sig_b = mod_b.generate(df, tf)
    out = np.zeros(len(df), dtype=np.int8)
    
    # State of B
    state_b = pd.Series(sig_b).replace(0, np.nan).ffill().fillna(0)
    
    out[(sig_a == 1) & (state_b == 1)] = 1
    out[(sig_a == -1) & (state_b == -1)] = -1
    return out
'''
    elif p['method'] == 'VETO':
        strategy_code += f'''
    sig_b = mod_b.generate(df, tf)
    out = np.zeros(len(df), dtype=np.int8)
    
    sig_b_s = pd.Series(sig_b)
    b_long_recent = sig_b_s.rolling(window={p['k']+1}, min_periods=1).max() == 1
    b_short_recent = sig_b_s.rolling(window={p['k']+1}, min_periods=1).min() == -1
    
    out[(sig_a == 1) & ~b_short_recent] = 1
    out[(sig_a == -1) & ~b_long_recent] = -1
    return out
'''
    elif p['method'] == 'MTF':
        strategy_code += f'''
    import sys
    sys.path.append('.')
    import data
    
    tf_mapping = {{'M1': 'M5', 'M5': 'M15', 'M15': 'H1', 'M30': 'H4', 'H1': 'D1', 'H4': 'D1', 'D1': 'D1'}}
    tf_big = tf_mapping.get(tf, 'D1')
    
    tf_sec = {{'M1': 60, 'M5': 300, 'M15': 900, 'M30': 1800, 'H1': 3600, 'H4': 14400, 'D1': 86400}}
    
    if tf_big == tf:
        return mod_a.generate(df, tf)
        
    df_big = pd.DataFrame(data.load_bars(tf_big))
    
    # causal mapping
    current_time_max = df['time'].iloc[-1] + tf_sec[tf]
    df_big = df_big[(df_big['time'] + tf_sec[tf_big]) <= current_time_max].copy()
    
    if len(df_big) == 0:
        return np.zeros(len(df), dtype=np.int8)
        
    sig_b_big = mod_b.generate(df_big, tf_big)
    state_b_big = pd.Series(sig_b_big, index=df_big['time']).replace(0, np.nan).ffill().fillna(0)
    
    # align
    state_aligned = pd.Series(index=df['time'], dtype=float)
    # the last closed big bar state before current bar
    
    # We map state_b_big's time (which is open time) + tf_sec[tf_big] (which is close time)
    close_times = df_big['time'] + tf_sec[tf_big]
    state_b_big.index = close_times
    
    # reindex with ffill
    state_aligned = state_b_big.reindex(df['time'].values, method='ffill').fillna(0)
    
    out = np.zeros(len(df), dtype=np.int8)
    sig_a = mod_a.generate(df, tf)
    
    out[(sig_a == 1) & (state_aligned.values == 1)] = 1
    out[(sig_a == -1) & (state_aligned.values == -1)] = -1
    return out
'''

    os.makedirs(f'strategy/s20.{N}', exist_ok=True)
    with open(f'strategy/s20.{N}/strategy20_{N}.py', 'w', encoding='utf-8') as f:
        f.write(strategy_code)
        
    # Run run_one.py
    print(f"Running run_one.py for {N}")
    proc = subprocess.run([sys.executable, 'strategy/s20_gen/run_one.py', str(N)], capture_output=True, text=True, encoding='utf-8')
    with open(f'strategy/s20.{N}/run_one_stdout.txt', 'w', encoding='utf-8') as f_out:
        f_out.write(proc.stdout)
    if proc.stderr: print("ERR:", proc.stderr.encode('cp874', 'replace').decode('cp874'))
    
    # Check result
    res_path = f'strategy/s20.{N}/result_365d.json'
    res_data = load_json(res_path)
    
    verdict_str = "FAIL"
    is_duplicate = "DUPLICATE" in proc.stdout
    if is_duplicate:
        verdict_str = "DUPLICATE"
    elif not res_data:
        verdict_str = "FAIL (No result)"
    else:
        # Check TFs
        tfs = res_data.get('tf', {})
        pass_tfs = [tf for tf, d in tfs.items() if isinstance(d, dict) and d.get('verdict') == 'PASS']
        if pass_tfs:
            verdict_str = f"PASS ({','.join(pass_tfs)})"
        else:
            weak_tfs = [tf for tf, d in tfs.items() if isinstance(d, dict) and d.get('verdict') == 'WEAK']
            if weak_tfs:
                verdict_str = "WEAK"
    
    print(f"Verdict: {verdict_str}")
    
    if is_duplicate or verdict_str == "FAIL (No result)" or (not res_data.get('lookahead_ok', True)):
        print("Cleaning up due to fail/duplicate/lookahead")
        shutil.rmtree(f'strategy/s20.{N}', ignore_errors=True)
        shutil.rmtree(f'reports/s20_{N}', ignore_errors=True)
    else:
        if pass_tfs:
            print(f"Running final_gate for {N}")
            subprocess.run([sys.executable, 'strategy/s20_gen/final_gate.py', str(N)])
            
            # Create mix_check.txt
            try:
                res_a = load_json(f'strategy/s20.{p["A"]}/result_365d.json')
                mix_check = "MIX_OK\n"
                for p_tf in pass_tfs:
                    mix_pf = tfs[p_tf]['pf']
                    mix_oos = tfs[p_tf]['oos']['net']
                    mix_n = tfs[p_tf]['n']
                    
                    a_pf = res_a['tf'][p_tf]['pf']
                    a_oos = res_a['tf'][p_tf]['oos']['net']
                    
                    if mix_n < 50:
                        mix_check = f"MIX_FAIL: b (n={mix_n} < 50 in {p_tf})\n"
                    elif mix_pf < a_pf + 0.10:
                        mix_check = f"MIX_FAIL: a (PF {mix_pf} not > {a_pf}+0.10 in {p_tf})\n"
                    elif mix_oos < a_oos:
                        mix_check = f"MIX_FAIL: a (OOS {mix_oos} worse than A {a_oos} in {p_tf})\n"
                    
                    mix_check += f"{p_tf}: PF {mix_pf} vs A {a_pf} | OOS {mix_oos} vs A {a_oos} | N {mix_n}\n"
                    
                with open(f'strategy/s20.{N}/mix_check.txt', 'w', encoding='utf-8') as f:
                    f.write(mix_check)
            except Exception as e:
                print("Error creating mix_check:", e)
                
        # Clean reports for non-winners
        fg_path = f'strategy/s20.{N}/final_gate.txt'
        mc_path = f'strategy/s20.{N}/mix_check.txt'
        is_winner = False
        if os.path.exists(fg_path) and os.path.exists(mc_path):
            with open(fg_path, 'r', encoding='utf-8') as f: fg = f.read()
            with open(mc_path, 'r', encoding='utf-8') as f: mc = f.read()
            if fg.startswith('WINNER') and mc.startswith('MIX_OK'):
                is_winner = True
        
        if not is_winner:
            shutil.rmtree(f'reports/s20_{N}', ignore_errors=True)
            
    date_str = datetime.now().strftime('%Y-%m-%d')
    with open(mix_log_path, 'a', encoding='utf-8') as f:
        f.write(f"| {N} | 20.{p['A']} | 20.{p['B']} | {p['method']} | {date_str} | {verdict_str} |\n")
        
    if not (is_duplicate or verdict_str == "FAIL (No result)"):
        progress['next'] = N + 1
        processed_count += 1
    save_json(progress_path, progress)
    
    print(f"Finished {N}, next is {progress['next']}")
