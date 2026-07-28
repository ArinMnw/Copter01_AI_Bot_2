with open('d:\\Project\\Copter01_AI_Bot_2\\config.py', 'r', encoding='utf-8') as f:
    for i, line in enumerate(f):
        if 'SYMBOL' in line.upper():
            print(f"{i}: {line.strip()}")
