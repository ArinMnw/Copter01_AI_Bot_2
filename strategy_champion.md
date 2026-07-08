# Strategy Champion (P13) / Max-Yield Blend (P16) — เอกสารหลัก

วันที่สร้าง: 2026-07-01
สถานะ: ✅ Deploy บน demo account จริงแล้ว (IUXMarkets-Demo) ผ่าน Telegram

---

## คืออะไร

**Champion (P13)** และ **Max-Yield Blend (P16)** คือผลลัพธ์สุดท้ายจากงานวิจัยกลยุทธ์ XAUUSD
standalone (S21-S58 + blend/regime/exit optimization) — เป็น **portfolio ของหลายกลยุทธ์ที่รันพร้อม
กัน** ไม่ใช่กลยุทธ์เดี่ยว แต่ละตัวมี mechanism ต่างกันโดยสิ้นเชิง (decorrelated) รวมกันเพื่อลด
drawdown/ความผันผวนของผลตอบแทนรายวัน

| | **Champion (P13)** | **Max-Yield Blend (P16)** |
|---|---|---|
| จำนวน leg | 13 | 16 |
| Sharpe (backtest 60-180d) | 0.49 – 0.71 | 0.47 – 0.73 |
| Max losing-day streak | 3-4 วัน | 4-5 วัน |
| เหมาะกับ | **ความสม่ำเสมอ** (default แนะนำ) | เน้น**เงินสูงสุด** |

ทั้งสองไม่ใช่ "ตัวหนึ่งดีตัวหนึ่งแย่" — ทั้งคู่ผ่านการทดสอบแล้ว เป็นแค่ trade-off ระหว่าง
consistency กับ raw $ พี่เลือกได้ตามต้องการ

---

## 💰 กำไรที่คาดหวัง (แก้ไขแล้ว 2026-07-01 — ดูหัวข้อ "⚠️ แก้ไขตัวเลข" ด้านล่าง)

**ตัวเลขที่ถูกต้อง (fixed-lot 0.01, ไม่ทบต้น — ตรงกับที่ `demo_portfolio.py` ใช้จริงบน live):**

| Window | P13 $/เดือน | P13 $/วัน | P16 $/เดือน | P16 $/วัน |
|---|---|---|---|---|
| 30d | $6,670 | $222 | $7,870 | $262 |
| 60d | $4,558 | $152 | $5,457 | $182 |
| 90d | $2,540 | $85 | $2,560 | $85 |
| 120d | $2,477 | $83 | $2,592 | $86 |
| 150d | $1,898 | $63 | $1,865 | $62 |
| 180d | $2,160 | $72 | $2,266 | $76 |

**สังเกต:** ตัวเลขลดลงชัดเจนที่ window ยาวขึ้น (window สั้นๆ เจอ market condition ที่เข้ากับ config
พอดี ยังไม่ผ่านความหลากหลายพอ) — window 90-180 วัน ($1,900-2,600/เดือน) น่าเชื่อถือกว่า window 30-60
วัน ($4,500-7,900/เดือน) มาก เพราะ sample ใหญ่กว่าและเจอสภาพตลาดหลากหลายกว่า

**⚠️ ผลจริงบน demo (live) ตอนนี้ยังนับไม่ได้** เพราะเพิ่งรันมาไม่กี่ชั่วโมง (sample สั้นเกินไป) —
ต้องสะสมข้อมูลอย่างน้อย 30-60 วันก่อนถึงจะเทียบกับตัวเลขนี้ได้อย่างมีความหมาย ดูผลจริงสะสมได้จาก
`export_demo_portfolio_compare.py` → `strategy/demo_portfolio/excel/demo_portfolio_summary.csv`

### ⚠️ แก้ไขตัวเลข (2026-07-01) — เจอ compounding artifact ในตัวเลขเดิมที่เคยรายงาน

**ตัวเลขเดิมที่เคยรายงานผิด:** P13 $7,908-8,658/เดือน, P16 $8,442-9,319/เดือน — **สูงเกินจริงมาก**

**สาเหตุ:** backtest (ทั้งของ `backtest_demo_portfolio.py` และของงานวิจัยทั้งหมดตั้งแต่ S21-S58)
คำนวณ lot จาก `risk_usd = equity × risk_pct%` โดย **`equity` เป็นค่าที่ทบต้นขึ้นเรื่อยๆ** (ไม่ใช่ทุน
$1,000 คงที่) — พิสูจน์จาก equity curve จริงที่ backtest ให้: equity โตจาก $1,000 ไปถึง **$37,000+
ภายใน 120 วัน** ทำให้กำไรวันเดียวพุ่งถึง +$2,385 ในบางวัน (จาก lot ที่ใหญ่ขึ้นตามทุนที่โตขึ้น)

