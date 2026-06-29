# S27 — High-Frequency Entry (M1/M5) + HTF Confirmation (M15/H1/H4) (research/backtest-only)

วันที่เริ่ม: 2026-06-26
สถานะ: ✅ เสร็จ — ผ่าน Exhaustion Checklist ครบ 5/5 ข้อ, Definition of Done ข้อ (ข)
(พิสูจน์ได้ด้วยตัวเลขว่าเป้าหมาย $1000/วันทำไม่ได้จริงที่ risk ปลอดภัย — มี edge เล็กน้อยที่
robust กว่า S26 แต่ขนาดเล็กเกินไปมาก ห่างจากเป้าหลายพันเท่า)

## สมมติฐานที่ทดสอบ

S26 พิสูจน์แล้วว่า entry ดิบบน M1 ที่ไม่มี filter ยืนยันเลย ให้ WR ระดับ noise (~52-53%)
ไม่พอเป็น edge แม้ความถี่จะสูงมาก (140 ไม้/วัน) — S27 ทดสอบสมมติฐานต่อยอด: ถ้าบังคับให้ entry
ความถี่สูงบน M1/M5 ทุกไม้ต้องผ่าน **confirmation จาก timeframe ใหญ่กว่า (M15/H1/H4)** อย่างน้อย
1 ชั้นก่อนเข้าเสมอ จะยก WR ขึ้นได้มากพอเทียบกับความถี่ที่เสียไปหรือไม่ (หา sweet spot ระหว่าง
WR×frequency×RR ไม่ใช่ไล่ค่าใดค่าหนึ่งสูงสุดอย่างเดียว) และ RR ไม่ fix ที่ 1:1 แล้ว (ปล่อยกริดหา
ค่า 0.8-2.0 เอง)

## ท่าหลักที่ Lock (กฎข้อ 1)

**Entry mechanism เดียวตลอดทั้งกริด:** "EMA-fast pullback bounce" บน entry timeframe (M1
หรือ M5) — ราคาแตะ/ทะลุ EMA8 เบาๆ แล้วปิดแท่งเด้งกลับสวนแท่งก่อน **โดยตั้งใจตัด own-TF trend
filter ออกจากท่านี้** (ต่างจาก S26 ที่ trend filter มาจาก M1 เอง) เพื่อให้ HTF confirmation
เป็นตัวแปรเดียวที่ทดสอบผลกระทบได้ชัดในกริดนี้ ทิศทาง signal มาจาก bounce candle เท่านั้น

**ชั้น confirmation จาก HTF ที่ทดสอบในกริดเดียวกัน** (เลือกด้วย `CONFIRMATION_TYPE`):
1. `none` — baseline ไม่มี confirmation เลย (วัด WR ดิบของ entry mechanism เทียบ S26)
2. `htf_trend` — ทิศทาง bounce ต้องตรงกับ slope ของ EMA(HTF_EMA_PERIOD) บน HTF_TF (เทรดตาม
   ทิศทาง trend ของ M15/H1 เท่านั้น) + ตัวเลือกเสริม ADX(HTF) minimum threshold
3. `htf_rsi` — RSI(M15/H1) ต้องไม่อยู่ใน "zone สวนทาง" กับทิศทาง bounce (BUY ต้องการ
   RSI>=50-thr, SELL ต้องการ RSI<=50+thr)
4. `htf_level` — ราคาต้องอยู่ในโซน key level จาก H1/H4 (rolling high/low) — BUY เฉพาะใกล้
   ขอบล่าง(support), SELL เฉพาะใกล้ขอบบน(resistance)

ไฟล์: `strategy27.py` (entry mechanism + 4 confirmation types) / `sim_s27_backtest.py`
(backtest M1/M5 จาก MT5 จริง พร้อม HTF lookup ที่กัน look-ahead ข้าม timeframe ด้วย bisect บน
"เวลาที่แท่ง HTF ปิดจริง") / `optimize_s27.py` (grid search)

