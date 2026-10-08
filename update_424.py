import json
import os

try:
    with open('strategy/s20_gen/progress.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    data['424'] = {
        "name": "Heikin Ashi WMA Pullback",
        "pass_tfs": [],
        "total_net": -334.94,
        "total_pf": 0.891
    }
    data['next'] = 425
    
    with open('strategy/s20_gen/progress_tmp.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=1, ensure_ascii=False)
        
    os.replace('strategy/s20_gen/progress_tmp.json', 'strategy/s20_gen/progress.json')
    print("Progress updated to 425")
except Exception as e:
    print("Error:", e)
