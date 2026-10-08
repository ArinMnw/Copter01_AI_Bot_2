# -*- coding: utf-8 -*-
"""ต่อท้าย section สรุปของ 1 group เข้าไปใน tf_optimization_summary.md (ก่อน '## Group ... ยังไม่ได้รัน' placeholder)
ใช้: python scratch_append_group_summary.py <group_id>
"""
import re, sys, os

GROUP_NAMES = {
    13: "Institutional FVG Retest", 14: "GapSweep Momentum Filter", 15: "Macro Fibo Strategy",
    16: "Heavy Volume Scalper", 17: "Low Frequency Precision Engine", 18: "Divergence Momentum Capture",
    19: "Order #34 Dedicated Filter", 20: "GapSweep Reversion Engine", 21: "ATR Volatility Filter",
    22: "GapSweep M15 Dynamic Engine", 23: "S20.1423 Multi-Timeframe System Engine", 24: "FollowDiv Trend Capture",
}
V1_BEST = {
    13: ("H4", "FVG", "+$8,374.25", "18.5%", "529"),
    14: ("H1", "GapSweep", "+$1,157.01", "58.0%", "100"),
    15: ("H12", "Fibo", "+$2,669.37", "25.8%", "558"),
    16: ("M30", "Naiya Doji", "+$10,589.24", "11.9%", "19,350"),
    17: ("M30", "Naiya Doji", "+$10,589.24", "11.9%", "19,350"),
    18: ("M30", "Naiya Doji", "+$10,591.90", "11.9%", "19,349"),
    19: ("-", "-", "รอรัน", "-", "-"),
    20: ("H1", "GapSweep", "+$1,157.01", "58.0%", "100"),
    21: ("H1", "GapSweep", "+$1,157.01", "58.0%", "100"),
    22: ("M15", "GapSweep", "+$2,582.94", "9.2%", "229"),
    23: ("H1", "Naiya", "-$1,919.73", "38.2%", "76"),
    24: ("H4", "FVG", "+$8,374.25", "18.5%", "529"),
}

def fnum(s):
    return float(s.replace(",", ""))