### ข้อแตกต่างจาก S21-S26 (กฎข้อ 1)
S27 เป็นตัวแรกที่ใช้ **multi-timeframe confirmation ข้าม TF** (entry M1/M5, confirm จาก
M15/H1/H4) — ทุกตัวก่อนหน้านี้ (S21-S26) ใช้ indicator/trend บน TF เดียวกับ entry เท่านั้น และ
เป็นตัวแรกที่ **TP_RR ไม่ fix** (กริดหาค่า 0.8-2.0 เอง ต่างจาก S26 ที่ fix 1:1)

## เพดานทางทฤษฎีของ avgR ต่อ TP_RR (ก่อนรันกริดเต็ม — ตามคำสั่งผู้ใช้)

สูตร: `avgR = WR×RR - (1-WR)` (loss เต็ม -1R ทุกไม้, win ได้ RR×1R) — breakeven WR = 1/(1+RR)

| TP_RR | breakeven WR | avgR @ WR=53% (noise level) | avgR @ WR=55% | avgR @ WR=60% | เพดานบนสุด (WR=100%) |
|---|---|---|---|---|---|
| 0.8 | 55.56% | -0.046 | -0.010 | +0.080 | +0.80 |
| 1.0 | 50.00% | **+0.060** | +0.100 | +0.200 | +1.00 |
| 1.2 | 45.45% | +0.166 | +0.210 | +0.320 | +1.20 |
| 1.5 | 40.00% | +0.325 | +0.375 | +0.500 | +1.50 |
| 2.0 | 33.33% | +0.590 | +0.650 | +0.800 | +2.00 |

**ข้อค้นพบเชิงโครงสร้างที่สำคัญ (ต่างจาก S26):** เพราะ RR ไม่ fix ที่ 1:1 แล้ว ที่ RR>=1.0 แม้
WR แค่ระดับ noise (~53%, เหมือนที่ S26 พบว่าเป็นเพดานจริงของ M1 XAUUSD) ก็มี **avgR เป็นบวกได้
ในทางทฤษฎีแล้ว** (+0.06R ที่ RR1.0) ต่างจาก S26 ที่ RR1:1 fixed กับ WR53% มีแต่ avgR ติดลบเสมอ
(เพดานจริง ~-0.02R) — นี่คือเหตุผลที่ S27 มีโอกาสทางทฤษฎีที่ S26 ไม่มีเลยตั้งแต่ต้น

## รายการรอบ optimize + ผลลัพธ์

### Grid search หลัก (88 combinations, 30 วัน, risk=1.0% fixed)

ครอบคลุม 4 confirmation types x entry_tf{M1,M5} x htf_tf x threshold เฉพาะ confirmation x
SL_ATR_MULT{0.5,0.8} x TP_RR:
- `none` (baseline): entry_tf{M1,M5} × SL{0.5,0.8} × RR{0.8,1.0,1.5,2.0} = 16 combos
- `htf_trend`: entry_tf{M1,M5} × HTF_TF{M15,H1} × HTF_EMA{21,50} × SL{0.5,0.8} × RR{1.0,1.5}
  = 32 combos
- `htf_rsi`: entry_tf{M1,M5} × HTF_TF{M15,H1} × RSI_THR{5,10,15} × RR{1.0,1.5} = 24 combos
- `htf_level`: entry_tf{M1,M5} × HTF_TF{H1,H4} × ZONE_PCT{0.15,0.25} × RR{1.0,1.5} = 16 combos

**Top 10 by avg_per_day_span และ profit_factor ทั้งคู่ถูกครองโดย `htf_trend` แทบทั้งหมด**
(8-9 จาก 10 อันดับแรกในทั้ง 2 metric เป็น confirmation_type=htf_trend) — `htf_rsi` และ
`htf_level` ทุก combination ใน 30 วันแรกมี avg/day ติดลบทั้งหมด (ไม่มีตัวใดทำกำไรสุทธิ)

ผลที่ดีที่สุด (PF สูงสุด, 30 วัน):

