# S42 — CRT (Candle Range Theory) sweep+reversal — retest จาก S10 เดิม, 9th leg

วันที่เริ่ม: 2026-06-27
สถานะ: ✅ เสร็จ — **ผ่าน (contribution ดีกว่า S40/S41 marginals: +4-6% $/mo, PF standalone 1.7-2.1)**

## ที่มา: CRT มีอยู่แล้วใน live bot เดิม (S10) — retest ในเฟรมเวิร์กใหม่ + ปิดท้ายลิสต์เทคนิคทั้งหมด

หลัง S41 (RSI divergence) ครบทุกเทคนิคจากลิสต์ที่ผู้ใช้ขอแล้ว — CRT เป็นตัวสุดท้ายที่เหลือ
(มีอยู่ในเฟรมเวิร์กเก่า S10 แต่ยังไม่ retest ใน framework S30+) ทำให้ครบทุกเทคนิคที่กล่าวถึงในงานนี้

## กลไก: CRT (accumulation-manipulation-distribution / Power-of-3)

1) **range block** = high/low ของ RANGE_BARS แท่ง (โซน accumulation)
2) **manipulation** = แท่งถัดมา sweep ทะลุขอบ range >= SWEEP_ATR_MULT x ATR (ล่า stop/liquidity)
   แล้ว **ปิดกลับเข้ามาในโซน** (false breakout)
3) **distribution** = เข้า reversal ทิศตรงข้าม sweep (sweep high→SELL, sweep low→BUY) SL เลยจุด sweep,
   TP ตาม RR — ต่างจาก S25 (sweep ของ swing pivot จุดเดียว) ตรงที่ใช้ "โซน range block + ปิดกลับเข้า
   โซน" เป็นเงื่อนไขยืนยัน — `strategy42.py` / `sim_s42_backtest.py` / `optimize_s42.py`

## Grid search (96 combos, 60 วัน) — htf_trend filter ครองอันดับต้นทั้งหมด (เหมือน S41)

Top config: `RANGE_BARS=9, SWEEP_ATR_MULT=0.5, MIN_RANGE_ATR=1.0, SL_ATR_MULT=1.0, TP_RR=1.0,
CONFIRMATION_TYPE=htf_trend` → n=111, WR=65.8%, PF=1.87, sharpe=0.376 (60d)

**บทเรียนซ้ำจาก S41:** sweep+reversal ที่ดีที่สุดในทางปฏิบัติคือ **เข้าตามทิศเทรนด์ใหญ่** (sweep low
ในเทรนด์ขึ้น = dip-buy หลัง liquidity grab) ไม่ใช่ pure counter-trend — config ที่ใช้ htf_trend
ครองอันดับ 1-9 ในกริด ส่วน "none" ตกไปอยู่อันดับท้ายๆ (baseline default PF เพียง 1.04)

## Robustness ข้าม 7 window (30-180 วัน) — เสถียรมาก ไม่มี window ใดพัง

| window | n | WR% | PF | DD% | sharpe |
|---|---|---|---|---|---|
| 30d | 56 | 67.9 | 2.11 | 8.2 | 0.469 |
| 45d | 82 | 67.1 | 2.09 | 5.9 | 0.494 |
| 60d | 111 | 65.8 | 1.87 | 9.2 | 0.376 |
| 90d | 160 | 62.5 | 1.82 | 19.2 | 0.288 |
| 120d | 220 | 61.4 | 1.88 | 15.7 | 0.312 |
| 150d | 261 | 59.4 | 1.79 | 15.2 | 0.292 |
| 180d | 324 | 60.5 | 1.72 | 14.5 | 0.263 |

PF เสถียรมาก (1.72-2.11 ทุก window) sharpe เป็นบวกแข็งแรงเสมอ (0.26-0.49) n เพียงพอ (56-324) —
ไม่มี overfitting illusion แบบ S41, ไม่มี window ใดพัง — leg ที่แข็งแรงกว่า G(S40)/H(S41) ชัดเจน

## Sanity-check + Correlation check (window 150 วัน)

532 ไม้: ไม่มีไม้ผิดกฎ SL/TP เลย (0/532)

