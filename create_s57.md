# S57 — Previous-Month High/Low Reversal — ❌ REJECTED (monthly หยาบเกินไป)

วันที่เริ่ม: 2026-06-28 (Opus)
สถานะ: ❌ ตก — fixed-lot PF < 1.0 ทุก config (ไม่มี edge จริง)

## ที่มา: ต่อยอด S56 (weekly reversal ที่ชนะ) ขึ้นไปอีกขั้น TF (monthly)

สมมติฐาน: "ยิ่ง level เป็น HTF ยิ่งเป็น reversal point ที่ดี" (บทเรียน S56) → ลอง prev-month H/L
`strategy57.py` / `sim_s57_backtest.py`

## ผล smoke test (150 วัน) — fixed-lot PF < 1.0 ทุก config

| conf | touch | n (ไม้/วัน) | PF compounding | **PF fixed-lot** | sharpe | WR% |
|---|---|---|---|---|---|---|
| none | 0.5 | 1.8/d | 1.24 | **0.78** | 0.099 | 56.1 |
| none | 0.8 | 2.5/d | 1.65 | **0.87** | 0.259 | 61.3 |
| htf_trend | 0.5 | 0.7/d | 1.03 | **0.78** | 0.032 | 46.9 |
| htf_trend | 0.8 | 1.0/d | 1.21 | **0.96** | 0.110 | 58.7 |

**fixed-lot PF อยู่ใต้ 1.0 ทุก config (0.78-0.96)** — compounding PF=1.65 เป็น artifact (fixed-lot
check จับได้ทันที) ไม่มี edge จริง

## บทสรุปสุดท้าย — ❌ REJECT + บทเรียน "weekly คือ sweet spot, monthly หยาบเกินไป"

**บทเรียนใหม่ (25):** หลักการ "ยิ่ง HTF ยิ่งเป็น reversal ดี" (จาก S56) **มีเพดาน** — monthly
extreme หยาบเกินไปสำหรับ M5 intraday reversal เพราะ (1) กว่าราคาจะถึง monthly extreme มักอยู่ใน
strong directional move ที่ทะลุผ่าน (level ที่ตั้งไว้เป็นเดือนแล้ว "เก่า"/stale, regime เปลี่ยนไป
แล้ว) (2) ความถี่ต่ำมาก (1.8-2.5 ไม้/วัน) และ touch ที่เกิดไม่ใช่ bounce ที่เชื่อถือได้ — **weekly
(S56) คือ sweet spot: HTF พอที่จะเป็น reversal point แต่ไม่เก่าเกินไปและยังถูก retest บ่อยพอ** —
เวลาหา HTF-reversal level ใหม่ ให้อยู่ในโซน daily-to-weekly ไม่ใช่ monthly+

จบ S57 — standalone research/backtest-only 100%, ไม่ wire เข้า live, ไม่แก้ S1-S56 หรือไฟล์ระบบหลัก
