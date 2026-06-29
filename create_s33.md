# S33 — Equity-curve dynamic position sizing (research/backtest-only)

วันที่เริ่ม: 2026-06-27
สถานะ: ✅ เสร็จ — เจอ technique ที่ใช้งานได้จริงแต่มีเงื่อนไข ไม่ทำให้ champion เปลี่ยนที่ risk เดิม

## สมมติฐานที่ทดสอบ

ลด risk_pct อัตโนมัติตาม %drawdown ปัจจุบันจาก peak equity (ไม่ใช่นับไม้แพ้ติดกันแบบ
circuit_breaker เดิม) — เป็น "anti-martingale" position sizing คาดว่าจะลด losing-day-streak
ได้มากกว่า circuit_breaker เดี่ยวๆ

## พบ structural finding สำคัญก่อน (ทำไม tier ทุกแบบให้ผลเหมือนกันตอนแรก)

ทดสอบ tier 5 แบบ (loose 5/15%, tight 3/8%, gradual 5-step) รวมกับ circuit_breaker ที่ risk 0.5%
(base ของ champion) — **ผลออกมาเหมือนกันทุกตัวเป๊ะ** (n, $/วัน, DD ตรงกันทุกทศนิยม) ตรวจสอบ
`lot` distribution พบว่า **ทุกไม้ (329/329) ใช้ lot=0.01 (ติด MIN_LOT floor)** เพราะ risk_usd
($5 ที่ risk0.5%) ÷ risk_distance (~7-15 จุด) = lot ดิบ ~0.003-0.007 ซึ่งต่ำกว่า 0.01 อยู่แล้ว
แม้ multiplier=1.0 (เต็ม) จึงปัดขึ้นเป็น 0.01 เสมอ ไม่มีที่ให้ "ลดต่อ" — **dynamic sizing ไม่มีผล
เลยที่ risk 0.5% บนทุน $1000** เป็นข้อจำกัดเชิงโครงสร้างจาก lot granularity ไม่ใช่บั๊ก

## ทดสอบที่ risk% สูงขึ้น (lot มีที่ขยับจริง)

| risk% | sizing | 60d sharpe | 90d sharpe | 120d sharpe | 150d sharpe | maxDD(60→150d) |
|---|---|---|---|---|---|---|
| 2% | flat | 0.210 | 0.172 | 0.137 | 0.117 | 15.6%→33.0% |
| 2% | tight_3_8 | 0.203 | 0.163 | 0.128 | 0.112 | 14.0%→18.5% |
| 5% | flat | 0.199 | 0.159 | 0.091 | **0.072** | 39.3%→**70.0%** |
| 5% | tight_3_8 | 0.189 | 0.142 | 0.099 | **0.104** | 21.5%→**27.6%** |

**ผลชัด: ที่ risk สูง (5%) dd-sizing ตัด DD ระเบิดได้จริง** (70.0%→27.6% ที่ 150 วัน) และ sharpe
นิ่งกว่า flat อย่างเห็นได้ชัดที่ window ยาว (0.072→0.104, ดีขึ้น) — เป็น **safety layer ที่ใช้งาน
ได้จริง** สำหรับคนที่อยากดัน risk% สูงขึ้นเพื่อกำไรมากขึ้น

**แต่เทียบกับ champion ปัจจุบัน (risk 0.5%, ไม่มี/ไม่ต้องมี dd-sizing):**

| | risk 0.5% champion (S30/S31) | risk 5% + dd-sizing (S33) |
|---|---|---|
| $/เดือน (60-150วัน) | $159-240 | $203-545 (สูงกว่า) |
| DD (60-150วัน) | 11-19% | 19-28% (สูงกว่า) |
| sharpe (60-150วัน) | **0.151-0.207** | 0.099-0.189 (ต่ำกว่า) |

risk5%+dd-sizing ให้ **$/เดือนสูงกว่า แต่สม่ำเสมอน้อยกว่า** champion เดิม — dd-sizing ช่วยให้
risk สูงปลอดภัยขึ้น "เทียบกับตัวมันเองที่ไม่มี safety" แต่ยังไม่ดีกว่า champion ที่ risk ต่ำในแง่
ความสม่ำเสมอ (sharpe) ที่ผู้ใช้ต้องการ

## สถานะ Exhaustion Checklist

1. [x] ทดสอบ technique ใหม่ (equity-curve dd-sizing) เดี่ยวๆ และรวมกับ circuit_breaker เดิม
       ตามที่ผู้ใช้ขอให้ลองรวมหลายเทคนิค ✅
2. [x] debug หา root cause ตอนผลดูเหมือนไม่มีผล (lot floor) ก่อนสรุปผิด ✅
3. [x] ทดสอบข้าม risk% level (0.5/2/5%) เพื่อแยกผลของ technique จาก capital-floor artifact ✅
4. [x] robustness check ข้าม 4 window ทุก config ✅
5. [x] เขียนสรุปลงไฟล์นี้ ✅

## บทสรุปสุดท้าย

**Equity-curve dynamic sizing เป็น technique ที่ใช้งานได้จริง แต่เป็น "safety layer สำหรับ risk
สูง" ไม่ใช่ "ตัวเพิ่มความสม่ำเสมอที่ risk ปัจจุบัน"** — ที่ทุน $1000 + risk 0.5% (champion) lot ติด
floor ขั้นต่ำจนเทคนิคนี้ไม่มีผลเลย ถ้าจะใช้ประโยชน์จากมันต้องดัน risk% ขึ้นไปก่อน (ซึ่งลด
ความสม่ำเสมอลงอยู่ดีเทียบ champion แม้จะปลอดภัยกว่า flat-risk ที่ risk เดียวกัน)

**Champion ไม่เปลี่ยน:** ยังเป็น S30/S31 (`SL_ATR_MULT=1.2, TP_RR=1.0, risk=0.5%, circuit_breaker`)
sharpe 0.151-0.207 robust สุดในทุก technique ที่ลองมา (S31 diversification, S32 regime filter,
S33 dynamic sizing — ทั้ง 3 รอบไม่มีตัวไหนดีกว่า champion เดิมในแง่ความสม่ำเสมอที่ risk ฐาน)

**ข้อเสนอแยกสำหรับอนาคต (ไม่ใช่ champion แต่เป็นตัวเลือกที่ถูกต้องตามบริบทต่างกัน):** ถ้าผู้ใช้
ต้องการกำไร/เดือนสูงกว่านี้และยอมรับ DD ที่สูงขึ้น (19-28% แทน 11-19%) ได้ risk5%+dd-sizing
(tight_3_8 tiers) เป็นตัวเลือกที่ปลอดภัยกว่าการดัน risk% เปล่าๆ (flat) อย่างมีนัยสำคัญ
(DD 27.6% vs 70.0% ที่ risk เดียวกัน)

จบ S33 — standalone research/backtest-only 100%, ไม่ wire เข้า live, ไม่แก้ S1-S32 หรือไฟล์ระบบหลัก
