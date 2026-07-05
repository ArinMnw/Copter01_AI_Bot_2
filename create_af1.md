# AF1 — Ambfix Ladder Champion แรก: Inverse S84 RD 4.0-5.0 H17 (Honest Resolution)

วันที่: 2026-07-04
สถานะ: research/backtest-only, ยังไม่ wire เข้า live bot

## Ambfix Ladder คืออะไร

Ladder เส้นใหม่ (แยกจาก S89→S131 convention เดิม) ที่ใช้ **honest intrabar resolution**:

- แท่ง exit ที่แตะทั้ง TP+SL → **M1 replay** ตัดสินตามระดับที่ถูกแตะก่อนจริง
- M1 ไม่ครอบ / M1 ยังกำกวม → **pessimistic ต่อ leg ของเราเสมอ**
  (direct → SL, inverse → raw TP = inverse แพ้)
- ที่เหลือเหมือน framework เดิมทุกประการ: `simulate_equity_substream` $1000/leg,
  windows 90/120/150/180, streak ≤ 3, floors -700/-900/-973.16/-999.91/-1000,
  ชนะ base ต้องทั้ง avg และ min $/day

ที่มา: `create_ambfix_audit.md` พิสูจน์ว่า ladder เดิมอาศัย SL-first artifact
(19.3% ของไม้จบในแท่งกำกวม) — AF ladder หา leg ที่**รอดโดยไม่พึ่งช่องโหว่นั้น**
แบบเดียวกับที่ P13/P16 (ambiguity 0.07%) รอดบน live จริง

## Base

`S88 = S87 + S86RUN_M15_FIBO_RUN_RATR3x0.91` (จาก `s88_s86run_ratr3_daily.csv`)

| Metric | S88 base |
|---|---:|
| Avg $/day | 481.6235 |
| Min $/day | 449.1242 |
| Min PF | 4.06644 |
| Max streak | 3 |
| Worst day | -999.90790 |

⚠️ Caveat ที่บันทึกไว้: base chain (S83→S87) มี inverse legs บน D1/M30
(S88_D1_INV x14.43, S89_D1_INV x10, INV S85SIG_M30 x0.007) ที่ยังไม่ถูก audit
ด้วยวิธีเดียวกัน — เป็นงานตรวจต่อไป

## Search รอบนี้

Ambfix sweep ครั้งแรก: config-28 S84, **ทั้ง direct และ inverse**, 8 RD bands ×
(ทั้งวัน + H0-H23) บน S88 base — ผู้รอดใต้กติกาซื่อสัตย์ (top):

| Mode | Band | Hour | Best w | avg | min |
|---|---|---|---:|---:|---:|
| **inverse** | **4.0-5.0** | **H17** | **172** | **522.79** | **465.13** | ✅ ผู้ชนะ |
| direct | 2.7-3.4 | H12 | 122 | 517.67 | 471.64 | candidate AF2 |
| direct | 5.0-7.0 | H17 | 92 | 512.21 | 473.87 | candidate |
| inverse | 3.4-4.0 | H11 | 280 | 507.42 | 471.66 | candidate |
| direct | 2.7-3.4 | H10 | 96 | 500.50 | 470.44 | candidate |

ข้อสังเกตสำคัญ: **โหมด direct โผล่มาเป็น candidate จำนวนมาก** — กติกาเดิม (SL-first)
เคยกดมันไว้ พอใช้ M1 ตัดสินจริง edge ของมันปรากฏ / ฝั่ง inverse เหลือรอดเฉพาะ
band RD กว้าง (SL ห่าง → แท่งกำกวมน้อย → edge จริงกว่า)

## New Champion

```text
AF1 = S88 + AMBFIX_INV_S84_M15_OLDWICK_FOLLOW_RD4.0_5.0_H17x172.759
```

(leg config เดียวกับ S123 ของ ladder เดิม แต่ตัดสินไม้แบบ honest — น้ำหนักต่างกัน
และคราวนี้ผ่านทั้งที่โดน penalty 235 ไม้ unresolved)

| Metric | AF1 |
|---|---:|
| Avg $/day | 522.9762 |
| Min $/day | 465.2004 |
| Min PF | 4.35870 |
| Max losing-day streak | 3 |
| Worst day | -999.90790 |
| Leg lot max | 0.01 |
| Leg DD | 1.31% |
| Leg skipped by CB | 10 |

Per-window exact from `af1_ambfix_inv_rdmin40_rd50_h17_daily.csv`:

| Window | $/day | PF | Streak | Worst day | Raw trades |
|---:|---:|---:|---:|---:|---:|
| 90 | 523.1894 | 4.90476 | 3 | -999.90232 | 12 |
| 120 | 595.0069 | 5.63671 | 3 | -984.30288 | 16 |
| 150 | 508.5082 | 5.28475 | 3 | -998.76150 | 19 |
| 180 | 465.2004 | 4.35870 | 3 | -999.90790 | 22 |

## Weight Threshold

`af1_ambfix_inv_rdmin40_rd50_h17_probe.csv` (สแกน 0.001-step ใต้ ambfix):

| Weight | Result |
|---:|---|
| 172.759 | highest 0.001-step weight that passes `-999.91` + streak ≤ 3 |
| 172.760 | fails |

## Resolution Stats (config-28 stream 180d)

| | จำนวน |
|---|---:|
| ไม้กำกวมทั้งหมด | 371 |
| M1 ตัดสิน: SL ก่อน | 74 |
| M1 ตัดสิน: TP ก่อน | 62 |
| Unresolved → pessimistic (leg แพ้) | 235 |

## No-Blow Guard

| Floor | Result |
|---|---|
| -700 / -900 / -973.16 | fail (base S88 มีวันชิด -1000 อยู่แล้ว) |
| -999.91 | pass |
| -1000 | pass |

## Look-Ahead Bias Audit

- Detection ใช้ closed bar `j`, fill จาก `j+1`, filter (RD/hour) ใช้ข้อมูล ณ ตอนเข้าไม้
- M1 replay ใช้ตัดสิน**ผลของไม้หลังเข้าแล้วเท่านั้น** (ไม่ได้ใช้เลือกไม้/สร้างสัญญาณ)
  = ไม่มี look-ahead และแม่นกว่ากติกาเดิม
- Pessimistic fallback ทำให้ตัวเลขเป็นขอบล่าง ไม่ใช่ขอบบน
- Research/backtest-only

## Verdict

```text
AF1 = S88 + AMBFIX_INV_S84_M15_OLDWICK_FOLLOW_RD4.0_5.0_H17x172.759
```

ชนะ S88 base ทั้ง avg (481.62 → 522.98) และ min (449.12 → 465.20) ภายใต้กติกาที่
เข้มกว่าเดิม (แท่งกำกวมไม่เข้าข้างเรา + unresolved โดนปรับแพ้) — ไล่ AF2 ต่อ
(direct 2.7-3.4 H12 คือ candidate แรก)
