with open('strategy_lts.py', 'r', encoding='utf-8') as f:
    content = f.read()

line_to_add = '_load_lts_weights(os.path.join(_dir, "lts_optimized_weights.txt"), "LTS10K")'

if line_to_add not in content:
    content += f'\n{line_to_add}\n'

with open('strategy_lts.py', 'w', encoding='utf-8') as f:
    f.write(content)
print('strategy_lts.py updated with LTS10K weights')
