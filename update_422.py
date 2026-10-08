import json
import os

try:
    with open('strategy/s20_gen/progress.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    data['422'] = {
        "name": "Triple MA Volatility Breakout",
        "pass_tfs": ["M15"],
        "total_net": 1773.37,
        "total_pf": 1.126
    }
    data['next'] = 423
    
    with open('strategy/s20_gen/progress_tmp.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=1, ensure_ascii=False)
        
    os.replace('strategy/s20_gen/progress_tmp.json', 'strategy/s20_gen/progress.json')
    print("Progress updated to 423")
except Exception as e:
    print("Error:", e)