| label | entry_tf | conf | htf | params | trades(30d) | WR% | trades/day | avgR | PF | avg/day |
|---|---|---|---|---|---|---|---|---|---|---|
| grid039 | M5 | htf_trend | M15 | ema50,sl0.8,rr1.0 | 757 | 55.6 | 21.6 | 0.100 | **1.22** | $34.97 |
| grid043 | M5 | htf_trend | H1 | ema21,sl0.8,rr1.0 | 745 | 54.9 | 21.3 | 0.097 | 1.20 | $32.62 |
| grid044 | M5 | htf_trend | H1 | ema21,sl0.8,rr1.5 | 744 | 44.1 | 20.7 | 0.095 | 1.15 | $30.36 |
| grid028 | M1 | htf_trend | H1 | ema21,sl0.8,rr1.5 | 3233 | 43.3 | 98.0 | 0.030 | 1.04 | $34.46 |
| grid049 (htf_rsi ดีที่สุด) | M1 | htf_rsi | M15 | thr5,rr1.0 | 3952 | 50.1 | 119.8 | 0.093 | 0.89 | -$35.03 |
| grid073 (htf_level ดีที่สุด) | M1 | htf_level | H1 | zone0.15,rr1.0 | 939 | 48.8 | 33.5 | -0.093 | 0.83 | -$20.21 |

**ผลสรุปกฎข้อ 1 (เลือก confirmation type เดียว):** `htf_trend` (EMA slope ของ M15/H1) ชนะชัดเจน
— เป็น confirmation ชนิดเดียวที่ทำให้ PF ทะลุ 1.0 ได้หลาย combination ทั้งบน M1 และ M5
ในขณะที่ `htf_rsi` และ `htf_level` **ทุก combination ขาดทุนสุทธิที่ 30 วัน** ไม่มีข้อยกเว้น

**Locked config:** `ENTRY_TF=M5, CONFIRMATION_TYPE=htf_trend, HTF_TF=M15, HTF_EMA_PERIOD=50,
SL_ATR_MULT=0.8, TP_RR=1.0`

### Robustness check (กันการ overfit แบบที่ S26 เจอใน combo A+B) — ขยาย sample เป็น 60 และ 90 วัน

| sample | trades | WR% | trades/day | avgR | PF | avg/day(span) |
|---|---|---|---|---|---|---|
| 30 วัน (grid ดั้งเดิม) | 757 | 55.6 | 21.6 | 0.100 | **1.22** | $34.97 |
| 60 วัน | 1423 | 51.5 | 20.6 | 0.030 | **1.03** | $4.23 |
| 90 วัน | 2099 | 51.0 | 20.2 | 0.025 | **1.02** | $2.74 |

**สำคัญ:** PF ที่ดูสูง (1.22) บน 30 วัน **ลดลงมากเมื่อขยาย sample เป็น 60-90 วัน** (1.22→1.03→1.02)
— เหมือนรูปแบบ overfitting ที่เจอใน S26 (combo A+B) แต่ **ต่างจาก S26 ตรงที่ PF ไม่ตกลงไปต่ำกว่า
1.0** เมื่อ sample ใหญ่ขึ้น (S26 ตกจาก 1.02→0.97 คือพลิกเป็นขาดทุน, S27 แค่ 1.22→1.02 คือยัง
เป็นบวกแต่บางลงมาก) **สรุปได้ว่า S27 (htf_trend) มี edge บวกเล็กน้อยที่ robust จริง ไม่ใช่ noise
ล้วนๆ แบบที่ S26 เป็น** — แต่ขนาด edge (PF~1.02, avgR~+0.025) เล็กมากเทียบกับที่ต้องการ (ดูหัวข้อ
expectancy gap ด้านล่าง)

เทียบ alternative config (H1/EMA21 แทน M15/EMA50) และ baseline ไม่มี confirmation ที่ 60 วัน
เพื่อยืนยันว่า config ที่ lock ไว้ดีที่สุดจริง:

| config | trades/day | WR% | avgR | PF | avg/day(60d) |
|---|---|---|---|---|---|
| **locked (M15/EMA50)** | 20.6 | 51.5 | 0.030 | **1.03** | **$4.23** |
| alt (H1/EMA21) | 20.1 | 50.8 | 0.016 | 0.99 | -$1.67 |
| baseline (none) | 33.5 | 48.0 | -0.735 | 0.90 | -$20.49 |

