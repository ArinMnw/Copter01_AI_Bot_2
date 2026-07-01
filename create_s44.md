# S44 — Volume Profile (POC/VAH/VAL bounce) — 10th leg, second-strongest contributor after S37

วันที่เริ่ม: 2026-06-27
สถานะ: ✅ เสร็จ — **ผ่านอย่างชัดเจน (เพิ่ม $/mo +40-45%, สูงกว่า S39/S42 ในแง่ผลกระทบ blend)**

## ที่มา: ลิสต์ใหม่จากผู้ใช้ (รอบ 2 หลัง Turtle) — แนะนำให้ลองก่อนเพราะเป็น level-based

จากลิสต์: ORB, SuperTrend, MACD entry, **Volume Profile (S44 นี้)**, Order Block — Volume Profile
ถูกเลือกก่อนเพราะเป็น level-based mechanism (สอดคล้องกับสิ่งที่พิสูจน์แล้วว่าเวิร์กกับทอง ต่างจาก
breakout/trend-following ที่ S43 พิสูจน์แล้วว่าไม่เวิร์ก)

## กลไก: Volume Profile (POC/VAH/VAL)

สร้าง volume histogram ตามระดับราคา (ใช้ `tick_volume` เหมือน S34 เพราะ XAUUSD CFD ไม่มี
real_volume) ย้อนหลัง LOOKBACK_BARS แท่ง แบ่งเป็น bucket ขนาด BUCKET_ATR_MULT x ATR หา **POC**
(bucket ที่มี volume สูงสุด) แล้วขยายออกจาก POC จนได้ **Value Area** (VAH/VAL) ที่ครอบคลุม 70%
ของ volume — เข้า BUY ที่ VAL/POC จากด้านบน, SELL ที่ VAH/POC จากด้านล่าง (high-volume node =
แนวรับ/ต้านที่แข็งแรงเพราะมีคนเทรดผ่านเยอะ) ยืนยันด้วย htf_trend — `strategy44.py` /
`sim_s44_backtest.py` / `optimize_s44.py`

## Grid search (144 combos, 60 วัน, 1293.3s)

Top config: `LOOKBACK_BARS=80, BUCKET_ATR_MULT=0.2, TOUCH_ATR_MULT=0.5, REJECT_ATR_MULT=0.15,
SL_ATR_MULT=1.0, TP_RR=1.5` → n=570, WR=57.7%, $/mo=2036.7, PF=2.15, sharpe=0.416 (60d)

## Robustness ข้าม 7 window (30-180 วัน) — แข็งแรงมาก เสถียร n สูง

| window | n | WR% | PF | DD% | sharpe | $/mo |
|---|---|---|---|---|---|---|
| 30d | 326 | 62.9 | 2.40 | 8.6 | 0.552 | $2196.0 |
| 45d | 468 | 60.7 | 2.23 | 8.2 | 0.506 | $2092.8 |
| 60d | 570 | 57.7 | 2.15 | 17.6 | 0.416 | $2036.7 |
| 90d | 783 | 52.5 | 1.83 | 20.7 | 0.339 | $1508.7 |
| 120d | 1090 | 52.8 | 1.75 | 15.1 | 0.313 | $1731.6 |
| 150d | 1340 | 51.8 | 1.73 | 14.4 | 0.291 | $1691.4 |
| 180d | 1622 | 52.8 | 1.70 | 14.0 | 0.273 | $1883.4 |

PF ไม่เคยตกต่ำกว่า 1.7 ทุก window, sharpe เป็นบวกแข็งแรงเสมอ (0.27-0.55), n สูงมาก (326-1622 —
มากกว่าทุก leg ยกเว้น D) — leg ที่แข็งแรงเป็นอันดับ 2 รองจาก D (S37) ของทั้งชุดงานวิจัย

## Sanity-check + Correlation check (window 150 วัน)

3087 ไม้: ไม่มีไม้ผิดกฎ SL/TP เลย (0/3087)

overlap: A=9.2%, B=0.2%, C=0.3%, **D=41.7%** (สูงสุด, ทั้งคู่ level-based+htf_trend), E=7.2%,
F=13.3%, G=0.1%, H=1.0%, I=5.8% — overlap กับ D สูงแต่ยังมี 58.3% unique

