"""
Export AF ladder composition reports.

This reconstructs each AF portfolio from the stored daily CSV ladder:
- S88 base daily P/L
- AF1..AFN overlay contribution = AFn daily total - previous base daily total

Outputs:
- af_ladder_leg_window_summary.csv
- af_ladder_leg_daily.csv
- af_ladder_leg_monthly.csv
- af_ladder_components.csv
"""

import argparse
import csv
import re
from datetime import datetime, timedelta
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / "strategy" / "af" / "excel"
DEFAULT_WINDOWS = [30, 60, 90, 120, 150, 180]


def _read_csv(path):
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _write_csv(path, rows, fields):
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def _formula_from_doc(n):
    text = (ROOT / f"create_af{n}.md").read_text(encoding="utf-8")
    matches = re.findall(rf"AF{n}\s*=\s*([^\n`]+)", text)
    if not matches:
        raise ValueError(f"Cannot find AF{n} formula")
    formula = matches[-1].strip()
    if "+" in formula:
        leg = formula.split("+", 1)[1].strip()
    else:
        leg = formula.strip()
    weight = None
    m = re.search(r"x([0-9]+(?:\.[0-9]+)?)$", leg)
    if m:
        weight = float(m.group(1))
        leg_name = leg[:m.start()].rstrip()
    else:
        leg_name = leg
    return formula, leg_name, weight, text


def _raw_trades_by_window(doc_text):
    out = {}
    for line in doc_text.splitlines():
        m = re.match(r"\|\s*(90|120|150|180)\s*\|.*\|\s*([0-9]+)\s*\|", line.strip())
        if m:
            out[int(m.group(1))] = int(m.group(2))
    if out:
        return out
    m = re.search(r"Raw trades:\s*([0-9]+)\s*/\s*([0-9]+)\s*/\s*([0-9]+)\s*/\s*([0-9]+)", doc_text)
    if m:
        return {90: int(m.group(1)), 120: int(m.group(2)), 150: int(m.group(3)), 180: int(m.group(4))}
    return {}


def _daily_file_for_af(n, leg_name):
    candidates = sorted(ROOT.glob(f"af{n}_*_daily.csv"))
    if not candidates:
        raise FileNotFoundError(f"No daily CSV for AF{n}")
    if len(candidates) == 1:
        return candidates[0]
    lower = leg_name.lower()
    hour = re.search(r"_h([0-9]+)", lower)
    cfg = re.search(r"c([0-9]+)", lower)
    scored = []
    for path in candidates:
        name = path.name.lower()
        score = 0
        if hour and f"_h{hour.group(1)}_" in name:
            score += 5
        if cfg and f"c{cfg.group(1)}" in name:
            score += 3
        if "_inv_" in name and "_inv_" in lower:
            score += 1
        if "_dir_" in name and "_dir_" in lower:
            score += 1
        scored.append((score, path))
    scored.sort(key=lambda x: (-x[0], x[1].name))
    return scored[0][1]


def _rows_by_key(rows):
    return {(int(r["days"]), r["date"]): float(r["total"]) for r in rows}


def _leg_definitions(max_af):
    defs = []
    for n in range(1, max_af + 1):
        formula, leg_name, weight, doc_text = _formula_from_doc(n)
        daily_file = _daily_file_for_af(n, leg_name)
        defs.append({
            "leg_no": n,
            "formula": formula,
            "leg_name": leg_name,
            "weight": weight,
            "raw_trades": _raw_trades_by_window(doc_text),
            "daily_file": daily_file,
            "daily": _rows_by_key(_read_csv(daily_file)),
        })
    return defs


def _month(date_text):
    return date_text[:7]


def _items_for_window(data, window):
    direct = [(date, value, False) for (days, date), value in data.items() if days == window]
    if direct:
        return sorted(direct)

    larger = sorted({days for days, _ in data if days > window})
    if not larger:
        return []
    source_days = larger[0]
    source = [(date, value) for (days, date), value in data.items() if days == source_days]
    if not source:
        return []
    max_date = max(datetime.strptime(date, "%Y-%m-%d").date() for date, _ in source)
    cutoff = max_date - timedelta(days=window - 1)
    out = []
    for date, value in source:
        d = datetime.strptime(date, "%Y-%m-%d").date()
        if d >= cutoff:
            out.append((date, value, True))
    return sorted(out)


