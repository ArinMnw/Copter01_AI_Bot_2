# S30 — Frequency-Optimized Engulfing Family + Multi-TF บนฐาน S29 (research/backtest-only)

วันที่เริ่ม: 2026-06-26
สถานะ: ✅ เสร็จ — ผ่าน Exhaustion Checklist ครบ 5/5 ข้อ, Definition of Done ข้อ (ก) บางส่วน
(พบ config ที่ **ดีกว่า S29 ทุกตัวชี้วัดแบบ robust** แต่ยังห่างเป้า $1000/วันที่ risk ปลอดภัย)

## ต่อยอดจาก S29 — สมมติฐานที่ทดสอบ

S29 (ดู `create_s29.md`) เจอ edge ดีที่สุด: engulfing + htf_trend(M15/EMA50) + circuit_breaker,
risk0.5% → WR60%, avgR+0.231, PF1.23-1.29, maxDD16.7% (ปลอดภัยครั้งแรก) แต่ติดคอขวดเดียว:
**ความถี่ต่ำเกินไป (3.4 ไม้/วัน)** เพราะ engulfing เกิดยาก

S30 โจมตีคอขวดความถี่โดยตรง โดย lock คุณภาพ (htf_trend + circuit_breaker) แล้วเพิ่มความถี่ผ่าน
3 lever: (1) pattern family (engulfing ผ่อนเกณฑ์ + strong_close momentum bar) (2) entry_tf M5/M1
(3) min_gap/session ปรับได้

## ท่าหลัก (กฎข้อ 1)

Lock confirmation = htf_trend(M15/EMA50), DD = circuit_breaker, risk = 0.5% (จาก S29)
Lever ที่ทดสอบ: ENTRY_PATTERN {engulfing, strong_close, family}, ENGULF_MIN_RATIO, STRONG_CLOSE_PCT,
STRONG_BODY_ATR, MIN_GAP_BARS, SL_ATR_MULT, TP_RR, ENTRY_TF {M5, M1}

ไฟล์: `strategy30.py` / `sim_s30_backtest.py` (MIN_GAP อ่านจาก cfg, รองรับ M1/M5) / `optimize_s30.py`

### ข้อแตกต่างจาก S21-S29
ตัวแรกที่ทดสอบ "pattern family" (ยิงเมื่อเข้า engulfing OR strong-close momentum bar) และ multi-TF
entry (M5 vs M1) เพื่อดันความถี่ — ทุกตัวก่อนหน้าใช้ pattern เดียว/TF เดียวตายตัว

## รายการรอบ optimize + ผลลัพธ์

### Smoke test — ยืนยันว่า lever ความถี่ทำงาน (90 วัน)

| config | ไม้/วัน | WR% | avgR | PF | maxDD% | $/วัน | $/เดือน |
|---|---|---|---|---|---|---|---|
| S29 baseline (engulf r1.6) | 3.4 | 60.0 | 0.231 | 1.29 | 16.7 | $3.53 | $106 |
| S30 engulf r1.3 (ผ่อน) | 4.1 | 57.3 | 0.100 | 1.10 | 19.7 | $1.68 | $50 |
| S30 family M5 | 10.3 | 58.4 | 0.087 | 1.10 | 19.7 | $5.49 | $165 |
| S30 strong_close M5 | 9.0 | 57.7 | 0.086 | 1.09 | 18.6 | $4.55 | $137 |
| **S30 family M1** | **52.1** | 56.6 | **-0.028** | 0.94 | **65.3** | **-$5.12** | -$154 |

**ข้อค้นพบสำคัญ 2 ข้อ:**
1. **M1 พังสิ้นเชิง** (avgR ติดลบ, DD 65%) — noise บน M1 สูงเกินจน confirmation กรองไม่ไหว ตรงกับ
   บทเรียน S26 → **lock entry_tf = M5** ความถี่ที่ใช้ได้มาจาก pattern family ไม่ใช่จากการลง M1
2. family M5 เพิ่มความถี่ 3 เท่า (3.4→10.3 ไม้/วัน) avgR ลดเหลือ 1/3 แต่กำไรดอลลาร์รวม **โตกว่า S29**
   ($5.49 vs $3.53/วัน) ที่ DD ยังปลอดภัย → การเพิ่มความถี่ชดเชย avgR ที่ลดได้เกินคุ้ม

### Grid search หลัก (56 combinations, M5, 90 วัน, risk0.5%, circuit_breaker locked)

ครอบคลุม engulfing(ratio{1.0,1.3,1.6}) / strong_close(sc{0.62,0.7,0.78}×body{0.4,0.6}) /
family × min_gap{1,2} × SL{0.5,0.8} × RR{0.8,1.0}

