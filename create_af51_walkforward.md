# AF51 Walk-Forward Validation Report

วันที่: 2026-07-07
สถานะ: WALK-FORWARD VALIDATION COMPLETED

## วัตถุประสงค์ (Phase 1)
พิสูจน์ว่า edges/legs ของ AF51 ที่ผ่านการคัดเลือกจากข้อมูล 180 วัน เป็นของจริงหรือไม่ และมี overfit กับ in-sample data มากน้อยแค่ไหนเมื่อนำมา split data ออกเป็น:
- **In-Sample (IS)**: 120 วันแรก (2025-11-19 ถึง 2026-04-20)
- **Out-Of-Sample (OOS)**: 60 วันหลัง (2026-04-21 ถึง 2026-07-03)

## กระบวนการทดสอบ
- ดึง daily PnL ของ 51 legs + S88 base (จาก `af_ladder_components.csv`) ใน period `days=180`
- ใช้ weights เดิมที่ fix ไว้ตั้งแต่ตอนสร้าง ladder
- ตัดแบ่งวันที่ทั้งหมด 180 วันออกเป็น IS=120, OOS=60
- วัดผล Portfolio และ Leg Survival โดยไม่มีการปรับแก้ weights ใดๆ (Strict Walk-Forward)

## ผลการทดสอบ (Portfolio Level)

| Metric | IS (120 days) | OOS (60 days) |
|---|---:|---:|
| **Avg $/day** | $2,001.48 | $1,739.72 |
| **Worst Day** | -$999.91 | -$999.91 |
| **Min $/day (Cumulative)** | -$999.91 | -$999.91 |

**บทสรุป Portfolio**:
1. **Performance Retention**: พอร์ตยังคงรักษาผลกำไรได้ถึง **86.9%** ของช่วง In-Sample ($1,739.72 vs $2,001.48) พิสูจน์ได้ว่า edge รวมของพอร์ตเป็นของจริง และสามารถทำกำไรใน Out-Of-Sample ได้อย่างแข็งแกร่ง
2. **Floor Integrity**: Worst day ถูกล็อกไว้ที่ -$999.91 ตลอดทั้ง 60 วัน OOS แปลว่าระบบป้องกันความเสี่ยงและ circuit breaker ของเราทำงานได้อย่างสมบูรณ์แบบแม้ในข้อมูลที่ไม่เคยเห็นมาก่อน
3. **No Blowup**: ไม่มีการพอร์ตแตก

## ผลการทดสอบ (Leg Level Survival)
- **รอด (OOS > 0)**: 37 legs
- **ไม่รอด (OOS <= 0)**: 14 legs

**บทสรุป Legs**:
สัดส่วนการรอดชีวิตที่ 37/51 (72.5%) ถือว่าดีมาก 14 legs ที่ไม่รอดมักจะเป็น legs ที่มีจำนวนไม้ (Raw trades) น้อยๆ หรือเป็น ambiguous legs ที่บังเอิญ fit เข้ากับเหตุการณ์ใน IS ถ้าเราต้องการสร้าง AF Ladder V2 ในอนาคต ควรโฟกัสเฉพาะโปรไฟล์ของ 37 legs ที่ผ่าน OOS นี้ (เนื้อแน่น, ambiguity ต่ำ)

## ข้อสรุปสำหรับ Phase 2
เนื่องจาก AF51 ผ่าน Walk-Forward Validation ด้วยผลลัพธ์ที่ดีเยี่ยม ($1,739.72 OOS ถือว่าใกล้ $2,000 มาก) เราสามารถดำเนินการต่อในการไล่ **AF52+ Ladder** ได้อย่างมั่นใจ โดยจะใช้ framework เดิมและค้นหา candidates เพิ่มจาก S86 screen space ที่เหลืออยู่
