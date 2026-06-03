"""Unit test rules 4-11 price violation"""
import sys, hhll_swing
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

def mk(pair):
    return {'price': pair[1], 'time': 1000, 'label': pair[0]} if pair else None

tests = [
    # (name, hl, p_hl, hh, p_hh, lh, p_lh, ll, p_ll, expected)
    ('Rule4  HL->HL curr<prev  → BEAR',
     ('HL',4478),('HL',4522), None,None, None,None, None,None, 'BEAR'),
    ('Rule4  HL->HL curr>prev  → None (ok)',
     ('HL',4535),('HL',4522), None,None, None,None, None,None, None),
    ('Rule5  HH->HH curr<prev  → BEAR',
     None,None, ('HH',4541),('HH',4595), None,None, None,None, 'BEAR'),
    ('Rule5  HH->HH curr>prev  → None (ok)',
     None,None, ('HH',4595),('HH',4541), None,None, None,None, None),
    ('Rule6  LH->LH curr>prev  → BULL',
     None,None, None,None, ('LH',4510),('LH',4496), None,None, 'BULL'),
    ('Rule6  LH->LH curr<prev  → None (ok)',
     None,None, None,None, ('LH',4490),('LH',4496), None,None, None),
    ('Rule7  LL->LL curr>prev  → BULL',
     None,None, None,None, None,None, ('LL',4500),('LL',4447), 'BULL'),
    ('Rule7  LL->LL curr<prev  → None (ok)',
     None,None, None,None, None,None, ('LL',4430),('LL',4447), None),
    ('Rule8  HH->LH curr>prev  → BULL',
     None,None, None,None, ('LH',4550),('HH',4541), None,None, 'BULL'),
    ('Rule8  HH->LH curr<prev  → None (ok)',
     None,None, None,None, ('LH',4520),('HH',4541), None,None, None),
    ('Rule9  LH->HH curr<prev  → BEAR',
     None,None, ('HH',4450),('LH',4496), None,None, None,None, 'BEAR'),
    ('Rule9  LH->HH curr>prev  → None (ok)',
     None,None, ('HH',4550),('LH',4496), None,None, None,None, None),
    ('Rule10 LL->HL curr<prev  → BEAR',
     ('HL',4460),('LL',4470), None,None, None,None, None,None, 'BEAR'),
    ('Rule10 LL->HL curr>prev  → None (ok)',
     ('HL',4480),('LL',4470), None,None, None,None, None,None, None),
    ('Rule11 HL->LL curr>prev  → BULL',
     None,None, None,None, None,None, ('LL',4490),('HL',4480), 'BULL'),
    ('Rule11 HL->LL curr<prev  → None (ok)',
     None,None, None,None, None,None, ('LL',4460),('HL',4480), None),
]

passed = 0
failed = 0
for name, hl, p_hl, hh, p_hh, lh, p_lh, ll, p_ll, expected in tests:
    hhll_swing._hhll_data['_t'] = {
        'hl': mk(hl), 'prev_hl': mk(p_hl),
        'hh': mk(hh), 'prev_hh': mk(p_hh),
        'lh': mk(lh), 'prev_lh': mk(p_lh),
        'll': mk(ll), 'prev_ll': mk(p_ll),
        'structure': [],
    }
    v = hhll_swing._check_price_violation('_t')
    ok = v == expected
    passed += ok; failed += (not ok)
    tag = 'OK  ' if ok else 'FAIL'
    print(f'  {tag} | {name}: got={v}')

print(f"\n  passed={passed} failed={failed}")
