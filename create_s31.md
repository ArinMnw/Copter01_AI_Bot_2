# S31 — Consistency-focused: diversification + SL/RR grid (research/backtest-only)

วันที่เริ่ม: 2026-06-27
สถานะ: ✅ เสร็จ — เป้าหมาย "ความสม่ำเสมอของกำไร" (ไม่ใช่ DD ต่ำสุด/WR สูงสุด ตามที่ผู้ใช้ระบุ)
ผลสรุป: **champion ไม่เปลี่ยน** (SL1.2/RR1.0 จาก S30 "wider_sl") — เป็นตัวที่ robust สุดจริง

## เป้าหมายที่เปลี่ยนจาก S21-S30

ผู้ใช้ระบุชัด: ไม่ต้องการ DD ต่ำลง ไม่ต้องการ WR สูงขึ้น ต้องการ **"กำไรต่อเนื่องสม่ำเสมอ"**
เมตริกที่ใช้แทน: %วันที่กำไรบวก, max losing-day-streak (วันแพ้ติดกันยาวสุด), sharpe-like
(mean daily pnl / std daily pnl) — ไม่ใช่ PF/WR/DD ตามเดิม

## Lever ที่ทดสอบ

### 1. Diversification (พิสูจน์แล้วว่าไม่ช่วย — ทดสอบ 2 แบบ)

**Fake blend (SL/RR ต่างกัน, entry detector เดียวกัน):** ดูดีตอนแรก ($/mo พุ่งเป็น 449) แต่ตรวจสอบ
`signal_time_ts` แล้วพบว่า **overlap 99.7-100%** — engulfing detector เดียวกันยิงสัญญาณที่แท่งเดียวกัน
เสมอ ไม่ว่า SL/RR จะต่างกันแค่ไหน ผลที่ดูดีคือ overfitting จากการ stack ไม้ correlated ไม่ใช่ edge จริง
→ **ทิ้ง ไม่ใช้**

**Session-split blend (London core vs NY core, overlap=0 ยืนยันด้วยโค้ด):** decorrelate ที่ trade-level
จริง (ไม่มีไม้ซ้อนเวลากันแน่นอน) แต่ผล **แย่กว่า full-session เดิมทุก window** (sharpe ต่ำกว่า, $/mo
ลดเกือบครึ่ง) เพราะ day-level ยัง correlate กับ market regime ของวันนั้น (วันเทรนด์ดีทั้ง 2 session
ชนะพร้อมกัน, วันป่วนแพ้พร้อมกัน) — การแบ่งทุนครึ่งแค่เจือจาง edge โดยไม่ลด correlation จริง → **ทิ้ง**

### 2. SL/RR grid ขยาย (0.8-2.6 x 0.8-1.2, 90 วัน)

เจอ 2 candidate ที่ sharpe สูงกว่าเดิมที่ 90 วัน: SL1.0/RR1.2 (sharpe 0.232) และ SL1.2/RR1.2
(sharpe 0.224) เทียบ champion เดิม SL1.2/RR1.0 (sharpe 0.205 ที่ 90วัน)

**Robustness check ข้าม 60/90/120/150 วัน (เผย overfitting):**

| config | 60d sharpe | 90d sharpe | 120d sharpe | 150d sharpe | maxStreak range |
|---|---|---|---|---|---|
| SL1.0/RR1.2 | 0.186 | 0.232 | 0.139 | 0.158 | 4d (คงที่) |
| SL1.2/RR1.2 | 0.194 | **0.224** | **0.078** | **0.081** | **4d→12d→12d** (พัง) |
| **SL1.2/RR1.0 (champion)** | **0.217** | 0.205 | **0.157** | **0.151** | **3d-4d (นิ่งสุด)** |

SL1.2/RR1.2 ดูดีที่สุดที่ 90 วัน (window เดียวกับที่ grid ใช้ค้นหา) แต่ **พังที่ 120/150 วัน**
(sharpe ร่วง 0.224→0.078, maxStreak พุ่งจาก 4→12 วัน, DD 51-54%) — overfitting ชัดเจน เหมือน
pattern ที่เจอใน S26/S27/S29 (เลือกจาก window เดียวไม่เช็ค robust)

**SL1.2/RR1.0 (champion เดิมจาก S30) คือตัวเดียวที่ sharpe และ maxStreak นิ่งสุดทุก window**
— ไม่ใช่ตัวที่ดีที่สุดในแต่ละ window เดี่ยวๆ แต่เป็นตัวที่ **แปรปรวนน้อยที่สุดข้าม window** ซึ่งตรง
กับนิยาม "สม่ำเสมอ" ที่ผู้ใช้ต้องการมากกว่า

## สถานะ Exhaustion Checklist

1. [x] ทดสอบ lever ใหม่ 2 แนวทางต่างกันโดยสิ้นเชิง — diversification (entry-stacking) และ SL/RR
       grid ขยาย (risk/reward placement) ✅
2. [x] sanity-check correlation ด้วยโค้ดจริง (signal_time_ts overlap) ก่อนเชื่อผล blend ✅
3. [x] robustness check ข้าม 4 window (60/90/120/150 วัน) ก่อนสรุป champion ✅
4. [x] ไม่หลงไปกับตัวเลขที่ดีที่สุดของ window เดียว — เลือกตัวที่แปรปรวนน้อยสุดข้าม window ✅
5. [x] เขียนสรุปลงไฟล์นี้ ✅

## บทสรุปสุดท้าย

**Champion ไม่เปลี่ยนจาก S30 wider_sl:** `ENTRY_TF=M5, ENTRY_PATTERN=engulfing,
ENGULF_MIN_RATIO=1.0, SL_ATR_MULT=1.2, TP_RR=1.0, MIN_GAP_BARS=1, htf_trend(M15/EMA50),
circuit_breaker(trig3/cool10), RISK_PCT=0.5%`

ตัวเลข robust (เฉลี่ย 4 window): **$/วัน ~$5.85-7.84, $/เดือน ~$159-237, maxStreak 3-4 วันเสมอ,
sharpe 0.15-0.22 เสมอ** — นี่คือระดับความสม่ำเสมอสูงสุดที่หาได้จากการทดสอบ diversification และ
SL/RR grid รอบนี้ ทั้ง 2 lever ใหม่ที่ลอง (diversification, SL/RR ที่กว้างขึ้น) ไม่พบจุดที่ดีกว่าจริง
แบบ robust — diversification ไม่ช่วยเพราะ correlation อยู่ที่ระดับวัน/regime ไม่ใช่ระดับไม้,
SL/RR ที่กว้างกว่าเดิมดูดีเฉพาะ window เดียว (overfit)

จบ S31 — standalone research/backtest-only 100%, ไม่ wire เข้า live, ไม่แก้ S1-S30 หรือไฟล์ระบบหลัก
