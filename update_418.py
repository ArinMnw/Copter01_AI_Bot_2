import json
import os

try:
    with open('strategy/s20_gen/progress.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    data['418'] = {
        "name": "Keltner Momentum Reversal",
        "pass_tfs": [],
        "total_net": -344.69,
        "total_pf": 0.631
    }
    data['next'] = 419
    
    with open('strategy/s20_gen/progress_tmp.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=1, ensure_ascii=False)
        
    os.replace('strategy/s20_gen/progress_tmp.json', 'strategy/s20_gen/progress.json')
    print("Progress updated to 419")
except Exception as e:
    print("Error:", e)
