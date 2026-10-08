import subprocess
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

winners = [143, 148, 161, 168, 194, 210, 237, 242, 255, 277, 339, 342, 356, 422]
valid = []
for a in winners:
    for b in winners:
        if a == b: continue
        res = subprocess.run(['python', 'strategy/s20_gen/mix_pair_check.py', str(a), str(b)], capture_output=True)
        if res.returncode == 0:
            valid.append((a, b))

print(f"Total valid pairs: {len(valid)}")
for a, b in valid[:50]:
    print(f'VALID: {a} {b}')