**แต่ `demo_portfolio.py` (ของจริงบน live) ใช้ `MIN_LOT = 0.01` คงที่ทุกไม้ ไม่ทบต้นเลย** — backtest
กับของจริงจึงมีวิธีคิดต่างกัน ตัวเลขเดิมจึง**สูงเกินจริง 3-5 เท่า** ที่ window ยาว

**ผลดี:** เพราะ live ใช้ lot คงที่ 100% **ระบบจะไม่มีทาง "ระเบิด" equity แบบที่เห็นใน backtest**
(นั่นเป็นแค่ artifact ทางคณิตศาสตร์ ไม่ใช่พฤติกรรมจริง) — แต่กำไรจริงจะต่ำกว่าที่เคยประเมินไว้มาก
ใช้ตัวเลขตารางด้านบน (fixed-lot) เป็นค่าอ้างอิงที่ถูกต้องแทน

---

## องค์ประกอบ (leg composition)

| Key | Strategy | กลไก | อยู่ใน P13 | อยู่ใน P16 |
|---|---|---|---|---|
| A | S31 | Engulfing pattern | ❌ | ✅ |
| B | S34 | Volume Breakout | ✅ | ✅ |
| C | S36 | FVG / ICT-SMC | ✅ | ✅ |
| D | S37 | S/R Pivot Bounce | ✅ | ✅ |
| E | S38 | Fibonacci OTE (Premium/Discount) | ❌ | ✅ |
| F | S39 | Demand/Supply Zone | ✅ | ✅ |
| G | S40 | Elliott Wave proxy | ✅ | ✅ |
| H | S41 | RSI Divergence | ✅ | ✅ |
| I | S42 | CRT sweep+reversal | ✅ | ✅ |
| K | S44 | Volume Profile (POC/VAH/VAL) | ✅ | ✅ |
| L | S45 | Order Block | ❌ | ✅ |
| M | S46 | Opening Range Breakout | ✅ | ✅ |
| N | S47 | SuperTrend flip | ✅ | ✅ |
| P | S49 | Session VWAP Bounce | ✅ | ✅ |
| Q | S51 | Prev-Day High/Low | ✅ | ✅ |
| R | **S56** | **Prev-Week High/Low Reversal** 🏆 | ✅ | ✅ |

**P13 = P16 ลบ A(S31)/E(S38)/L(S45)** — ทั้ง 3 ตัวนี้ผ่านการทดสอบ (ไม่ได้ "ตก") แต่จาก
leave-one-out analysis พบว่าเมื่อรวมกับ leg อื่นแล้วดึง sharpe ลง (เป็น "sharpe-drag") มากกว่าจะช่วย
— ถอดออกได้ blend ที่ sharpe ดีขึ้น 4/5 window แลกกับ $/mo ลดลง ~7-11%

**Leg R (S56) คือ contributor แรงที่สุด** (+0.088 sharpe จาก leave-one-out — มากกว่าทุก leg อื่นรวม
กัน) กลไก: ราคาแตะ high/low ของ**สัปดาห์ก่อนหน้า**แล้ว reject กลับ (counter-trend reversal ไม่ใช่
continuation) เป็น breakthrough หลักของงานวิจัยรอบนี้ (ดู `create_s56.md`)

---

## กลไกทำงานยังไง (ภาพรวม)

ทุก leg แบ่งเป็น 4 กลุ่มหลัก:

| กลุ่ม | ตัวอย่าง | หาอะไร |
|---|---|---|
| แตะระดับแล้วเด้งกลับ | D, K, P, Q, **R** | ราคาแตะระดับสำคัญ (pivot/volume-node/VWAP/prior H-L) แล้วปิดถอยห่างออก (rejection) |
| ทะลุกรอบ (breakout) | B, M | ราคาทะลุกรอบที่กำหนด + volume/momentum ยืนยัน |
| indicator | N, H | ทิศทางพลิก/divergence ระหว่างราคากับ indicator |
| pattern เฉพาะ | A, C, E, F, G, I, L | รูปแบบแท่งเทียน/โซนราคาเฉพาะทาง |

**ทุก leg ใช้ M5 เป็น entry timeframe** ยกเว้น scan interval ทุก 5 นาที บาง leg เพิ่ม HTF
confirmation (M15) หรือ weekly reference (W1, เฉพาะ R) — Entry/SL/TP คำนวณจาก **ATR** (ความผันผวน
ปัจจุบัน) ทุกครั้ง ไม่ใช่ค่าคงที่ SL_ATR_MULT/TP_RR ของแต่ละ leg มาจาก grid search ใน backtest แล้ว

**เข้าไม้:** Market order ทันทีที่ราคาตลาด (ไม่ใช่ pending/limit) — Lot คงที่ 0.01 ทุกไม้ — SL/TP
ฝากไว้กับ broker ตรงๆ ไม่มี trailing/breakeven (research พิสูจน์แล้วว่า fixed SL/TP ดีที่สุด ดู
`create_exit_optimization.md`)

