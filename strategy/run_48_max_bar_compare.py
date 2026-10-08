# -*- coding: utf-8 -*-
"""run_48_max_bar_compare.py
รัน backtest 365 วันของ 48_New_God_S20 สองรอบต่อกลยุทธ์: baseline (ค่ารอ retest เดิม) vs max-bar 7 วัน
ผ่านตัวแปร env ที่ runner แต่ละตัวอ่าน (ค่า default = พฤติกรรมเดิม):
  FILL_WAIT_M5   (group1, 31-53/130-139/300)  default 24 แท่ง M5  -> 7d = 2016
  FILL_WAIT_BARS (group2, 23/25/26/27/29/30)  default 5 แท่ง M30  -> 7d = 336
  FILL_WAIT_DAYS (11 God engine, backtest_s20_unified.py)         -> 7
ผลดิบเก็บใน results JSON (resume ได้), output ดิบของแต่ละรอบเก็บใน raw dir
"""
import json, os, re, subprocess, sys, concurrent.futures as cf

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "_48_max_bar_work")
RAW_DIR = os.path.join(OUT_DIR, "raw")
RES_JSON = os.path.join(OUT_DIR, "results.json")
os.makedirs(RAW_DIR, exist_ok=True)

WAIT7 = {"FILL_WAIT_M5": "2016", "FILL_WAIT_BARS": "336", "FILL_WAIT_DAYS": "7"}
NUM = r"(-?[\d,]+\.?\d*)"


def f(x):
    return float(str(x).replace(",", "").replace("$", "").strip())


def parse_g1(txt, row=None):
    trades = re.search(r"Total Trades Executed:\s*([\d,]+)", txt)
    net = re.search(r"Net Profit[^$\n]*\$\s*" + NUM, txt)
    pf = re.search(r"Profit Factor:\s*([\d\.]+)", txt)
    dd = re.search(r"Max(?:imum)? Drawdown(?: \(\$\))?:\s*\$\s*([\d,\.]+)", txt)
    wins = re.search(r"Wins[^\n]*?:\s*([\d,]+)\s*\(([\d\.]+)%\)", txt)
    loss = re.search(r"(?:Stop Losses Hit|Losses):\s*([\d,]+)", txt)
    if not (trades and net and pf):
        return None
    return {"trades": int(f(trades.group(1))), "wr": float(wins.group(2)) if wins else None,
            "net": f(net.group(1)), "pf": float(pf.group(1)), "dd": f(dd.group(1)) if dd else None,
            "losses": int(f(loss.group(1))) if loss else None}


def parse_31(txt, row=None):
    m = re.search(r"Mode: sweep_only\s*\| TP: 1\.8R \| Trades: (\d+) \| WR: ([\d\.]+)%.*?Loss:\s*(\d+) \| NetPnL: \$\s*" + NUM +
                  r" \| PF: ([\d\.]+) \| MaxDD: \$\s*([\d\.]+)", txt)
    if not m:
        return None
    return {"trades": int(m.group(1)), "wr": float(m.group(2)), "losses": int(m.group(3)),
            "net": f(m.group(4)), "pf": float(m.group(5)), "dd": float(m.group(6))}


def parse_23(txt, row=None):
    t = re.search(r"Total Trades:\s*(\d+)", txt)
    n = re.search(r"Total Net Profit[^$\n]*\$\s*" + NUM, txt)
    p = re.search(r"Profit Factor:\s*([\d\.]+)\s*\|\s*Max Drawdown:\s*\$\s*([\d,\.]+)", txt)
    w = re.search(r"Overall Win Rate:\s*([\d\.]+)%", txt)
    l = re.search(r"Losses:\s*(\d+)", txt)
    if not (t and n and p):
        return None
    return {"trades": int(t.group(1)), "wr": float(w.group(1)) if w else None, "net": f(n.group(1)),
            "pf": float(p.group(1)), "dd": f(p.group(2)), "losses": int(l.group(1)) if l else None}


def parse_25(txt, row=None):
    m = re.search(r"Full Fusion[^\n]*?\s(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+([\d\.]+)\s+" + NUM + r"\s+([\d\.]+)\s+([\d\.]+)\s*\n", txt)
    if not m:
        return None
    return {"trades": int(m.group(1)), "wr": float(m.group(5)), "net": f(m.group(6)),
            "pf": float(m.group(7)), "dd": float(m.group(8)), "losses": int(m.group(3))}


def parse_matrix(label, tf):
    def _p(txt, row=None):
        m = re.search(r"^\s*" + re.escape(label) + r"\s+" + tf + r"\s+(?:[\d\.]+\s+)??(\d+)\s+([\d\.]+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+"
                      + NUM + r"\s+([\d\.]+)\s+([\d\.]+)", txt, re.M)
        if not m:
            return None
        return {"trades": int(m.group(1)), "wr": float(m.group(2)), "losses": int(m.group(6)),
                "net": f(m.group(7)), "pf": float(m.group(8)), "dd": float(m.group(9))}
    return _p



def parse_row(label_re):
    def _p(txt, row=None):
        m = re.search(label_re + r"[^|\n]*\| Trades: (\d+) \| W/BE/L: (\d+)/(\d+)/(\d+) \| WR: ([\d\.]+)%.*?NetPnL: \$\s*" + NUM + r" \| PF:\s*([\d\.]+) \| MaxDD: \$\s*([\d\.]+)", txt)
        if not m:
            return None
        return {"trades": int(m.group(1)), "wr": float(m.group(5)), "losses": int(m.group(4)),
                "net": f(m.group(6)), "pf": float(m.group(7)), "dd": float(m.group(8))}
    return _p

