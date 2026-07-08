with open('mt5_utils.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_lines = []
in_ml_block = False
ml_indent = ""
for line in lines:
    if 'if getattr(config, "ML_SCORING_ENABLED", False):' in line:
        in_ml_block = True
        ml_indent = line.split('if')[0]
        new_lines.append(line)
        new_lines.append(ml_indent + '    try:\n')
        new_lines.append(ml_indent + '        sid_num = int(str(sid).replace("S", ""))\n')
        new_lines.append(ml_indent + '    except:\n')
        new_lines.append(ml_indent + '        sid_num = 0\n')
        new_lines.append(ml_indent + '    if sid_num >= 80:\n')
        continue
        
    if in_ml_block:
        if line.strip() == '':
            new_lines.append(line)
            continue
            
        if line.startswith(ml_indent + '    '):
            # This line belongs to the ML block (like import ml_scoring, features = ...)
            # BUT wait, the lines after 'if sid_num >= 80:' need extra indentation!
            # Let's just indent it if it was previously 4 spaces deep inside the config block
            
            # EXCEPT the try/except block we already inserted, those lines are not in the original
            if 'try:' in line or 'sid_num =' in line or 'except:' in line or 'if sid_num >=' in line:
                pass # This is from my previous bad patch! I need to skip them to clean up
                continue
                
            # Wait, my previous patch actually replaced the lines in mt5_utils.py, 
            # so the try/except block is already there!
            pass
            
        else:
            in_ml_block = False
            
with open('mt5_utils.py', 'w', encoding='utf-8') as f:
    f.writelines(new_lines)