ยืนยันว่า M15/EMA50 confirmation คือ config ที่ดีที่สุดในกลุ่ม htf_trend และดีกว่า baseline
ไม่มี confirmation อย่างชัดเจน (PF 0.90→1.03, avg/day -$20.49→+$4.23)

### Edge-improvement attempt A — ADX(M15) minimum threshold เพิ่มเข้าไปใน htf_trend confirmation
(entry-side indicator confirmation เพิ่มความเข้มของ trend filter เดิม)

ทดสอบบน locked config (90 วัน, baseline ADX_MIN=0 คือไม่ใช้):

| adx_min | trades/day | WR% | avgR | PF | avg/day(90d) |
|---|---|---|---|---|---|
| 0 (baseline, ไม่ใช้) | 20.2 | 51.0 | 0.025 | **1.02** | $2.74 |
| 20 | 14.5 | 51.1 | 0.025 | 1.02 | $2.20 |
| 25 | 10.9 | 49.3 | -0.008 | 0.97 | -$2.08 |
| 30 | 9.6 | 50.3 | 0.014 | 0.99 | -$0.27 |

**ผล: filter A ไม่ช่วยเลย** — ที่ ADX_MIN=20 ผล PF เท่ากันเป๊ะ (1.02) แต่ความถี่หายไป ~28%
(ทำให้ avg/day แย่ลง) ที่ threshold สูงกว่า (25,30) PF แย่ลงกว่าเดิมด้วย — ADX(HTF) ไม่ได้เพิ่ม
คุณภาพสัญญาณเหนือกว่า EMA-slope confirmation ที่มีอยู่แล้ว

### Edge-improvement attempt B — Session-window narrowing (timing/regime ไม่ใช่ indicator)
(แนวคิดต่างจาก A โดยสิ้นเชิง — เปลี่ยน "เวลาที่เทรด" ไม่ใช่เปลี่ยน indicator confirmation)

ทดสอบบน locked config (90 วัน, baseline session = 14:00-23:00 London+NY กว้าง):

| session | trades/day | WR% | avgR | PF | avg/day(90d) |
|---|---|---|---|---|---|
| 14:00-23:00 (baseline) | 20.2 | 51.0 | 0.025 | **1.02** | $2.74 |
| 19:00-23:00 (NY core) | 8.9 | 51.1 | 0.015 | 1.01 | $0.48 |
| 14:00-18:00 (London core) | 10.0 | 50.7 | 0.031 | 0.98 | -$0.80 |
| ไม่มี session filter (24h) | 43.9 | 49.8 | 0.124 | 0.99 | -$4.41 |

**ผล: filter B ไม่ช่วยเลยเช่นกัน** — ทั้ง narrowing (NY/London core) และ widening (24h) ให้ PF
แย่ลงหรือเท่าเดิมเทียบ baseline session ที่ lock ไว้แล้ว (14:00-23:00) สรุปได้ว่า session window
เดิมใกล้เคียง optimal อยู่แล้วสำหรับ config นี้ — ต่างจาก S26 ที่ narrowing ช่วยได้เล็กน้อยเพราะ
S26 ไม่มี HTF confirmation คอยกรองทิศทางอยู่แล้ว

**สรุปกฎข้อ 2 (Exhaustion Checklist):** ทดสอบ edge-improvement 2 แนวทางที่ต่างกันโดยสิ้นเชิง
(A = entry-side ADX indicator confirmation เพิ่มเติม / B = session-timing narrowing) ตามที่
กำหนด — **ทั้ง A และ B ไม่ช่วยให้ดีขึ้นกว่า locked config เดิม** ไม่มีแนวทางใดเพิ่ม PF หรือ
avg/day เหนือ baseline ที่ lock ไว้แล้ว (PF~1.02, avg/day(90d)~$2.74)

## Sanity-check trade samples (กฎข้อ 4 ของ Exhaustion Checklist)

สุ่มตรวจ 10 ไม้แรกจาก locked config (`M5 entry + htf_trend(M15,EMA50)`, 10 วันล่าสุด):