def parse_unified(txt, row=None):
    net = re.search(r"Net Profit:\s*\$\s*" + NUM, txt)
    dd = re.search(r"Max Drawdown:\s*\$\s*([\d,\.]+)", txt)
    tr = re.search(r"Total Trades Executed:\s*([\d,]+)\s*\(W:\s*(\d+)\s*\|\s*L:\s*(\d+)\s*\|\s*BE:\s*(\d+)\)", txt)
    wr = re.search(r"Overall Win Rate:\s*([\d\.]+)%", txt)
    out_dir = re.search(r"Output Directory:\s*(.+)", txt)
    if not (net and tr):
        return None
    pf = None
    if out_dir:
        import glob, csv
        for p in glob.glob(os.path.join(out_dir.group(1).strip(), "*_trades.csv")):
            gp = gl = 0.0
            with open(p, encoding="utf-8") as fh:
                for r in csv.DictReader(fh):
                    v = float(r["P&L"])
                    gp += v if v > 0 else 0
                    gl += -v if v < 0 else 0
            pf = round(gp / gl, 2) if gl > 0 else 999.99
    return {"trades": int(f(tr.group(1))), "wr": float(wr.group(1)) if wr else None, "net": f(net.group(1)),
            "pf": pf, "dd": f(dd.group(1)) if dd else None, "losses": int(tr.group(3))}


JOBS = []
# 11 God ที่ใช้ใน 48_New_God_S20 (8 ตัว) -> engine กลาง backtest_s20_unified.py (โหมดเดียวกับ 11_God_summary: ไม่ใส่ --concurrent)
for s in ("S20_18", "S20_19", "S20_20", "S20_21", "S20_22", "S20_24", "S20_28", "S20_304"):
    JOBS.append({"sid": s.replace("_", "."), "group": "11god", "parse": parse_unified,
                 "cmd": ["backtest_s20_unified.py", "--strategy", s, "--days", "365"], "unified": s})
# กลุ่ม 2
JOBS += [
    {"sid": "S20.23", "group": "g2", "parse": parse_23, "cmd": ["s20.23/backtest_s20_23_runner.py", "--days", "365", "--tf", "M30", "--lot", "0.01"]},
    {"sid": "S20.25", "group": "g2", "parse": parse_25, "cmd": ["s20.25/backtest_s20_25_runner.py", "--days", "365"]},
    {"sid": "S20.26", "group": "g2", "parse": parse_matrix("session_pool", "M30"), "cmd": ["s20.26/backtest_s20_26_runner.py", "--days", "365"]},
    {"sid": "S20.27", "group": "g2", "parse": parse_matrix("nexus_htf", "M30"), "cmd": ["s20.27/backtest_s20_27_runner.py", "--days", "365"]},
    {"sid": "S20.29", "group": "g2", "parse": parse_matrix("mode_stepped_macro", "M30"), "cmd": ["s20.29/backtest_s20_29_runner.py", "--days", "365"]},
    {"sid": "S20.30", "group": "g2", "parse": parse_matrix("combo_baseline_sweep", "M30"), "cmd": ["s20.30/backtest_s20_30_runner.py", "--days", "365", "--tf", "M30"]},
]
# กลุ่ม 1
JOBS.append({"sid": "S20.31", "group": "g1", "parse": parse_31, "cmd": ["s20.31/run_m5_verified.py"]})
for n in list(range(32, 54)) + list(range(130, 140)) + [300]:
    pr = parse_row(r"S20\.32-Champion") if n == 32 else (parse_row(rf"S20\.{n} ") if n in (33, 34, 35, 36) else parse_g1)
    JOBS.append({"sid": f"S20.{n}", "group": "g1", "parse": pr, "cmd": [f"s20.{n}/run_s20_{n}_m5_verified.py"]})


# COMPARE=fill -> เทียบ fill แบบเดิม (เริ่มจากแท่งเปิด, legacy) กับแบบแก้แล้ว (หลังแท่งปิด, fixed) เฉพาะกลุ่ม 1
MODES = ("legacy", "fixed") if os.environ.get("COMPARE") == "fill" else ("base", "wait7d")
if os.environ.get("COMPARE") == "fill":
    JOBS = [j for j in JOBS if j["group"] == "g1"]


def run_one(job, mode):
    key = f"{job['sid']}|{mode}"
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    if mode == "wait7d":
        env.update(WAIT7)
    if mode == "legacy":
        env["LEGACY_FILL_FROM_BAR_OPEN"] = "1"
    cmd = [sys.executable] + job["cmd"]
    if job.get("unified"):
        cmd += ["--out-dir", os.path.join(OUT_DIR, "unified_out", f"{job['unified']}_{mode}")]
    p = subprocess.run(cmd, cwd=ROOT, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=3600)
    txt = p.stdout + "\n" + p.stderr
    with open(os.path.join(RAW_DIR, f"{job['sid']}_{mode}.txt"), "w", encoding="utf-8") as fh:
        fh.write(txt)
    return key, job["parse"](txt)


def worker(job, results):
    out = {}
    for mode in MODES:
        key = f"{job['sid']}|{mode}"
        if results.get(key):
            continue
        try:
            k, r = run_one(job, mode)
        except Exception as e:  # noqa
            k, r = key, None
            print("ERR", key, e, flush=True)
        out[k] = r
        print("done", k, r, flush=True)
    return out


def main():
    results = json.load(open(RES_JSON, encoding="utf-8")) if os.path.exists(RES_JSON) else {}
    workers = int(os.environ.get("WORKERS", "3"))
    with cf.ThreadPoolExecutor(workers) as ex:
        futs = [ex.submit(worker, j, results) for j in JOBS]
        for fu in cf.as_completed(futs):
            results.update(fu.result())
            json.dump(results, open(RES_JSON, "w", encoding="utf-8"), indent=1)
    print("ALL DONE", len(results))


if __name__ == "__main__":
    main()
