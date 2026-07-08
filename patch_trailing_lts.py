with open('trailing.py', 'r', encoding='utf-8') as f:
    content = f.read()

rep1 = """        ticket = pos.ticket
        
        # กรองให้ทำเฉพาะ LTS (SID >= 80) เท่านั้น
        sid = _resolve_pos_sid(ticket, getattr(pos, "comment", ""))
        if sid < 80:
            continue
            
        is_buy = pos.type == mt5.ORDER_TYPE_BUY"""

content = content.replace('        ticket = pos.ticket\n        is_buy = pos.type == mt5.ORDER_TYPE_BUY', rep1)

with open('trailing.py', 'w', encoding='utf-8') as f:
    f.write(content)
print('trailing.py patched for LTS only')
