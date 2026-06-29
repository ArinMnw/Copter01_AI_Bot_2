# S51 — Previous Day High/Low (PDH/PDL) Bounce — 15th leg, clean accept

วันที่เริ่ม: 2026-06-28
สถานะ: ✅ accept ชัดเจน — เทคนิคที่ 3 จาก self-research รอบ 3 (หลัง S49✅, S50❌)

## ที่มา: web research รอบ 3 — PDH/PDL เป็น structural level มาตรฐานที่ traders ทุกคนจับตา

`strategy51.py` / `sim_s51_backtest.py`

## กลไก: bounce ที่ high/low ของ "เมื่อวาน" (daily OHLC, reset เที่ยงคืน BKK)

ต่างจาก S37 (fractal pivot จาก M5 intrabar) เพราะ S51 ใช้ high/low ของวันก่อนหน้าทั้งวันตรงๆ (ไม่ต้อง
หา pivot pattern) — เข้า BUY ตอนราคาแตะ PDL แล้ว reject กลับขึ้น, SELL ตอนแตะ PDH แล้ว reject กลับลง
ต่อทิศ htf_trend (continuation เหมือน S37/S44/S49)

## Grid search (48 combos, 90 วัน) — ceiling ดี กว่า S47 ชัดเจน

Top config: **TOUCH_ATR_MULT=0.5, REJECT_ATR_MULT=0.1, SL_ATR_MULT=0.8, TP_RR=1.5, htf_trend** →
n=54, WR=57.4%, PF=1.63, sharpe=0.300, $/mo=51.9 — sample ใหญ่พอเชื่อได้ (54 ไม้ใน 90 วัน) ไม่ใช่
illusion

## Robustness ข้าม 7 window — PF ไม่เคยตกต่ำกว่า 1.37 (แข็งแรงกว่า S47/S49)

| window | n | WR% | PF | DD% | sharpe | $/mo |
|---|---|---|---|---|---|---|
| 30d | 22 | 50.0 | 1.37 | 6.0 | 0.220 | $40.8 |
| 45d | 37 | 59.5 | 1.85 | 5.5 | 0.450 | $88.5 |
| 60d | 51 | 60.8 | 1.92 | 5.2 | 0.416 | $96.6 |
| 90d | 54 | 57.4 | 1.63 | 7.8 | 0.300 | $51.9 |
| 120d | 82 | 57.3 | 1.72 | 11.3 | 0.248 | $85.8 |
| 150d | 128 | 59.4 | 1.74 | 12.1 | 0.250 | $99.3 |
| 180d | 168 | 57.7 | 1.76 | 11.9 | 0.233 | $107.7 |

PF ไม่เคยตกต่ำกว่า 1.37 ทุก window (แข็งแรงกว่า S47 และใกล้เคียง S49) sharpe เป็นบวกแข็งแรงเสมอ
(0.22-0.45) ไม่มี DD-spike รุนแรงแบบ S38/S45/S49

## Sanity-check + Correlation check (window 150 วัน) — overlap ต่ำมากทุก leg

276 ไม้: ไม่มีไม้ผิดกฎ SL/TP เลย (0/276)

overlap: A=4.0%, B=0.0%, C=0.7%, D=14.5% (สูงสุด, S37), E=2.2%, F=6.2%, G=0.4%, H=0.7%, I=4.0%,
K=6.9%, L=0.4%, M=0.7%, N=1.1%, P=3.3% — **overlap ต่ำที่สุดในกลุ่ม level-based ทั้งหมด** (สูงสุดแค่
14.5% เทียบ S49 ที่ overlap กับ D สูงถึง 49.1%) เพราะ PDH/PDL คำนวณจาก daily OHLC ซึ่งต่างจาก
fractal pivot (D) หรือ volume node (K) หรือ VWAP (P) ในเชิงโครงสร้างจริง

## 🏆 15-way Blend Test — ชนะทุกมิติทุก window ไม่มีข้อเสียเลย

| window | 14-way เดิม $/mo | 15-way ใหม่ $/mo | 14-way sharpe | 15-way sharpe |
|---|---|---|---|---|
| 60d | $7438.6 | **$7535.3** (+1.3%) | 0.574 | **0.582** (+1.4%) |
| 90d | $7007.5 | **$7059.4** (+0.7%) | 0.464 | **0.467** (+0.6%) |
| 120d | $7571.4 | **$7657.1** (+1.1%) | 0.427 | **0.429** (+0.5%) |
| 150d | $6888.1 | **$7053.9** (+2.4%) | 0.399 | **0.404** (+1.3%) |
| 180d | $7484.3 | **$7591.9** (+1.4%) | 0.401 | **0.403** (+0.5%) |

**$/mo ชนะทุก window (+0.7% ถึง +2.4%) และ sharpe ชนะทุก window ด้วย (+0.5% ถึง +1.4%) — ไม่มี
window ใดแย่ลงเลย** clean accept เหมือน S49 — overlap ต่ำกว่ามากทำให้ contribution สม่ำเสมอกว่า

## สถานะ Exhaustion Checklist

1. [x] smoke test (60 วัน) — n=17, PF=1.09 (อ่อน แต่ขยาย sample แล้วดีขึ้น) ✅
2. [x] grid search 48 combos (90 วัน) — ceiling sharpe=0.300 ✅
3. [x] robustness check ข้าม 7 window — PF ไม่เคยตกต่ำกว่า 1.37 ✅
4. [x] sanity-check trades (276 ไม้ที่ 150 วัน) — ไม่มีบั๊ก ✅
5. [x] correlation check กับ A-P — overlap ต่ำที่สุดในกลุ่ม level-based (สูงสุด 14.5%) ✅
6. [x] ทดสอบ 15-way blend ข้าม 5 window เทียบ 14-way เดิม — ชนะทุกมิติทุก window ✅
7. [x] เขียนสรุปลงไฟล์นี้ ✅

## บทสรุปสุดท้าย — 🏆 NEW CHAMPION (15-way blend, A-N + P + Q) — accept ชัดเจน

**Champion ใหม่ = รัน 15 ระบบพร้อมกันบนทุน $1000 เดียวกัน** (A-N + P เหมือนเดิมจาก create_s49.md):

**ระบบ Q (PDH/PDL Bounce, S51 — ใหม่):** `M5, TOUCH_ATR_MULT=0.5, REJECT_ATR_MULT=0.1,
SL_ATR_MULT=0.8, TP_RR=1.5, htf_trend(M15/EMA50), circuit_breaker(trig3/cool10), risk0.5%`

**ตัวเลข robust (เฉลี่ย 5 window 60-180วัน):** $/เดือน **$7053-7657** (เทียบ 14-way เดิม
$6888-7571), sharpe **0.40-0.58** (ดีขึ้นทุก window)

**ครบทุก candidate จาก self-research รอบ 3 แล้ว** (VWAP✅, Judas Swing❌, PDH/PDL✅) — round 3
สรุปผล: 2 จาก 3 candidate ผ่าน (66%) เทียบ round 2 ที่ 3 จาก 5 ผ่าน (60%) — อัตราผ่านใกล้เคียงกัน
แปลว่ายังมี "ของจริง" เหลืออยู่นอกลิสต์เดิมถ้าค้นด้วยหลักการที่ถูกต้อง (level-based +
session-anchored มักชนะ)

จบ S51 — standalone research/backtest-only 100%, ไม่ wire เข้า live, ไม่แก้ S1-S50 หรือไฟล์ระบบหลัก
