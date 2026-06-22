import os

parts = [f"ALCHEMIST 2.00 AbayFX (1)_unlocked_part{i}_pdf.md" for i in range(1, 11)]
output = "ALCHEMIST 2.00 AbayFX (1)_unlocked_pdf.md"

with open(output, "w", encoding="utf-8") as outfile:
    outfile.write("# สรุปไฟล์ ALCHEMIST 2.00 AbayFX (1)_unlocked.pdf (รวมทุก Part 1-10)\n\n")
    for part in parts:
        if os.path.exists(part):
            with open(part, "r", encoding="utf-8") as infile:
                outfile.write(infile.read())
                outfile.write("\n\n---\n\n")
        else:
            print(f"Missing: {part}")

print("Combine finished.")
