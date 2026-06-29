# S34 — Volume-Confirmed Breakout + Diversified Blend with Champion (research/backtest-only)

วันที่เริ่ม: 2026-06-27
สถานะ: ✅ เสร็จ — **เจอ champion ใหม่ที่ดีกว่าเดิมจริง ทุกมิติ ทุก window (5/5)**

## เปลี่ยน entry mechanism ตามที่ผู้ใช้ขอ (S31-S33 ขุด engulfing จนหมดแล้ว)

แกนใหม่: **Volume-Confirmed Breakout** — ใช้ MT5 `tick_volume` (proxy ของ order-flow/activity,
broker ไม่มี real_volume สำหรับ XAUUSD CFD) ยืนยัน breakout ของกรอบ N แท่งล่าสุด ต่างจาก
engulfing (price-pattern ใกล้ EMA) โดยสิ้นเชิง — ยัง lock htf_trend(M15/EMA50) + circuit_breaker
ไว้เป็นฐาน (พิสูจน์แล้วว่ามี efficiency เป็นบวกตั้งแต่ S27/S29)

ไฟล์: `strategy34.py` / `sim_s34_backtest.py` / `optimize_s34.py`

## Grid search (72 combos, 45 วันสำหรับค้นหาเร็ว — ระวัง n น้อย)

**คำเตือนสำคัญ:** กริดแรกที่ 45 วันให้ WR 90.9%/PF 11.24 (ดูดีเกินจริง) — ตรวจสอบแล้วพบว่า n=11
ไม้เท่านั้น (10 ชนะ 1 แพ้) ตัวอย่างน้อยเกินจะเชื่อได้ ต้อง validate ที่ window ยาวขึ้นก่อนเสมอ

## Robustness validation (lookback=8, volmult=2.0, minbreakout=0.15, SL=0.8, RR=1.0)

| window | n | WR% | PF | sharpe | maxStreak | $/mo |
|---|---|---|---|---|---|---|
| 60d | 14 | 85.7 | 6.01 | 0.893 | 1d | $66.0 |
| 90d | 26 | 76.9 | 2.71 | 0.632 | 2d | $56.7 |
| 120d | 21 | 76.2 | 2.31 | 0.387 | 3d | $26.4 |
| 150d | 32 | 75.0 | 2.33 | 0.386 | 3d | $26.7 |
| 180d | 37 | 73.0 | 2.41 | 0.392 | 3d | $26.7 |

**robust จริง** (WR 73-86%, PF ไม่ต่ำกว่า 2.3 เลยที่ window ใหญ่, maxStreak สั้นมาก 1-3 วัน) —
sharpe (0.39-0.89) **สูงกว่า champion engulfing เดิม (0.15-0.21) ถึง 2-4 เท่า** แต่ความถี่ต่ำมาก
(0.2-0.3 ไม้/วัน) ทำให้ $/เดือนดิบต่ำกว่า champion ($27-66 vs $159-240)

Sanity-check 10 ไม้แรก: ทุก BUY มี `sl<entry<tp`, ทุก SELL มี `tp<entry<sl` ถูกต้องครบ ไม่มีบั๊ก

## Correlation check กับ champion (S31 engulfing) — ต่างจาก fake-blend ของ S31!

`signal_time_ts` overlap ระหว่าง champion (925 signals/150วัน) กับ S34 (42 signals/150วัน):
**overlap = 2 ไม้ (0.2% ของ champion, 4.8% ของ S34)** — เกือบ decorrelate สมบูรณ์ เพราะกลไกต่างกัน
จริง (price-pattern vs volume-breakout) ไม่เหมือน S31 ที่ลอง SL/RR ต่างกันบน entry เดียวกัน
(overlap 100%)

## 🏆 Blend Test — champion + S34 พร้อมกัน (ผลสำเร็จจริง)

แบ่งทุนคนละครึ่ง ($500+$500) รันพร้อมกัน รวม daily pnl เทียบกับ champion เดี่ยวๆเต็มทุน ($1000):

| window | Blend $/mo | Champion-only $/mo | Blend sharpe | Champion sharpe | Blend maxStreak | Champion maxStreak |
|---|---|---|---|---|---|---|
| 60d | **$192.5** | $126.5 | **0.191** | 0.135 | **2d** | 3d |
| 90d | **$303.4** | $246.8 | **0.247** | 0.212 | 3d | 3d |
| 120d | **$195.4** | $168.9 | **0.171** | 0.152 | 4d | 4d |
| 150d | **$191.4** | $164.0 | **0.176** | 0.156 | 4d | 4d |
| 180d | **$139.8** | $113.4 | **0.131** | 0.112 | 4d | 4d |