def export(targets, windows):
    max_af = max(targets)
    leg_defs = _leg_definitions(max_af)
    base_file = ROOT / "s88_s86run_ratr3_daily.csv"
    base_daily = _rows_by_key(_read_csv(base_file))

    components = [{
        "component_no": 0,
        "component_type": "base",
        "component_name": "S88",
        "weight": "",
        "daily_file": base_file.name,
    }]
    for leg in leg_defs:
        components.append({
            "component_no": leg["leg_no"],
            "component_type": "overlay",
            "component_name": leg["leg_name"],
            "weight": leg["weight"],
            "daily_file": leg["daily_file"].name,
        })

    daily_rows = []
    summary_rows = []
    prev_daily = base_daily

    # Base contribution for every requested target.
    for target in targets:
        for days in windows:
            for date, value, derived in _items_for_window(base_daily, days):
                daily_rows.append({
                    "target_af": f"AF{target}",
                    "window_days": days,
                    "date": date,
                    "month": _month(date),
                    "component_no": 0,
                    "component_type": "base",
                    "component_name": "S88",
                    "weight": "",
                    "raw_trades": "",
                    "pnl": round(value, 6),
                    "derived_window": "yes" if derived else "no",
                })

    for leg in leg_defs:
        cur_daily = leg["daily"]
        prev_daily_for_diff = prev_daily
        contribution_maps = {}
        source_days = sorted({days for days, _ in set(cur_daily) | set(prev_daily_for_diff)})
        for source_day in source_days:
            keys = sorted({key for key in cur_daily if key[0] == source_day} | {key for key in prev_daily_for_diff if key[0] == source_day})
            for key in keys:
                contribution_maps[key] = cur_daily.get(key, 0.0) - prev_daily_for_diff.get(key, 0.0)
        for target in targets:
            if leg["leg_no"] > target:
                continue
            for days in windows:
                for date, pnl, derived in _items_for_window(contribution_maps, days):
                    daily_rows.append({
                        "target_af": f"AF{target}",
                        "window_days": days,
                        "date": date,
                        "month": _month(date),
                        "component_no": leg["leg_no"],
                        "component_type": "overlay",
                        "component_name": leg["leg_name"],
                        "weight": leg["weight"],
                        "raw_trades": "" if derived else leg["raw_trades"].get(days, ""),
                        "pnl": round(pnl, 6),
                        "derived_window": "yes" if derived else "no",
                    })
        prev_daily = cur_daily

    # Window summary from daily rows.
    grouped = {}
    for row in daily_rows:
        key = (
            row["target_af"], row["window_days"], row["component_no"], row["component_type"],
            row["component_name"], row["weight"], row["raw_trades"], row["derived_window"],
        )
        item = grouped.setdefault(key, {
            "target_af": row["target_af"],
            "window_days": row["window_days"],
            "component_no": row["component_no"],
            "component_type": row["component_type"],
            "component_name": row["component_name"],
            "weight": row["weight"],
            "raw_trades": row["raw_trades"],
            "derived_window": row["derived_window"],
            "pnl": 0.0,
        })
        item["pnl"] += float(row["pnl"])
    for item in grouped.values():
        days = int(item["window_days"])
        item["pnl"] = round(item["pnl"], 6)
        item["pnl_per_day"] = round(item["pnl"] / days, 6) if days else 0.0
        summary_rows.append(item)
    summary_rows.sort(key=lambda r: (int(r["target_af"][2:]), int(r["window_days"]), int(r["component_no"])))

    monthly_grouped = {}
    for row in daily_rows:
        key = (
            row["target_af"], row["window_days"], row["month"], row["component_no"],
            row["component_type"], row["component_name"], row["weight"], row["raw_trades"], row["derived_window"],
        )
        item = monthly_grouped.setdefault(key, {
            "target_af": row["target_af"],
            "window_days": row["window_days"],
            "month": row["month"],
            "component_no": row["component_no"],
            "component_type": row["component_type"],
            "component_name": row["component_name"],
            "weight": row["weight"],
            "raw_trades": row["raw_trades"],
            "derived_window": row["derived_window"],
            "pnl": 0.0,
        })
        item["pnl"] += float(row["pnl"])
    monthly_rows = []
    for item in monthly_grouped.values():
        item["pnl"] = round(item["pnl"], 6)
        monthly_rows.append(item)
    monthly_rows.sort(key=lambda r: (int(r["target_af"][2:]), int(r["window_days"]), r["month"], int(r["component_no"])))

    component_fields = ["component_no", "component_type", "component_name", "weight", "daily_file"]
    summary_fields = [
        "target_af", "window_days", "component_no", "component_type", "component_name",
        "weight", "raw_trades", "derived_window", "pnl", "pnl_per_day",
    ]
    daily_fields = [
        "target_af", "window_days", "date", "month", "component_no", "component_type",
        "component_name", "weight", "raw_trades", "derived_window", "pnl",
    ]
    monthly_fields = [
        "target_af", "window_days", "month", "component_no", "component_type",
        "component_name", "weight", "raw_trades", "derived_window", "pnl",
    ]
    _write_csv(OUT_DIR / "af_ladder_components.csv", components, component_fields)
    _write_csv(OUT_DIR / "af_ladder_leg_window_summary.csv", summary_rows, summary_fields)
    _write_csv(OUT_DIR / "af_ladder_leg_daily.csv", daily_rows, daily_fields)
    _write_csv(OUT_DIR / "af_ladder_leg_monthly.csv", monthly_rows, monthly_fields)
    for target in targets:
        tag = f"af{target}"
        _write_csv(
            OUT_DIR / f"af_ladder_leg_window_summary_{tag}.csv",
            [r for r in summary_rows if r["target_af"] == f"AF{target}"],
            summary_fields,
        )
        _write_csv(
            OUT_DIR / f"af_ladder_leg_monthly_{tag}.csv",
            [r for r in monthly_rows if r["target_af"] == f"AF{target}"],
            monthly_fields,
        )
    return len(components), len(summary_rows), len(daily_rows), len(monthly_rows)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--targets", nargs="+", type=int, default=[22, 34, 47])
    ap.add_argument("--days", nargs="+", type=int, default=DEFAULT_WINDOWS)
    args = ap.parse_args()
    counts = export(args.targets, args.days)
    print(f"components={counts[0]} window_rows={counts[1]} daily_rows={counts[2]} monthly_rows={counts[3]}")
    print(f"-> {OUT_DIR / 'af_ladder_components.csv'}")
    print(f"-> {OUT_DIR / 'af_ladder_leg_window_summary.csv'}")
    print(f"-> {OUT_DIR / 'af_ladder_leg_daily.csv'}")
    print(f"-> {OUT_DIR / 'af_ladder_leg_monthly.csv'}")
    for target in args.targets:
        print(f"-> {OUT_DIR / f'af_ladder_leg_window_summary_af{target}.csv'}")
        print(f"-> {OUT_DIR / f'af_ladder_leg_monthly_af{target}.csv'}")


if __name__ == "__main__":
    main()
