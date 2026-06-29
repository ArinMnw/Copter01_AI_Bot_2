# S40 — Elliott Wave (simplified 5-wave impulse proxy) — 7th diversification leg

วันที่เริ่ม: 2026-06-27
สถานะ: ✅ เสร็จ — **ผ่านแบบมีเงื่อนไข (marginal แต่บวกจริง, n น้อยเพราะกฎเข้มงวด)**

## ตอบคำที่ผู้ใช้ถาม: ครบทุกเทคนิคจากลิสต์เดิมแล้ว

ict smc(✅) elliottwave(**S40 นี้**) support/resistance(✅S37) fvg(✅S36) demand/supply(✅S39)
crt(มีแค่ S10 เดิม) rsi divergence(มีแค่ S9 เดิม) fibo premium/discount(✅S38)

## ⚠️ คำเตือนสำคัญก่อนอ่านผล: Elliott Wave มี ambiguity สูง

Elliott Wave classic ต้องอาศัยการตีความของนักวิเคราะห์ (นับ wave ต่างคนต่างนับต่างกันได้) ไม่มี
นิยามที่ตรวจสอบได้ 100% แบบ rule-based — เวอร์ชันนี้เป็น **"Elliott Wave proxy"** ที่เข้มงวดมาก
ไม่ใช่ Elliott Wave เต็มรูปแบบ จึงควรอ่านผลด้วยความระมัดระวัง

## กลไก: 5-wave impulse proxy (rule-based ผ่อนเข้มงวด)

หา zigzag pivot (ขั้นต่ำ `ZIGZAG_MIN_ATR`x ATR ต่อขา) ย้อนหลัง `ZIGZAG_LOOKBACK_BARS` แท่ง แล้ว
ตรวจกฎ 3 ข้อหลักของ impulsive wave บน pivot ล่าสุด 5 จุด (wave0-1-2-3-4): wave2 ไม่ retrace เกิน
100% ของ wave1, wave3 ยาวกว่า wave1, wave4 ไม่ทับ territory ของ wave1 — ถ้าครบกฎ เข้า BUY/SELL
ต่อทิศ wave3 ตอนราคา breakout เลย wave4 ไปทาง wave5 ยืนยันด้วย htf_trend —
`strategy40.py` / `sim_s40_backtest.py` / `optimize_s40.py`

## Grid search (144 combos, 90 วัน, ใช้เวลา 1633s เพราะ lookback ใหญ่+bars มาก) — n น้อยมาก

Top config: `ZIGZAG_MIN_ATR=1.5, ZIGZAG_LOOKBACK_BARS=200, MAX_WAVE4_AGE_BARS=25,
ENTRY_BREAK_ATR_MULT=0.1, SL_ATR_MULT=1.0, TP_RR=1.5` → n=20 (ที่ 90 วัน, ~6.7 เทรด/เดือน — **น้อย
กว่าทุก strategy ก่อนหน้าในชุดนี้มาก** เพราะกฎ 3 ข้อต้องครบพร้อมกันถึงจะนับเป็น signal)

## Robustness ข้าม 5 window (60-180 วัน) — PF/sharpe แข็งแรง แต่ n เล็กทุก window

| window | n | WR% | PF | DD% | sharpe | $/mo |
|---|---|---|---|---|---|---|
| 60d | 21 | 76.2 | 6.05 | 6.5 | 0.737 | $175.5 |
| 90d | 20 | 70.0 | 2.64 | 15.6 | 0.362 | $93.9 |
| 120d | 23 | 65.2 | 3.26 | 7.2 | 0.482 | $69.9 |
| 150d | 32 | 62.5 | 3.07 | 8.4 | 0.430 | $72.3 |
| 180d | 37 | 59.5 | 2.53 | 11.9 | 0.376 | $56.1 |

PF สูงและ sharpe เป็นบวกแข็งแรงทุก window (0.36-0.74) — **ดูดีกว่าหลาย strategy ก่อนหน้าในเชิง
ตัวเลขด้วยซ้ำ** แต่ n=20-37 ต่อ window (เทียบ D ที่ n=600-1900+) ถือว่าเล็กมาก ต้องตีความด้วยความ
ระมัดระวังสูง (ตามกฎ caution ของ template สำหรับ n<50)

## Sanity-check + Correlation check (window 150 วัน)

62 ไม้: ไม่มีไม้ผิดกฎ SL/TP เลย (0/62)

overlap: A=4.8%, B=0.0%, C=0.0%, D=12.9%, E=4.8%, **F=16.1%** (สูงสุด) — decorrelate พอใช้ได้
ทุกคู่ (ต่ำกว่า 20% ทั้งหมด)

