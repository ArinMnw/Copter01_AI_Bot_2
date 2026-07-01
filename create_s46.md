# S46 — Opening Range Breakout (ORB) — 12th leg, strong accept (surprised expectations)

วันที่เริ่ม: 2026-06-27
สถานะ: ✅ เสร็จอย่างชัดเจน — **น่าแปลกใจที่ ORB (เป็น breakout-type เหมือน S43 ที่ตก) กลับผ่านได้ดี**

## ที่มา: ลิสต์รอบ 2 ตัวสุดท้ายในกลุ่ม level/session-based ที่ยังไม่ทำ

จากลิสต์: ORB (S46 นี้), SuperTrend, MACD entry — เหลือ 2 ตัวหลังจบ S46

## กลไก: Opening Range Breakout (session-anchored breakout)

นิยาม "opening range" = high/low ของแท่งในช่วง OR_MINUTES นาทีแรกหลัง session เปิด (default =
London open 14:00 BKK) รอ breakout เลยขอบ range ภายใน MAX_BREAKOUT_AGE_MIN นาทีถัดมา (BUY ทะลุ
OR high, SELL ทะลุ OR low) — **ต่างจาก S43 (Turtle/Donchian) ที่ใช้ rolling N-bar window ธรรมดา
ORB ใช้ session-open เป็นจุดยึด** ซึ่งเป็นช่วงที่ volatility expansion จริงเกิดขึ้นเป็นประจำ
(สถาบันเริ่มเทรดพร้อมกัน) — `strategy46.py` / `sim_s46_backtest.py` / `optimize_s46.py`

## บั๊กที่พบระหว่างพัฒนา (แก้แล้ว)

`TypeError: can't compare offset-naive and offset-aware datetimes` — `config.mt5_ts_to_bkk()` คืน
datetime แบบ tz-aware แต่ `datetime.combine(today, dtime(sh,sm))` สร้าง naive datetime — แก้โดย
ส่ง `tzinfo=dt_bkk.tzinfo` เข้า `datetime.combine()`

## Grid search (96 combos, 60 วัน, 722.8s) — London open (14:00) ชนะ NY open (19:30) ทุกอันดับ

Top 15 ทั้งหมดใช้ `OR_SESSION_START=14:00` (London) ไม่มี NY open (19:30) ติดเลย — London open มี
volatility expansion ที่ชัดเจนกว่าสำหรับ XAUUSD (สอดคล้องกับที่ London เป็นช่วงเทรดทองที่หนาแน่นกว่า)

Top config: `OR_SESSION_START=14:00, OR_MINUTES=30, MAX_BREAKOUT_AGE_MIN=90, MIN_BREAK_ATR=0.1,
SL_ATR_MULT=0.8, TP_RR=1.5` → n=111, WR=71.2%, PF=3.73, sharpe=0.484, DD=14.5% (60d)

## Robustness ข้าม 7 window (30-180 วัน) — แข็งแรงมาก ไม่พังเหมือน S43

| window | n | WR% | PF | DD% | sharpe | $/mo |
|---|---|---|---|---|---|---|
| 30d | 55 | 65.5 | 2.90 | 7.3 | 0.388 | $698.1 |
| 45d | 105 | 75.2 | 4.77 | 6.1 | 0.580 | $1316.1 |
| 60d | 111 | 71.2 | 3.73 | 14.5 | 0.484 | $914.7 |
| 90d | 141 | 65.2 | 2.88 | 30.8 | 0.364 | $715.2 |
| 120d | 181 | 60.2 | 3.02 | 19.4 | 0.350 | $808.8 |
| 150d | 235 | 62.1 | 3.21 | 14.8 | 0.367 | $823.8 |
| 180d | 257 | 58.4 | 2.84 | 16.8 | 0.322 | $668.4 |

PF ไม่เคยตกต่ำกว่า 2.84 ทุก window (สูงกว่าทุก leg อื่นในชุดงานวิจัยนี้!) sharpe เป็นบวกแข็งแรง
เสมอ (0.32-0.58) maxStreak ขยับเป็น 9 วันที่ window ยาว (150-180d) แต่ PF/sharpe ยังแข็งแรง —
**ทำไม ORB ผ่านแต่ Turtle/Donchian (S43) ตก?** เพราะ session-open เป็นจุดที่ volatility expansion
จริงเกิดขึ้นสม่ำเสมอ (catalysts ข่าว/สถาบันเริ่มเทรด) ในขณะที่ rolling-window breakout (S43) ไม่มี
catalyst ที่แน่นอน ถูก mean-reversion ของทองในเฟรมเล็กกวาดทิ้งบ่อย — บทเรียน: breakout ใช้ได้ถ้ามี
"เหตุผลเชิงโครงสร้าง" รองรับ (session open, volume confirm) ไม่ใช่แค่ price level ทะลุ

