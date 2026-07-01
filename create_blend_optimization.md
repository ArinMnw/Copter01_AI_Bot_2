# Blend Optimization (Option B) — Leave-One-Out → 13-way Consistency-Tuned Champion

วันที่: 2026-06-28 (Opus) — option B ตามที่ผู้ใช้เลือก (optimize การจัดสรร leg แทนหา leg ใหม่)

## วิธี: Leave-One-Out analysis บน 16-way champion

ถอด leg ทีละตัวจาก 16-way แล้ววัด delta = (full − without) ของ sharpe/$mo เฉลี่ย 3 window
(90/150/180) — delta sharpe เป็นลบ = leg นั้นเป็น "drag" ต่อ consistency (`scratch/blend_loo.py`)

FULL 16-way avg: $/mo=8778, sharpe=0.513

| leg | avg Δ$/mo | avg Δsharpe | verdict |
|---|---|---|---|
| **S56 wkHL (R)** | +1543 | **+0.0880** | 🏆 champion contributor |
| **S39 zone (F)** | +1551 | **+0.0230** | แข็งมาก |
| **S37 S/R (D)** | +1569 | **+0.0090** | แข็ง |
| S47 supertr (N) | +509 | +0.0033 | ok |
| S51 pdhl (Q) | +108 | +0.0017 | ok |
| S49 vwap (P) | +44 | +0.0017 | ok |
| S36 FVG (C) | +36 | +0.0017 | ok |
| S34 volbrk (B) | +36 | +0.0013 | ok |
| S42 crt (I) | +194 | +0.0010 | ok |
| S44 volprof (K) | +1672 | +0.0003 | $เยอะแต่ sharpe-redundant |
| S41 rsi (H) | +51 | +0.0003 | neutral |
| S40 elliott (G) | +75 | −0.0003 | neutral |
| **S31 engulf (A)** | +175 | **−0.0040** | drag |
| **S45 OB (L)** | +168 | **−0.0060** | drag |
| **S46 ORB (M)** | +753 | **−0.0090** | drag (แต่ $เยอะ) |
| **S38 fib (E)** | +293 | **−0.0100** | drag (worst) |

## ผล trim variants (เฉลี่ย 90/150/180)

| variant | legs | $/mo | sharpe | maxStreak |
|---|---|---|---|---|
| 16-way FULL | 16 | 8778 | 0.5127 | 4.0 |
| **drop e,l,a → 13-way** | **13** | **8142** | **0.5320** | **3.7** |
| drop +g → 12 | 12 | 8067 | 0.5313 | 3.7 |
| drop +ORB → 11 | 11 | 7315 | 0.5363 | 3.7 |

**sweet spot = 13-way (ถอด S38 fib, S45 OB, S31 engulf)** — ถอด g(S40) ไม่ช่วย (sharpe นิ่ง),
ถอด ORB เสีย $ 17% แลก sharpe +0.004 (ไม่คุ้ม). S46 ORB ถึงจะเป็น sharpe-drag เล็กน้อยแต่ให้ $753/mo
จึงเก็บไว้

## Per-window 13-way vs 16-way — 13-way ชนะ sharpe 4/5 window

| window | 16w sharpe | 13w sharpe | 16w $/mo | 13w $/mo |
|---|---|---|---|---|
| 60d | 0.733 | 0.712 | 9248 | 8181 |
| 90d | 0.587 | **0.605** | 8885 | 8133 |
| 120d | 0.517 | **0.545** | 9319 | 8658 |
| 150d | 0.479 | **0.505** | 8442 | 7908 |
| 180d | 0.472 | **0.486** | 9007 | 8386 |

13-way ชนะ sharpe ทุก window ยกเว้น 60d (สั้น), edge โตตาม window ยาว (drag legs ยิ่งเห็นชัดเมื่อ
ข้อมูลเยอะ) แลกกับ $/mo ต่ำลง ~7-11%

## บทสรุป — champion 2 ตัวเลือก (ขึ้นกับ priority)

- **13-way (ถอด S38/S45/S31) = consistency-tuned champion** — sharpe 0.49-0.71, $/mo $7908-8658,
  maxStreak 3-4d. **ตรงกับเป้าหมายที่ผู้ใช้ย้ำ (consistency) มากที่สุด** + ง่ายต่อการ deploy (น้อย leg)
- **16-way FULL = max-$ champion** — sharpe 0.47-0.73, $/mo $8442-9319 (มากกว่า ~7-11%) แต่ sharpe
  ต่ำกว่าที่ window ยาว

**บทเรียน (29):** leave-one-out เผยว่า leg ที่เพิ่ม $/mo เยอะ (S44 volprof +$1672, S46 ORB +$753)
อาจ sharpe-redundant/drag เมื่อ blend โตขึ้น — การ "เพิ่ม leg เรื่อยๆ" ไม่ได้ดีกว่าเสมอ ควร LOO เป็น
ระยะเพื่อ trim drag. legs ที่เพิ่มมาช่วงต้น (S31 engulf, S38 fib) กลายเป็น drag เมื่อมี S56/S39/S37
ที่แรงกว่าครอบคลุม signal คล้ายกันแล้ว

## Regime-switching (option B ต่อ) — ❌ NEGATIVE (vol-gating ทำให้แย่ลง)

ทดสอบ gate leg ตาม regime ตลาด:
1. **Trendiness regime** (|dayClose-dayOpen|/range): same-day แยกผลงาน leg ชัดมาก (ส่วนใหญ่ trend-fav;
   S51/S49 ขาดทุนในวัน trend) **แต่ causal ไม่ได้** — prior-day trend-state ทำนายไม่ได้ (bias ของ
   S56/S51/S49 flip ระหว่าง same-day กับ causal) → trendiness วันนี้ "เดาล่วงหน้าไม่ได้"
2. **Vol regime** (prior-5d avg range): **causal ได้จริง** (corr prior-vol→today-range = 0.474, vol
   clusters) และแยก leg สมเหตุผล — HIVOL-fav: S46 ORB(+46)/S47(+30)/S42; LOVOL-fav: S44(+40)/S37(+27)/
   S51(+14) (breakout ชอบ hivol, mean-reversion ชอบ lovol)

**แต่ vol-gated blend แย่กว่า always-on ทุก window:** 90d $8133→$6358 (sharpe 0.605→0.575), 150d
$7908→$6536, 180d $8386→$7093 — เพราะ **ไม่มี leg ไหนขาดทุนใน regime ที่ไม่เอื้อ** (แค่กำไรน้อยลง)
การ gate off จึงแค่ตัด positive PnL ที่ diversify ทิ้ง + ที่ทุน $1000 lot ติดพื้น 0.01 ทำ fractional
weight ไม่ได้ (มีแต่ on/off แข็ง) → diversification ของ always-on ชนะ regime tilt เสมอ

**บทเรียน (30):** regime ที่ "เดาล่วงหน้าได้" (vol, corr 0.47) ≠ regime ที่ "ควรใช้ gate" — vol แยก
leg ได้แต่ gate แล้วแย่ลงเพราะทุก leg ยังบวกในทุก regime + ทุนน้อยทำได้แค่ on/off. trendiness ที่ gate
น่าจะได้ผลกลับ "เดาล่วงหน้าไม่ได้". **สรุป: always-on blend ดีกว่า regime-switch ทุกแบบที่ทดสอบ** —
13-way lean (LOO) คือคำตอบสุดท้ายของ option B

ไม่แก้ S1-S58 หรือไฟล์ระบบหลัก — research/analysis only