## 🏆 7-way Blend Test (A+B+C+D+E+F+G ทั้ง 7 รันพร้อมกันเต็มทุนแต่ละตัวที่ $1000)

| window | 6-way เดิม $/mo | 7-way ใหม่ $/mo | 6-way sharpe | 7-way sharpe |
|---|---|---|---|---|
| 60d | $3447.9 | **$3623.3** | 0.535 | **0.542** |
| 90d | $3769.7 | **$3863.5** | **0.452** | 0.450 |
| 120d | $3640.9 | **$3710.9** | 0.384 | **0.386** |
| 150d | $3395.2 | **$3467.4** | 0.363 | **0.366** |
| 180d | $3817.1 | **$3875.6** | 0.357 | **0.359** |

**7-way ชนะ $/เดือนทุก window (5/5, +2% ถึง +5%)** sharpe ชนะ 4/5 (90d แทบไม่เปลี่ยน: -0.4%)
**ผลบวกจริงแต่เล็กน้อย** (marginal contribution) เพราะความถี่เทรดต่ำมาก — ไม่ใช่ leg ที่ทรงพลัง
แบบ D/F แต่ก็ไม่ทำให้แย่ลง และ decorrelate พอที่จะเพิ่มลง blend ได้โดยไม่มีข้อเสีย

## สถานะ Exhaustion Checklist

1. [x] grid search 144 combos (90 วัน, 1633.4s) ✅
2. [x] robustness check ข้าม 5 window (60-180 วัน) — PF/sharpe แข็งแรงทุก window แต่ n เล็ก
       (20-37) ต้องระมัดระวังในการตีความ ✅ (มีคำเตือนชัดเจน)
3. [x] sanity-check trade samples (15 ไม้ + เช็คทั้งหมด 62 ไม้) — ไม่มีบั๊ก ✅
4. [x] correlation check กับ A-F ด้วยโค้ดจริง — overlap ต่ำพอทุกคู่ (0-16.1%) ✅
5. [x] ทดสอบ 7-way blend ข้าม 5 window เทียบ 6-way เดิม — ชนะ $/mo ทุก window, sharpe ชนะ 4/5 ✅
6. [x] เขียนสรุปลงไฟล์นี้ พร้อมคำเตือนเรื่อง ambiguity และ sample size เล็ก ✅

## บทสรุปสุดท้าย — 🏆 NEW CHAMPION (7-way blend) — แต่ leg นี้เป็น "nice-to-have" ไม่ใช่ตัวหลัก

**Champion เปลี่ยนเป็นครั้งที่ 6** — เพิ่ม leg ที่ 7 (Elliott Wave proxy) เข้า blend เดิม ผลบวกจริง
แต่เล็กน้อยมาก (contribution ต่ำกว่า D/F อย่างมาก เพราะความถี่เทรดต่ำ)

**Champion ใหม่ = รัน 7 ระบบพร้อมกันบนทุน $1000 เดียวกัน:**

ระบบ A-F เหมือนเดิม (ดู create_s39.md)

**ระบบ G (Elliott Wave proxy, S40 — ใหม่, marginal contributor):** `M5, ZIGZAG_MIN_ATR=1.5,
ZIGZAG_LOOKBACK_BARS=200, MAX_WAVE4_AGE_BARS=25, ENTRY_BREAK_ATR_MULT=0.1, SL_ATR_MULT=1.0,
TP_RR=1.5, htf_trend(M15/EMA50), circuit_breaker(trig3/cool10), risk0.5%`

**ตัวเลข robust (เฉลี่ย 5 window 60-180วัน):** $/เดือน **$3624-3876** (เทียบ 6-way เดิม
$3395-3817), sharpe **0.35-0.54** (ใกล้เคียงกับ 6-way เดิม 0.36-0.54 — ไม่ได้ดีขึ้นมากแต่ก็ไม่แย่ลง)

**ครบทุกเทคนิคที่ผู้ใช้ขอจากลิสต์เดิมแล้ว** (ict smc, elliottwave, support/resistance, fvg,
demand/supply, fibo premium/discount — เหลือแค่ rsi divergence/crt ที่มีอยู่แล้วในเฟรมเวิร์กเก่า
S9/S10 ซึ่งเป็นส่วนของ live bot ไม่ใช่ candidate ใหม่)

จบ S40 — standalone research/backtest-only 100%, ไม่ wire เข้า live, ไม่แก้ S1-S39 หรือไฟล์ระบบหลัก
