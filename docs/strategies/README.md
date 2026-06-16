# เอกสารกลยุทธ์รายท่า (Per-Strategy Docs)

เอกสารชุดนี้แยกอธิบาย **แต่ละท่า** และ **แต่ละ pattern** โดยยึดตาม logic จริงในโค้ด
ใช้คู่กับ [`../strategies.md`](../strategies.md) (ภาพรวมรวมไฟล์เดียว) — ไฟล์รายท่านี้คือ
รายละเอียดเชิงลึก ถ้าข้อมูลขัดกัน ให้ยึดไฟล์รายท่า + source `strategyN.py` เป็นหลัก

## ดัชนีท่า

| ท่า | ชื่อ | ไฟล์ | ประเภท | Default |
|---|---|---|---|---|
| 1 | กลืนกิน / ตำหนิ / ย้อนโครงสร้าง | [s1.md](s1.md) | main-flow | ON |
| 2 | FVG (Fair Value Gap) | [s2.md](s2.md) | main-flow | ON |
| 3 | DM / SP / Marubozu | [s3.md](s3.md) | main-flow | ON |
| 4 | นัยยะสำคัญ FVG | [s4.md](s4.md) | main-flow | ON |
| 5 | Scalping (Momentum + Reversal) | [s5.md](s5.md) | main-flow | OFF |
| 6 / 7 | Trail ท่า 2/3 (S6) + S6i swing | [s6.md](s6.md) | management | — |
| 8 | กินไส้ Swing | [s8.md](s8.md) | main-flow | OFF* |
| 9 | RSI Divergence | [s9.md](s9.md) | standalone | ON |
| 10 | CRT TBS (Candle Range + Three Bar Sweep) | [s10.md](s10.md) | standalone | ON |
| 11 | Fibo S1 | [s11.md](s11.md) | hook (S1) | OFF |
| 12 | Range Trading | [s12.md](s12.md) | standalone | ON |
| 13 | EzAlgo V5 (Supertrend) | [s13.md](s13.md) | standalone | OFF |
| 14 | Sweep RSI | [s14.md](s14.md) | standalone | OFF |
| 15 | Volume Profile POC + Absorption | [s15.md](s15.md) | standalone | OFF |
| 16 | AMD x iFVG | [s16.md](s16.md) | standalone (M1) | OFF |
| 17 | Sweep Sniper | [s17.md](s17.md) | standalone (M1) | OFF |
| 18 | TJR / ICT Full-Confluence | [s18.md](s18.md) | standalone | OFF |
| 19 | ICT Advanced (Silver Bullet + Breaker + BPR) | [s19.md](s19.md) | standalone | OFF |

\* S8 ต้องเปิดรายตัว — ปุ่ม "เลือกทั้งหมด" ไม่เปิดให้

## รหัสที่ควรรู้

- `6` = S6 (trail ของ position ท่า 2/3), `7` = S6i (swing อิสระ)
- ท่า standalone = bypass/skip filter กลาง (trend filter, recheck ฯลฯ) — ดูตารางในแต่ละไฟล์
- comment ของ order: `{TF}_S{SID}_{PATTERN_CODE}` เช่น `M1_S1_PA`, `[M5_M15]_S2`

## โครงของแต่ละไฟล์

แต่ละไฟล์รายท่ามีหัวข้อประมาณนี้ (เท่าที่ท่านั้นมี):
แนวคิด → Pattern/Sub-pattern (เงื่อนไข BUY/SELL) → Entry/SL/TP → Order flow →
Standalone/Filter interaction → Config → State → Comment format → Backtest → หมายเหตุ
