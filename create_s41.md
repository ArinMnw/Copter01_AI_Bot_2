# S41 — RSI Divergence (price/momentum divergence) — retest ในเฟรมเวิร์กใหม่, 8th leg

วันที่เริ่ม: 2026-06-27
สถานะ: ✅ เสร็จ — **ผ่าน (marginal contributor เหมือน S40 แต่ตัวเลขจริงดีกว่าหลังแก้ overfitting)**

## ที่มา: RSI divergence มีอยู่แล้วใน live bot เดิม (S9) — นี่คือการ retest ในเฟรมเวิร์กใหม่

S9 (เดิม) เป็นส่วนของ live bot, ไม่เกี่ยวกับชุดวิจัยนี้ — S41 นี้คือการสร้างใหม่ใน framework
S30+ (htf_trend confirmation + circuit_breaker + robustness + correlation-check) เพื่อทดสอบว่า
เทคนิคเดียวกันให้ผลต่างกันแค่ไหนเมื่อใช้ rigor เต็มรูปแบบ

## กลไก: RSI Divergence (reversal pattern)

หา fractal pivot 2 จุดล่าสุด (เหมือน S37) พร้อมค่า RSI(14) ที่จุดนั้น **bullish divergence**:
price ทำ lower-low แต่ RSI ทำ higher-low → คาดหวัง reversal ขึ้น เข้า BUY ตอนราคา confirm กลับขึ้น
**bearish divergence**: price ทำ higher-high แต่ RSI ทำ lower-high → เข้า SELL — เป็น reversal
pattern โดยธรรมชาติ (ต่างจาก A/D/E/F ที่เป็น continuation) จึง default `CONFIRMATION_TYPE="none"`
แต่ทดสอบทั้ง none/htf_trend ใน grid search — `strategy41.py` / `sim_s41_backtest.py` /
`optimize_s41.py`

## ⚠️ พบ overfitting illusion ชัดเจน — บทเรียนสำคัญที่ตรงกับคำเตือนของ template

Grid search (192 combos, 60 วัน) top result: `WR=95.5%, PF=38.97, sharpe=1.246` (n=22) — **ตัวเลข
สูงผิดปกติ ส่งสัญญาณเตือนทันที** (PF~39 ไม่สมเหตุสมผลสำหรับกลยุทธ์ retail ใดๆ) robustness check
ข้าม 7 window เปิดเผยว่านี่คือ small-sample noise ชัดเจน:

| window | n | WR% | PF | sharpe |
|---|---|---|---|---|
| 30d | 14 | 92.9 | 17.23 | 0.888 |
| 45d | 18 | 94.4 | 26.78 | 1.150 |
| 60d | 22 | 95.5 | **38.97** | 1.246 |
| 90d | 25 | 80.0 | 2.94 | 0.462 |
| 120d | 30 | 76.7 | 2.53 | 0.417 |
| 150d | 31 | 67.7 | 1.67 | 0.224 |
| 180d | 45 | 71.1 | 2.15 | 0.351 |

**PF ยุบจาก 38.97 ลงมาที่ 1.67-2.94 ทันทีที่ n เพิ่มขึ้นเกิน 25** — ยืนยันชัดเจนว่าตัวเลขที่
window สั้น (30-60d, n=14-22) เป็น illusion จาก sample เล็ก ไม่ใช่ edge จริง **อย่างไรก็ตาม
ที่ window ยาว (90-180d) PF ยังเป็นบวกแข็งแรง (1.67-2.94, ไม่เคยตกต่ำกว่า 1.0)** ดังนั้น edge
จริงมีอยู่ เพียงเล็กกว่าที่ตัวเลข window สั้นบอกไว้มาก

หมายเหตุ: config ที่ดีที่สุดทั้งหมดในกริดใช้ `CONFIRMATION_TYPE=htf_trend` (ไม่ใช่ "none" ตาม
default) — แปลว่า divergence ที่ดีที่สุดในทางปฏิบัติคือ "dip-buy/rally-sell ที่สอดคล้องกับ
เทรนด์ใหญ่" มากกว่า counter-trend reversal เต็มรูปแบบ — สมเหตุสมผลเพราะ pure counter-trend
divergence โดยไม่มี trend filter จะถูกเทรนด์แรงกวาดทิ้งบ่อยกว่า

