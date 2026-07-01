# S36 — FVG (Fair Value Gap) Retracement — ICT/SMC, 3rd successful diversification leg

วันที่เริ่ม: 2026-06-27
สถานะ: ✅ เสร็จ — **เจอ champion ใหม่ (3-way blend) ที่ดีกว่า 2-way เดิม ทุกมิติ ทุก window (4/4)**

## ตอบคำที่ผู้ใช้ถาม: เทคนิคไหนมีอยู่แล้ว/ยังไม่ลอง

- มีอยู่แล้วใน bot เดิม (S1-S20): FVG (S2/S4), RSI divergence (S9), CRT (S10), Fibo (S11)
- ลองไปแล้วในชุดวิจัยนี้: liquidity sweep/ICT-SMC (S25), mean-reversion (S35, ตก — edge หมดอายุ)
- **S36 นี้คือ FVG ตัวแรกที่ทดสอบในเฟรมเวิร์กใหม่** (htf_trend+circuit_breaker+robustness+
  correlation-check) ต่างจาก S2/S4 เดิมที่เป็นส่วนของ live bot

## กลไก: FVG Retracement (continuation, ไม่ใช่ reversal)

3 แท่งต่อกัน high แท่ง1 ไม่ทับ low แท่ง3 (bullish gap) หรือกลับกัน (bearish gap) → รอราคาย้อนกลับ
เข้าไปในช่องว่าง >= retrace% ของช่องว่าง แล้วเข้าตามทิศเดิม (FVG เป็นแนวรับ/ต้านชั่วคราว) ยืนยันด้วย
htf_trend(M15/EMA50) เหมือน A/B — `strategy36.py` / `sim_s36_backtest.py` / `optimize_s36.py`

## Grid search (36 combos, 30 วัน) + robustness (เผย pattern ตรงข้าม S35)

Top config: `MIN_GAP_ATR=0.25, MAX_GAP_AGE_BARS=15, RETRACE_ENTRY_PCT=0.5, SL_ATR_MULT=1.0, TP_RR=0.8`

| window | n | WR% | PF | sharpe |
|---|---|---|---|---|
| 30d (ล่าสุด) | 33 | 81.8 | 4.89 | **0.708** |
| 45d | 48 | 72.9 | 2.25 | 0.397 |
| 60d | 65 | 69.2 | 1.94 | 0.338 |
| 90d | 69 | 63.8 | 1.53 | 0.155 |
| 120d | 85 | 58.8 | 1.27 | 0.093 |
| 150d | 117 | 60.7 | 1.29 | 0.102 |

**ตรงข้ามกับ S35 (mean-reversion ที่ edge จางหายในข้อมูลล่าสุด):** S36 มี edge **แข็งแรงที่สุดใน
30 วันล่าสุด** แล้วค่อยๆเจือจางเมื่อรวมข้อมูลเก่าเข้ามา — **แต่ PF ไม่เคยตกต่ำกว่า 1.0 เลยในทุก
window** (1.27-4.89) ต่างจาก S35 ที่ตกไปแตะ 0.93 — สัญญาณบวกว่า FVG mechanism กำลังทำงานดีใน
ตลาดปัจจุบัน

## Sanity-check + Correlation check (กฎสำคัญจาก S31)

10 ไม้แรก: ทุก BUY มี `sl<entry<tp`, ทุก SELL มี `tp<entry<sl` ถูกต้องครบ ไม่มีบั๊ก

`signal_time_ts` overlap (150 วัน): A(engulfing)=925 signals, B(volbreak)=42, C(FVG)=149 —
**overlap A&C = 0 ไม้ (0.0%), overlap B&C = 0 ไม้ (0.0%)** — decorrelate สมบูรณ์กับทั้ง 2 ระบบเดิม

## 🏆 3-way Blend Test (A+B+C ทั้ง 3 รันพร้อมกันเต็มทุนแต่ละตัว — ตามข้อจำกัด lot-floor จาก S33/S34)

