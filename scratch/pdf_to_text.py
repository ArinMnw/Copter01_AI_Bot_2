import fitz
import sys

pdf_path = r"C:\Users\Copter\Downloads\อออิน4s\4s vip\ท่าไม้ตายอออิน4วิ 2.pdf"
out_path = r"d:\Project\Copter01_AI_Bot_2\scratch\pdf_text.txt"

with fitz.open(pdf_path) as doc:
    text = ""
    for i in range(len(doc)):
        text += f"\n--- Page {i+1} ---\n"
        text += doc[i].get_text("text")

with open(out_path, "w", encoding="utf-8") as f:
    f.write(text)
print("Saved to", out_path)
