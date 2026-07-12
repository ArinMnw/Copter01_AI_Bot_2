
import json
with open(r'C:\Users\Copter\.gemini\antigravity-ide\brain\46b76b60-dc83-4319-86c1-8cec2d62a6ff\.system_generated\logs\transcript_full.jsonl', 'r', encoding='utf-8') as f:
    for line in f:
        if 'มิติ' in line:
            obj = json.loads(line)
            if obj.get('type') in ('PLANNER_RESPONSE', 'USER_INPUT'):
                text = obj.get('content', '')
                if 'มิติ' in text:
                    print(f'[{obj.get(\'source\')}] ' + text[:1500].replace('\n', ' '))

