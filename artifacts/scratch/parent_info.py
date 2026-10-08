import re, sys
for s in sys.argv[1:]:
    t = open(f'strategy/s20.{s}/strategy20_{s}.py', encoding='utf-8').read()
    def g(k):
        m = re.search(r'"' + k + r'":\s*([^\n]+)', t)
        return m.group(1)[:140] if m else ''
    print(s, g('name'), '|', g('concept'), '|', g('sl_atr'), g('rr'), g('max_hold'), g('be_r'))
