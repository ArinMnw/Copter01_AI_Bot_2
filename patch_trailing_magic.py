import re

with open('trailing.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_lines = []
for i, line in enumerate(lines):
    new_lines.append(line)
    
    # Check if this line starts a loop over positions or orders
    m_pos = re.match(r'^(\s*)for\s+pos\s+in\s+positions\s*:\s*(#.*)?$', line)
    if m_pos:
        indent = m_pos.group(1)
        # Add the filter line right after the for-loop line
        new_lines.append(f'{indent}    if getattr(pos, "magic", 0) >= 990000: continue\n')
        continue
        
    m_order = re.match(r'^(\s*)for\s+order\s+in\s+orders\s*:\s*(#.*)?$', line)
    if m_order:
        indent = m_order.group(1)
        new_lines.append(f'{indent}    if getattr(order, "magic", 0) >= 990000: continue\n')
        continue

with open('trailing.py', 'w', encoding='utf-8') as f:
    f.writelines(new_lines)

print("Patched trailing.py successfully!")