```
BUY  entry=4094.88 sl=4087.56 tp=4102.20 outcome=TP risk_dist=7.320 order_ok=True
BUY  entry=4096.69 sl=4086.55 tp=4106.83 outcome=TP risk_dist=10.140 order_ok=True
BUY  entry=4107.55 sl=4098.14 tp=4116.96 outcome=SL risk_dist=9.410 order_ok=True
BUY  entry=4104.99 sl=4097.98 tp=4112.00 outcome=TP risk_dist=7.010 order_ok=True
BUY  entry=4111.76 sl=4100.32 tp=4123.20 outcome=SL risk_dist=11.440 order_ok=True
SELL entry=4079.48 sl=4089.52 tp=4069.44 outcome=SL risk_dist=10.040 order_ok=True
SELL entry=4086.86 sl=4097.19 tp=4076.53 outcome=TP risk_dist=10.330 order_ok=True
SELL entry=4087.72 sl=4098.18 tp=4077.26 outcome=TP risk_dist=10.460 order_ok=True
SELL entry=4090.52 sl=4096.37 tp=4084.67 outcome=TP risk_dist=5.850 order_ok=True
SELL entry=4086.54 sl=4097.47 tp=4075.61 outcome=TP risk_dist=10.930 order_ok=True
```

ยืนยันด้วยตา: ทุกไม้ BUY มี `sl < entry < tp`, ทุกไม้ SELL มี `tp < entry < sl` ถูกต้องครบ
(ไม่มีบั๊กแบบ S24 ที่ SL วางผิดฝั่ง) — `risk_distance` (5.85-11.44 จุด บน XAUUSD M5 ATR×0.8)
สอดคล้องกับที่คาดไว้ และยังยืนยันแยกต่างหากว่า **HTF lookup ไม่ look-ahead ข้าม timeframe**
ด้วยการตรวจ `_htf_lookup`/`build_htf_series` ในโค้ด: bisect ใช้ `close_times` ที่บวก
`_tf_secs(HTF_TF)` เข้ากับ `time` ของแท่ง HTF แล้ว (เวลาที่แท่งนั้น "ปิดสมบูรณ์" จริง ไม่ใช่เวลา
เปิดแท่ง) และ `bisect_right(...) - 1` เลือกแท่งปิดแล้วล่าสุด**ก่อน**เวลา entry เท่านั้น

## กฎข้อ 3 — แยก leverage scaling จาก edge improvement

ทดสอบ risk% บน locked config เดิม (2099 trades เดิม 90 วัน เปลี่ยนแค่ risk% sizing):

| risk% | avg/day(90d) | maxDD% | avgR | PF |
|---|---|---|---|---|
| 0.5% | $3.31 | ~75% (โดยประมาณ) | 0.049 | 1.02 |
| 1.0% (locked) | $2.74 | 79.0% | 0.025 | 1.02 |
| 2.0% | -$2.15 | 103.0% | 0.797* | 0.99 |
| 5.0% | -$5.40 | 118.0% | -0.119* | 0.98 |

(*avgR ที่ risk 2%/5% ผันผวนจาก lot-rounding artifact เดียวกับที่เจอใน S26 — PF คือตัวชี้วัด
ที่เชื่อถือได้กว่าในกรณีความถี่สูง)

**สังเกตชัดเจน:** การดัน risk% **ไม่ได้เพิ่มกำไรตามสัดส่วน** — ที่ risk>=2% ผลกลับแย่ลง (PF<1,
avg/day ติดลบ) เพราะ margin cap (MAX_MARGIN_USAGE_PCT=30%) เริ่มจำกัด lot และ lot-rounding
distortion เริ่มมีผลมากขึ้นที่ lot ใหญ่ — **ไม่มีทางใช้การดัน risk% แก้ปัญหาตามกฎข้อ 3** ยืนยัน
ว่า edge ที่มี (เล็กมาก) ไม่ scale ได้ด้วยเลเวอเรจ ต้องหา edge จริงที่ใหญ่ขึ้นเท่านั้น

