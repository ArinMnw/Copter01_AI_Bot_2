with open('ml_scoring.py', 'r', encoding='utf-8') as f:
    content = f.read()

orig_loop = """        # Build position_id -> sid map from IN deals
        pos_sid_map = {}
        for _, row in df[df['entry'] == mt5.DEAL_ENTRY_IN].iterrows():
            pos_id = row['position_id']
            comment = str(row.get('comment', ''))
            sid = 0
            if "_S" in comment:
                try:
                    sid = int(comment.split("_S")[1].split("_")[0])
                except:
                    pass
            pos_sid_map[pos_id] = sid"""

new_loop = """        # Build position_id -> sid map from IN deals
        pos_sid_map = {}
        for _, row in df[df['entry'] == mt5.DEAL_ENTRY_IN].iterrows():
            pos_id = row['position_id']
            comment = str(row.get('comment', ''))
            sid = 0
            if "LTS" in comment:
                try:
                    sid = int(comment.split("LTS")[1].split("_")[0])
                except:
                    pass
            elif "_S" in comment:
                try:
                    sid = int(comment.split("_S")[1].split("_")[0])
                except:
                    pass
            pos_sid_map[pos_id] = sid"""

content = content.replace(orig_loop, new_loop)

# Also need to make sure we don't crash if len(X) == 0
crash_check = """        print(f"[ML Scoring] Training RandomForest on {len(X)} historical trades...")
        clf = RandomForestClassifier(n_estimators=100, max_depth=5, random_state=42)"""

safe_check = """        print(f"[ML Scoring] Training RandomForest on {len(X)} historical trades...")
        if len(X) < 10:
            print("[ML Scoring] Not enough LTS trades to train (need at least 10).")
            return False
            
        clf = RandomForestClassifier(n_estimators=100, max_depth=5, random_state=42)"""

content = content.replace(crash_check, safe_check)

with open('ml_scoring.py', 'w', encoding='utf-8') as f:
    f.write(content)
print('ml_scoring.py patched for LTS parsing and safe check')
