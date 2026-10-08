import json
import os

try:
    with open('strategy/s20_gen/progress.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    data['427'] = {
        "name": "LinReg RSI Pullback Acceleration",
        "pass_tfs": [],
        "total_net": -235.96,
        "total_pf": 0.935
    }
    data['next'] = 428
    
    with open('strategy/s20_gen/progress_tmp.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=1, ensure_ascii=False)
        
    os.replace('strategy/s20_gen/progress_tmp.json', 'strategy/s20_gen/progress.json')
    print("Progress updated to 428")
except Exception as e:
    print("Error:", e)
