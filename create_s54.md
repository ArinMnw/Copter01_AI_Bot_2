# S54 — Floor Trader Pivot Points Bounce — ❌ REJECTED (caught by new fixed-lot sanity check)

วันที่เริ่ม: 2026-06-28
สถานะ: ❌ ตก — ตัวอย่างแรกที่ fixed-lot sanity check (เพิ่มเข้า template หลัง S53) จับได้สำเร็จ

## ที่มา: self-research ต่อจาก S51 (PDH/PDL) — floor pivot เป็น quant model มาตรฐานที่เก่าแก่ที่สุด

คำนวณ PP=(H+L+C)/3, R1=2PP-L, S1=2PP-H, R2=PP+(H-L), S2=PP-(H-L) จาก daily OHLC เมื่อวาน เข้า
bounce ที่ support (S1/S2/PP) หรือ resistance (R1/R2/PP) ต่อทิศ htf_trend — ต่างจาก S51 (PDH/PDL
ดิบ) เพราะใช้สูตรสังเคราะห์ระดับเพิ่ม `strategy54.py` / `sim_s54_backtest.py`

## Smoke test + Grid search (108 combos, 90 วัน) — ดูดีตอนแรก (compounding sim)

smoke (60d default): n=108, PF=1.76, sharpe=0.261 — ดูสมเหตุสมผล (ไม่ใช่ red flag แบบ S53 ทันที)
grid search top: **touch=0.5, reject=0.15, sl=1.0, rr=1.0** → n=661 (90d, ~7.3 ไม้/วัน — สูงกว่า
leg อื่นปกติ 1-5/วัน แต่ยังไม่ถึง threshold 10/วัน), PF=1.60, sharpe=0.408, $/mo=651.6

## ⚠️ Fixed-lot sanity check (กฎใหม่จาก S53) จับความผิดปกติได้ทันที

คำนวณ PF จริงที่ lot คงที่ 0.01 (ไม่ผ่าน equity compounding):

| window | n (raw) | PF compounding | PF fixed-lot | $/mo fixed-lot |
|---|---|---|---|---|
| 30d | 352 | - | 1.36 | $505.18 |
| 60d | 773 | - | 1.05 | $96.96 |
| 90d | 1148 | 1.60 | **1.06** | $126.84 |
| 120d | 1602 | - | **0.98** | **-$40.23** |
| 150d | 2091 | - | **0.96** | **-$104.36** |
| 180d | 2472 | - | **0.99** | **-$29.09** |

**PF จริงที่ fixed lot ตกจาก 1.36 (30d) ลงมาเป็นติดลบที่ window ยาว (120-180d: PF=0.96-0.99)** —
ไม่มี edge จริงเลย (เหมือนเหรียญโยน) ตัวเลข PF=1.60/sharpe=0.408 ที่ compounding sim รายงานคือ
artifact จาก position-sizing เหมือนที่พบใน S53 (รุนแรงน้อยกว่าเพราะความถี่ 7.3 ไม้/วัน เทียบ S53 ที่
27-63 ไม้/วัน แต่ยังมากพอที่จะบิดเบือนผลลัพธ์อย่างมีนัยสำคัญ)

## บทสรุปสุดท้าย — ❌ REJECT (fixed-lot sanity check ทำงานได้จริงตามที่ออกแบบ)

**บทเรียนใหม่ (22):** fixed-lot sanity check (ที่เพิ่มเข้า template หลัง S53) ใช้งานได้จริง — จับ
S54 ได้ทั้งที่ trade frequency (7.3 ไม้/วัน) ต่ำกว่า threshold 10 ไม้/วันที่ตั้งไว้ ควรปรับ
threshold ลงมาเป็น **"เช็คทุกครั้งที่ trade frequency > 5 ไม้/วัน"** แทน (ไม่ใช่ 10) เพราะ
distortion เริ่มมีนัยสำคัญตั้งแต่ความถี่ระดับนี้แล้ว — Floor Pivot Points (แม้เป็น quant model
มาตรฐานที่ใช้กันมานาน) ไม่มี edge จริงที่ M5 XAUUSD เมื่อตรวจสอบอย่างถูกต้อง

จบ S54 — standalone research/backtest-only 100%, ไม่ wire เข้า live, ไม่แก้ S1-S53 หรือไฟล์ระบบหลัก
