# S45 — Order Block (ICT/SMC) — 11th leg, marginal contributor with notable edge-decay caveat

วันที่เริ่ม: 2026-06-27
สถานะ: ✅ เสร็จ (marginal — เพิ่ม $/mo ทุก window แต่ sharpe ผสม: ดีขึ้น 2/5, แย่ลงเล็กน้อย 3/5)

## ที่มา: ลิสต์รอบ 2 ของผู้ใช้ — ตัวสุดท้ายในกลุ่ม "level-based candidate ใหม่"

จากลิสต์: ORB, SuperTrend, MACD entry, Volume Profile (✅S44), **Order Block (S45 นี้)**

## กลไก: Order Block (last-opposite-color-candle-before-impulse)

**bullish OB** = แท่งแดงล่าสุด (close<open) ก่อนแท่ง impulse ที่วิ่งขึ้นแรง (range >=
IMPULSE_ATR_MULT x ATR และทะลุ high ของแท่งแดงนั้น) — โซน [low,high] ของแท่งแดงนั้นกลายเป็น
order block **bearish OB** = แท่งเขียวล่าสุดก่อน impulse ลง — ต่างจาก S39 (Demand/Supply) ที่ใช้
"โซน consolidation หลายแท่ง" Order Block ใช้ **แท่งเดียว** (นิยามแคบกว่า/เข้มงวดกว่า) —
`strategy45.py` / `sim_s45_backtest.py` / `optimize_s45.py`

## Grid search (108 combos, 60 วัน, 360.2s)

Top config: `IMPULSE_ATR_MULT=1.5, MAX_OB_AGE_BARS=40, MAX_VIOLATION_WICK_ATR=0.1, SL_ATR_MULT=1.0,
TP_RR=1.5` → n=190, WR=62.1%, $/mo=484.2, PF=2.37, sharpe=0.473, DD=4.4% (60d — ดูดีมาก)

## ⚠️ Robustness ข้าม 7 window เปิดเผย edge-decay ที่รุนแรงกว่า S38 — DD พุ่งสูงที่ window กลาง

| window | n | WR% | PF | DD% | sharpe | $/mo |
|---|---|---|---|---|---|---|
| 30d | 104 | 64.4 | 2.20 | 6.9 | 0.399 | $406.8 |
| 45d | 159 | 64.2 | 2.68 | 4.6 | 0.413 | $601.8 |
| 60d | 190 | 62.1 | 2.37 | 4.4 | 0.473 | $484.2 |
| 90d | 240 | 55.4 | 1.32 | **44.3** | 0.121 | $154.8 |
| 120d | 316 | 53.5 | 1.22 | **50.4** | 0.087 | $102.9 |
| 150d | 370 | 51.6 | 1.15 | **54.0** | 0.063 | $66.9 |
| 180d | 462 | 55.0 | 1.54 | 30.2 | 0.192 | $239.4 |

ที่ window 30-60d (ข้อมูลล่าสุด) ผลดีมาก DD ต่ำ (4-7%) แต่พอรวมข้อมูลเก่าเข้ามา (90-150d) **DD
พุ่งสูงถึง 44-54%** (แย่กว่า S38 ที่ DD สูงสุดแค่ ~40%) แม้ PF จะไม่เคยตกต่ำกว่า 1.0 ก็ตาม — นี่คือ
edge-decay ที่รุนแรงกว่าตัวก่อนหน้า บ่งชี้ว่ามีช่วง losing-streak หนักในอดีต (maxStreak พุ่งถึง
10 วันที่ 120-150d) ที่ window 180d ฟื้นตัวบ้าง (DD ลงมาที่ 30%) — pattern ไม่ชัดเจนเป็น
monotonic staircase แบบ S35/S38 แต่เป็นการ "เด้งกลับ" ที่ผิดปกติกว่า

## Sanity-check + Correlation check (window 150 วัน)

823 ไม้: ไม่มีไม้ผิดกฎ SL/TP เลย (0/823)

overlap: A=2.7%, B=0.0%, C=0.1%, D=27.7%, E=13.0%, **F=27.9%** (สูงสุด, ทั้งคู่เป็น impulse-based:
F=consolidation-zone, L=single-candle), G=0.0%, H=0.0%, I=4.4%, K=18.1% — decorrelate พอใช้ได้

## 🏆 11-way Blend Test — ผลผสม (mixed) แต่สุทธิเป็นบวกเล็กน้อย

