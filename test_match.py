import sys
lines = open('handlers/callback_handler.py', encoding='utf-8').readlines()
for i, line in enumerate(lines):
    if 'elif data ==' in line or 'if data ==' in line:
        val = line.split('==')[1].strip().strip('\'\"').strip(':\'\"')
        if 'prompt_s20_8_risk_pct' == val:
            print(f'Match == at {i+1}: {line.strip()}')
    elif 'elif data.startswith' in line or 'if data.startswith' in line:
        val = line.split('startswith(')[1].split(')')[0].strip('\'\"')
        if 'prompt_s20_8_risk_pct'.startswith(val):
            print(f'Match startswith at {i+1}: {line.strip()}')
