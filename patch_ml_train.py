with open('ml_scoring.py', 'r', encoding='utf-8') as f:
    content = f.read()

orig_loop = """        df = pd.DataFrame(list(history_deals), columns=history_deals[0]._asdict().keys())
        df['time'] = pd.to_datetime(df['time'], unit='s')
        
        df_out = df[df['entry'] == mt5.DEAL_ENTRY_OUT].copy()
        
        X, y = [], []
        for _, row in df_out.iterrows():"""

new_loop = """        df = pd.DataFrame(list(history_deals), columns=history_deals[0]._asdict().keys())
        df['time'] = pd.to_datetime(df['time'], unit='s')
        
        # Build position_id -> sid map from IN deals
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
            pos_sid_map[pos_id] = sid
            
        df_out = df[df['entry'] == mt5.DEAL_ENTRY_OUT].copy()
        
        X, y = [], []
        for _, row in df_out.iterrows():
            pos_id = row['position_id']
            sid = pos_sid_map.get(pos_id, 0)
            
            # Filter for LTS only
            if sid < 80:
                continue
"""

content = content.replace(orig_loop, new_loop)

with open('ml_scoring.py', 'w', encoding='utf-8') as f:
    f.write(content)
print('ml_scoring.py patched for LTS training filter')
