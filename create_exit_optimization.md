# Exit-Logic Optimization — ❌ NEGATIVE (fixed SL/TP ชนะทุก exit ที่ซับซ้อนกว่า)

วันที่: 2026-06-29 (Opus)
สถานะ: ❌ ทดสอบแล้วไม่ช่วย — เก็บ fixed SL/TP เดิมไว้ทุก leg

## ที่มา: ปรับวิธีออก (exit) ของ leg ที่มีอยู่แทนหา entry ใหม่ — ทดสอบ 3 เทคนิคมาตรฐาน

1. **Breakeven (BE)** — เลื่อน SL มาที่ entry เมื่อกำไร >= trigger×R (0.5R, 1.0R)
2. **Trailing (ATR)** — ลาก SL ตาม best price ห่าง N×ATR (2.0, 3.0)
3. **Partial TP** — ปิดครึ่ง position ที่ 1.0R แล้วปล่อยครึ่งที่เหลือวิ่งไป TP เดิม

ทดสอบบน 2 leg ที่ mechanism ตรงข้ามกัน: **S56 (weekly H/L reversal)** และ **S37 (pivot bounce
continuation)** — `scratch/exit_test_s56.py`, `scratch/exit_test_s37.py` (fixed-lot, ไม่ผ่าน
compounding — วัด edge ดิบไม่ปนกับ position-sizing)

## ผล S56 (reversal) — baseline ชนะทุก policy ทุก window

| policy | $/mo (90d) | sharpe (90d) | $/mo (180d) |
|---|---|---|---|
| **baseline** | **462** | **0.126** | **133** |
| BE@0.5R | -469 | -0.233 | -545 |
| trail 2ATR | -54 | -0.025 | -273 |
| trail 3ATR | 268 | 0.092 | 20 |
| partialTP@1.0R | 286 | 0.092 | 21 |

## ผล S37 (continuation) — baseline ชนะทุก policy ทุก window เช่นกัน

| policy | $/mo (90d) | sharpe (90d) | $/mo (180d) |
|---|---|---|---|
| **baseline** | **464** | **0.114** | **-106** |
| BE@0.5R | -965 | -0.475 | -1278 |
| trail 3ATR | 267 | 0.071 | -196 |
| partialTP@1.0R | 351 | 0.101 | -149 |

## บทสรุปสุดท้าย — ❌ ไม่เปลี่ยน exit logic ของ leg ใดเลย

**บทเรียนใหม่ (31):** fixed SL/TP (ออกที่จุดเดียวตายตัว) ชนะทุก exit-management ที่ซับซ้อนกว่า
ทั้งใน mechanism reversal (S56) และ continuation (S37) — สาเหตุ:
- **Breakeven ทำร้ายมากที่สุด** (BE@0.5R: sharpe -0.233 ถึง -0.565) เพราะย้าย SL มา entry เร็วเกินไป
  ทำให้ trade ที่จะไปถึง TP จริงถูก stop ออกด้วย noise ปกติก่อนแกว่งกลับไปแตะ TP (โดยเฉพาะ setup ที่
  ต้องการ "พื้นที่หายใจ" อย่าง reversal/pivot-bounce)
- **Trailing ATR แคบ (2.0) ทำร้าย, กว้าง (3.0) ใกล้เคียง baseline แต่ไม่เคยดีกว่า** — ยิ่ง trail แคบ
  ยิ่งตัดกำไรเร็วก่อนถึง TP design เดิม
- **Partial TP ใกล้เคียง baseline ที่สุด** (บาง window ดีกว่าเล็กน้อยที่ short window) แต่ไม่ robust
  ข้าม window ยาว — ไม่คุ้มกับความซับซ้อนที่เพิ่ม

**ข้อสรุปเชิงโครงสร้าง:** TP_RR ของทุก leg (1.0-2.0) ถูก grid search มาแล้วว่าเหมาะสมกับ distribution
ของการเคลื่อนไหวหลัง entry ของ mechanism นั้นๆ อยู่แล้ว — การใส่ exit-management เพิ่มเป็นการ "เดา"
ทับ TP ที่ optimize มาแล้ว ซึ่งมักทำให้แย่ลงไม่ใช่ดีขึ้น เพราะตัด upside ของ winner ออกก่อนเวลา โดยไม่
ได้ลด downside ของ loser ลงจริง (ยังโดน SL เท่าเดิมหรือแย่กว่า). สรุป: **fixed SL/TP + grid-searched
RR คือ exit ที่ optimal แล้วสำหรับ mechanism ระดับ pullback/reversal ที่ใช้ในโปรเจกต์นี้ทั้งหมด** —
ไม่ต้องทดสอบ exit-logic กับ leg อื่นเพิ่ม (ผลตรงกันข้ามกัน 2 mechanism type แล้ว)

## Day-of-Week effect (option B ต่อยอด) — ❌ NEGATIVE (ไม่ robust ข้าม window)

ทดสอบ 13-way blend PnL แยกตามวันในสัปดาห์ (Mon-Fri) ที่ 90/150/180 วัน — เจอ pattern ที่ 180d
(Fri $337 สูงสุด, Thu $214 ต่ำสุด) แต่ **rank order flip ที่ window อื่น**: 90d Tue สูงสุด ($283, Fri
แค่อันดับ 3), Thu ที่ 90d ใกล้เคียงค่าเฉลี่ย (ไม่ใช่ต่ำสุด) — ด้วย n=18-39 วัน/สัปดาห์ต่อ window
เป็น sample เล็กเกินไปที่จะเชื่อ ไม่มี day-of-week filter ที่ robust พอจะใช้

**บทเรียนใหม่ (32):** day-of-week ไม่มี edge ที่ทดสอบเจอ (ต่างจาก vol-regime ที่มี causal signal
จริง) — n ต่อวัน/สัปดาห์เล็กเกินไป (18-39) ทำให้ rank ไม่เสถียรข้าม window เป็นตัวอย่างที่ดีของ
"ดูเหมือนมี pattern แต่ small-sample noise" (คล้าย lesson 10 เรื่อง overfitting illusion) —
ไม่ต้องเพิ่ม day-of-week filter ให้ blend

ไม่แก้ S1-S58 หรือไฟล์ระบบหลัก — research/analysis only
