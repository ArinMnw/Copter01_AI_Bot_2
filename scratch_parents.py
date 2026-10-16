import os, re

winners = ['614', '648', '708', '724', '732', '753', '778', '854', '888', '937']
for w in winners:
    path = f'strategy/s20.{w}/strategy20_{w}.py'
    if os.path.exists(path):
        txt = open(path, encoding='utf-8').read()
        match = re.search(r'"parents"\s*:\s*\[(.*?)\]', txt, re.DOTALL)
        if match:
            print(f'{w}: parents=[{match.group(1).strip()}]')
        else:
            print(f'{w}: no parents')
