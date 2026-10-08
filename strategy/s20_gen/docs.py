# -*- coding: utf-8 -*-
"""docs.py — อัปเดต strategy/strategy.md และ strategy/strategy_evolution.md สำหรับ S20.140–S20.299

idempotent: แถวใน strategy.md อยู่ในบล็อก marker <!-- S20GEN:BEGIN/END -->, section ใน evolution อยู่ใน
<!-- S20GEN:S20.<N>:BEGIN/END --> รันซ้ำจะเขียนทับของเดิม ไม่ซ้อน. รักษา line ending เดิมของไฟล์ (CRLF)
"""
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
MD = os.path.join(ROOT, "strategy", "strategy.md")
EVO = os.path.join(ROOT, "strategy", "strategy_evolution.md")
OLD_NOTICE = re.compile(r"^> ⚠️ \*\*S20\.140–S20\.299 ถูกลบออกจากเอกสารนี้แล้ว\*\*.*$", re.M)
BEGIN, END = "<!-- S20GEN:BEGIN -->", "<!-- S20GEN:END -->"
HEADER = [
    BEGIN,
    "### S20.140–S20.299 — แคมเปญ Checklist-Verified (เริ่ม 2026-09-29)",
    "",
    "> สร้างใหม่ทั้งหมด (โฟลเดอร์เดิมถูกลบไปแล้ว) ทุกตัวเป็น concept ที่ไม่ซ้ำกับ strategy อื่นในเอกสารนี้ + เช็คความซ้ำของสัญญาณอัตโนมัติ (Jaccard ≤ 0.5)",
    "> backtest ด้วย `strategy/s20_gen/engine.py` (next-bar-open market entry, SL-first, spread/swap/slippage จริง, IS70/OOS30, Monte-Carlo drop 15%, lookahead truncation audit)",
    "> ตัวเลขเป็น XAUUSD lot 0.01 ช่วง 365 วัน (M1 มีข้อมูลได้แค่ ~100 วันเพราะ terminal maxbars=100000) — **PASS** = n≥30, PF≥1.15, OOS บวก, MC p5>0 และชนะ null test (สุ่มจุดเข้า 200 ชุด p<0.05); ยังไม่ wire เข้า live",
    "",
    "| รหัส | ชื่อ/Concept | ท่าเทรด + ผล 365 วัน |",
    "|---|---|---|",
]


def _read(p):
    with open(p, "rb") as f:
        raw = f.read().decode("utf-8")
    nl = "\r\n" if "\r\n" in raw else "\n"
    return raw.replace("\r\n", "\n"), nl


def _write(p, text, nl):
    with open(p, "wb") as f:
        f.write(text.replace("\n", nl).encode("utf-8"))


def _fmt_tf(res):
    parts = []
    for tf, v in res["tf"].items():
        if v["n"] == 0:
            continue
        mark = "✅" if v["verdict"] == "PASS" else ""
        parts.append(f"{tf} {v['net']:+.0f}/PF{v['pf']}{mark}")
    return ", ".join(parts)


def md_row(n, res):
    p = res["pass_tfs"]
    status = f"✅ PASS: {', '.join(p)}" if p else "❌ ไม่มี TF ผ่านเกณฑ์ (research only)"
    return (f"| S20.{n} | {res['name']} | {res['concept']} — 365d: {_fmt_tf(res)} — "
            f"รวม {res['total']['net']:+.2f}$ PF{res['total']['pf']} — {status} |")


def update_md(n, res):
    text, nl = _read(MD)
    if BEGIN not in text:
        m = OLD_NOTICE.search(text)
        block = "\n".join(HEADER + [END])
        if m:
            text = text[:m.start()] + block + text[m.end():]
        else:
            anchor = text.find("| S20.300 |")
            text = text[:anchor] + block + "\n\n" + text[anchor:]
    b, e = text.index(BEGIN), text.index(END)
    body = text[b:e].split("\n")
    rows = {}
    head = []
    for line in body:
        m = re.match(r"^\| S20\.(\d+) \|", line)
        if m:
            rows[int(m.group(1))] = line
        elif not rows:
            head.append(line)
    rows[n] = md_row(n, res)
    while head and head[-1] == "":
        head.pop()
    new = "\n".join(head + [rows[k] for k in sorted(rows)]) + "\n"
    text = text[:b] + new + text[e:]
    text = re.sub(r"^# รายชื่อ Strategy ทั้งหมด \(.*\)$", "# รายชื่อ Strategy ทั้งหมด (S1–S434, S20.5–S20.305)", text, count=1, flags=re.M)
    _write(MD, text, nl)


