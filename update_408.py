import json

try:
    with open('strategy/s20_gen/progress.json', 'r+', encoding='utf-8') as f:
        data = json.load(f)
        
        data['408'] = {
            "name": "Triple EMA Pullback Stoch",
            "pass_tfs": [],
            "total_net": -655.51,
            "total_pf": 0.897
        }
        data['next'] = 409
        
        f.seek(0)
        f.truncate()
        json.dump(data, f, indent=1, ensure_ascii=False)
    print("Progress updated to 409")
except Exception as e:
    print("Error:", e)
