with open('mt5_utils.py', 'r', encoding='utf-8') as f:
    content = f.read()

rep1 = """        if getattr(config, "ML_SCORING_ENABLED", False):
            try:
                sid_num = int(str(sid).replace("S", ""))
            except:
                sid_num = 0
            
            if sid_num >= 80:
                import ml_scoring"""

content = content.replace('        if getattr(config, "ML_SCORING_ENABLED", False):\n            import ml_scoring', rep1)

with open('mt5_utils.py', 'w', encoding='utf-8') as f:
    f.write(content)
print('mt5_utils.py patched to limit ML scoring to LTS')