## 🏆 10-way Blend Test (A-I+K ทั้ง 10 รันพร้อมกันเต็มทุนแต่ละตัวที่ $1000) — ผลกระทบใหญ่ที่สุดตั้งแต่ S37

| window | 9-way เดิม $/mo | 10-way ใหม่ $/mo | 9-way sharpe | 10-way sharpe | 9-way streak | 10-way streak |
|---|---|---|---|---|---|---|
| 60d | $4001.4 | **$5841.9** (+46%) | 0.557 | 0.551 | 3d | 3d |
| 90d | $4089.0 | **$5639.1** (+38%) | 0.459 | **0.472** | 4d | 4d |
| 120d | $4065.8 | **$5847.4** (+44%) | 0.403 | **0.414** | 6d | **5d** |
| 150d | $3717.7 | **$5379.5** (+45%) | 0.375 | **0.386** | 7d | **5d** |
| 180d | $4135.2 | **$5940.3** (+44%) | 0.371 | **0.377** | 8d | **6d** |

**10-way ชนะ $/เดือนทุก window ขนาดใหญ่ (+38% ถึง +46%)** sharpe ชนะ 4/5 (60d เสมอตัว -1%)
**maxStreak ดีขึ้นด้วย** (ลดลงที่ 120/150/180d) — ผลกระทบใหญ่กว่า S39/S42/S38 มาก เทียบเท่าระดับ S37

## สถานะ Exhaustion Checklist

1. [x] grid search 144 combos (60 วัน, 1293.3s) ✅
2. [x] robustness check ข้าม 7 window — PF/sharpe แข็งแรงมาก เสถียร n สูง ✅
3. [x] sanity-check trade samples (15 ไม้ + เช็คทั้งหมด 3087 ไม้) — ไม่มีบั๊ก ✅
4. [x] correlation check กับ A-I — overlap สูงสุดที่ D=41.7% แต่ผ่าน (58.3% unique) ✅
5. [x] ทดสอบ 10-way blend ข้าม 5 window เทียบ 9-way เดิม — ชนะ $/mo มาก (+38-46%), sharpe ชนะ 4/5,
       maxStreak ดีขึ้น ✅
6. [x] เขียนสรุปลงไฟล์นี้ ✅

## บทสรุปสุดท้าย — 🏆 NEW CHAMPION (10-way blend) — leg ที่แข็งแรงที่สุดตั้งแต่ S37

**Champion เปลี่ยนเป็นครั้งที่ 9** — Volume Profile เป็น contributor ที่แข็งแรงเป็นอันดับ 2 ของ
ทั้งชุดงานวิจัย (รองจาก D=S37 เท่านั้น) ผลกระทบใหญ่กว่า S39/S40/S41/S42 มาก

**Champion ใหม่ = รัน 10 ระบบพร้อมกันบนทุน $1000 เดียวกัน:**

ระบบ A-I เหมือนเดิม (ดู create_s42.md)

**ระบบ K (Volume Profile, S44 — ใหม่, contributor แข็งแรงอันดับ 2):** `M5, LOOKBACK_BARS=80,
BUCKET_ATR_MULT=0.2, TOUCH_ATR_MULT=0.5, REJECT_ATR_MULT=0.15, SL_ATR_MULT=1.0, TP_RR=1.5,
htf_trend(M15/EMA50), circuit_breaker(trig3/cool10), risk0.5%`

**ตัวเลข robust (เฉลี่ย 5 window 60-180วัน):** $/เดือน **$5379-5941** (เทียบ 9-way เดิม
$3718-4135 — เพิ่มขึ้นมาก), sharpe **0.38-0.55** (ดีขึ้นเล็กน้อยส่วนใหญ่)

บทเรียนเพิ่ม: high-volume-node levels (volume profile) มีพลังมากกว่า price-only levels (fractal
pivot S37) ในบางมิติ — น่าจะเพราะ volume สะท้อน "ความเชื่อ" ของตลาดที่ระดับนั้นได้ดีกว่าราคาล้วน
ยังเหลือ Order Block, ORB, SuperTrend, MACD เป็น candidate ต่อไป

จบ S44 — standalone research/backtest-only 100%, ไม่ wire เข้า live, ไม่แก้ S1-S43 หรือไฟล์ระบบหลัก
