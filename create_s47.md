# S47 — SuperTrend flip entry — 13th leg, weak-but-positive marginal accept

วันที่เริ่ม: 2026-06-27
สถานะ: ✅ accept เป็น marginal contributor — **ยืนยันบทเรียนเดิมว่า pure trend-following ที่ M5
XAUUSD เป็น edge ที่อ่อนกว่า level-based/session-anchored mechanism เสมอ**

## ที่มา: Trend Module จากลิสต์รอบ 2 (EMA, ADX, SuperTrend)

EMA/ADX ถูกใช้เป็น filter อยู่แล้วในทุก leg ผ่าน htf_trend confirmation, SuperTrend เป็นตัวเดียวที่
ยังไม่ทำเป็น entry mechanism ของตัวเอง — `strategy47.py` / `sim_s47_backtest.py` / `optimize_s47.py`

## กลไก: SuperTrend (ATR-band ratchet trailing line)

คำนวณ basic upper/lower band จาก (high+low)/2 ± ST_ATR_MULT × ATR(ST_ATR_PERIOD) แต่ละแท่ง แล้ว
trail แบบ ratchet (final band ขยับเข้าหาราคาเท่านั้น ไม่ขยับออกจนกว่าราคาทะลุ) — trend พลิกขึ้นเมื่อ
close ทะลุ final upperband, พลิกลงเมื่อ close ทะลุ final lowerband — เข้า BUY/SELL ที่แท่งที่ trend
พลิกครั้งแรก (flip bar) ยืนยันด้วย htf_trend (M15/EMA50)

## การสำรวจพารามิเตอร์ — พบว่า conf=htf_trend จำเป็น, raw signal (conf=none) ใช้ไม่ได้เลย

ทดสอบ period∈{7,10,14,20} × mult∈{1.5,2.0,2.5,3.0} × conf∈{none,htf_trend} ที่ 90 วัน (ไม่มี
session filter): **conf=none ทุก config ให้ PF<=1.00 (ไม่มี edge เลย)** — ดีที่สุดคือ
conf=htf_trend, period=10, mult=2.5 → PF=1.17, n=87, $/mo=66.6 (ยังอ่อนมาก)

ขยาย grid ไปที่ SL_ATR_MULT∈{0.8,1.0,1.5} × TP_RR∈{1.0,1.5,2.0} × SESSION_FILTER∈{False,True}
(72 combos, 90 วัน): top คือ **period=20, mult=2.0, sl=1.5, rr=2.0, sess=False, conf=htf_trend**
→ n=141, WR=42.6%, PF=1.44, sharpe=0.196, $/mo=315.0

## Robustness ข้าม 7 window — เป็นบวกตลอด แต่อ่อนกว่าทุก leg ที่ accept ก่อนหน้า

| window | n | WR% | PF | DD% | sharpe | $/mo |
|---|---|---|---|---|---|---|
| 30d | 56 | 46.4 | 1.74 | 11.3 | 0.330 | $483.0 |
| 45d | 75 | 42.7 | 1.50 | 11.5 | 0.241 | $304.5 |
| 60d | 101 | 41.6 | 1.39 | 22.4 | 0.201 | $260.1 |
| 90d | 141 | 42.6 | 1.44 | 23.3 | 0.196 | $315.0 |
| 120d | 194 | 44.8 | 1.98 | 10.6 | 0.270 | $701.1 |
| 150d | 230 | 43.0 | 1.86 | 18.8 | 0.244 | $564.6 |
| 180d | 293 | 45.7 | 1.91 | 11.8 | 0.266 | $598.8 |

PF ไม่เคยตกต่ำกว่า 1.0 (edge จริงมีอยู่) แต่ sharpe (0.20-0.33) อ่อนกว่าทุก leg ที่ accept ก่อนหน้า
(ปกติ 0.27-0.58) — สมเหตุสมผลกับบทเรียนเดิม: trend-following ล้วน (ไม่ยึดกับ level/session
catalyst) แพ้ mean-reversion ของ M5 XAUUSD เสมอ เพียงแต่ SuperTrend มี ratchet trailing band
ที่ทนทานกว่า raw Donchian breakout (S43) มากพอที่จะรักษา PF>1.0 ได้