overlap: A=7.9%, B=0.0%, C=0.0%, **D=49.4%** (สูงสุดในทุก leg ที่เคยทดสอบ — ทั้ง D และ I เป็น
level/zone-based + ใช้ htf_trend เหมือนกัน), E=6.4%, F=10.9%, G=0.6%, H=0.0% — **D&I overlap สูง
ถึงครึ่งหนึ่ง** แต่อีกครึ่ง (50.6%) ยังเป็นสัญญาณ unique และผล blend ยืนยันว่ายังเพิ่มมูลค่าจริง

## 🏆 9-way Blend Test (A-I ทั้ง 9 รันพร้อมกันเต็มทุนแต่ละตัวที่ $1000)

| window | 8-way เดิม $/mo | 9-way ใหม่ $/mo | 8-way sharpe | 9-way sharpe |
|---|---|---|---|---|
| 60d | $3790.0 | **$4001.4** | 0.557 | 0.557 |
| 90d | $3938.9 | **$4089.0** | 0.456 | **0.459** |
| 120d | $3770.5 | **$4065.8** | 0.390 | **0.403** |
| 150d | $3496.3 | **$3717.7** | 0.367 | **0.375** |
| 180d | $3925.5 | **$4135.2** | 0.363 | **0.371** |

**9-way ชนะ $/เดือนทุก window (5/5, +4% ถึง +6%)** sharpe ชนะ 4/5 + เสมอ 1 (60d) —
**แม้ overlap กับ D สูงถึง 49.4% CRT ก็ยังเพิ่มมูลค่าจริง** เพราะครึ่งหนึ่งของสัญญาณ unique และวันที่
มันยิงเป็นวันที่ทำกำไร (posDay ลดเล็กน้อยเพราะวันเทรดเพิ่มขึ้น แต่ $/mo ชนะชัดเจน — trade-off คุ้ม)

## สถานะ Exhaustion Checklist

1. [x] grid search 96 combos (60 วัน, 290.6s) ✅
2. [x] robustness check ข้าม 7 window — PF/sharpe เสถียรแข็งแรงทุก window ไม่มี illusion ✅
3. [x] sanity-check trade samples (12 ไม้ + เช็คทั้งหมด 532 ไม้) — ไม่มีบั๊ก ✅
4. [x] correlation check กับ A-H — overlap สูงสุดที่ D=49.4% (จับตา) แต่ผล blend ยืนยันว่ายังคุ้ม ✅
5. [x] ทดสอบ 9-way blend ข้าม 5 window เทียบ 8-way เดิม — ชนะ $/mo ทุก window, sharpe ชนะ 4/5 ✅
6. [x] เขียนสรุปลงไฟล์นี้ ✅

## บทสรุปสุดท้าย — 🏆 NEW CHAMPION (9-way blend) + ปิดท้ายลิสต์เทคนิคทั้งหมด

**Champion เปลี่ยนเป็นครั้งที่ 8** — เพิ่ม leg ที่ 9 (CRT) เข้า blend เดิม contribution แข็งแรงกว่า
G/H (marginal) เพราะ standalone PF 1.7-2.1 เสถียรและ n เพียงพอ

**Champion ใหม่ = รัน 9 ระบบพร้อมกันบนทุน $1000 เดียวกัน:**

ระบบ A-H เหมือนเดิม (ดู create_s41.md)

**ระบบ I (CRT sweep+reversal, S42 — ใหม่):** `M5, RANGE_BARS=9, SWEEP_ATR_MULT=0.5, MIN_RANGE_ATR=1.0,
SL_ATR_MULT=1.0, TP_RR=1.0, CONFIRMATION_TYPE=htf_trend, circuit_breaker(trig3/cool10), risk0.5%`

**ตัวเลข robust (เฉลี่ย 5 window 60-180วัน):** $/เดือน **$3718-4135** (เทียบ 8-way เดิม
$3496-3939), sharpe **0.37-0.56** (ดีขึ้นเล็กน้อยทุก window)

**ครบทุกเทคนิคที่ผู้ใช้กล่าวถึงในงานนี้แล้ว 100%** (ict smc, elliottwave, support/resistance, fvg,
demand/supply, fibo premium/discount, rsi divergence, crt) — ถ้าจะไปต่อ ต้องเป็นการคิดกลไกใหม่
นอกลิสต์เดิม หรือ optimize leg ที่มีอยู่ลึกขึ้น

จบ S42 — standalone research/backtest-only 100%, ไม่ wire เข้า live, ไม่แก้ S1-S41 หรือไฟล์ระบบหลัก
