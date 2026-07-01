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

## Session H/L Reversal (London range → NY session) — ❌ REJECTED (4th confirmation ของ S56 uniqueness)

ทดสอบ level source ใหม่: London session (14:00-19:00 BKK) H/L เป็น endogenous level, เทรด
reversal ช่วง NY session (19:00-24:00) ต่อ — สมมติฐาน: อยู่ระหว่าง prev-day (noisy, ตก) กับ
weekly (sweet spot, S56) ใน frequency spectrum, "fresh" กว่า weekly เพราะสร้างเสร็จในวันเดียวกัน

**Fixed-lot robustness:** PF 0.96-1.27 ทุก window (60d เกือบ breakeven 1.01, 90-180d 1.13-1.27) —
edge อ่อนแต่มีจริง (ไม่ล่มเหมือน artifact) คล้าย marginal leg (S47 SuperTrend) มากกว่า S56

**Blend contribution vs 13-way champion — ❌ REJECT:**

| window | 13-way sharpe | +LondonNY sharpe | Δ | $/mo Δ |
|---|---|---|---|---|
| 90d | 0.594 | 0.538 | **-0.056** | +$1039 |
| 150d | 0.504 | 0.485 | **-0.019** | +$612 |
| 180d | 0.479 | 0.471 | **-0.008** | +$481 |

sharpe แย่ลง**ทุก window ที่ทดสอบ** (3/3) แม้ $/mo เพิ่ม — เข้าเกณฑ์ reject แบบ S43 (แย่ลงทุก window)
ไม่ใช่ marginal-accept แบบ S45 (แย่ลงบางส่วน) แม้ magnitude จะเล็กลงเมื่อ window ยาวขึ้นก็ตาม

## บทสรุป — endogenous-level-neighbor search ปิดสมบูรณ์ (4 reject ยืนยัน S56 unique)

**บทเรียนใหม่ (33):** session-level H/L (London range) เป็น reject ตัวที่ 4 ที่ล้อมรอบ S56
(หลัง monthly/prev-day/weekly-open) — ยืนยันซ้ำว่า **weekly H/L extreme (S56) เป็นจุดเดียวใน
frequency×extreme-type space ทั้งหมดที่มี edge จริงสำหรับ prior-period-reversal family** ไม่มี
neighbor ไหนในทุกทิศทาง (TF สั้นกว่า/ยาวกว่า, extreme ต่างประเภท) ที่ผ่าน blend test — การค้นหา
เพิ่มในทิศทางนี้ไม่คุ้ม effort อีกต่อไป

## Level Confluence (S56 weekly H/L + S44 volume node) — ❌ NEGATIVE (ไม่มี discriminating power)

สมมติฐาน: S56 signal ที่เกิดตรงกับ high-volume node (จาก S44 logic) ควรแม่นกว่า signal ที่ไม่ตรง —
ทดสอบ PF แยกตาม volume density รอบระดับ (180 วัน)

ผล: **CONFLUENCE PF=1.13 (n=1037) vs NO-confluence PF=1.10 (n=240)** — ต่างกันเพียงเล็กน้อย ไม่มี
นัยสำคัญ + 81% ของ trade อยู่ใน "confluence" อยู่แล้ว (เพราะ weekly extreme ตามธรรมชาติมักมี volume
สะสมมาก ไม่ใช่ signal ที่ independent) → ไม่ใช่ filter ที่ใช้แยกคุณภาพ trade ได้จริง

**บทเรียนใหม่ (34):** endogenous level 2 ตัวที่ independent กัน (weekly H/L, volume node) มักจะ
overlap กันอยู่แล้วโดยธรรมชาติ (ราคาที่ทำ weekly extreme มักมี volume เยอะด้วย) — "confluence filter"
จึงไม่ได้เพิ่มข้อมูลใหม่ ไม่ discriminate คุณภาพ trade ได้จริง

ไม่แก้ S1-S58 หรือไฟล์ระบบหลัก — research/analysis only
