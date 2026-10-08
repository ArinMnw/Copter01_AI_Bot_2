import sys, re, itertools
sys.path.insert(0, 'strategy/s20_gen')
import mix_pair_check as m
rows = m.load_rows()
S = ['194','168','242','277','143','169','158','153','356','342','379','255','210','237','148','161','160','228','184','281','177','751','339','422']
for a, b in itertools.combinations(S, 2):
    u = [x[2] for x in rows if frozenset((x[0], x[1])) == frozenset((a, b))]
    if len(u) < 2:
        print(a, b, u)
for s in S:
    t = open(f'strategy/s20.{s}/strategy20_{s}.py', encoding='utf-8').read()
    mm = re.search(r"['\"]name['\"]:\s*['\"]([^'\"]+)", t)
    print(s, mm.group(1) if mm else '?')
