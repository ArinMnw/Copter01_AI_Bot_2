# S50 — Asian Range Liquidity Sweep / Judas Swing — ❌ REJECTED

วันที่เริ่ม: 2026-06-28
สถานะ: ❌ ตก

## ที่มา: web research รอบ 3 (ICT Asian Range + London Judas Swing)

ผสม session-anchored (เหมือน ORB S46) + sweep-reversal (เหมือน CRT S42) ทั้ง 2 หมวดที่ชนะมาก่อน —
ดูมีศักยภาพในทางทฤษฎี แต่ backtest ไม่สนับสนุน ([fxnx.com](https://fxnx.com/en/blog/ict-asian-range-liquidity-trading-london-judas-swing-trap))
`strategy50.py` / `sim_s50_backtest.py`

## กลไก: Asian range (08:00-12:00 BKK) → London Judas Swing sweep+reversal

นิยาม Asian range จาก high/low ของแท่งช่วง 08:00-12:00 BKK (≈ 20:00-00:00 EST ตามนิยาม ICT) รอ
sweep ทะลุขอบ range ภายในช่วง MAX_SWEEP_AGE_MIN นาทีหลัง London เปิด (14:00 BKK) แล้วปิดกลับเข้า
โซน (false breakout) → เข้า reversal ทิศตรงข้าม sweep

## ⚠️ พบ small-sample illusion ทันทีตั้งแต่ smoke test (ตรงกับบทเรียน #10)

smoke test (60 วัน, default + htf_trend): n=6, WR=100%, **PF=73.67**, sharpe=8.319 — ตัวเลขสูง
เกินจริงชัดเจน (n เล็กมาก) ตรวจสอบด้วย raw signal (conf=none, ไม่มี filter) ที่ 90/180 วัน:

| days | conf | n | WR% | PF | sharpe |
|---|---|---|---|---|---|
| 90 | none | 51 | 29.4 | 0.55 | -0.279 |
| 90 | htf_trend | 8 | 50.0 | 1.60 | 0.267 |
| 180 | none | 82 | 29.3 | 0.53 | -0.266 |
| 180 | htf_trend | 12 | 41.7 | 1.21 | 0.099 |

**raw signal (n=51-82, sampleใหญ่พอเชื่อได้) ให้ PF=0.53-0.55 สม่ำเสมอทั้ง 90 และ 180 วัน — เป็น
negative edge จริง ไม่ใช่ noise** htf_trend filter ที่ทำให้ดูเหมือนเป็นบวกคือ small-sample
illusion (n=8-12 เชื่อไม่ได้) เหมือน pattern ที่เจอใน S41

## สำรวจพารามิเตอร์เพิ่ม — ceiling อ่อนกว่า S48 (MACD) ที่ตกไปแล้วอีก

ทดสอบ Asian range 3 แบบ ([08:00,12:00], [06:00,13:00], [20:00,00:00]) × maxage∈{90,180,240} ×
sweepmult∈{0.1,0.25,0.5} × sl∈{0.8,1.0} × rr∈{1.0,1.5} (108 combos, 150 วัน, conf=none) — ดีที่สุด
คือ **asian=[06:00,13:00], maxage=90, sweepmult=0.25** → n=38, PF=1.35, sharpe=0.135 — **ceiling
อ่อนกว่า S48/MACD (sharpe=0.158) ที่ตกไปแล้วอีก** ส่วน Asian range แบบ ICT มาตรฐาน
[20:00,00:00 EST]=[08:00,12:00 BKK] ไม่ติด top-15 เลย (แย่กว่าทุก config อื่น)

## บทสรุปสุดท้าย — ❌ REJECT (ไม่ถึงขั้น blend test เพราะ ceiling ต่ำกว่า threshold ที่เคย accept)

Judas Swing mechanism ตามที่นิยามไว้ (Asian range + London sweep+reversal) ไม่มี edge ที่ใช้ได้จริง
ที่ M5 XAUUSD — แม้แนวคิดจะผสม 2 หมวดที่ชนะ (session-anchored + sweep-reversal) แต่การบังคับให้
sweep ต้องเกิด "เฉพาะ" ในช่วง 90-240 นาทีแรกหลัง London เปิดเท่านั้น (ต่างจาก S42/CRT ที่ปล่อยให้
sweep เกิดได้ทุกเวลา) ทำให้ sample เล็กเกินไปและ/หรือ timing ไม่ตรงกับพฤติกรรมจริงของ XAUUSD ในช่วงนี้
— ไม่เพิ่มเข้า blend ไม่ทดสอบต่อ (ceiling ต่ำกว่า S48 ที่ตกไปแล้วซึ่งก็ยังตก blend test)

**บทเรียนใหม่ (18):** concept ที่ "ผสมหมวดที่ชนะ" ในทางทฤษฎี (session-anchored + sweep-reversal)
ไม่ได้ guarantee ว่าจะมี edge จริง — การบังคับ timing window ที่แคบเกินไป (เฉพาะ 90-240 นาทีแรกหลัง
session เปิด) อาจทำให้ sample เล็กจนวัดไม่ได้ หรือ momentum/sweep pattern ที่คาดไว้ไม่ตรงกับพฤติกรรม
จริงของราคาทองในช่วงนั้น ต้องทดสอบจริงเสมอ ไม่ใช่เชื่อ theory จาก web research อย่างเดียว

จบ S50 — standalone research/backtest-only 100%, ไม่ wire เข้า live, ไม่แก้ S1-S49 หรือไฟล์ระบบหลัก
