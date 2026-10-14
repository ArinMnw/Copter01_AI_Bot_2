import json

parents_to_check = ['339', '422', '242', '158', '277', '194', '143', '168', '255', '210', '237', '148', '161', '379', '342', '356']
print("Parent Performance:")
for sid in parents_to_check:
    try:
        data = json.load(open(f'strategy/s20.{sid}/result_365d.json', encoding='utf-8'))
        has_good_tf = False
        output = [f'S20.{sid} - {data.get("name", "")}:']
        for tf, d in data.get('tf', {}).items():
            verdict = d.get('verdict', 'FAIL')
            oos = d.get('oos', {})
            oos_net = oos.get('net', 0)
            if verdict in ['PASS', 'WEAK'] and oos_net > 0:
                has_good_tf = True
                output.append(f'  {tf}: {verdict} OOS net={oos_net:.2f} PF={d.get("pf", 0):.3f} trades={d.get("n", 0)}')
        if has_good_tf:
            print('\n'.join(output))
    except Exception as e:
        pass
