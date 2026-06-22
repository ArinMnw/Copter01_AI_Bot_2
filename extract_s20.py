import os

def extract_keywords(file_path, keywords, context_lines=5):
    results = []
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            for i, line in enumerate(lines):
                if any(kw.lower() in line.lower() for kw in keywords):
                    start = max(0, i - context_lines)
                    end = min(len(lines), i + context_lines + 1)
                    block = "".join(lines[start:end])
                    results.append(f"--- Match found around line {i+1} ---\n{block}")
    except Exception as e:
        results.append(str(e))
    return results

keywords = [
    "s20", "ท่าไม้ตาย", "entry", "จุดเข้า", "tp", "sl", "stop loss",
    "risk", "money", "ทุน", "เงื่อนไข", "กลืนกิน", "ตำหนิ", "2L", "2H", "LQ", "Sweep",
    "solid", "พักตัว", "fvg", "divergence"
]

vip_res = extract_keywords("all_vip.txt", keywords, 2)
nay_res = extract_keywords("all_nay.txt", keywords, 2)

with open("s20_extracted.txt", "w", encoding="utf-8") as f:
    f.write("=== VIP ===\n")
    f.write("\n".join(vip_res[:100])) # Limit to 100 blocks
    f.write("\n=== NAY ===\n")
    f.write("\n".join(nay_res[:100]))

print("Extraction done.")