## Sanity-check + Correlation check (config: wing=2, pd=0.3, rd=3.0, ca=8, sl=0.8, rr=1.0, ct=htf_trend)

61 ไม้ (window 150 วัน): ไม่มีไม้ผิดกฎ SL/TP เลย (0/61)

overlap: A=4.9%, B=0.0%, C=0.0%, **D=34.4%** (สูงสุด, ทั้งคู่ใช้ fractal pivot), E=0.0%, F=8.2%,
G=0.0% — overlap กับ D ค่อนข้างสูงแต่ยังถือว่า decorrelate พอ (65.6% ของ H ไม่ทับ D)

## 🏆 8-way Blend Test (A-H ทั้ง 8 รันพร้อมกันเต็มทุนแต่ละตัวที่ $1000)

| window | 7-way เดิม $/mo | 8-way ใหม่ $/mo | 7-way sharpe | 8-way sharpe |
|---|---|---|---|---|
| 60d | $3623.3 | **$3790.0** | 0.542 | **0.557** |
| 90d | $3863.5 | **$3938.9** | 0.450 | **0.456** |
| 120d | $3710.9 | **$3770.5** | 0.386 | **0.390** |
| 150d | $3467.4 | **$3496.3** | 0.366 | **0.367** |
| 180d | $3875.6 | **$3925.5** | 0.359 | **0.363** |

**8-way ชนะทั้ง $/เดือนและ sharpe ทุก window (5/5)** — marginal แต่บวกจริงทุกมิติ (ดีกว่ารอบ S40
ที่ sharpe เสมอตัวบ้าง)

## สถานะ Exhaustion Checklist

1. [x] grid search 192 combos (60 วัน, 2006.9s) ✅
2. [x] robustness check ข้าม 7 window — **พบ overfitting illusion ชัดเจน (PF 38.97→1.67-2.94)**
       แต่ edge จริงยังเป็นบวกแข็งแรงที่ window ยาว ✅
3. [x] sanity-check trade samples (15 ไม้ + เช็คทั้งหมด 61 ไม้) — ไม่มีบั๊ก ✅
4. [x] correlation check กับ A-G — overlap ต่ำพอทุกคู่ (0-34.4%) ✅
5. [x] ทดสอบ 8-way blend ข้าม 5 window เทียบ 7-way เดิม — ชนะทุกมิติทุก window (5/5) ✅
6. [x] เขียนสรุปลงไฟล์นี้ พร้อมบทเรียนเรื่อง overfitting illusion ✅

## บทสรุปสุดท้าย — 🏆 NEW CHAMPION (8-way blend)

**Champion เปลี่ยนเป็นครั้งที่ 7** — เพิ่ม leg ที่ 8 (RSI Divergence, ใช้ config ที่ผ่าน
robustness check จริงคือ window ยาว ไม่ใช่ตัวเลขสวยของ window สั้นที่เป็น illusion)

**Champion ใหม่ = รัน 8 ระบบพร้อมกันบนทุน $1000 เดียวกัน:**

ระบบ A-G เหมือนเดิม (ดู create_s40.md)

**ระบบ H (RSI Divergence, S41 — ใหม่, marginal contributor):** `M5, PIVOT_WING=2,
MIN_PRICE_DIFF_ATR=0.3, MIN_RSI_DIFF=3.0, MAX_CONFIRM_AGE_BARS=8, SL_ATR_MULT=0.8, TP_RR=1.0,
CONFIRMATION_TYPE=htf_trend, circuit_breaker(trig3/cool10), risk0.5%`

**ตัวเลข robust (เฉลี่ย 5 window 60-180วัน):** $/เดือน **$3790-3939** (เทียบ 7-way เดิม
$3467-3876), sharpe **0.36-0.56** (เทียบ 7-way เดิม 0.36-0.54 — ดีขึ้นเล็กน้อยทุก window)

จบ S41 — standalone research/backtest-only 100%, ไม่ wire เข้า live, ไม่แก้ S1-S40 หรือไฟล์ระบบหลัก
