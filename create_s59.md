# S59 — Intermarket (Gold↔DXY) Investigation — ❌ NO STRATEGY (closed by microstructure)

วันที่: 2026-06-28 (Opus) — option A ตามที่ผู้ใช้เลือก
สถานะ: ❌ ไม่สร้าง strategy file — พิสูจน์ด้วย correlation analysis ว่า intermarket ไม่ exploitable
สำหรับ single-instrument gold (ก่อนเสีย effort เขียนโค้ด backtest)

## ที่มา: ทองวิ่งผกผันกับ USD — ลองใช้ DXY เป็น signal/filter

broker IUX มี DXY.iux, EURUSD.iux, USDJPY.iux, GBPUSD.iux

## ผลวิเคราะห์ correlation (16,819-30,000 common M5 bars)

**1. Contemporaneous correlation: -0.49** (ทุก horizon 5-60min), beta(logGold~logDXY) = **-4.44**
→ ความสัมพันธ์ผกผัน "จริงและแรง" — gold กับ DXY วิ่งสวนกัน ณ เวลาเดียวกัน

**2. Lead/lag correlation ≈ 0.00** (DXY_prior6 → gold_next1/3/6 = -0.007, 0.000, -0.002)
→ **DXY ไม่ได้นำ gold** — ไม่มี information lag ให้เทรด (กว่าจะเห็น DXY ขยับ gold ขยับไปแล้วพร้อมกัน)

**3. Residual mean-reversion ≈ 0** (z-score ของ spread = logGold - beta·logDXY, W=60):
corr(z, futRet) = -0.010 ถึง -0.030; เมื่อ |z|>2 การ revert = -1.1 ถึง +1.3 bps (noise, sign ไม่
สม่ำเสมอ) → divergence ของ gold-DXY **ไม่ revert** ในฝั่ง gold (มัน correct ผ่าน DXY ขยับแทน หรือ
persist)

## บทสรุป — ❌ intermarket ปิดด้วย market microstructure (ไม่ใช่ปัญหา tuning)

**บทเรียนใหม่ (27):** ความสัมพันธ์ gold↔DXY เป็น **identity ไม่ใช่ predictive signal** — ทั้งคู่ถูก
price จากค่า USD เดียวกัน ณ ขณะเดียวกัน โดย liquidity provider กลุ่มเดียวกัน จึง (1) ไม่มี lead/lag
(corr≈0) (2) residual ไม่ revert ในฝั่ง gold (corr≈-0.01). การจะ monetize divergence ต้องเทรด
**ทั้ง 2 instrument (pairs trade)** ไม่ใช่ gold ตัวเดียว — ซึ่งอยู่นอก scope ของบอท XAUUSD-only
(สอดคล้องกับที่เคยสรุปว่า Statistical Arbitrage/Pair Trading ใช้ไม่ได้กับ single instrument). **อย่า
ลอง 가intermarket-as-gold-signal อีก — ปิดด้วยโครงสร้างตลาด ไม่ใช่ tuning** (ประหยัด effort: เช็ค
correlation lead/lag + residual reversion ก่อนเขียน strategy ใดๆ ที่อิง intermarket).

## หมายเหตุ Cost realism (จากคำเตือนผู้ใช้เรื่อง spread/slippage)

ตรวจ spread จริงของ XAUUSD.iux จาก M5 bars (~104 วัน): **median $0.16, mean $0.16, p95 $0.18, p99
$0.25** (max spike $1.29 หายาก) — สม่ำเสมอทุก session ($0.155-0.165). backtest ใช้ spread=0.20
**conservative อยู่แล้ว** (สูงกว่า median จริง). Cost-sensitivity ของ S56 champion: ที่ spread 0.20/
0.35/0.50 → fixed-lot PF = 1.84/1.80/1.77 (60d), 1.09/1.07/1.06 (150d) — **edge ทนทานต่อ cost
แม้ที่ 0.50 (2.5x baseline, รวม slippage buffer)** เพราะ weekly-reversal trade ขนาดใหญ่พอที่ spread
เล็กเมื่อเทียบ edge ต่อไม้. ⚠️ snapshot ราคา ask-bid ปัจจุบันอ่านได้ $2.00 แต่เป็น anomaly ชั่วขณะ
(market เพิ่งเปิด/news spike) ไม่ใช่ค่า typical.

จบ S59 (investigation only, ไม่มี strategy file) — ไม่แก้ S1-S58 หรือไฟล์ระบบหลัก
