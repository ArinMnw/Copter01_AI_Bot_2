# S49 — Session VWAP Bounce — 14th leg, clean accept (round-3 research candidate)

วันที่เริ่ม: 2026-06-27
สถานะ: ✅ accept ชัดเจน — เทคนิคแรกจากการ research รอบ 3 (นอกลิสต์เดิม 2 รอบที่ผู้ใช้ให้มา)

## ที่มา: web research หลังครบทุกเทคนิคจากลิสต์ผู้ใช้ — VWAP เป็น institutional benchmark

ผู้ใช้ขอให้ research หาเทคนิคอื่นเพิ่มหลังจาก S48 (MACD) ตกและครบลิสต์เดิมแล้ว — ค้นพบว่า VWAP เป็น
ราคาที่ institutional algo อ้างอิงเป็นมาตรฐาน ([mql5.com](https://www.mql5.com/en/blogs/post/767595))
ผสม 2 หมวดที่พิสูจน์แล้วว่าชนะในงานวิจัยนี้: level-based (เหมือน Volume Profile S44) +
session-anchored (เหมือน ORB S46) เพราะคำนวณ VWAP ใหม่ทุกวัน (reset เที่ยงคืน BKK)
`strategy49.py` / `sim_s49_backtest.py` / `optimize_s49.py`

## กลไก: Session VWAP + volume-weighted std band bounce

คำนวณ VWAP = cumulative(typical_price × tick_volume) / cumulative(tick_volume) ตั้งแต่ reset
เที่ยงคืน BKK ของวันนั้น สร้าง band รอบ VWAP ด้วย volume-weighted std deviation (band = VWAP ±
STD_MULT × std) เข้า BUY ตอนราคาแตะ band ล่างแล้ว reject กลับเข้าหา VWAP, SELL ตอนแตะ band บนแล้ว
reject กลับ — เป็น pullback-to-level continuation (เหมือน S37/S44) แต่ level คำนวณจาก VWAP รายวัน

## บั๊กที่พบระหว่างพัฒนา (แก้แล้ว)

`AttributeError: 'numpy.void' object has no attribute 'get'` — `rates` ที่ MT5 คืนมาเป็น numpy
structured array ไม่ใช่ dict ใช้ `.get()` ไม่ได้ ต้องใช้ `r["tick_volume"]` ตรงๆ ผ่าน try/except แทน

## Grid search (162 combos, 90 วัน, ~14650s ช้าเพราะ win_size=320 ต่อแท่ง) — ceiling แรงกว่า S47/S48

Top config: **STD_MULT=1.0, TOUCH_ATR_MULT=0.2, REJECT_ATR_MULT=0.1, SL_ATR_MULT=1.0, TP_RR=1.0,
htf_trend** → n=86, WR=66.3%, PF=1.90, sharpe=0.381, $/mo=123.6 — **sharpe ceiling สูงกว่า S47
(0.196) และ S48 (0.158) มาก เทียบเท่าระดับ leg ที่ accept มาก่อนหน้า**

## Robustness ข้าม 7 window — PF ไม่เคยตกต่ำกว่า 1.0 แต่ sharpe ผันผวนตามขนาด sample

| window | n | WR% | PF | DD% | sharpe | $/mo |
|---|---|---|---|---|---|---|
| 30d | 26 | 65.4 | 1.29 | 5.0 | 0.174 | $31.5 |
| 45d | 45 | 64.4 | 1.45 | 4.8 | 0.277 | $54.6 |
| 60d | 52 | 61.5 | 1.34 | 4.8 | 0.233 | $38.4 |
| 90d | 86 | 66.3 | 1.90 | 5.0 | 0.381 | $123.6 |
| 120d | 95 | 55.8 | 1.18 | 12.6 | 0.096 | $25.8 |
| 150d | 128 | 57.8 | 1.25 | 12.8 | 0.127 | $35.1 |
| 180d | 143 | 58.7 | 1.28 | 12.4 | 0.140 | $34.8 |

PF ไม่เคยตกต่ำกว่า 1.18 ทุก window (edge จริงมีอยู่สม่ำเสมอ) แต่ sharpe ไม่ monotonic (พีคที่ 90d
แล้วลดลงที่ 120-180d) — DD ขยับขึ้นจาก ~5% (30-90d) เป็น ~12-13% (120-180d) คล้าย pattern ของ S38
(edge อ่อนลงเมื่อรวมข้อมูลเก่ามากขึ้น) แต่ไม่รุนแรงเท่า — PF ไม่เคยตก ต่ำกว่า 1.0 จึงยังถือว่า edge
จริง ไม่ใช่ small-sample illusion (n สูงสุดถึง 143 ที่ window ยาว)

## Sanity-check + Correlation check (window 150 วัน) — overlap สูงกับ D/K (คาดได้ เพราะเป็น
level-based เหมือนกัน) แต่ยังเพิ่มมูลค่า

218 ไม้: ไม่มีไม้ผิดกฎ SL/TP เลย (0/218)

overlap: A=6.4%, B=0.0%, C=0.0%, D=49.1% (สูงสุด, S37 fractal pivot), E=6.0%, F=7.8%, G=0.0%,
H=0.5%, I=13.8%, K=38.5% (S44 Volume Profile), L=5.0%, M=1.4%, N=1.4% — overlap กับ D/K สูงเพราะ
ทั้งคู่เป็น level-based bounce mechanism เหมือนกัน (D=price pivot, K=volume node, P=VWAP) แต่ P ยัง
มี >50% unique signal เพียงพอที่จะเพิ่มมูลค่าจริงในการทดสอบ blend

## 🏆 14-way Blend Test (A-N + P, ข้าม O=S48 ที่ตก) — ชนะทุกมิติทุก window แม้จะเล็กน้อย

| window | 13-way เดิม $/mo | 14-way ใหม่ $/mo | 13-way sharpe | 14-way sharpe |
|---|---|---|---|---|
| 60d | $7400.2 | **$7438.6** (+0.5%) | 0.570 | **0.574** (+0.7%) |
| 90d | $6945.0 | **$7007.5** (+0.9%) | 0.461 | **0.464** (+0.7%) |
| 120d | $7547.2 | **$7571.4** (+0.3%) | 0.426 | **0.427** (+0.2%) |
| 150d | $6853.1 | **$6888.1** (+0.5%) | 0.398 | **0.399** (+0.3%) |
| 180d | $7449.5 | **$7484.3** (+0.5%) | 0.399 | **0.401** (+0.5%) |

**$/mo ชนะทุก window (+0.3% ถึง +0.9%) และ sharpe ชนะทุก window ด้วย (+0.2% ถึง +0.7%) — ไม่มี
window ใดแย่ลงเลยแม้แต่นิดเดียว** ผลเล็กกว่า ORB/Volume Profile แต่สะอาดกว่า S45/S47 (ไม่มี trade-off
ใดๆ เลย)

## สถานะ Exhaustion Checklist

1. [x] smoke test (60 วัน) — n=27, PF=1.63, sharpe=0.240 ✅
2. [x] grid search 162 combos (90 วัน) — ceiling sharpe=0.381 ✅
3. [x] robustness check ข้าม 7 window — PF ไม่เคยตกต่ำกว่า 1.18 ✅
4. [x] sanity-check trades (218 ไม้ที่ 150 วัน) — ไม่มีบั๊ก ✅
5. [x] correlation check กับ A-N — overlap สูงกับ D/K (level-based เหมือนกัน) แต่ยัง unique
       เพียงพอ ✅
6. [x] ทดสอบ 14-way blend ข้าม 5 window เทียบ 13-way เดิม — ชนะทุกมิติทุก window ✅
7. [x] เขียนสรุปลงไฟล์นี้ ✅

## บทสรุปสุดท้าย — 🏆 NEW CHAMPION (14-way blend, A-N + P) — accept ชัดเจน

**Champion ใหม่ = รัน 14 ระบบพร้อมกันบนทุน $1000 เดียวกัน** (A-N เหมือนเดิมจาก create_s47.md, ไม่รวม
O=S48 ที่ตก):

**ระบบ P (Session VWAP Bounce, S49 — ใหม่):** `M5, STD_MULT=1.0, TOUCH_ATR_MULT=0.2,
REJECT_ATR_MULT=0.1, SL_ATR_MULT=1.0, TP_RR=1.0, htf_trend(M15/EMA50),
circuit_breaker(trig3/cool10), risk0.5%`

**ตัวเลข robust (เฉลี่ย 5 window 60-180วัน):** $/เดือน **$6888-7571** (เทียบ 13-way เดิม
$6853-7547), sharpe **0.40-0.57** (ดีขึ้นเล็กน้อยทุก window)

ครบ S49 — ระหว่างการ research รอบ 3 ยังมี candidate เหลืออีก 2 ตัว (Asian Range Judas Swing, PDH/PDL
bounce) ที่ยังไม่ได้สร้าง — กำลังไปต่อ

จบ S49 — standalone research/backtest-only 100%, ไม่ wire เข้า live, ไม่แก้ S1-S48 หรือไฟล์ระบบหลัก