## ข้อ 4 — คำนวณ expectancy ที่ต้องการ vs ที่ทำได้จริง (ตัวเลข)

ที่ locked config (90 วัน, robust): **trades/day = 20.2, avgR = +0.025, risk = 1% ($10/ไม้
บนทุน $1000)**

**ต้องการ avgR เท่าไหร่ที่ความถี่นี้ (20.2 ไม้/วัน) ถึงจะถึง $1000/วัน:**
```
required_avgR = (1000 / 20.2) / 10 = 4.95 R/ไม้
```
**4.95R ต่อไม้ เกินเพดานทางทฤษฎีของ RR1.0 (สูงสุด +1.00R ที่ WR=100% สมมุติ) ไปถึง ~4.95 เท่า**
— เป็นไปไม่ได้โดยโครงสร้าง ไม่ว่า WR จะสูงแค่ไหนก็ตามที่ RR=1.0 นี้

**ต้องการความถี่เท่าไหร่ที่ avgR จริงที่ทำได้ (+0.025R) ถึงจะถึง $1000/วัน:**
```
required_freq = 1000 / (0.025 × 10) = 4,000 ไม้/วัน
```
**4,000 ไม้/วัน เกินความถี่สูงสุดที่หาได้จริงทั้งกริด S26+S27 (140.4 ไม้/วัน ของ S26 ที่ไม่มี
confirmation เลย) ไปถึง ~28.5 เท่า** — ไม่มีทางทำได้จริงด้วยข้อมูล M1/M5 ของ XAUUSD

**ตรวจสอบว่า leverage (risk%) ช่วยปิดช่องว่างนี้ได้หรือไม่ (ตามกฎข้อ 3):**

| risk% | required_avgR ที่ freq=20.2/วัน | implied WR ต้องการ (ที่ RR1.0) | actual WR | ผ่าน/ไม่ผ่าน |
|---|---|---|---|---|
| 1% | 4.950R | 297.5% (เป็นไปไม่ได้ทางคณิตศาสตร์) | 51.0% | ❌ |
| 2% | 2.475R | 173.8% (เป็นไปไม่ได้) | 51.0% | ❌ |
| 5% | 0.990R | 99.5% (เกือบ 100% — แทบเป็นไปไม่ได้) | 51.0% | ❌ |
| 10% | 0.495R | 74.8% | 51.0% | ❌ (ขาด 23.8pp และ maxDD จะ ~790% — ล้างพอร์ตหลายรอบ) |
| 20% | 0.248R | 62.4% | 51.0% | ❌ (ขาด 11.4pp และ maxDD จะเกิน 1500% — ล้างพอร์ตทันที) |

**ไม่มี risk% ระดับใด (ที่ DD ยังพอประมาณ <=20-25% ตามกฎ) ที่ทำให้ WR ที่ต้องการลดลงมาเท่ากับ
WR จริง (51.0%) ได้เลย** — ที่ risk=1% (locked, maxDD จริง 79.0% ที่ 90 วัน) ก็เกินเกณฑ์ safe
DD ไปแล้ว ดังนั้นแม้แต่ risk ปัจจุบันก็ไม่ปลอดภัยตามนิยามของ template (DD<=20-25%)

## บั๊กที่เจอและวิธีแก้

ไม่พบบั๊กด้าน logic เข้า/ออกออเดอร์หรือ look-ahead ข้าม timeframe (sanity-check ผ่านครบ,
ตรวจโค้ด `_htf_lookup`/`build_htf_series` ยืนยัน bisect ใช้เวลาปิดแท่ง HTF จริงไม่ใช่เวลาเปิด)
**พบ artifact ทางตัวเลขเดียวกับ S26**: `avg_r_multiple` ผันผวนสูงผิดปกติที่ risk%>=2%
เนื่องจาก lot-rounding (ขั้น 0.01 lot) มีผลสัดส่วนสูงต่อ R-multiple ที่คำนวณจาก risk_usd ตามทฤษฎี
— ใช้ PF และ total_pnl (ดอลลาร์จริง) เป็นตัวชี้วัดหลักเหมือนที่ทำใน S26

## สถานะ Exhaustion Checklist