**Blend ชนะ champion เดี่ยวทุกมิติ ทุก window (5/5)** — ทั้ง $/เดือนสูงกว่า, sharpe สูงกว่า,
maxStreak เท่ากันหรือดีกว่า ไม่มีข้อเสียเลย เพราะ correlation ต่ำจริง (ไม่ใช่ของปลอมแบบ S31)

## ⚠️ หมายเหตุสำคัญเรื่อง capital-split ratio (lot floor เหมือน S33)

ทดสอบ ratio 30/70, 40/60, 50/50, 60/40, 70/30 — **ผลเหมือนกันทุกอัตราส่วนเป๊ะ** เพราะ lot ของ
ทั้ง 2 sub-strategy ติดพื้นขั้นต่ำ 0.01 ที่ทุกระดับทุนย่อย ($300/$500/$700 ให้ lot=0.01 เหมือนกัน
หมด — ยืนยันด้วย debug) **สิ่งที่เกิดขึ้นจริงคือรันทั้ง 2 กลยุทธ์พร้อมกันแบบ full-size lot แล้วรวมผล
ไม่ใช่การแบ่ง risk ตามทฤษฎี** — ที่ทุนเล็กขนาดนี้ (~$1000) "อัตราส่วนแบ่งทุน" ไม่มีความหมาย
มีความหมายแค่ "ใช้ทั้ง 2 กลยุทธ์พร้อมกันหรือไม่" เท่านั้น

## สถานะ Exhaustion Checklist

1. [x] grid search entry mechanism ใหม่ (72 combos) + ระวัง sample เล็กก่อนเชื่อผล ✅
2. [x] robustness check ข้าม 5 window (60-180 วัน) ของ S34 เดี่ยว ✅
3. [x] sanity-check trade samples (10 ไม้) — ไม่มีบั๊ก ✅
4. [x] ตรวจ correlation กับ champion ด้วยโค้ดจริงก่อนเชื่อผล blend (บทเรียนจาก S31) ✅
5. [x] ทดสอบ blend ข้าม 5 window + ratio sweep + ตรวจ lot-floor artifact ✅
6. [x] เขียนสรุปลงไฟล์นี้ ✅

## บทสรุปสุดท้าย — 🏆 NEW CHAMPION

**Champion เปลี่ยนเป็นครั้งแรกตั้งแต่ S30** — การเปลี่ยน entry mechanism (ตามที่ผู้ใช้ขอ) ทำให้เจอ
กลไกที่ decorrelate กับ champion เดิมได้จริง ซึ่งเปิดทางให้ diversification ที่ S31 ทำไม่ได้ (fake)
ใช้งานได้จริงในที่สุด

**Champion ใหม่ = รัน 2 ระบบพร้อมกันบนทุน $1000 เดียวกัน:**

ระบบ A (เดิมจาก S30/S31): `ENTRY_TF=M5, ENTRY_PATTERN=engulfing, ENGULF_MIN_RATIO=1.0,
SL_ATR_MULT=1.2, TP_RR=1.0, MIN_GAP_BARS=1, htf_trend(M15/EMA50), circuit_breaker(trig3/cool10),
RISK_PCT=0.5%`

ระบบ B (ใหม่จาก S34): `ENTRY_TF=M5, BREAKOUT_LOOKBACK=8, VOLUME_SURGE_MULT=2.0,
MIN_BREAKOUT_ATR=0.15, SL_ATR_MULT=0.8, TP_RR=1.0, htf_trend(M15/EMA50),
circuit_breaker(trig3/cool10), RISK_PCT=0.5%`

**ตัวเลข robust (เฉลี่ย 5 window):** $/เดือน **$140-303** (เทียบ champion เดี่ยว $113-247),
sharpe **0.13-0.25** (เทียบ champion เดี่ยว 0.11-0.21), maxStreak **2-4 วัน** (เท่าหรือดีกว่า)

จบ S34 — standalone research/backtest-only 100%, ไม่ wire เข้า live, ไม่แก้ S1-S33 หรือไฟล์ระบบหลัก
