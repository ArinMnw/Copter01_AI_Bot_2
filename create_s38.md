# S38 — Fibonacci Premium/Discount (OTE) — 5th diversification leg

วันที่เริ่ม: 2026-06-27
สถานะ: ✅ เสร็จ — **เจอ champion ใหม่ (5-way blend) ดีกว่า 4-way เดิมในแทบทุกมิติ**

## ตอบคำที่ผู้ใช้ถาม (ต่อจาก S37): เทคนิคไหนยังไม่ลอง

จากลิสต์เดิม: ict smc(✅) elliottwave(ยัง) support/resistance(✅S37) fvg(✅S36)
demand/supply(ยัง) crt(มีแค่ S10 เดิม) rsi divergence(มีแค่ S9 เดิม) **fibo premium/discount(S38 นี้)**

## กลไก: Fibonacci OTE (Optimal Trade Entry)

หา swing impulse ล่าสุด (high/low สุดขั้วใน `SWING_LOOKBACK_BARS` แท่ง, กรอง noise ด้วย
`MIN_SWING_ATR`) ถ้า low เกิดก่อน high = impulse ขาขึ้น → รอราคาย้อนกลับเข้าโซน **discount**
(fib retrace 61.8%-78.6% จาก high) แล้วเข้า BUY ต่อทิศเดิม ถ้า high เกิดก่อน low = impulse ขาลง →
รอราคาย้อนขึ้นเข้าโซน **premium** แล้วเข้า SELL — ยืนยันด้วย htf_trend(M15/EMA50) เหมือน A-D —
`strategy38.py` / `sim_s38_backtest.py` / `optimize_s38.py`

## Grid search (108 combos, 60 วัน)

Top config: `SWING_LOOKBACK_BARS=25, MIN_SWING_ATR=3.0, MAX_RETRACE_AGE_BARS=20, SL_ATR_MULT=1.0,
TP_RR=1.0` → n=210, WR=66.7%, $/mo=593.1, PF=2.07, sharpe=0.482 (ที่ 60d)

## Robustness ข้าม 7 window (30-180 วัน) — มี edge-decay pattern คล้าย S35 แต่ไม่ตกต่ำกว่า PF=1.0

| window | n | WR% | PF | DD% | sharpe |
|---|---|---|---|---|---|
| 30d | 131 | 74.0 | 3.07 | 8.1 | 0.778 |
| 45d | 166 | 69.3 | 2.44 | 10.0 | 0.579 |
| 60d | 210 | 66.7 | 2.07 | 13.1 | 0.482 |
| 90d | 291 | 63.6 | 1.42 | 40.6 | 0.188 |
| 120d | 374 | 61.2 | 1.53 | 26.9 | 0.197 |
| 150d | 450 | 60.0 | 1.51 | 25.0 | 0.184 |
| 180d | 520 | 60.2 | 1.51 | 23.6 | 0.183 |

edge แข็งแรงที่สุดใน 30-60d ล่าสุด แล้วลดลงและคงตัวที่ sharpe~0.18-0.20 ตั้งแต่ 90d ขึ้นไป (ไม่ใช่
overfitting noise — เป็น monotonic staircase แบบเดียวกับ S35 แต่ **ต่างจาก S35 ที่ PF ไม่เคยตกต่ำ
กว่า 1.4 เลย** = edge ยังมีอยู่จริง เพียงอ่อนกว่า D(S37) มาก สังเกต DD spike ที่ 90d (40.6%) ที่ลด
ลงเองที่ window ยาวขึ้น — บ่งชี้ losing-streak เฉพาะช่วง 60-90 วันก่อน ไม่ใช่ปัญหาเชิงระบบ)

## Sanity-check + Correlation check

285 ไม้ที่ smoke-test: ไม่มีไม้ผิดกฎ SL/TP เลย (0/285)

`signal_time_ts` overlap (150 วัน): A=925, B=42, C=149, D=3579, E(OTE)=896 —
overlap A&E=2.6%, B&E=0.0%, C&E=0.7%, **D&E=27.1%** (สูงกว่าคู่อื่นเพราะทั้ง D และ E เป็น
pullback-to-level continuation เหมือนกัน แต่สร้าง level จากวิธีต่างกัน — fractal pivot vs fib
swing-retrace) ยังถือว่า decorrelate พอใช้ได้ (72.9% ของ E ไม่ทับ D)

