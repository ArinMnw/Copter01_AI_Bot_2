import sys
with open('v38_standalone_group24.py', 'r', encoding='utf-8') as f:
    text = f.read()

text = text.replace('days = 365', 'days = 3')
text = text.replace('"FVG": ["H1"]', '"FVG": ["M15"]')
text = text.replace("'FVG': ['H1']", "'FVG': ['M15']")

with open('g24_fast.py', 'w', encoding='utf-8') as f:
    f.write(text)
print("done")
