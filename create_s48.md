# S48 — MACD crossover entry — ❌ REJECTED (last technique from list #2)

วันที่เริ่ม: 2026-06-27
สถานะ: ❌ ตก — เทคนิคสุดท้ายจากลิสต์รอบ 2 ของผู้ใช้ ปิดการสำรวจเทคนิคทั้งหมดแล้ว

## ที่มา: Momentum Module (MACD, RSI) จากลิสต์รอบ 2 — RSI ทำไปแล้วใน S41, เหลือ MACD

`strategy48.py` / `sim_s48_backtest.py`

## กลไก: MACD bullish/bearish crossover

MACD = EMA(FAST) - EMA(SLOW), signal line = EMA(SIGNAL) ของ MACD เข้า BUY ตอน MACD ตัดขึ้นเหนือ
signal line, SELL ตอนตัดลงต่ำกว่า — momentum entry ล้วน (lagging indicator แบบดั้งเดิม) ยืนยันด้วย
htf_trend ทางเลือก

## สำรวจพารามิเตอร์ — ceiling ต่ำกว่าทุก leg ที่ accept มาก

ทดสอบ macd period (12/26/9, 8/21/5, 5/13/3, 6/19/5) × SL_ATR_MULT∈{0.8,1.0,1.5} ×
TP_RR∈{1.0,1.5,2.0} × conf∈{none,htf_trend} × MIN_HIST_ATR∈{0.0,0.1} (144 combos, 90 วัน) — top คือ
**macd=8/21/5, sl=1.5, rr=1.0, conf=none, minh=0.1** → n=186, WR=54.8%, PF=1.21, sharpe=0.158,
$/mo=63.6 — **ceiling อ่อนกว่า SuperTrend (S47, sharpe 0.196) อีก**

## Robustness ข้าม 7 window — แทบไม่มี edge ที่ window ยาว (sharpe≈0, PF≈1.0)

| window | n | WR% | PF | DD% | sharpe | $/mo |
|---|---|---|---|---|---|---|
| 30d | 56 | 57.1 | 1.30 | 4.3 | 0.193 | $62.1 |
| 45d | 80 | 56.2 | 1.27 | 4.2 | 0.174 | $57.3 |
| 60d | 107 | 52.3 | 1.07 | 11.4 | 0.052 | $17.7 |
| 90d | 186 | 54.8 | 1.21 | 10.0 | 0.158 | $63.6 |
| 120d | 227 | 51.5 | 1.01 | 19.5 | 0.011 | $4.5 |
| 150d | 287 | 53.0 | 1.06 | 18.4 | 0.041 | $15.9 |
| 180d | 348 | 52.0 | 1.01 | 19.3 | 0.011 | $4.2 |

PF ที่ window ยาว (120d, 180d) เกือบเท่า 1.0 พอดี (1.01) sharpe เกือบ 0 (0.011) — เป็นสัญญาณว่าแทบ
ไม่มี edge จริง ดูเหมือนบวกได้บางช่วงโดยบังเอิญ (30-45d, 90d) มากกว่าจะเป็น edge ที่ยั่งยืน — สอดคล้อง
กับชื่อเสียงทั่วไปของ MACD ว่าเป็น lagging indicator ที่ false signal บ่อยในตลาด choppy แบบ M5 XAUUSD

## Sanity-check — ไม่มีบั๊ก

457 ไม้ (150 วัน): ไม่มีไม้ผิดกฎ SL/TP เลย (0/457)

## ❌ 14-way Blend Test — $/mo แทบไม่ขยับ + sharpe แย่ลงทุก window → REJECT

| window | 13-way เดิม $/mo | 14-way ใหม่ $/mo | 13-way sharpe | 14-way sharpe |
|---|---|---|---|---|
| 60d | $7400.2 | $7425.4 (+0.3%) | 0.570 | 0.566 (-0.7%) |
| 90d | $6945.0 | $6993.5 (+0.7%) | 0.461 | 0.460 (-0.2%) |
| 120d | $7547.2 | $7557.4 (+0.1%) | 0.426 | 0.421 (-1.2%) |
| 150d | $6853.1 | $6869.1 (+0.2%) | 0.398 | 0.393 (-1.3%) |
| 180d | $7449.5 | $7456.4 (+0.1%) | 0.399 | 0.395 (-1.0%) |

**$/mo เพิ่มขึ้นแค่ +0.1% ถึง +0.7% (อยู่ใน noise ไม่ใช่ contribution จริง) และ sharpe แย่ลงทุก
window (5/5, -0.2% ถึง -1.3%)** — เข้าเกณฑ์ reject ตามกฎที่ใช้กับ S43 (sharpe แย่ลงทุก window อย่าง
มีนัยสำคัญ) ยิ่งแย่กว่า S43 ตรงที่ $/mo ก็ไม่ได้เพิ่มขึ้นจริงด้วย (S43 อย่างน้อยยังเพิ่ม $/mo
+1.7-2.5% ทุก window) — S48 ไม่มีจุดเด่นด้านใดเลยเทียบกับ blend ปัจจุบัน

## สถานะ Exhaustion Checklist

1. [x] smoke test + grid search 144 combos (90 วัน) — ceiling sharpe=0.158, อ่อนกว่าทุก leg ที่
       accept มาก่อน ✅
2. [x] robustness check ข้าม 7 window — PF≈1.0/sharpe≈0 ที่ window ยาว (120d, 180d) ✅
3. [x] sanity-check trades (457 ไม้ที่ 150 วัน) — ไม่มีบั๊ก ✅
4. [x] ทดสอบ 14-way blend ข้าม 5 window เทียบ 13-way เดิม — $/mo แทบไม่ขยับ + sharpe แย่ลงทุก
       window → reject ✅
5. [x] เขียนสรุปลงไฟล์นี้ ✅

## บทสรุปสุดท้าย — ❌ REJECT — Champion ยังเป็น 13-way (A-N) เหมือนเดิม

S48 ไม่ผ่าน ไม่เพิ่มเข้า blend — champion ยังคงเป็น 13-way ตามที่บันทึกใน `create_s47.md`

**MACD เป็นเทคนิคสุดท้ายจากลิสต์รอบ 2 ของผู้ใช้ — ครบทุกเทคนิคที่ขอให้สำรวจแล้ว 100%**
(Turtle❌, Wyckoff≈ของเดิม, ICT/SMC≈ของเดิม, Price Action≈ของเดิม, Trend Following≈SuperTrend✅
marginal, Mean Reversion❌(S35), Opening Range Breakout✅ครั้งใหญ่, Volume Profile✅ครั้งใหญ่,
Market Profile≈Volume Profile, Quant/Stat Arb/Pair/Carry Trade=ใช้ไม่ได้กับ single instrument,
Grid Trading=ไม่ตรงกับเป้า consistency, Momentum Investing≈MACD❌/RSI✅, EMA/ADX/SuperTrend✅,
MACD❌/RSI✅, Liquidity Sweep/FVG/Order Block✅, ATR/Bollinger❌(S35), Session module=filter ทุก
leg, Risk module=ATR SL/position sizing/RR=ใช้อยู่แล้วทุก leg)

จบ S48 — standalone research/backtest-only 100%, ไม่ wire เข้า live, ไม่แก้ S1-S47 หรือไฟล์ระบบหลัก