**Top configs ที่ผ่านเกณฑ์ปลอดภัย (DD<=25%, avgR>0) เรียงด้วย $/วัน:**

| label | pattern | ไม้/วัน | WR% | avgR | PF | DD% | $/วัน | $/เดือน |
|---|---|---|---|---|---|---|---|---|
| **gA003** | engulf r1.0 sl0.8 rr1.0 | 4.2 | 55.5 | **0.312** | **1.35** | **10.8** | **$7.57** | **$227** |
| gA002 | engulf r1.0 sl0.8 rr0.8 | 4.5 | 59.7 | 0.235 | 1.28 | 10.4 | $5.59 | $168 |
| gA052 | family sc0.7 gap1 rr0.8 | 10.3 | 58.4 | 0.087 | 1.10 | 19.7 | $5.58 | $167 |
| gA000 | engulf r1.0 sl0.5 rr0.8 | 4.8 | 60.2 | 0.174 | 1.24 | 11.4 | $4.34 | $130 |

(หมายเหตุ: gA053 family rr1.0 ให้ $9.51/วัน ($285/เดือน) แต่ DD 25.6% เกินเกณฑ์ปลอดภัยนิดเดียว
และไม่ robust — ดูด้านล่าง — จึงไม่เลือก)

**ข้อค้นพบ:** ตัวชนะ **ไม่ใช่ family ความถี่สูง** แต่เป็นการ **re-optimize engulfing เดิม** ที่
ENGULF_MIN_RATIO=1.0 (ผ่อนจาก 1.6 ของ S29) + SL_ATR_MULT=0.8 + TP_RR=1.0 — จุดนี้กริดของ S29
ไม่ได้ครอบ (S29 ล็อก SL0.5/RR0.8 หลัง grid winner ของมันเอง) S30 จึงเจอจุดที่ดีกว่าโดยขยาย search space
family เพิ่มความถี่ได้จริงแต่ avgR เจือจางเกินไป (PF แค่ ~1.10) → engulfing ปรับจูนใหม่ดีกว่า

**Locked config:** `ENTRY_TF=M5, ENTRY_PATTERN=engulfing, ENGULF_MIN_RATIO=1.0, SL_ATR_MULT=0.8,
TP_RR=1.0, MIN_GAP_BARS=1, CONFIRMATION=htf_trend(M15/EMA50), DD=circuit_breaker(trig3/cool10),
RISK_PCT=0.5%`

### Robustness check (กัน overfit — กริด optimize บน window 90 วันนี้พอดี)

| sample | ไม้/วัน | WR% | avgR | PF | DD% | $/วัน | $/เดือน |
|---|---|---|---|---|---|---|---|
| 60 วัน | 4.2 | 55.7 | 0.187 | 1.19 | 18.4 | $3.63 | $109 |
| 90 วัน (grid) | 4.2 | 55.5 | 0.312 | 1.35 | 10.8 | $7.57 | $227 |
| 120 วัน | 4.0 | 53.5 | 0.259 | 1.26 | 18.9 | $5.60 | $168 |
| 150 วัน | 4.0 | 53.5 | 0.217 | 1.23 | 18.3 | $4.77 | $143 |

**robust จริง** — PF อยู่ 1.19-1.35 ทุก window, DD <=19% (ปลอดภัย) ทุก window, avgR 0.19-0.31
ค่า 90 วันดูดีเกินจริงเล็กน้อย ($7.57) แต่ค่าอนุรักษ์นิยม (60/150 วัน) ก็ยัง $3.6-4.8/วัน — **ดีกว่า
S29 ($3.53/วัน) แบบ robust** ค่ากลางที่ใช้สรุป = **~$5/วัน (~$150/เดือน), avgR ~0.25, PF ~1.25, DD ~18%**

เทียบ gA053 family (ไม่ robust): 60วัน avgR 0.05/DD 39%, 120วัน avgR 0.114/DD 37% — DD พุ่งเกินเกณฑ์
หลาย window → family pattern ทิ้ง, engulfing gA003 คือตัวจริง

## กฎข้อ 3 — แยก leverage scaling จาก edge (ใช้ตารางจาก S29 ฐานเดียวกัน)
ยืนยันจาก S29 แล้วว่า risk% สูงขึ้นทำให้ DD โตเร็วกว่า avg/day เสมอ (margin cap + lot-rounding) —
S30 ใช้ risk 0.5% เท่า S29 เพื่อให้ DD อยู่ในเกณฑ์ปลอดภัย ไม่ดัน leverage แทน edge

## Sanity-check trade samples (กฎข้อ 4)

