# usage: python log_row.py N A B METHOD "result"
import sys, datetime, subprocess
N, A, B, M, R = sys.argv[1:6]
d = datetime.date.today().isoformat()
p = "strategy/s20_gen/mix_log.md"
s = open(p, encoding="utf-8").read()
if not s.endswith("\n"):
    s += "\n"
s += f"| {N} | 20.{A} | 20.{B} | {M} | {d} | {R} |\n"
open(p, "w", encoding="utf-8", newline="\n").write(s)
out = subprocess.run([sys.executable, "-X", "utf8", "strategy/s20_gen/progress_repair.py", "--check"],
                     capture_output=True, encoding="utf-8").stdout
print(out)
