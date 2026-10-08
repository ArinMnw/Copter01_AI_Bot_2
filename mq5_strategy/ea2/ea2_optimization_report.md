# EA2 MQ5 Input Optimization — 365 วัน / ทุก TF

ช่วง optimize: `2025-10-06 21:57:03` ถึง `2026-10-06 21:57:03` (BKK)  
ช่วง holdout ที่ไม่ใช้เลือกค่า: `2024-10-06 21:57:03` ถึง `2025-10-06 21:57:03` (BKK)  
TF ที่รันทุก candidate: `M1 M5 M15 M30 H1 H4 H12 D1`  
ขนาดสัญญาจำลอง: fixed `0.01 lot`

## วิธีค้นหา

- Greedy coordinate search 2 รอบ และ refinement รอบค่าชนะ
- ทุกครั้งที่เปลี่ยน input จะ backtest ครบทั้ง 8 TF
- Optimization evaluation 310 ชุด หรือ 2,480 individual-TF runs
- Validation/stress เพิ่มอีก 25 ชุด all-TF
- Magic number, สี, dashboard และ input แสดงผลไม่ถูก optimize เพราะไม่เปลี่ยน trade
- Risk% ไม่ถูก optimize เพื่อหลีกเลี่ยงการเลือกกำไรด้วยการเพิ่มความเสี่ยง
- ค่า BE ถูกบังคับให้ `trigger - lock >= 50 points` เพื่อหลีกเลี่ยงค่าที่ broker มีโอกาส reject จาก stop/freeze level

## Baseline MQ5 เดิม — optimize period

| TF | PnL | PF | Max DD | Trades |
|---|---:|---:|---:|---:|
| M1 | -12.29 | 1.00 | 195.84 | 4,428 |
| M5 | 265.52 | 1.34 | 29.76 | 825 |
| M15 | 260.91 | 2.34 | 26.01 | 241 |
| M30 | 43.29 | 1.32 | 25.56 | 125 |
| H1 | 9.10 | 1.12 | 11.05 | 59 |
| H4 | 14.59 | 2.22 | 4.99 | 13 |
| H12 | 14.00 | 4.50 | 4.00 | 5 |
| D1 | 0.00 | — | 0.00 | 0 |
| **รวม** | **595.12** | **1.11** | **182.34** | **5,696** |

## Practical all-TF candidate

ใช้สำหรับเปรียบเทียบ portfolio ทุก TF ไม่แนะนำให้ใส่ live M1 โดยตรง

| Input | MQ5 เดิม | Candidate |
|---|---:|---:|
| SL points | 200 | 350 |
| TP points | 600 | 5,000 |
| BE trigger / lock | 150 / 10 | 75 / 15 |
| Trail trigger / distance / step | 200 / 300 / 10 | 125 / 75 / 5 |
| Swing bars | 2 | 1 |
| Enter on BOS confirm | false | true |
| Fib OB filter | true | false |
| OB search bars | 20 | 5 |
| OB min bars before retest | 3 | 2 |
| Min leg points | 100 | 200 |
| OB max age | 50 | 0 (ไม่หมดอายุ) |
| Prefer deeper range | 300 | 100 |
| Max open positions | 2 | 1 |
| Session BKK | 08–22 | 00–24 |

ผล optimize period ที่ spread 20 points:

| TF | PnL | PF | Max DD | Trades |
|---|---:|---:|---:|---:|
| M1 | 7,770.57 | 1.57 | 60.15 | 15,535 |
| M5 | 6,316.68 | 2.91 | 24.50 | 3,904 |
| M15 | 3,674.40 | 4.15 | 22.48 | 1,248 |
| M30 | 2,573.70 | 4.66 | 23.65 | 624 |
| H1 | 1,632.29 | 4.43 | 17.50 | 362 |
| H4 | 568.47 | 7.02 | 17.50 | 70 |
| H12 | 281.68 | 8.32 | 11.28 | 28 |
| D1 | 190.61 | 10.08 | 3.50 | 16 |
| **รวม** | **23,008.40** | **2.18** | **43.62** | **21,787** |

