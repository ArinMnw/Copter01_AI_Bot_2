# S58 — Weekly-Open Reaction — ❌ REJECTED (center level ไม่มี edge, ต้องเป็น extreme)

วันที่เริ่ม: 2026-06-28 (Opus)
สถานะ: ❌ ตก — fixed-lot PF 0.81-1.04 ทุก config (ไม่มี edge จริง)

## ที่มา: หา weekly endogenous level ตัวอื่นนอกจาก H/L extremes (S56)

weekly open = ราคาอ้างอิงกลางสัปดาห์ที่ institutional ใช้เป็น benchmark — single level ที่เป็นทั้ง
support/resistance ขึ้นกับราคาเข้าหาจากด้านไหน (mean-reversion กลับเข้าหา anchor กลาง)
`strategy58.py` / `sim_s58_backtest.py`

## ผล grid (150 วัน, ทั้ง conf=none และ htf_trend) — fixed-lot PF ≈ 1.0 ทุก config

ดีที่สุด: htf_trend touch=0.8 → PFcomp=1.82 แต่ **PFfix=1.00** (breakeven). conf=none แย่กว่า
(PFfix=0.81-0.86). compounding PF=1.82-1.88 เป็น artifact ทั้งหมด ไม่มี edge จริง

## บทสรุปสุดท้าย — ❌ REJECT + ปิดภาพ "weekly EXTREME เท่านั้นที่มี edge"

**บทเรียนใหม่ (26):** edge ของ weekly level อยู่ที่ **H/L extremes เท่านั้น (S56)** ไม่ใช่ center/
open (S58) — เพราะ extreme คือจุดที่ stop กระจุก + exhaustion + stop-run เกิดจริง (จุดกลับตัว) ส่วน
center/open เป็นแค่ระดับอ้างอิง ไม่มีแรงกดดันเชิงโครงสร้าง — สรุปการสำรวจ weekly-reversal เพื่อนบ้าน
ของ S56 ครบแล้ว: monthly (S57)❌หยาบ, daily-reversal❌noisy, weekly-open (S58)❌center →
**S56 (weekly H/L extreme reversal) เป็น sweet spot เดี่ยวที่ unique จริงๆ** การสำรวจรอบนี้ยืนยัน
ว่า S56 ไม่ใช่ฟลุค แต่ vein ของ "prior-period level reversal" ถูกขุดถึงแก่นแล้ว

จบ S58 — standalone research/backtest-only 100%, ไม่ wire เข้า live, ไม่แก้ S1-S57 หรือไฟล์ระบบหลัก