def build_section(g):
    log_path = f"strategy/s20.14.1/backtest-summary/quant-verification-v2/raw_logs/group{g}.log"
    text = open(log_path, encoding="utf-8", errors="replace").read()
    rows = []
    for m in re.finditer(r"^Saved: (.+?) set \(Trades: ([\d,]+) \| W: ([\d,]+) \| L: ([\d,]+) \| BE: \d+ \| WR: ([\d.]+)% \| P&L: (-?[\d,.]+)\)$", text, re.M):
        pat, trades, w, l, wr, pnl = m.groups()
        rows.append((pat, int(trades.replace(",", "")), int(w.replace(",", "")), wr, fnum(pnl)))
    rows.sort(key=lambda r: -r[4])
    total_m = re.search(r"^Saved: trades\.csv \(Total Trades: ([\d,]+) \| W: ([\d,]+) \| L: ([\d,]+) \| BE: \d+ \| WR: ([\d.]+)% \| P&L: (-?[\d,.]+)\)$", text, re.M)
    if not total_m:
        return None, None
    tot_trades, tot_w, tot_l, tot_wr, tot_pnl = total_m.groups()

    pos = [r for r in rows if r[4] > 0]
    neg = [r for r in rows if r[4] <= 0]

    v1tf, v1pat, v1pnl, v1wr, v1n = V1_BEST[g]
    if pos:
        bestpat, bestn, bestw, bestwr, bestpnl = pos[0]
        best_pattern_name, best_tf = bestpat.rsplit("_", 1)
    else:
        best_pattern_name, best_tf, bestn, bestwr, bestpnl = "-", "-", 0, "0.0", 0.0

    sec = []
    sec.append(f"## 📌 Group {g}: {GROUP_NAMES[g]} — ผลหลังแก้บั๊ก\n")
    sec.append("### สรุประดับพอร์ต (ทุก pattern/TF รวมกัน)\n")
    sec.append("| | v1 (มีบั๊ก) | v2 (แก้แล้ว) |")
    sec.append("|---|---|---|")
    sec.append(f"| Total Trades | *(ไม่ได้รายงานรวมในเอกสารเดิม)* | **{tot_trades}** |")
    sec.append(f"| Win Rate | *(-)* | **{tot_wr}%** |")
    tp = fnum(tot_pnl)
    sec.append(f"| Net P&L | *(-)* | **{'-' if tp < 0 else '+'}${abs(tp):,.2f}** |")
    sec.append("")
    sec.append("### Timeframe แนะนำที่ดีที่สุด\n")
    sec.append(f"- **v1 (มีบั๊ก):** `{v1tf}` ใน Pattern `{v1pat}` — กำไรสุทธิ {v1pnl} | Win Rate {v1wr} | {v1n} ไม้")
    if pos:
        sign = "+" if bestpnl >= 0 else "-"
        sec.append(f"- **v2 (แก้แล้ว):** `{best_tf}` ใน Pattern `{best_pattern_name}` — กำไรสุทธิ **{sign}${abs(bestpnl):,.2f}** | Win Rate {bestwr}% | {bestn:,} ไม้")
    else:
        sec.append(f"- **v2 (แก้แล้ว):** ไม่มีคู่ผสมไหนกำไรบวกเลย")
    sec.append("")
    sec.append("### ตารางคู่ผสมที่ทำกำไรบวก (v2)\n")
    if pos:
        sec.append("| Pattern | Timeframe (TF) | จำนวนไม้ (Trades) | ชนะ (Wins) | Win Rate (%) | Net PnL ($) |")
        sec.append("|---|:---:|---|---|:---:|---|")
        for pat, n, w, wr, pnl in pos:
            pname, tf = pat.rsplit("_", 1)
            sec.append(f"| {pname} | `{tf}` | {n:,} | {w:,} | {wr}% | +${pnl:,.2f} |")
    else:
        sec.append("*(ไม่มีคู่ผสมไหนกำไรบวกเลยในกลุ่มนี้)*")
    sec.append("")
    sec.append("### ตารางคู่ผสมที่ขาดทุน (v2)\n")
    sec.append("| Pattern | Timeframe (TF) | จำนวนไม้ (Trades) | ชนะ (Wins) | Win Rate (%) | Net PnL ($) |")
    sec.append("|---|:---:|---|---|:---:|---|")
    for pat, n, w, wr, pnl in neg:
        pname, tf = pat.rsplit("_", 1)
        sec.append(f"| {pname} | `{tf}` | {n:,} | {w:,} | {wr}% | -${abs(pnl):,.2f} |")
    sec.append("")
    sec.append("---\n")
    return "\n".join(sec), (tot_trades, tot_wr, tp, best_pattern_name, best_tf, bestpnl, bestwr)

def main():
    g = int(sys.argv[1])
    section, stats = build_section(g)
    if section is None:
        print(f"group{g}: log not ready / no total line found")
        sys.exit(1)

    doc_path = "strategy/s20.14.1/backtest-summary/quant-verification-v2/tf_optimization_summary.md"
    doc = open(doc_path, encoding="utf-8").read()

    marker = None
    for cand in ("## Group 15-24", "## Group 16-24", "## Group 17-24", "## Group 18-24",
                 "## Group 19-24", "## Group 20-24", "## Group 21-24", "## Group 22-24",
                 "## Group 23-24", "## Group 24", "## Group 13-24", "## Group 14-24"):
        if cand in doc:
            marker = cand
            break
    idx = doc.find(marker) if marker else -1
    if idx == -1:
        print("no placeholder marker found, appending at end")
        doc = doc.rstrip("\n") + "\n\n" + section + "\n"
    else:
        doc = doc[:idx] + section + "\n" + doc[idx:]
        if g < 24:
            new_marker = f"## Group {g + 1}-24"
            doc = doc.replace(marker, new_marker, 1)
        else:
            # กลุ่มสุดท้าย: ลบ placeholder ทิ้ง (บรรทัดหัวข้อ + ข้อความใต้หัวข้อ 1 บรรทัด)
            doc = re.sub(re.escape(marker) + r"\n\n[^\n]*\n\n", "", doc, count=1)
    open(doc_path, "w", encoding="utf-8", newline="\n").write(doc)
    tot_trades, tot_wr, tp, bp, btf, bpnl, bwr = stats
    print(f"group{g} appended: trades={tot_trades} wr={tot_wr}% pnl={tp:,.2f} best={bp}/{btf} {bpnl:,.2f}({bwr}%)")

if __name__ == "__main__":
    main()
