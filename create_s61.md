# S61 — CYQONX Three-Line Mean Reversion — research/backtest-only

วันที่เริ่ม: 2026-07-02 (Codex/Alice)
สถานะ: กำลังวิจัย — ยังไม่ wire เข้า live

## ที่มา

ถอดจาก TikTok `@chxcrm21` / เว็บ `cyqonx.netlify.app` ที่อธิบาย CYQONX เป็น framework:

- Three-Line structure: upper / mean / lower
- quartile / position relative to equilibrium
- phase / cycle / energy / entropy
- Master Equation `M(t) = Φ · Ψ · Ω · Λ`

เวอร์ชัน S61 เลือกส่วนที่ทำ backtest ได้ก่อน:

- mean line = EMA/SMA
- upper/lower = mean ± deviation
- position `z = (close - mean) / deviation`
- phase turn = oscillator เริ่มกลับเข้าหา mean

## ไฟล์

- `strategy61.py`
- `sim_s61_backtest.py`
- `optimize_s61.py`
- `s61_backtest_summary.csv`

## Grid plan

Quick grid >50 combinations:

- mean period: 24, 48, 96
- deviation: ATR/STD, period 24/48
- entry z: 0.8, 1.0, 1.25
- phase lookback: 3, 4
- slope filter: none, mean_flat
- SL ATR: 0.8, 1.2
- TP mode: mean, rr
- RR: 0.8, 1.2

## สถานะล่าสุด

- [x] เลือกเลข strategy ถัดไป: S61
- [x] สร้าง strategy/backtest/optimizer
- [x] รัน grid search >= 50 combination
- [x] robust window check
- [x] sanity-check trade ตัวอย่าง
- [ ] สรุปว่าเป็น Champion candidate หรือ reject

## ผล baseline

Baseline 90 วัน (`mean=48`, `dev=ATR48`, `z=1.0`, `phase=3`, TP กลับ mean):

- signals = 2684
- compounding $/day = +15.25, PF = 1.18, DD = 53.5%
- fixed-lot $/day = -10.76, PF = 0.95

สรุป: baseline มี frequency สูงเกินและ compounding artifact ชัดเจน ต้องเชื่อ fixed-lot

## ผล grid

Quick grid 1152 combinations บน 90 วัน:

Best fixed-lot:

- config = `mp24_atr24_z1.0_ph4_mean_flat_sl0.8_mean_rr0.8`
- fixed PF = 1.732
- fixed $/day = +1.62
- sharpe = 0.267
- trades = 60
- max losing-day streak = 3

Top candidates ส่วนใหญ่ชี้ pattern เดียวกัน:

- mean period 24
- ATR band period 24
- entry z = 1.0
- phase lookback = 4
- slope filter = `mean_flat`
- TP กลับ mean

## Robust check

| Window | Trades | fixed $/day | fixed PF | Sharpe | Max losing-day streak |
|---|---:|---:|---:|---:|---:|
| 90d | 60 | +1.62 | 1.73 | 0.267 | 3 |
| 120d | 79 | +1.74 | 1.78 | 0.298 | 3 |
| 150d | 101 | +1.30 | 1.59 | 0.237 | 3 |
| 180d | 117 | +0.98 | 1.44 | 0.187 | 3 |

## Sanity-check trade sample

ผ่าน: BUY มี TP เหนือ entry / SL ใต้ entry, SELL มี TP ใต้ entry / SL เหนือ entry และ diff ตรง outcome

```text
2026-04-07 08:45 BUY  SL entry 4641.68 sl 4626.93 tp 4652.91 diff -14.75
2026-04-08 18:05 BUY  TP entry 4782.35 sl 4774.16 tp 4789.76 diff +7.41
2026-04-09 08:20 SELL TP entry 4720.91 sl 4729.31 tp 4713.43 diff +7.48
2026-04-17 10:15 SELL SL entry 4796.04 sl 4800.48 tp 4789.55 diff -4.44
```

## บทสรุปชั่วคราว

S61 เป็น edge จริงเชิง fixed-lot และตรง concept CYQONX Three-Line มากกว่า baseline:

- ไม่ใช่ Champion เดี่ยว เพราะ fixed $/day ยังเล็ก
- จุดแข็งคือความนิ่ง: max losing-day streak = 3 ทุก window 90-180 วัน
- เหมาะเป็น candidate leg ใหม่สำหรับ blend/correlation test กับ P13/P16

เทียบกับ S60:

- S60 AsiaBreakout: fixed $/day สูงกว่าเล็กน้อย (+2.4 ถึง +3.2 ใน 120-180d), streak 5-7
- S61 CYQONX: fixed $/day ต่ำกว่า (+1.0 ถึง +1.7), แต่ streak ต่ำกว่าและ PF/sharpe ดี
