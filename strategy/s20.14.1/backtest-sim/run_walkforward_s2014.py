# -*- coding: utf-8 -*-
"""Walk-forward validation ของ 23 กลุ่ม S20.14 (ยกเว้น Group 23 ตามคำสั่ง)
เช็คว่าคู่ (Pattern, TF) ที่เป็นแชมป์ top-1 (จาก s20_14_live_top10_mapping.json) ยังทำกำไรบวก
ในทั้ง 2 หน้าต่างเวลาแยกกันไหม (dual-window) ไม่ใช่แค่ภาพรวม 365 วันเดียว
ใช้ TPSL_EXP_MODE/TARGET ของ round ที่เป็นแชมป์จริงของแต่ละกลุ่ม (ตรงกับที่มาของตัวเลข top-1)
"""
import os, re, json, subprocess, sys, io

SIM_DIR = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(SIM_DIR, "..", "backtest-summary", "walkforward-2026-09-23")
RAW_DIR = os.path.join(OUT_DIR, "raw_logs")
os.makedirs(RAW_DIR, exist_ok=True)

MAPPING_PATH = os.path.join(SIM_DIR, "..", "..", "s20.14", "s20_14_live_top10_mapping.json")

ROUND_ENV = {
    "R1": ("S20.14.23", "SL_ONLY"),
    "R2": ("S20.13.23", "SL_ONLY"),
    "R3": ("S20.14.23", "BOTH"),
    "R4": ("S20.13.23", "BOTH"),
}

WINDOWS = [
    ("A", "2025-09-23", "2026-03-23"),
    ("B", "2026-03-23", "2026-09-23"),
]

GROUPS = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 24]  # ไม่รวม 23

SAVE_RE = re.compile(
    r"^Saved: (.+?)_(M1|M5|M15|M30|H1|H4|H12|D1) set \(Trades: ([\d,]+) \| W: ([\d,]+) \| L: [\d,]+ \| BE: \d+ \| WR: ([\d.]+)% \| P&L: (-?[\d,.]+)\)$",
    re.M,
)


def load_mapping():
    return json.load(io.open(MAPPING_PATH, encoding="utf-8"))


def run_one(group, win_label, start, end, mode, target):
    log_path = os.path.join(RAW_DIR, f"group{group}_{win_label}.log")
    script = os.path.join(SIM_DIR, f"v38_standalone_group{group}.py")
    env = os.environ.copy()
    env["TPSL_EXP_MODE"] = mode
    env["TPSL_EXP_TARGET"] = target
    env["PYTHONIOENCODING"] = "utf-8"
    cmd = [sys.executable, "-u", script, "--start", start, "--end", end]
    print(f"=== group{group} window{win_label} ({start}..{end}) mode={mode} target={target} ===", flush=True)
    with open(log_path, "w", encoding="utf-8") as f:
        p = subprocess.run(cmd, cwd=SIM_DIR, env=env, stdout=f, stderr=subprocess.STDOUT, text=True)
    print(f"  exit={p.returncode}", flush=True)
    return log_path, p.returncode


def parse_champion_pnl(log_path, champ_pattern, champ_tf):
    text = io.open(log_path, encoding="utf-8", errors="replace").read()
    rows = {}
    for m in SAVE_RE.finditer(text):
        pat, tf, trades, w, wr, pnl = m.groups()
        rows[(pat, tf)] = dict(trades=int(trades.replace(",", "")), wins=int(w.replace(",", "")), wr=wr, pnl=float(pnl.replace(",", "")))
    key = (champ_pattern.split("/")[0], champ_tf)  # เผื่อ pattern รวม เช่น FVG/Fibo เอาตัวแรกก่อน
    if key in rows:
        return rows[key]
    # ลองหาแบบ pattern เต็มตรงเป๊ะก่อน (เผื่อ key ไม่ตรง)
    for (pat, tf), v in rows.items():
        if tf == champ_tf and pat == champ_pattern:
            return v
    return None


def main():
    mapping = load_mapping()
    results = {}
    for g in GROUPS:
        entry = mapping.get(str(g))
        if not entry:
            print(f"group {g}: no mapping, skip")
            continue
        champ = entry["top10"][0]
        rnd = champ["round"]
        mode, target = ROUND_ENV[rnd]
        pattern, tf = champ["pattern"], champ["tf"]
        win_pnls = {}
        for label, start, end in WINDOWS:
            log_path, rc = run_one(g, label, start, end, mode, target)
            if rc != 0:
                win_pnls[label] = {"error": f"exit={rc}"}
                continue
            r = parse_champion_pnl(log_path, pattern, tf)
            win_pnls[label] = r if r else {"note": "champion pattern/tf ไม่มีไม้เลยในหน้าต่างนี้"}
        results[g] = dict(name=entry["name"], round=rnd, pattern=pattern, tf=tf,
                           full_365d_pnl=champ["pnl"], windows=win_pnls)
        # เซฟผลสะสมทุกครั้งกันสคริปต์ตายกลางทาง
        io.open(os.path.join(OUT_DIR, "walkforward_results.json"), "w", encoding="utf-8").write(
            json.dumps(results, ensure_ascii=False, indent=2)
        )
    print("ALL DONE")


if __name__ == "__main__":
    main()