---

## การ Deploy จริง (Live บน Demo)

### ควบคุมผ่าน Telegram

เมนู **"🧪 Demo Portfolio"** ในปุ่มหลัก — แสดงสถานะ + ปุ่มควบคุม:
```
[⏸️/▶️ P13]  [⏸️/▶️ P16]     ← เปิด/ปิดแยกอิสระ
[🔄 รีเฟรช]                   ← ดึงสถานะล่าสุด (ไม่กระทบการเทรด)
```
แสดง: จำนวนไม้วันนี้, โพซิชั่นเปิดอยู่, **กำไร/ขาดทุนแยกราย leg** (realized + floating, เฉลี่ย
ต่อวัน/เดือน)

### ค่า default

`config.DEMO_PORTFOLIO_ACTIVE = {"P13": True, "P16": True}` — **เปิดทั้งคู่โดย default** (ผู้ใช้
ยืนยันแล้ว 2026-07-01) หมายความว่าหลัง bot restart/คอมดับแล้วเปิดใหม่ ระบบจะเทรดจริงทันทีโดยไม่ต้อง
กด Telegram ยืนยันก่อน — ใช้ปุ่ม ⏸️ หยุดชั่วคราวได้ตามต้องการ

### ความเป็นอิสระจากบอทหลัก (S1-S20)

- **ไม่แตะ** `scanner.py` / `active_strategies` / `bot_state.json`'s save-load logic
- **Magic number แยก**: P13=990013, P16=990016 (บอทเดิมใช้ 234001 ตัวเดียวหมด)
- **Comment แยก**: `{TF}-P13-<leg>` / `{TF}-P16-<leg>` เช่น `M5-P13-D`
- **State แยก**: `demo_portfolio_state.json` (ไม่ใช้ `bot_state.json`)
- **วางออเดอร์ผ่าน `mt5.order_send()` ตรงๆ** ไม่ผ่าน `mt5_utils.open_order_market()` — เพราะจะโดน
  `ML_SCORING_ENABLED`/`SCALE_OUT_ENABLED` (เปิดอยู่โดย default ในบอทเดิม) เปลี่ยน volume/filter
  สัญญาณแบบไม่ตรงกับที่ backtest สมมติไว้

### ⚠️ บั๊กสำคัญที่เจอ+แก้แล้ว: generic position-management ของ S1-S20 เผลอปิดไม้เรา

`trailing.py` มีฟังก์ชัน generic (เช่น `check_fill_trend_recheck`, `SL Guard Group`,
`check_fill_pdfiboplus`) ที่สแกน**ทุกโพซิชั่นในสัญลักษณ์** แล้ว skip เฉพาะไม้ที่ `sid` อยู่ใน
skip-list — ไม้ของเราไม่เคยลงทะเบียน sid เลยจึงได้ `None` (ไม่ตรง skip-list ใดๆ) → หลุดเข้าไปโดน
บอทเดิมปิดก่อนถึง SL/TP จริง

**แก้โดย:** ลงทะเบียน `position_sid[ticket] = 21` ทันทีหลังวางออเดอร์สำเร็จ (ใน `demo_portfolio.py`)
— `sid=21` เป็นค่าที่ถูกจองไว้แล้วในทุก skip-list หลักของ `trailing.py` (ตรงกับ `strategy21.py` เดิม
ที่ import ไว้เฉยๆไม่เคยถูกเรียกจริง — ปลอดภัย ไม่ชนกับ strategy ไหน) — **ไม่ได้แก้ `trailing.py`
เลยแม้แต่บรรทัดเดียว** ใช้กลไก skip-list ที่มีอยู่แล้ว

ยืนยันจาก log จริง: ไม้ที่เปิด**ก่อน** deploy fix (8 ไม้) โดนบั๊กเดิม, ไม้ที่เปิด**หลัง** deploy
(23+ ไม้ ณ ตอนเช็คล่าสุด) ปิดตรง SL/TP จริงทุกไม้ ไม่มีบั๊กหลงเหลือ

### ⚠️ บั๊กที่เจอ+แก้แล้ว: MT5 account/symbol resolution

script รายงาน/backtest เคยต่อผิดบัญชี (`config.SYMBOL="XAUUSD"` ไม่มี suffix ไม่ตรงกับที่
IUXMarkets-Demo ต้องการ `.iux`) — แก้โดยใช้ `config.mt5_initialize(mt5)` แทน `mt5.initialize()`
ตรงๆ ในทุก script รายงาน/backtest — บังคับ login เข้าบัญชีที่ config.py กำหนดเสมอ + resolve symbol
อัตโนมัติ

---

## เครื่องมือ (scripts)

