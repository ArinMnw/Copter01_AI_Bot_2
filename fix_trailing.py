import sys

with open('trailing.py', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace('ทำงาน*\nTicket', 'ทำงาน*\\nTicket')
content = content.replace('})\nเหตุผล', '})\\nเหตุผล')
content = content.replace('reason}\nเพื่อรักษา', 'reason}\\nเพื่อรักษา')

with open('trailing.py', 'w', encoding='utf-8') as f:
    f.write(content)
print('Fixed!')