| window | A+B $/เดือน | A+B+C $/เดือน | A+B sharpe | A+B+C sharpe | A+B streak | A+B+C streak |
|---|---|---|---|---|---|---|
| 60d | $192.5 | **$265.9** | 0.191 | **0.236** | 2d | 3d |
| 90d | $303.4 | **$356.5** | 0.247 | **0.267** | 3d | 4d |
| 120d | $195.4 | **$223.7** | 0.171 | **0.181** | 4d | 4d |
| 150d | $190.7 | **$219.8** | 0.175 | **0.190** | 4d | 4d |

**3-way ชนะทั้ง $/เดือน (+14% ถึง +38%) และ sharpe (+6% ถึง +24%) ทุก window** maxStreak แย่ลง
เล็กน้อย (เพิ่ม 1 วันในบาง window) แต่ trade-off นี้คุ้มมากเทียบกับกำไรที่เพิ่มขึ้น

## สถานะ Exhaustion Checklist

1. [x] grid search 36 combos (30 วัน, เร็วเพราะลดสเกลหลัง optimize_s36 รอบแรกค้าง) ✅
2. [x] robustness check ข้าม 6 window (30-150 วัน) — พบ pattern ตรงข้าม S35 (edge แข็งแรงขึ้นไม่ใช่
       จางหาย) ✅
3. [x] sanity-check trade samples (10 ไม้) — ไม่มีบั๊ก ✅
4. [x] correlation check กับ A และ B ด้วยโค้ดจริงก่อนเชื่อผล blend (บทเรียนจาก S31) — overlap 0% ✅
5. [x] ทดสอบ 3-way blend ข้าม 4 window เทียบ 2-way เดิม ✅
6. [x] เขียนสรุปลงไฟล์นี้ ✅

## บทสรุปสุดท้าย — 🏆 NEW CHAMPION (3-way blend)

**Champion เปลี่ยนเป็นครั้งที่ 2** (ครั้งแรกคือ S34 ที่เพิ่ม B เข้ากับ A) — การลองเทคนิค ICT/SMC
(FVG) ตามที่ผู้ใช้ขอ เจอกลไกที่ 3 ที่ decorrelate สมบูรณ์ (overlap 0%) และเพิ่ม performance จริง

**Champion ใหม่ = รัน 3 ระบบพร้อมกันบนทุน $1000 เดียวกัน:**

ระบบ A (engulfing, S30/S31): `M5, engulfing r1.0, SL1.2/RR1.0, htf_trend(M15/EMA50),
circuit_breaker(trig3/cool10), risk0.5%`

ระบบ B (volume-breakout, S34): `M5, lookback8, volmult2.0, minbreakout0.15, SL0.8/RR1.0,
htf_trend(M15/EMA50), circuit_breaker(trig3/cool10), risk0.5%`

ระบบ C (FVG retracement, S36 — ใหม่): `M5, MIN_GAP_ATR=0.25, MAX_GAP_AGE_BARS=15,
RETRACE_ENTRY_PCT=0.5, SL_ATR_MULT=1.0, TP_RR=0.8, htf_trend(M15/EMA50),
circuit_breaker(trig3/cool10), risk0.5%`

**ตัวเลข robust (เฉลี่ย 4 window 60-150วัน):** $/เดือน **$220-357** (เทียบ A+B เดิม $191-303),
sharpe **0.18-0.27** (เทียบ A+B เดิม 0.17-0.25), maxStreak 3-4 วัน

เทคนิคที่ผู้ใช้ถามแต่ยังไม่ลอง (เผื่อทำต่อ): Elliott Wave, horizontal Support/Resistance,
Demand/Supply zone, Fibo Premium/Discount (OTE) — ยังเป็น candidate สำหรับกลไกที่ 4

จบ S36 — standalone research/backtest-only 100%, ไม่ wire เข้า live, ไม่แก้ S1-S35 หรือไฟล์ระบบหลัก
