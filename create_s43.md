# S43 — Turtle Trading (Donchian channel breakout) — ❌ REJECTED

วันที่: 2026-06-27
สถานะ: ❌ **ตก — ไม่เพิ่มเข้า blend** (ตัวที่ 2 ที่ reject ต่อจาก S35 mean-reversion)

## ที่มา: ผู้ใช้รีเสิร์ชเพิ่มมาเป็นลิสต์ใหม่ — Turtle เป็นตัวแรกที่ชี้

Turtle Trading (Dennis/Eckhardt): Donchian channel breakout + ATR(2N) stop + pyramiding +
N-unit position sizing — pure trend-following classic

## กลไกที่ทดสอบ (adapt เข้า framework SL/TP)

BUY เมื่อราคาทะลุ highest-high ของ DONCHIAN_ENTRY_BARS แท่งก่อนหน้า, SELL เมื่อทะลุ lowest-low —
ATR-stop (2N) + RR-based TP (let winners run) แทน trailing Donchian exit ดั้งเดิม (engine ใช้
SL/TP คงที่) — ต่างจาก S34 (ต้องมี volume surge) ตรงที่ breakout ล้วน, ต่างจาก S37/S38 ที่ fade

## ผล: ไม่มี edge ที่ M5 XAUUSD — ตกทั้ง standalone และ blend

**Grid search 144 combos (60 วัน): config ที่ดีที่สุดทั้งกริด sharpe เพียง 0.077, PF 1.14** —
WR ต่ำ (34.6%), maxStreak 12 วัน, posDay 24.2% (แพ้เกือบทุกวัน!) — ต่ำกว่าทุก leg ที่เคยผ่าน
(S40/S41 ที่เป็น marginal ยังมี sharpe 0.36-0.74)

**Robustness check (top config db=80, sl=2.0, rr=2.0, htf_trend) ข้าม 7 window:**

| window | n | WR% | PF | posDay% | streak | sharpe |
|---|---|---|---|---|---|---|
| 30d | 45 | 42.2 | 1.55 | 37.5% | 7 | 0.246 |
| 45d | 69 | 37.7 | 1.26 | 25.0% | 10 | 0.133 |
| 60d | 81 | 34.6 | 1.14 | 24.2% | 12 | 0.077 |
| 90d | 111 | 33.3 | 1.06 | 22.9% | 12 | 0.032 |
| 120d | 146 | 35.6 | 1.23 | 27.6% | 12 | 0.098 |
| 150d | 191 | 37.2 | 1.25 | 25.4% | 12 | 0.104 |
| 180d | 247 | 37.2 | 1.27 | 29.9% | 12 | 0.113 |

**posDay 22-37% (แพ้เป็นส่วนใหญ่ของวัน) + maxStreak 12 วันทุก window** — ตรงข้ามกับเป้าหมาย
"กำไรต่อเนื่องสม่ำเสมอ" ของผู้ใช้โดยสิ้นเชิง

## Blend test (10-way) — ตัวตัดสินสุดท้าย: เพิ่ม $/mo นิดเดียวแต่ทำ sharpe แย่ลงทุก window

| window | 9-way $/mo | 10-way $/mo | 9-way sharpe | 10-way sharpe |
|---|---|---|---|---|
| 60d | $4001.4 | $4069.4 | **0.557** | 0.554 ▼ |
| 90d | $4089.0 | $4116.7 | **0.459** | 0.446 ▼ |
| 120d | $4065.8 | $4151.1 | **0.403** | 0.394 ▼ |
| 150d | $3717.7 | $3785.7 | **0.375** | 0.371 ▼ |
| 180d | $4135.2 | $4225.5 | **0.371** | 0.369 ▼ |

$/mo ดิบเพิ่ม +1.7-2.5% แต่ **sharpe แย่ลงทุก window (5/5)** — ผู้ใช้เน้น consistency (sharpe)
ไม่ใช่ $/mo ดิบ จึง **REJECT** (sanity-check 345 ไม้ ไม่มีบั๊ก — โค้ดถูก แต่ edge ไม่มีจริง)

## บทเรียน

**raw breakout / pure trend-following ใช้ไม่ได้ที่ M5 XAUUSD intraday** เพราะ microstructure ของ
ทองในเฟรมเล็กเป็น mean-reverting สูง (false breakout เยอะ) — สอดคล้องกับว่าทำไม leg ที่ชนะทั้งหมด
เป็น **pullback/fade เข้าหา level** (S37/S38/S39) หรือ **sweep-reversal** (S42) หรือ breakout
**ที่ต้องมี volume confirmation** (S34) — ไม่มี leg ไหนเป็น raw price breakout ล้วนๆเลย
→ เวลาเจอเทคนิค breakout/trend-following ใหม่ ให้คาดหวังว่าจะตกถ้าไม่มี filter พิเศษ (volume/
momentum divergence/level confluence)

champion ยังเป็น 9-way blend (A-I) เหมือนเดิม

จบ S43 (REJECTED) — standalone research/backtest-only 100%, ไม่ wire เข้า live, ไม่แก้ S1-S42