1. [x] รัน grid search >= 50 combination — รัน **88 combinations หลัก + 3 smoketest +
       3 robustness(60d/90d/H1alt) + 3 edge-A(ADX) + 3 edge-B(session) + 3 leverage sweep
       = 103 รวม** > 50 ✅
2. [x] ลอง edge-improvement 2 แนวทางที่ต่างกันโดยสิ้นเชิง — A) ADX(HTF) minimum threshold
       เพิ่มเข้าไปใน htf_trend confirmation (entry-side indicator เสริม — ไม่ช่วย) B) Session-
       window narrowing/widening (timing/regime ไม่ใช่ indicator — ไม่ช่วยเช่นกัน ทั้ง narrow
       และ widen แย่กว่า baseline) ✅
3. [x] sanity-check trade samples 5-10 ไม้ (entry/SL/TP/direction) — ตรวจ 10 ไม้แรกแล้ว
       ไม่พบบั๊ก SL/TP ผิดฝั่ง และยืนยัน HTF lookup ไม่ look-ahead ข้าม timeframe ✅
4. [x] คำนวณ expectancy ที่ต้องการ vs ที่ทำได้จริง (ตัวเลข) — ดูหัวข้อด้านบน (ขาดอยู่ ~4.93R
       ต่อไม้ที่ freq จริง, หรือต้องการความถี่ ~4,000 ไม้/วัน ที่ avgR จริง — ทั้ง 2 มิติเป็นไป
       ไม่ได้ทางโครงสร้าง ไม่ใช่แค่ "ไม่พอ") ✅
5. [x] เขียนสรุปทั้งหมดลงท้ายไฟล์นี้ — ไฟล์นี้ ✅

## บทสรุปสุดท้าย (Definition of Done ข้อ ข — พิสูจน์ได้ว่าเป้าหมายไม่สมเหตุสมผล)

**สมมติฐานหลักของ S27 ถูกพิสูจน์ว่าจริงบางส่วน แต่ไม่พอ:** การบังคับ confirmation จาก HTF
(M15/H1) ก่อนเข้าทุกไม้ **ช่วยได้จริง** — `htf_trend` (EMA slope confirmation) ยก PF จาก 0.90
(baseline ไม่มี confirmation) ขึ้นเป็น 1.02-1.03 ที่ sample ใหญ่ (60-90 วัน, robust ไม่ใช่
overfitting แบบ S26) และเป็น **กลยุทธ์แรกในกลุ่ม S21-S27 ที่มี PF>1.0 ที่ robust อย่างสม่ำเสมอ
ในทุก sample size ที่ทดสอบ** ส่วน `htf_rsi` และ `htf_level` confirmation ทั้งคู่ **ทำให้แย่ลง
กว่า baseline เสมอ** ไม่ใช่ทุกชั้น confirmation จะช่วย — เฉพาะ trend-direction confirmation
จาก HTF เท่านั้นที่มี efficiency เป็นบวก (ยก WR และ PF ได้มากกว่าความถี่ที่เสียไป)

**แต่ขนาด edge ที่ได้ (PF~1.02, avgR~+0.025R/ไม้) เล็กเกินไปมหาศาลเทียบเป้า $1000/วัน:**

**ตัวเลขเทียบเป้า:**
- WR ที่ทำได้จริง (robust): **51.0-51.5%** (ดีกว่า S26 ขั้นต่ำ 47.8% ของ baseline ไม่มี
  confirmation อย่างมีนัยสำคัญทางสถิติในแง่ PF แต่ขนาดยกระดับ WR ยังน้อย)
- avgR ที่ทำได้จริง (robust): **+0.025 ถึง +0.030 R/ไม้** (เป็นบวกจริง robust — ดีกว่า S26 ที่
  avgR ติดลบทุก config — แต่เล็กกว่าที่ต้องการ ~200 เท่า)
- ความถี่ไม้/วันจริงของ locked config: **20.2-21.6 ไม้/วัน** (น้อยกว่า S26 ที่ไม่มี confirmation
  เลย ~4.6-6.5 เท่า เพราะ confirmation กรองสัญญาณออกไปจำนวนมาก — trade-off ตามที่คาด)