## Sanity-check + Correlation check (window 150 วัน) — decorrelate ดีที่สุดในกลุ่ม level-based ใหม่

495 ไม้: ไม่มีไม้ผิดกฎ SL/TP เลย (0/495)

overlap: A=6.7%, B=0.0%, C=1.6%, D=9.9%, E=0.4%, F=13.9% (สูงสุด), G=0.0%, H=0.0%, I=0.6%, K=9.1%,
L=3.6% — **overlap ต่ำกว่า S44/S45/S42 มาก** (สูงสุดแค่ 13.9% เทียบ 41-49% ของ leg อื่น) เพราะ
session-anchored timing ทำให้ signal กระจุกตัวเฉพาะช่วง 14:00-15:30 BKK ต่างจาก leg อื่นที่ยิงได้
ทั้งวัน

## 🏆 12-way Blend Test — ชนะชัดเจนทุกมิติทุก window

| window | 11-way เดิม $/mo | 12-way ใหม่ $/mo | 11-way sharpe | 12-way sharpe |
|---|---|---|---|---|
| 60d | $6223.8 | **$7191.7** (+15.6%) | 0.567 | **0.576** |
| 90d | $5842.0 | **$6601.5** (+13.0%) | 0.463 | 0.463 (เท่ากัน) |
| 120d | $5941.9 | **$6840.6** (+15.1%) | 0.407 | **0.410** |
| 150d | $5454.2 | **$6278.0** (+15.1%) | 0.380 | **0.386** |
| 180d | $6166.7 | **$6841.6** (+10.9%) | 0.380 | **0.384** |

**12-way ชนะ $/เดือนทุก window มาก (+10.9% ถึง +15.6%) sharpe ชนะ/เสมอทุก window (4 ชนะ + 1 เสมอ)
— ไม่มี window ใดแย่ลงเลย** ผ่านชัดเจนกว่า S45 (Order Block) มาก

## สถานะ Exhaustion Checklist

1. [x] grid search 96 combos (60 วัน, 722.8s) ✅
2. [x] robustness check ข้าม 7 window — PF สูงสุดในชุดงานวิจัย (2.84-4.77) ไม่มี window พัง ✅
3. [x] sanity-check trade samples (15 ไม้ + เช็คทั้งหมด 495 ไม้) — ไม่มีบั๊ก (แก้ timezone bug
       ไปแล้วก่อนหน้า) ✅
4. [x] correlation check กับ A-L — overlap ต่ำที่สุดในกลุ่ม level-based ใหม่ (สูงสุด 13.9%) ✅
5. [x] ทดสอบ 12-way blend ข้าม 5 window เทียบ 11-way เดิม — ชนะทุกมิติทุก window (ไม่มีแย่ลงเลย) ✅
6. [x] เขียนสรุปลงไฟล์นี้ ✅

## บทสรุปสุดท้าย — 🏆 NEW CHAMPION (12-way blend) — accept ชัดเจนกว่า S45

**Champion เปลี่ยนเป็นครั้งที่ 11** — ORB เป็น contributor ที่แข็งแรงชัดเจน (ไม่ใช่ marginal/mixed
แบบ S40/S41/S45)

**Champion ใหม่ = รัน 12 ระบบพร้อมกันบนทุน $1000 เดียวกัน:**

ระบบ A-L เหมือนเดิม (ดู create_s45.md)

**ระบบ M (Opening Range Breakout, S46 — ใหม่):** `M5, OR_SESSION_START=14:00, OR_MINUTES=30,
MAX_BREAKOUT_AGE_MIN=90, MIN_BREAK_ATR=0.1, SL_ATR_MULT=0.8, TP_RR=1.5, htf_trend(M15/EMA50),
circuit_breaker(trig3/cool10), risk0.5%`

**ตัวเลข robust (เฉลี่ย 5 window 60-180วัน):** $/เดือน **$6278-7192** (เทียบ 11-way เดิม
$5454-6224), sharpe **0.38-0.58** (ดีขึ้นหรือเท่าเดิมทุก window)

เหลือ SuperTrend, MACD entry เป็น candidate สุดท้ายจากลิสต์รอบ 2

จบ S46 — standalone research/backtest-only 100%, ไม่ wire เข้า live, ไม่แก้ S1-S45 หรือไฟล์ระบบหลัก