Stress optimize period:

| Scenario | Combined PnL | PF | Max DD | TF บวก |
|---|---:|---:|---:|---:|
| Spread 30 | 20,157.21 | 1.96 | 56.75 | 8/8 |
| Spread 40 | 17,168.49 | 1.76 | 69.66 | 8/8 |
| Spread 50 | 14,416.83 | 1.59 | 115.94 | 8/8 |
| Slippage 20 | 17,183.23 | 1.76 | 69.66 | 8/8 |
| Commission $7/lot | 21,483.31 | 2.08 | 50.06 | 8/8 |
| Spread40 + slip10 + commission7 | 12,892.02 | 1.52 | 142.61 | 8/8 |

## Cost-aware M1 candidate

เลือกด้วย M1 net/max-DD ภายใต้ spread40 + slippage10 + commission $7/lot แต่ยังรันครบ 8 TF ทุก candidate

| Input | Candidate |
|---|---:|
| SL / TP | 1,200 / 5,000 |
| BE trigger / lock | 75 / 25 |
| Trail trigger / distance / step | 100 / 75 / 5 |
| Swing / BOS confirm | 1 / 1 |
| Enter on BOS / Fib filter | true / true |
| OB search / retest wait | 5 / 5 |
| Min leg / OB max age | 200 / 0 |
| Prefer deeper / max positions | 300 / 1 |
| Session | 00–24 BKK |

Optimize-period adverse-cost result: M1 `+$5,236.51`, PF `1.35`, DD `$202.32`; combined all TF `+$22,946.29`, PF `2.01`, DD `$105.45`; ทุก TF บวก

## Holdout จริง — ไม่ได้ใช้เลือกค่า

Cost-aware candidate, base cost (spread20, no slippage/commission):

| TF | PnL | PF | Max DD | Trades |
|---|---:|---:|---:|---:|
| M1 | 408.29 | 1.10 | 166.98 | 4,120 |
| M5 | 1,674.58 | 1.78 | 94.71 | 2,286 |
| M15 | 2,013.86 | 3.39 | 33.20 | 1,116 |
| M30 | 1,613.26 | 4.10 | 43.90 | 571 |
| H1 | 1,183.10 | 4.17 | 24.00 | 327 |
| H4 | 782.86 | 6.02 | 32.02 | 100 |
| H12 | 340.58 | 8.10 | 30.23 | 33 |
| D1 | 139.47 | 2.94 | 35.68 | 26 |

Cost-aware candidate, adverse cost:

- M1: `-$1,171.90`, PF `0.77`, DD `$1,174.88`
- M5–D1: ทุก TF ยังบวก

ค่า MQ5 เดิมบน holdout เดียวกันให้ M1 `-$625.84`, PF `0.80`, DD `$633.81` และ M5 `-$166.14`

## ข้อสรุป

- Optimization ทำให้ผล all-TF ดีขึ้นมาก และ holdout base-cost บวกครบทุก TF
- M1 ซึ่งเป็น TF live ของ EA2 ยังมี edge บาง: PF holdout เพียง 1.10 และพลิกติดลบเมื่อเพิ่มต้นทุน
- M5–D1 เสถียรกว่า M1 อย่างชัดเจน แต่ MQ5 ต้นฉบับ hard-wire M1 ดังนั้นถือเป็น research result
- ยังไม่ควรเปลี่ยน production config เป็น candidate โดยตรง ควร forward-test/demo พร้อมเก็บ spread, slippage, commission และ broker stop/freeze rejection จริงก่อน
- `TP=20,000` ให้ in-sample สูงสุด แต่ต่างจาก practical TP5,000 เพียงประมาณ 1.2% จึงเลือก 5,000 เพื่อลด boundary overfit
- Trail step1 ชนะ step5 เพียงไม่กี่ดอลลาร์ แต่ทำให้ส่งคำสั่งแก้ SL ถี่กว่า จึงเลือก step5 สำหรับ practical candidate

