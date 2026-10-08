import subprocess

winners = [143, 148, 161, 168, 194, 210, 237, 242, 255, 277, 339, 342, 356, 422, 471, 512, 614, 637, 648, 685, 689, 708, 724, 732, 751, 753, 778]
valid = []
for pA in [339, 422]:
    for pB in winners:
        if pA == pB: continue
        res = subprocess.run(['python', 'strategy/s20_gen/mix_pair_check.py', str(pA), str(pB)], capture_output=True, encoding='utf-8')
        if res.returncode == 0:
            valid.append((pA, pB))

print(valid)
