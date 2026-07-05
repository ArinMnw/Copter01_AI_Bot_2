# Ambiguous-Bar Resolution Audit — Re-run Ladder S89→S130 ด้วย resolution ที่แก้แล้ว

วันที่: 2026-07-04
สถานะ: research/backtest-only — เป็น **diagnostic audit** ไม่เปลี่ยน convention ของ ladder
(พี่สั่ง: แก้ resolution + re-run เป็น audit แล้วไล่ champion ต่อตาม convention เดิม)

## ปัญหาที่ audit

`sim_s84_backtest.py` (และ sim ทุกตัวใน repo) ตัดสินแท่งที่แตะ**ทั้ง TP และ SL ในแท่ง
เดียว** เป็น **SL เสมอ** (SL-first):

- Leg แบบ **direct** (เช่น P13/P16): กติกานี้เป็นผลลบ (conservative) — ปลอดภัย
- Leg แบบ **inverse** (INV_S84 ทั้ง ladder S89→S130): raw SL → inverse ชนะเสมอ =
  **optimistic bias เข้าข้างเราโดยระบบ**

## ขนาดของปัญหา (config 28, M15, 180d)

| Metric | ค่า |
|---|---:|
| ไม้ทั้งหมด | 1,920 |
| จบในแท่งกำกวม (แตะทั้ง TP+SL) | 371 (19.3%) |
| M1 ตัดสินได้: SL แตะก่อนจริง (sim ถูก) | 74 |
| M1 ตัดสินได้: **TP แตะก่อนจริง (sim ผิด — inverse แพ้จริงแต่นับชนะ)** | 62 (~46% ของที่ตัดสินได้) |
| M1 ยังกำกวม / ไม่มีข้อมูล M1 ครอบ | 8 / 227 |

เทียบ **P13/P16** (direct, M5, RR สูง, SL กว้าง): แท่งกำกวมแค่ **12/18,224 = 0.07%**
(leg R S56 = 0/1,281) → backtest ของ P13/P16 ไม่ได้รับผลจาก bias นี้ และเอียงทาง
ประเมินต่ำด้วยซ้ำ — สอดคล้องกับที่ใช้งานจริงบน demo ได้

## Resolution ที่แก้ (ambfix)

1. แท่งกำกวม → **M1 replay** ภายในแท่ง M15 นั้น ตัดสินตามระดับที่ถูกแตะก่อนจริง
2. M1 ไม่ครอบ / M1 เองก็กำกวม → **pessimistic สำหรับ inverse leg**: raw = TP
   (inverse แพ้) — 235/371 ไม้เข้าเกณฑ์นี้
3. ไม้ไม่กำกวม (80.7%) → เหมือนเดิมทุกประการ

## ผล Re-run ทั้ง ladder (bars ชุดเดียวกัน rebuild 2 แบบ)

Rebuild ด้วย resolution เดิมตรงกับ ladder ที่ล็อกไว้ (S130 = 1239.30/1206.53 worst
-999.91 ✓ = validation ว่า rebuild ถูกต้อง) แต่ด้วย ambfix:

| Rung | Convention เดิม avg/min/worst | Ambfix avg/min/worst | Streak (ambfix) |
|---|---|---|---:|
| S88 base | 481.62 / 449.12 / -999.91 | (ไม่ถูกแก้ — leg direct/น้ำหนักจิ๋ว) | 3 |
| S89 | 486.25 / 453.70 / -999.90 | 481.00 / 448.18 / **-1005.53** | 7 |
| S91 | 590.60 / 566.26 / -999.90 | 456.52 / 412.55 / **-1215.67** | 7 |
| S102 | 652.91 / 629.23 / -999.91 | 449.54 / 390.18 / **-1615.65** | 7 |
| S110 | 854.22 / 824.22 / -999.91 | 423.53 / 343.36 / **-2184.48** | 11 |
| S119 | 1022.58 / 1010.04 / -999.91 | 385.79 / 281.24 / **-2699.15** | 9 |
| S124 | 1200.41 / 1150.28 / -999.91 | 465.63 / 353.43 / **-2699.15** | 9 |
| **S130** | **1239.30 / 1206.53 / -999.91** | **429.91 / 321.73 / -3455.18** | 6 |

ครบทุก rung ดูใน `s130_ambfix_ladder_summary.csv`

## ข้อสรุป

1. **กำไรส่วนเกินของ INV_S84 ladder ทั้งหมดเหนือ S88 base คือ artifact ของ resolution**
   — ภายใต้ ambfix ladder ทำได้แย่กว่า S88 base ($429.91 vs $481.62) และหลุด no-blow
   ทุกระดับตั้งแต่ S89 (worst สุดท้าย -$3,455 = พอร์ต $1000 แตก 3.5 เท่า, streak พีค 11)
2. กลไกที่แท้จริง: config target28 ใช้ SL 0.2 ATR + RR 0.9 บน M15 → 1 ใน 5 ไม้จบใน
   แท่งกำกวม → "S84 follow แพ้รวด" ที่เห็นคือผลของกติกา ไม่ใช่พฤติกรรมตลาด →
   inverse จึงไม่มี edge จริง
3. ตัวเลข ambfix เป็นขอบล่าง (pessimistic fallback 235 ไม้ที่ไม่มี M1) ค่าจริงอยู่
   ระหว่างสองเส้น แต่ **น้ำหนักทุกชั้นถูกจูนชิด floor -999.91 พอดี** — แค่ 62 ไม้ที่
   M1 พิสูจน์แล้วว่านับผิดก็เพียงพอให้หลุด floor แล้ว
4. ⚠️ ควร audit ต่อ: base chain S83→S87 มี inverse leg บน D1/M30/M1
   (S88_D1_INV, S89_D1_INV, INV S85SIG_M30) ที่ยังไม่ถูกตรวจแบบเดียวกัน
5. Convention เดิมยังใช้ไล่ champion ต่อได้ในฐานะ **framework benchmark** (เทียบกันเอง
   ภายใต้กติกาเดียวกัน) แต่**ห้ามใช้ตัวเลข $/day เป็นความคาดหวังจริงเด็ดขาด** และ
   **ห้าม wire เข้า live** — ถ้าจะหาของจริง ต้องหา leg ที่รอดใต้ ambfix (แบบ P13/P16)

## Evidence

- `s130_ambfix_ladder_summary.csv` — ทุก rung × 2 variants
- `s130_ambfix_daily.csv` — daily ของ S130 ภายใต้ ambfix
- Script: scratchpad `ambfix_rerun.py` (M1 replay + pessimistic fallback,
  rebuild จาก `s88_s86run_ratr3_daily.csv` + 42 legs ตามน้ำหนักล็อกใน create_s89..s130)
