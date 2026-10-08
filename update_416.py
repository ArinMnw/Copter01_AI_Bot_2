import json
import os

try:
    with open('strategy/s20_gen/progress.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    data['416'] = {
        "name": "PSAR Keltner Pullback",
        "pass_tfs": ["H1"],
        "total_net": -1467.67,
        "total_pf": 0.884
    }
    data['next'] = 417
    
    with open('strategy/s20_gen/progress_tmp.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=1, ensure_ascii=False)
        
    os.replace('strategy/s20_gen/progress_tmp.json', 'strategy/s20_gen/progress.json')
    print("Progress updated to 417")
except Exception as e:
    print("Error:", e)