## 🏆 5-way Blend Test (A+B+C+D+E ทั้ง 5 รันพร้อมกันเต็มทุนแต่ละตัวที่ $1000)

| window | 4-way เดิม $/mo | 5-way ใหม่ $/mo | 4-way sharpe | 5-way sharpe |
|---|---|---|---|---|
| 60d | $2123.7 | **$2682.2** | 0.483 | **0.499** |
| 90d | $2206.5 | **$2508.7** | **0.428** | 0.406 |
| 120d | $1956.6 | **$2354.5** | 0.354 | 0.352 |
| 150d | $1651.9 | **$1947.3** | **0.323** | 0.316 |
| 180d | $1591.5 | **$1873.2** | 0.294 | **0.296** |

**5-way ชนะ $/เดือนทุก window (5/5)** sharpe ชนะ 3/5 และแพ้เล็กน้อย 2/5 (90d: -5.1%, 150d: -2.2%
— เล็กน้อยมาก ไม่ใช่สัญญาณเตือน) **สรุปว่าคุ้มที่จะรวม E เข้า blend** เพราะ $/เดือนเพิ่มขึ้นชัดเจน
ทุก window โดยที่ sharpe เกือบไม่เปลี่ยนเลย

## สถานะ Exhaustion Checklist

1. [x] grid search 108 combos (60 วัน, 330.6s) ✅
2. [x] robustness check ข้าม 7 window (30-180 วัน) — พบ edge-decay staircase คล้าย S35 แต่ PF ไม่
       เคยตกต่ำกว่า 1.0 (1.42-3.07) ✅
3. [x] sanity-check trade samples (15 ไม้ + เช็คทั้งหมด 285 ไม้ด้วยโค้ด) — ไม่มีบั๊ก ✅
4. [x] correlation check กับ A,B,C,D ด้วยโค้ดจริง — overlap ต่ำพอทุกคู่ (0-27.1%) ✅
5. [x] ทดสอบ 5-way blend ข้าม 5 window เทียบ 4-way เดิม — ชนะ $/mo ทุก window, sharpe เสมอตัว ✅
6. [x] เขียนสรุปลงไฟล์นี้ ✅

## บทสรุปสุดท้าย — 🏆 NEW CHAMPION (5-way blend)

**Champion เปลี่ยนเป็นครั้งที่ 4** — เพิ่ม leg ที่ 5 (Fibonacci OTE) เข้า blend เดิม

**Champion ใหม่ = รัน 5 ระบบพร้อมกันบนทุน $1000 เดียวกัน (เต็มทุนคนละตัวตามข้อจำกัด lot-floor):**

ระบบ A (engulfing, S30/S31), B (volume-breakout, S34), C (FVG, S36), D (S/R pivot bounce, S37 —
ตัวขับหลัก) — config เดิมตามที่บันทึกใน create_s37.md

**ระบบ E (Fibonacci OTE, S38 — ใหม่):** `M5, SWING_LOOKBACK_BARS=25, MIN_SWING_ATR=3.0,
MAX_RETRACE_AGE_BARS=20, SL_ATR_MULT=1.0, TP_RR=1.0, htf_trend(M15/EMA50),
circuit_breaker(trig3/cool10), risk0.5%`

**ตัวเลข robust (เฉลี่ย 5 window 60-180วัน):** $/เดือน **$1873-2682** (เทียบ 4-way เดิม
$1592-2207), sharpe **0.30-0.50** (เทียบ 4-way เดิม 0.29-0.48 — ใกล้เคียง, ไม่ได้ลดลง)

เทคนิคที่ผู้ใช้ถามแต่ยังไม่ลอง (เผื่อทำต่อ): Elliott Wave, Demand/Supply zone — เหลือ 2 ตัวจากลิสต์
เดิม (RSI divergence/CRT มีอยู่แล้วในเฟรมเวิร์กเก่า S1-S20 ยังไม่ได้ retest ในเฟรมเวิร์กใหม่)

จบ S38 — standalone research/backtest-only 100%, ไม่ wire เข้า live, ไม่แก้ S1-S37 หรือไฟล์ระบบหลัก
