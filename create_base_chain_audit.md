# Base Chain Audit (S82→S88) — ตรวจ intrabar both-touch bias ใน legs ของ base

วันที่: 2026-07-04
สถานะ: research/backtest-only — audit ต่อเนื่องจาก `create_ambfix_audit.md`
คำถาม: base ของ ambfix ladder (`s88_s86run_ratr3_daily.csv`) มี optimistic intrabar
bias แบบเดียวกับ INV_S84 ladder หรือไม่?

## ผลตรวจรายเลก

| Leg ใน base chain | Weight | เทรดยังไงจริง | ผลของกติกา SL-first |
|---|---:|---|---|
| P16 (16 legs S31-S56) | 1.0 | direct, M5, RR สูง | conservative ✅ (ambiguity 0.07% — วัดแล้วใน audit ก่อน) |
| S63 / S69 / S64 | 12.8 / 22.1925 / 13.875 | direct (All-in-4S) | conservative ✅ |
| S87_MAIN (D1_H12_TURN follow) | 33.55 | direct — S86 M15 trades คัดตามทิศ D1/H12 | conservative ✅ |
| **S88_D1_INV_NO17** | **14.43** | **direct!** — `filter_trades(relation="inverse")` แค่**คัดเลือก**ไม้ S86 M15 ที่สวนทาง D1 bias แล้วเทรดตามทิศไม้เดิม **ไม่ได้กลับ TP/SL/PnL** (ดู `strategy87.py:103-122`) | conservative ✅ |
| **S89_D1_INV_NO17_RISK20** | **10.0** | **direct!** — เหมือนบน + filter rd≤20 | conservative ✅ |
| S208_M1 | 39.33 | direct (S20.8 M1) | conservative ✅ |
| S2010_M30_FSP | 11.73 | direct (S20.10 M30) | conservative ✅ |
| INV(S85SIG_M30) | **0.007** | **inverse จริง** (`_invert_raw`) | ⚠️ optimistic แต่**ไม่มีนัยสำคัญ** — วัดจริง: ambiguity 5/165 ไม้ = 3.0% (M30 SL 0.25ATR RR1.0), leg daily อยู่ช่วง [-74.74, +46.23] → ที่ x0.007 ผลกระทบ ≤ **$0.52/วัน** |
| S86RUN_M15_RATR3 (ของ S88) | 0.91 | direct (follow) | conservative ✅ |

หลักฐานสำคัญ: `strategy87.filter_trades` relation="inverse" คืน trade dict เดิมทุก field
(ไม่ swap tp/sl, ไม่ negate diff) — ชื่อ "INV" ใน leg หมายถึง *counter-trend selection*
ไม่ใช่ *trade inversion* ต่างจาก `_invert_raw` ที่ INV_S84 ladder ใช้

## ข้อสรุป

1. **S88 base สะอาดจาก optimistic intrabar bias** — ทุก leg ที่มีนัยสำคัญเทรด direct
   ซึ่งกติกา SL-first กดตัวเลขให้ต่ำกว่าจริง (conservative) มีเพียง INV S85SIG_M30
   x0.007 ที่ optimistic แต่ผลกระทบถูกจำกัดด้วยน้ำหนักไว้ที่ ~$0.5/วัน
2. **Ambfix ladder (AF1→AF15) ยืนบนพื้นที่เชื่อถือได้** ไม่ต้อง rebase
3. ตัวเลข base จริงอาจ*ดีกว่า*ที่รายงานเล็กน้อยด้วยซ้ำ (direct legs โดน SL-first กดอยู่)

## Evidence

- `strategy87.py` filter_trades (no inversion of trade dict)
- `sim_s86_backtest.py` / `sim_s31_backtest.py` — SL-first resolution (conservative
  ต่อ direct)
- `sim_s87_filter_s86.py` S86_M15_STRICT (SL 0.20 ATR, RR 1.5)
- การวัด INV S85SIG_M30: 165 ไม้ @180d, ambiguity 5 (3.0%), daily range [-74.74,
  +46.23], impact ที่ x0.007 = [-0.523, +0.324] USD/วัน
