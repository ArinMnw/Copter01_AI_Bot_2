import subprocess

parents_A = ['339', '422']
parents_B = ['242', '158', '277', '194', '143', '168', '255', '210', '237', '148', '161', '379', '342', '356']

valid_pairs = []

for a in parents_A:
    for b in parents_B:
        if a == b: continue
        res = subprocess.run(['python', 'strategy/s20_gen/mix_pair_check.py', a, b], capture_output=True, text=True, encoding='utf-8')
        if res.returncode == 0:
            valid_pairs.append((a, b, res.stdout.strip()))

for vp in valid_pairs:
    print(f"{vp[0]} + {vp[1]}: {vp[2]}")