def evo_section(n, res):
    L = [f"<!-- S20GEN:S20.{n}:BEGIN -->", f"## S20.{n} — {res['name']}", "",
         f"ไฟล์: `strategy/s20.{n}/strategy20_{n}.py` | backtest: `python strategy/s20.{n}/backtest_s20_{n}.py --days 365` "
         f"(รองรับ `--start` `--end` `--compare`)", "",
         f"แนวคิด: {res['concept']}", "",
         f"พารามิเตอร์ (fixed, ไม่ auto-tune): SL {res['params']['sl_atr']}×ATR, TP {res['params']['rr']}R, "
         f"ถือสูงสุด {res['params']['max_hold']} แท่ง, BE {res['params']['be_r']}R | spread≥{res['spread_floor']} | "
         f"ช่วง BKK {res['period_bkk'][0]} → {res['period_bkk'][1]}", "",
         "| TF | วัน | Trades | WR% | Net $ | PF | MaxDD $ | IS net | OOS net | OOS PF | MC p5 | null p | ผล |",
         "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|"]
    for tf, v in res["tf"].items():
        npv = (v.get("null") or {}).get("p", "-")
        L.append(f"| {tf} | {v['days']:.0f} | {v['n']} | {v['wr']} | {v['net']:+.2f} | {v['pf']} | {v['dd']:.2f} | "
                 f"{v['is']['net']:+.2f} | {v['oos']['net']:+.2f} | {v['oos']['pf']} | {v['mc']['p5']:+.2f} | {npv} | {v['verdict']} |")
    t = res["total"]
    L.append(f"| **รวม** | | {t['n']} | {t['wr']} | {t['net']:+.2f} | {t['pf']} | {t['dd']:.2f} | | | | | | |")
    u = res.get("uniqueness", {})
    oc = {}
    for v in res["tf"].values():
        for k, c in v.get("outcomes", {}).items():
            oc[k] = oc.get(k, 0) + c
    gap = min([v.get("worst_weekend_gap_r", 0.0) for v in res["tf"].values()] + [0.0])
    L += ["", "Checklist: #1/#3 lookahead truncation audit "
          f"{'ผ่าน' if res.get('lookahead_ok') else 'ไม่ผ่าน/ไม่ได้รัน'} · #2 เข้าที่ open แท่งถัดไปหลังปิด · #4 SL-first · #5 fill ที่ open ของแท่ง path "
          "· #6 market (#7/#10/#13 N/A) · #8 spread+swap · #9 SL slip 0.10 + gap fill · "
          f"#11 outcome {oc} · #12 MC drop15% (ดู MC p5) · #14 fixed params + null test สุ่มจุดเข้า 200 ชุด (p<0.05) ·#15 IS70/OOS30 · "
          f"#16 N/A (XAUUSD เดียว) · #17 M1–H1 ปิดก่อน weekend, H4/D1 worst gap {gap}R · #18 N/A (ยังไม่ live) · #19 `--compare`",
          f"ความซ้ำ: max Jaccard {u.get('max_jaccard')} กับ {u.get('with')} → {'ไม่ซ้ำ' if u.get('unique', True) else 'ซ้ำ'}",
          "",
          f"สถานะ: {'✅ ผ่านเกณฑ์ที่ ' + ', '.join(res['pass_tfs']) + ' (ต้อง forward demo ก่อน live)' if res['pass_tfs'] else '❌ ไม่มี TF ผ่านเกณฑ์ — เก็บเป็นผลลบ ไม่ใช้ live'}",
          f"<!-- S20GEN:S20.{n}:END -->"]
    return "\n".join(L)


def update_evo(n, res):
    text, nl = _read(EVO)
    sec = evo_section(n, res)
    b, e = f"<!-- S20GEN:S20.{n}:BEGIN -->", f"<!-- S20GEN:S20.{n}:END -->"
    if b in text:
        i, j = text.index(b), text.index(e) + len(e)
        text = text[:i] + sec + text[j:]
    else:
        text = text.rstrip("\n") + "\n\n" + sec + "\n"
    _write(EVO, text, nl)


def update(n, res):
    update_md(n, res)
    update_evo(n, res)
