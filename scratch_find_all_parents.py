import json
import glob
import os

all_results = glob.glob('strategy/s20.*/result_365d.json')
good_parents = []
for p in all_results:
    sid = p.split('s20.')[1].split('\\')[0].split('/')[0]
    try:
        data = json.load(open(p, encoding='utf-8'))
        has_good_tf = False
        for tf, d in data.get('tf', {}).items():
            if d.get('verdict') in ['PASS', 'WEAK'] and d.get('oos', {}).get('net', 0) > 0:
                has_good_tf = True
                break
        if has_good_tf:
            good_parents.append(sid)
    except Exception as e:
        pass

print(f"Found {len(good_parents)} good parents.")
print(",".join(good_parents))
