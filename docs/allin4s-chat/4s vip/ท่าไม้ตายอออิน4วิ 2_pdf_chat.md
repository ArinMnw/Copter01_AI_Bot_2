# บันทึกการทำงาน S20.8_Allin4s_2 (Small 2L/2H & Wick Rejection Sniper)

## 📌 Phase 1: Research & Plan
- สแกน PDF: `ท่าไม้ตายอออิน4วิ 2.pdf` 
- พบว่าในไฟล์ MD ออริจินัลถูกสรุปไว้ละเอียด Page-by-Page ดีเยี่ยมแล้ว โดยเฉพาะหน้า 14-16 ที่อธิบาย "Small 2L/2H และพฤติกรรมแท่งตัน Rejection" (Pa BUY หลอก / Pa SELL หลอก) อย่างละเอียด
- วางแผนอัปเดตไฟล์: Rewrite โค้ด `strategy20_8.py` ใหม่ทั้งหมดให้ตรวจจับ Swing High/Low เล็กๆ (2-6 แท่ง) ประกอบกับแรงเทขาย/ซื้อที่เกิดทิ้งไส้ไม่หลุดฐานเดิม

## 📌 Phase 2: Implementation (ลงมือแก้ไขไฟล์จริง)
- **strategy20_8.py**: สร้างไฟล์ใหม่เพื่อจับรูปแบบ Small 2L/2H พร้อมเงื่อนไขแท่งเทียน Rejection
- **config.py**: จัดการเพิ่มตัวแปร Global `S20_8_ENABLED` พร้อมเชื่อมต่อกับฟังก์ชัน `load_bot_state()` และ `save_bot_state()` เพื่อเซฟลง `bot_state.json` ได้อย่างสมบูรณ์
- **handlers/keyboard.py**: ตรวจสอบและพบว่าเมนูถูกเชื่อมต่อไว้อย่างสมบูรณ์
- **handlers/callback_handler.py**: ดักจับ Event Toggle จากปุ่มได้อย่างสมบูรณ์
- **scanner.py**: ถูกเชื่อมต่อเพื่อ import ใช้งานแล้ว
- **trailing.py**: แก้ไขทำ Bypass ตรวจเช็กเทรนด์หลังเข้าออเดอร์ให้ S20.8 ทำงานอิสระแบบ Standalone สำเร็จ

## 📌 Phase 3: Backtest Execution (รันสถิติด้วย MT5 Data จริง)
**ตารางสรุปผลลัพธ์ (ย้อนหลัง 30 วัน):**

| กรอบเวลา | จำนวนการเข้าเทรดทั้งหมด (Trades) | เคสที่ชนะ (Win) | เคสที่แพ้ (Loss) | อัตราแพ้ชนะ (Win Rate %) | แนวราคา/ระดับสัญญาณเทคนิคอลที่เข้าบ่อยที่สุด | ผลรวมกำไรขาดทุนสุทธิ (Net P&L ($)) |
|---|---|---|---|---|---|---|
| M1 | 3347 | 2027 | 1319 | 60.56% | Small 2L/2H Rejection | $ 12870.00 |
| M5 | 1029 | 669 | 360 | 65.01% | Small 2L/2H Rejection | $ 4323.00 |
| M15 | 227 | 146 | 81 | 64.32% | Small 2L/2H Rejection | $ 941.00 |
| M30 | 43 | 29 | 14 | 67.44% | Small 2L/2H Rejection | $ 189.00 |
| H1 | 2 | 1 | 1 | 50.00% | Small 2L/2H Rejection | $ 6.00 |
| H4 | 0 | 0 | 0 | 0.00% | Small 2L/2H Rejection | $ 0.00 |
| H12 | 0 | 0 | 0 | 0.00% | Small 2L/2H Rejection | $ 0.00 |
| D1 | 0 | 0 | 0 | 0.00% | Small 2L/2H Rejection | $ 0.00 |
| **สรุปรวมทุก TF** | **4648** | **2872** | **1775** | **61.79%** | **Small 2L/2H Rejection** | **$ 18329.00** |

*รันผลด้วย Script: backtest_S20_8_runner_mt5.py --days 30 --tf all*