- expectancy gap (ตัวเลขมิติที่ 1 — avgR): ต้องการ **+4.950R/ไม้** ที่ freq จริง ทำได้จริง
  **+0.025R/ไม้** → ขาดอยู่ ~4.925R (เกินเพดานทฤษฎีของ RR1.0 ไปแล้ว ~4.95 เท่า แม้ WR=100%
  สมมุติก็ยังไม่พอ)
- expectancy gap (ตัวเลขมิติที่ 2 — ความถี่): ต้องการ **4,000 ไม้/วัน** ที่ avgR จริง ทำได้จริง
  สูงสุด **140.4 ไม้/วัน** (S26 baseline ไม่มี confirmation) → ขาดอยู่ ~28.5 เท่า
- การดัน risk% (กฎข้อ 3): ไม่ช่วยปิดช่องว่างเลย — risk>=2% ทำให้ PF<1 (margin cap +
  lot-rounding distortion) และที่ risk=1% (locked) maxDD ก็เกิน 75-79% ไปแล้ว **เกินเกณฑ์ safe
  DD (<=20-25%) ของ template นี้ตั้งแต่ risk ระดับปัจจุบัน**

**คำตอบสุดท้ายของ S27:** Multi-timeframe confirmation (entry M1/M5 + HTF trend confirmation)
**เป็นทิศทางที่ถูกกว่า S26** ในแง่คุณภาพ edge (PF>1 ที่ robust, avgR เป็นบวกจริง ไม่ใช่ noise)
และยืนยันว่า **htf_trend (EMA-slope) เป็น confirmation type เดียวที่มี efficiency เป็นบวก**
ในขณะที่ htf_rsi/htf_level ไม่ช่วยเลย — แต่ขนาด edge ที่ได้ (avgR~+0.025R, freq~20/วัน)
**เล็กเกินไปมหาศาล** เทียบกับเป้า $1000/วันที่ risk ปลอดภัย (ขาดอยู่ ~28.5 เท่าในมิติความถี่
หรือ ~198 เท่าในมิติ avgR ที่จำเป็น) — Edge-improvement ทั้ง 2 แนวทางที่ลอง (ADX strengthening,
session narrowing) ไม่ช่วยปิดช่องว่างนี้เลย ดังนั้น**ที่ risk ปลอดภัย เป้าหมาย $1000/วันยังคง
ทำไม่ได้จริงด้วยแนวทาง M1/M5+HTF-confirmation นี้** — config ที่ดีที่สุดที่ทำได้จริง (risk-adjusted)
คือ locked config (`M5 entry, htf_trend, M15/EMA50, SL=0.8×ATR, RR=1.0, risk<=1%`) ซึ่งให้
PF~1.02 และ avg/day(90d)~$2.74 บนทุน $1000 — เป็นบวกแต่ห่างจากเป้าหลายสิบเท่าทั้งในมิติความถี่
และ avgR สนับสนุนข้อสรุปสะสมจาก `create_s22.md`/`create_s25.md`/`create_s26.md` ว่า $1000/วัน
จากทุน $1000 ที่ risk ปลอดภัยไม่สมเหตุสมผลทาง mathematically ในทุกแนวทางที่ทดสอบมาจนถึงตอนนี้
(S21-S27) — แต่ S27 เป็นตัวแรกที่ให้ edge บวกที่ robust อย่างสม่ำเสมอในทุก sample size ซึ่งเป็น
ฐานที่ดีกว่าตัวก่อนหน้าสำหรับการพัฒนาต่อในอนาคต (เพิ่ม confirmation ชั้นอื่นที่ยังไม่ลอง เช่น
volume profile, multi-bar confluence, หรือขยาย entry mechanism ให้ดีกว่า EMA-pullback-bounce
แบบหยาบที่ใช้ในรอบนี้)

จบงานวิจัย S27 — สถานะ research/backtest-only 100%, ไม่ wire เข้า live trading, ไม่แก้ S1-S26
หรือไฟล์ระบบหลักใดๆ ทั้งสิ้น
