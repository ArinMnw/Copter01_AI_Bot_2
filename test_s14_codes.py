import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from mt5_utils import _pattern_comment_code

tests = [
    ('M5_S14_BSS', 'ท่าที่ 14 Sweep RSI BUY -- Sweep Swing', '14'),
    ('M5_S14_BRS', 'ท่าที่ 14 Sweep RSI BUY -- Sweep กลับตัว', '14'),
    ('M5_S14_SSS', 'ท่าที่ 14 Sweep RSI SELL -- Sweep Swing', '14'),
    ('M5_S14_SRS', 'ท่าที่ 14 Sweep RSI SELL -- Sweep กลับตัว', '14'),
]
all_pass = True
for expected_sfx, pattern, sid in tests:
    code = _pattern_comment_code(pattern, sid)
    full = f'M5_S14_{code}'
    ok = full == expected_sfx
    if not ok: all_pass = False
    print(f'  {"OK" if ok else "FAIL"} expected={expected_sfx} got={full}')

# Test SIDEWAY block
import config
print(f'\nS14_BLOCK_SIDEWAY = {config.S14_BLOCK_SIDEWAY}')
print(f'All tests pass: {all_pass}')