## Sanity-check — ไม่มีบั๊ก

522 ไม้ (150 วัน): ไม่มีไม้ผิดกฎ SL/TP เลย (0/522)

## 🏆 13-way Blend Test — ชนะ $/mo ทุก window, sharpe ผสม (เสียเล็กน้อย 2/5, ดีขึ้น 3/5)

| window | 12-way เดิม $/mo | 13-way ใหม่ $/mo | 12-way sharpe | 13-way sharpe |
|---|---|---|---|---|
| 60d | $7191.7 | **$7400.2** (+2.9%) | 0.576 | 0.570 (-1.0%) |
| 90d | $6601.5 | **$6945.0** (+5.2%) | 0.463 | 0.461 (-0.4%) |
| 120d | $6840.6 | **$7547.2** (+10.3%) | 0.410 | **0.426** (+3.9%) |
| 150d | $6278.0 | **$6853.1** (+9.2%) | 0.386 | **0.398** (+3.1%) |
| 180d | $6841.6 | **$7449.5** (+8.9%) | 0.384 | **0.399** (+3.9%) |

**13-way ชนะ $/เดือนทุก window (+2.9% ถึง +10.3%) sharpe แย่ลงเล็กน้อยเพียง 2/5 window (-1.0%,
-0.4% เท่านั้น) และดีขึ้น 3/5 window (+3.1% ถึง +3.9%)** — เข้าเกณฑ์ accept marginal positive
ตามกฎที่ใช้กับ S45 (sharpe แย่ลงเล็กน้อยบางช่วง + $/mo เพิ่มชัดเจนทุก window) แต่ผลรวมยังดีกว่า S45
เพราะ sharpe ส่วนใหญ่ดีขึ้นจริง ไม่ใช่แย่ลงหมด

## สถานะ Exhaustion Checklist

1. [x] smoke test + พารามิเตอร์สำรวจ (conf=none ใช้ไม่ได้เลย ต้องมี htf_trend) ✅
2. [x] grid search 72 combos (90 วัน) — ceiling sharpe=0.196 ✅
3. [x] robustness check ข้าม 7 window — PF ไม่เคยตกต่ำกว่า 1.0 แต่ sharpe อ่อนกว่า leg อื่น ✅
4. [x] sanity-check trades (522 ไม้ที่ 150 วัน) — ไม่มีบั๊ก ✅
5. [x] ทดสอบ 13-way blend ข้าม 5 window เทียบ 12-way เดิม — $/mo ชนะทุก window, sharpe ผสม
       (แย่ลงเล็กน้อย 2/5, ดีขึ้น 3/5) ✅
6. [x] เขียนสรุปลงไฟล์นี้ ✅

## บทสรุปสุดท้าย — 🏆 NEW CHAMPION (13-way blend) — accept marginal (อ่อนกว่า ORB แต่ยังเพิ่มมูลค่า)

**Champion ใหม่ = รัน 13 ระบบพร้อมกันบนทุน $1000 เดียวกัน:**

ระบบ A-M เหมือนเดิม (ดู create_s46.md)

**ระบบ N (SuperTrend flip, S47 — ใหม่, marginal):** `M5, ST_ATR_PERIOD=20, ST_ATR_MULT=2.0,
SL_ATR_MULT=1.5, TP_RR=2.0, htf_trend(M15/EMA50), SESSION_FILTER=False,
circuit_breaker(trig3/cool10), risk0.5%`

**ตัวเลข robust (เฉลี่ย 5 window 60-180วัน):** $/เดือน **$6853-7547** (เทียบ 12-way เดิม
$6278-7192), sharpe **0.39-0.57** (ดีขึ้น 3/5 window, แย่ลงเล็กน้อย <1% ใน 2/5)

เหลือ MACD entry เป็น candidate สุดท้ายจากลิสต์รอบ 2

จบ S47 — standalone research/backtest-only 100%, ไม่ wire เข้า live, ไม่แก้ S1-S46 หรือไฟล์ระบบหลัก
