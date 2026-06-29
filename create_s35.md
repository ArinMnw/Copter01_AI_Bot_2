# S35 — Mean-Reversion (deviation+RSI) — 3rd diversification leg attempt (research/backtest-only)

วันที่เริ่ม: 2026-06-27
สถานะ: ✅ เสร็จ — ผลลบ (edge หายไปในข้อมูลล่าสุด) ไม่เพิ่มเข้า blend champion

## สมมติฐานที่ทดสอบ

ต่อยอด S34 (เจอ champion ใหม่จากการรวม engulfing+volume-breakout ที่ decorrelate กันจริง) — ลอง
กลไกที่ 3: **mean-reversion** (ราคาเบี่ยงจาก SMA เกิน N×stdev + RSI exhaustion, ไม่ใช้ htf_trend
เพราะ contrarian by design, ใช้ ADX-max filter แทนเพื่อกรองเฉพาะตลาด sideways) คาดว่าจะ decorrelate
กับ A (engulfing, trend-follow) และ B (volume-breakout, momentum-follow) เพราะ mean-reversion
ทำกำไรช่วงที่อีก 2 ระบบมักแพ้ (sideways/choppy)

## ผล grid search + robustness (เผยปัญหาสำคัญ)

Grid 45 วัน (36 combos): **ไม่มี config ใดได้ PF > 1.00** เลย (ตัวดีสุด PF=1.00 พอดี, sharpe=0.000)
— ขัดกับ baseline default (sma=20,dev=2.0,rsiob=70,adxmax=25,sl=1.0,rr=1.0) ที่ smoke test แรกได้
PF=1.19 ที่ 90 วัน ต้องเช็คว่าทำไมต่างกัน

**Robustness check ของ baseline default ข้าม 6 window (เรียงจากใหม่สุดไปเก่าสุด):**

| window | n | WR% | PF | sharpe | DD% |
|---|---|---|---|---|---|
| 30d (ล่าสุด) | 15 | 53.3 | **0.93** | -0.039 | 2.7 |
| 45d | 24 | 54.2 | **0.99** | -0.009 | 2.7 |
| 60d | 39 | 56.4 | **1.01** | 0.006 | 3.3 |
| 90d | 66 | 59.1 | 1.19 | 0.087 | 4.1 |
| 120d | 82 | 59.8 | **1.38** | 0.170 | 3.8 |
| 150d | 93 | 55.9 | 1.21 | 0.101 | 6.2 |

**ข้อค้นพบสำคัญ: PF ไล่ระดับจาก 0.93 (30วันล่าสุด) ขึ้นไปถึง 1.38 (120วัน) อย่างเป็นขั้นบันได
ไม่ใช่สุ่ม** — แปลว่า edge ของ mean-reversion **อยู่ในข้อมูลเก่า (ช่วง 90-150 วันที่แล้ว) แต่กำลัง
หายไปในข้อมูลล่าสุด (30-60 วัน)** เป็น pattern ของ "regime change" จริง (ตลาด XAUUSD ช่วงนี้ไม่ได้
อยู่ในโหมด sideways ที่ mean-reversion ต้องการ) **ไม่ใช่ overfitting แบบที่เจอใน S26/S27/S29/S31**
(ซึ่งเป็น noise สุ่มไม่เรียงลำดับ)

## สถานะ Exhaustion Checklist

1. [x] grid search 36 combos (45 วัน) + ทดสอบ baseline ข้าม 6 window ✅
2. [x] วิเคราะห์ pattern ของผลที่ขัดกัน (window สั้น vs ยาว) ก่อนสรุปผิด — พบเป็น regime change
       ไม่ใช่ overfitting ✅
3. [x] ไม่เพิ่มกลไกที่ไม่ทำงานในข้อมูลปัจจุบันเข้า champion blend ✅
4. [x] เขียนสรุปลงไฟล์นี้ ✅

(ข้าม sanity-check trade samples และ correlation check เพราะ edge ไม่ผ่านเกณฑ์ขั้นต้น — ไม่มี
ประโยชน์ที่จะตรวจลึกกว่านี้ก่อนพิสูจน์ edge ปัจจุบันได้)

## บทสรุปสุดท้าย

**S35 ไม่ผ่าน — ไม่เพิ่มเข้า blend champion** ต่างจาก S31-S33 (ที่ตกเพราะ lever ไม่ช่วยอะไรเลย)
S35 มี edge จริงในอดีต (90-150 วันที่แล้ว PF 1.19-1.38) แต่ **edge นั้นกำลังจางหายไปในข้อมูลปัจจุบัน**
(30-60 วันล่าสุด PF 0.93-1.01 = breakeven/ขาดทุนเล็กน้อย) — เป็นความเสี่ยงที่ยอมรับไม่ได้ถ้าจะใช้
จริงตอนนี้ (อาจกลับมาทำงานได้ถ้าตลาดเข้าโหมด sideways อีก แต่ไม่ใช่ตอนนี้)

**Champion ไม่เปลี่ยนจาก S34:** ยังเป็น blend ของ A (engulfing) + B (volume-breakout) เท่านั้น
($/เดือน $140-303, sharpe 0.13-0.25 ข้าม 5 window) — ยังไม่มีกลไกที่ 3 ที่ผ่านเกณฑ์มาเสริม

จบ S35 — standalone research/backtest-only 100%, ไม่ wire เข้า live, ไม่แก้ S1-S34 หรือไฟล์ระบบหลัก