| ไฟล์ | ทำอะไร | อยู่ที่ |
|---|---|---|
| `demo_portfolio.py` | Engine หลัก — สแกนสัญญาณ + วางออเดอร์จริง (import โดย `main.py`) | project root (**ห้ามย้าย** — ผูกกับการ import ของบอท) |
| `backtest_demo_portfolio.py` | รัน backtest ของ P13/P16 (ดึง config จาก `demo_portfolio.py` โดยตรง) | `strategy/demo_portfolio/backtest-sim/` |
| `export_demo_portfolio_compare.py` | ดึงผลจริงจาก MT5 มาเทียบ (realized/floating PnL, TP/SL/OTHER) | `strategy/demo_portfolio/backtest-sim/` |
| `verify_signal_consistency.py` | เทียบ logic-level: ไม้จริง vs สิ่งที่ detect_s\<N\> ควรให้ผล ณ เวลานั้น | `strategy/demo_portfolio/backtest-sim/` |
| CSV ผลลัพธ์ทั้งหมด | `demo_portfolio_backtest_summary_<env>.csv`, `demo_portfolio_summary.csv`, `demo_portfolio_trades_detail.csv`, `signal_consistency_check.csv` | `strategy/demo_portfolio/excel/` |
| `handlers/btn_demo_portfolio.py` | เมนู Telegram | `handlers/` |

### คำสั่งที่ใช้บ่อย

```bash
cd strategy/demo_portfolio/backtest-sim

# Backtest (ดึง config จาก demo_portfolio.py ตรงๆ, ไม่มี drift) — --days = ขนาด window backtest
python backtest_demo_portfolio.py P13 --days 30,60,90,120,150,180 --env demo
python backtest_demo_portfolio.py all --env real   # ต้องตั้ง MT5_LOGIN_REAL/PASSWORD_REAL/SERVER_REAL ก่อน

# Compare กับผลจริงบน MT5 — --days = กรองไม้ที่จะดึงมาสรุป (ไม่ใส่ = ทุกไม้)
python export_demo_portfolio_compare.py all --days 7

# Verify logic-level: ไม้จริงตรงกับที่ backtest logic ควรให้ผล ณ เวลานั้นไหม
# --days = กรองไม้ที่จะตรวจ (ครอบคลุมทุก leg เท่ากัน ไม่ใช่แค่ N ไม้ล่าสุดรวม)
python verify_signal_consistency.py P13 --days 7
```

**`--env real`** (ใน `backtest_demo_portfolio.py`/`verify_signal_consistency.py`) ไม่ hardcode
credential บัญชีจริงไว้ในโค้ดเด็ดขาด — ต้องตั้ง environment variable เอง (`MT5_LOGIN_REAL`,
`MT5_PASSWORD_REAL`, `MT5_SERVER_REAL`) ทุกครั้งก่อนรัน ถ้าไม่ตั้งจะ error ทันทีพร้อมบอกวิธีตั้งค่า
(ไม่มี fallback ไปบัญชีอื่นแบบเงียบๆ)

**`verify_signal_consistency.py` ต้องใช้ `entry_bar_ts`** (MT5 timestamp ดิบที่ `demo_portfolio.py`
บันทึกไว้ตอนวางออเดอร์ตั้งแต่ 2026-07-01) — ไม้ที่ log ไว้ก่อนหน้านั้นจะถูก SKIP (ไม่มีเวลาดิบให้
fetch ย้อนหลังตรงเป๊ะ ไม่เดามั่ว)

---

## สรุปสถานะล่าสุด (2026-07-01)

- ✅ Deploy บน IUXMarkets-Demo แล้ว ทำงานถูกต้องตามที่ออกแบบ
- ✅ บั๊ก generic-management (sid=None) แก้แล้ว ยืนยันจาก log จริง
- ✅ บั๊ก account/symbol resolution แก้แล้วในทุก reporting script
- ✅ จัดระเบียบไฟล์ backtest/CSV เข้า `strategy/demo_portfolio/` ตาม convention เดียวกับ strategy อื่น (เช่น
  `strategy/s20.6/`)
- ✅ รองรับ `--env demo/real` สำหรับตอนพร้อมย้ายไปบัญชีจริงในอนาคต (ยังไม่ได้ตั้งค่า/ใช้งานจริง)

## เอกสารที่เกี่ยวข้อง

- `create_final_summary.md` — สรุปงานวิจัยทั้งหมด (S21-S58 + optimization)
- `create_s56.md` — รายละเอียด leg R (contributor หลัก)
- `create_blend_optimization.md` — leave-one-out analysis (ที่มาของ P13 vs P16)
- `create_exit_optimization.md` — ทำไมไม่มี trailing/breakeven
- `docs/new_strategy_research_template.md` — กฎกลางของงานวิจัยทั้งหมด
