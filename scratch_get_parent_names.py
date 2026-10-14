import json

for sid in ['339', '191', '381', '151', '238', '232', '224', '367', '200', '397', '269', '369', '374', '172', '355', '267']:
    try:
        with open(f'strategy/s20.{sid}/result_365d.json', encoding='utf-8') as f:
            data = json.load(f)
            print(f'S20.{sid}: {data.get("name", "")}')
    except Exception as e:
        print(f'S20.{sid}: Error')
