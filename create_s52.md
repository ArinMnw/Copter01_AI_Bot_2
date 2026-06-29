# S52 — Quantified Pin Bar Reversal — ❌ REJECTED

วันที่เริ่ม: 2026-06-28
สถานะ: ❌ ตก — เทคนิคแรกจาก self-research รอบ 4 (quantitative candlestick model)

## ที่มา: web research รอบ 4 (quantitative candlestick pattern model)

นิยาม pin bar เชิงปริมาณล้วน (wick:body ratio + opposite wick limit + min range) แทนการมองภาพ
([strike.money](https://www.strike.money/technical-analysis/pin-bar)) `strategy52.py` /
`sim_s52_backtest.py`

## กลไก: pure price-action candlestick pattern (ไม่มี level reference)

body=|close-open|, ต้องมี wick ด้านหนึ่งยาว >= MIN_WICK_BODY_RATIO×body และ wick ฝั่งตรงข้ามเล็ก
<= MAX_OPPOSITE_WICK_RATIO×wick หลัก — **ต่างจาก S37/S44/S49/S51 ที่ทุกตัวต้องมี "ระดับ" (pivot/
volume-node/VWAP/PDH-PDL) ก่อนเช็ค rejection S52 ไม่สนใจระดับราคาเลย เป็น price-action pattern
ล้วน**

## Grid search (216 combos, 90 วัน) — ceiling อ่อนที่สุดในกลุ่ม candidate ที่เคยทดสอบ

Top: wb=2.0, opp=0.5, minrange=0.5, sl=1.0, rr=1.5, htf_trend → **n=997, PF=1.09, sharpe=0.078**
sample ใหญ่มาก (n=997, ไม่ใช่ illusion) แต่ edge แทบไม่มี — **sharpe ceiling ต่ำกว่าทุก leg ที่เคย
ทดสอบในชุดงานวิจัยนี้ ทั้งที่ผ่านและตก** (อ่อนกว่า S48/MACD=0.158, S50/JudasSwing=0.135)

## บทสรุปสุดท้าย — ❌ REJECT (ไม่ถึงขั้น robustness/blend test เพราะ ceiling ต่ำกว่า threshold มาก)

**บทเรียนใหม่ (20):** candlestick pattern ที่ไม่ผูกกับ "ระดับราคา" เฉพาะใดๆ (price-action ล้วน)
ไม่มี edge จริงที่ M5 XAUUSD แม้จะนิยามเชิงปริมาณอย่างเข้มงวด (wick:body ratio) และมี sample ใหญ่
มาก (n=997, ไม่ใช่ small-sample illusion) — ยืนยันธีมหลักของทั้งโปรเจกต์ที่ค้นพบมาตั้งแต่ S37:
**"ระดับราคา" (level) คือตัวขับ edge ที่แท้จริง ไม่ใช่รูปร่างของแคนเดิลตัวเดียว** — pin bar/
rejection wick ที่ใช้ได้จริงในชุดนี้ (S37/S44/S49/S51) ทุกตัวต้องเช็คว่าเกิด "ที่ระดับ" ก่อน
(pivot/volume-node/VWAP-band/PDH-PDL) การถอดเงื่อนไขระดับออกแล้วเหลือแค่ shape ของแคนเดิลทำให้ edge
หายไปเกือบหมด

จบ S52 — standalone research/backtest-only 100%, ไม่ wire เข้า live, ไม่แก้ S1-S51 หรือไฟล์ระบบหลัก