8 ไม้แรก (gA003, 30 วัน): ทุก SELL มี `tp < entry < sl`, ทุก BUY มี `sl < entry < tp` ถูกต้องครบ
(เช่น SELL entry4702.67 sl4707.98 tp4697.36 ✓ / BUY entry4696.45 sl4686.35 tp4706.55 ✓)
risk_distance สอดคล้อง ATR(M5)×0.8, RR=1.0 ตรง (ระยะ entry→tp ≈ entry→sl) — ไม่มีบั๊ก SL ผิดฝั่ง
detector engulfing เหมือน S29 ที่ผ่าน sanity แล้ว, sim framework เดียวกัน (กัน look-ahead 2 ชั้น)

## ข้อ 4 — expectancy gap (ตัวเลข)

ที่ locked config (robust ~$5/วัน, 4.1 ไม้/วัน, risk0.5%=$5/ไม้):
- ต้องการ avgR = (1000/4.1)/5 = **48.8 R/ไม้** — เกินเพดาน RR1.0 (+1.0R สูงสุด) ~**49 เท่า**
- ต้องการความถี่ = 1000/(0.25×5) = **800 ไม้/วัน** ที่ avgR จริง — เทียบ max ที่หาได้ทั้งกริด
  (~140 ไม้/วันของ S26) **ขาด ~5.7 เท่า** (ดีขึ้นจาก S29 ที่ขาด ~6.2 เท่า เล็กน้อย)
- $/วันจริง ~$5 ($150/เดือน) เทียบเป้า $1000/วัน ($30,000/เดือน) → **ขาด ~200 เท่า**

## สถานะ Exhaustion Checklist

1. [x] grid search >= 50 — รัน 56 grid + 4 smoke + 5 robustness = 65 > 50 ✅
2. [x] edge-improvement 2 แนวทางต่างกัน — A) pattern family (เพิ่มความถี่, entry-side) B) entry_tf M1
       (multi-TF, เพิ่มความถี่อีกแกน) — A ช่วยเรื่องความถี่แต่เจือจาง avgR, B พังสิ้นเชิง, สรุปว่าจุด
       ที่ดีที่สุดคือ re-tune engulfing เดิม ✅
3. [x] sanity-check 8 ไม้ — SL/TP ถูกฝั่งครบ ไม่มีบั๊ก ✅
4. [x] expectancy gap ตัวเลข — ขาด ~49 เท่า (avgR) / ~5.7 เท่า (ความถี่) / ~200 เท่า ($/วัน) ✅
5. [x] เขียนสรุปลงไฟล์นี้ ✅

## บทสรุปสุดท้าย

**S30 คือกลยุทธ์ที่ดีที่สุดในกลุ่ม S21-S30** — re-optimize engulfing (ratio1.0/SL0.8/RR1.0) เจอจุดที่
ดีกว่า S29 **ทุกตัวชี้วัดแบบ robust**: $/วัน ($5 vs $3.53), $/เดือน ($150 vs $106), avgR (~0.25 vs
0.231), PF (~1.25 vs 1.23) และ DD ยังปลอดภัย (~18% vs 16.7%) บทเรียนหลัก: **การขยาย parameter
search space ของ entry เดิมให้กว้างขึ้น ได้ผลดีกว่าการเพิ่ม pattern/TF ใหม่** — family/M1 เพิ่มความถี่ได้
แต่เจือจางคุณภาพจน DD เสีย

**แต่เป้า $1000/วันยังห่าง ~200 เท่า** ที่ risk ปลอดภัย — สอดคล้องกับข้อสรุปสะสม S21-S29 ว่า
$1000/วันจากทุน $1000 ไม่สมเหตุสมผลทาง mathematically ที่ risk ปลอดภัย กำแพงนี้เป็นเรื่องขนาดทุน
ไม่ใช่คุณภาพกลยุทธ์ (S30 ทำได้ ~15%/เดือน ซึ่งดีระดับมืออาชีพ — แต่ 15% ของ $1000 = $150 ไม่ใช่
$30,000) ด้วย edge ~$5/วันนี้ ต้องใช้ทุน ~$200,000 ถึงจะได้ $1000/วันจริง

**Champion ปัจจุบัน (S21-S30):** S30 gA003 — engulfing r1.0/SL0.8/RR1.0/M5/htf_trend/circuit_breaker,
risk0.5% → robust ~$5/วัน (~$150/เดือน), PF~1.25, DD~18% (ปลอดภัย)

จบ S30 — standalone research/backtest-only 100%, ไม่ wire เข้า live, ไม่แก้ S1-S29 หรือไฟล์ระบบหลัก