| window | 10-way เดิม $/mo | 11-way ใหม่ $/mo | 10-way sharpe | 11-way sharpe |
|---|---|---|---|---|
| 60d | $5841.9 | **$6223.8** (+6.5%) | 0.551 | **0.567** |
| 90d | $5639.1 | **$5842.0** (+3.6%) | **0.472** | 0.463 (-1.9%) |
| 120d | $5847.4 | **$5941.9** (+1.6%) | **0.414** | 0.407 (-1.7%) |
| 150d | $5379.5 | **$5454.2** (+1.4%) | **0.386** | 0.380 (-1.6%) |
| 180d | $5940.3 | **$6166.7** (+3.8%) | 0.377 | **0.380** |

**$/mo ชนะทุก window (5/5, +1.4% ถึง +6.5%)** sharpe ชนะ 2/5 และแย่ลงเล็กน้อย 3/5 (เพียง
-1.6% ถึง -1.9% เท่านั้น — ต่างจาก S43 ที่แย่ลงหนักทุก window) **สรุปว่ายังคุ้มที่จะรวมเข้า blend**
เพราะการลดลงของ sharpe เล็กน้อยมาก ขณะที่ $/mo เพิ่มขึ้นชัดเจนทุก window — ใช้บรรทัดฐานเดียวกับ
S38/S40/S41 (marginal positive, ไม่ใช่ negative แบบ S43)

## สถานะ Exhaustion Checklist

1. [x] grid search 108 combos (60 วัน, 360.2s) ✅
2. [x] robustness check ข้าม 7 window — **พบ edge-decay รุนแรง (DD 44-54% ที่ window กลาง)** แต่
       PF ไม่เคยตกต่ำกว่า 1.0 ✅ (มีคำเตือนชัดเจน)
3. [x] sanity-check trade samples (15 ไม้ + เช็คทั้งหมด 823 ไม้) — ไม่มีบั๊ก ✅
4. [x] correlation check กับ A-K — overlap สูงสุดที่ F=27.9% แต่ผ่าน ✅
5. [x] ทดสอบ 11-way blend ข้าม 5 window เทียบ 10-way เดิม — $/mo ชนะ 5/5, sharpe ผสม (2 ชนะ/3 แพ้
       เล็กน้อย) → ยอมรับ (ไม่ reject) ตามบรรทัดฐาน S38/S40/S41 ✅
6. [x] เขียนสรุปลงไฟล์นี้ พร้อมคำเตือนเรื่อง DD ที่ window กลาง ✅

## บทสรุปสุดท้าย — 🏆 NEW CHAMPION (11-way blend) — marginal contributor พร้อมคำเตือน

**Champion เปลี่ยนเป็นครั้งที่ 10** — เพิ่ม leg ที่ 11 (Order Block) เข้า blend เดิม

**Champion ใหม่ = รัน 11 ระบบพร้อมกันบนทุน $1000 เดียวกัน:**

ระบบ A-K เหมือนเดิม (ดู create_s44.md)

**ระบบ L (Order Block, S45 — ใหม่, marginal + มี DD risk ในประวัติ):** `M5, IMPULSE_ATR_MULT=1.5,
MAX_OB_AGE_BARS=40, MAX_VIOLATION_WICK_ATR=0.1, SL_ATR_MULT=1.0, TP_RR=1.5, htf_trend(M15/EMA50),
circuit_breaker(trig3/cool10), risk0.5%`

**ตัวเลข robust (เฉลี่ย 5 window 60-180วัน):** $/เดือน **$5454-6224** (เทียบ 10-way เดิม
$5380-5941), sharpe **0.38-0.57** (ใกล้เคียง 10-way เดิม — บาง window ดีขึ้นเล็กน้อย บาง window
แย่ลงเล็กน้อย)

**คำเตือนสำหรับการพิจารณาในอนาคต:** หาก standalone DD ของ leg L เกิด spike รุนแรงในช่วงเวลาใดเวลา
หนึ่งของตลาดจริง อาจกระทบ portfolio รวม — ควรจับตา L เป็นพิเศษเทียบกับ leg อื่นที่เสถียรกว่า (D,K,F,I)

ยังเหลือ ORB, SuperTrend, MACD เป็น candidate ต่อไป

จบ S45 — standalone research/backtest-only 100%, ไม่ wire เข้า live, ไม่แก้ S1-S44 หรือไฟล์ระบบหลัก
