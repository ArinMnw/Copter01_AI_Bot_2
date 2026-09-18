# 🏆 ผลการทดสอบและสถิติคู่ผสม Timeframe เชิงลึก (S20.14 Group 1 - 24 Multi-TF Optimization Summary)

เอกสารสรุปผลการทดสอบค้นหาคู่ผสม Timeframe สแกนสัญญาณใหม่สำหรับกลยุทธ์ **S20.14 ทั้ง 24 กลุ่ม** (ย้อนหลัง 365 วันเต็ม)
ทดสอบบน 8 กรอบเวลาหลัก: `M1`, `M5`, `M15`, `M30`, `H1`, `H4`, `H12`, `D1`

---

## 📌 1. ภาพรวมพอร์ตและการเปรียบเทียบ S20.1423 (Group 23 Multi-TF Engine)

กลยุทธ์หลัก **S20.1423 (Group 23)** มีผลการรันเปรียบเทียบระหว่าง 3 รูปแบบการส่งคำสั่งดังนี้:

| รูปแบบการรัน Group 23 | ประเภทออเดอร์ | จำนวนออเดอร์ | Win Rate (%) | Net PnL ($) | สถานะประเมิน |
|---|---|---|:---:|---|:---:|
| **Group 23 MTF (Standard)** | Market / Sweep | **1,435** | **63.2%** | **+$15,359.12** | 🏆 **กำไรสูงสุด & Win Rate 63.2%** |
| **Group 23 Live** | Live Execution Config | 1,395 | 39.6% | **+$717.25** | 🟢 บวกเสถียร |
| **Group 23 Limit** | Limit Retest Config | 1,114 | 39.6% | **+$205.55** | 🟢 บวกเสถียร |

---

## 📊 2. ตารางสรุปอันดับคู่ผสม Timeframe + Pattern ที่กำไรดีที่สุดของแต่ละ Group (Group 1 - 24)

| Group | ชื่อกลุ่มกลยุทธ์ | Pattern ที่ทำกำไรสูงสุด | TF ที่ดีที่สุด | จำนวนไม้ | Win Rate (%) | Net PnL ($) |
|:---:|---|---|:---:|---|:---:|---|
| **Group 1** | Primary Baseline Setup | GapSweep | **H1** | 99 | 57.6% | **+$1,118.26** |
| **Group 2** | Micro Retest Engine | GapSweep | **H1** | 99 | 57.6% | **+$1,118.26** |
| **Group 3** | Institutional Fibo Zone | Fibo | **H12** | 558 | 33.0% | **+$3,988.50** |
| **Group 4** | Liquidity Sweep Cluster | Fibo | **H12** | 371 | 21.8% | **+$1,721.99** |
| **Group 5** | FVG + Fibo Confluence | FVG/Fibo | **H1** | 2,555 | 50.5% | **+$13,441.73** |
| **Group 6** | Naiya Doji Volume Trap | Naiya Doji | **M30** | 19,354 | 12.3% | **+$15,443.00** |
| **Group 7** | Institutional Order Flow | Fibo | **H12** | 558 | 33.0% | **+$3,988.50** |
| **Group 8** | High-RR Trend Follower | Naiya Doji | **M30** | 19,354 | 12.3% | **+$15,443.00** |
| **Group 9** | Naiya High Volatility | Naiya Doji | **M30** | 19,354 | 14.0% | **+$18,858.08** |
| **Group 10** | Quant Fibo Expansion | Fibo | **H12** | 558 | 33.0% | **+$3,988.50** |
| **Group 11** | Fibo Multi-Layer Engine | Fibo | **H12** | 558 | 33.0% | **+$3,988.50** |
| **Group 12** | Master Naiya Cashflow Engine | Naiya | **H1** | 5,440 | 16.9% | **+$498,309.82** |
| **Group 13** | Institutional FVG Retest | FVG/FVG | **H1** | 119 | 44.5% | **+$1,988.37** |
| **Group 14** | GapSweep Momentum Filter | GapSweep | **H1** | 99 | 57.6% | **+$1,118.26** |
| **Group 15** | Macro Fibo Strategy | Fibo | **H12** | 558 | 26.0% | **+$2,765.22** |
| **Group 16** | Heavy Volume Scalper | Naiya Doji | **M30** | 19,354 | 12.3% | **+$15,443.00** |
| **Group 17** | Low Frequency Precision Engine | Naiya Doji | **H12** | 461 | 10.6% | **+$3,234.15** |
| **Group 18** | Divergence Momentum Capture | Naiya Doji | **M30** | 19,354 | 12.3% | **+$15,443.00** |
| **Group 19** | Order #34 Dedicated Filter | Order #34 Filter | - | 0 | 0.0% | $0.00 (กรองเฉพาะ Order 34) |
| **Group 20** | GapSweep Reversion Engine | GapSweep | **H1** | 99 | 57.6% | **+$1,118.26** |
| **Group 21** | ATR Volatility Filter | GapSweep | **H1** | 99 | 57.6% | **+$1,118.26** |
| **Group 22** | GapSweep M15 Dynamic Engine | GapSweep | **M15** | 230 | 10.0% | **+$2,582.91** |
| **Group 23** | S20.1423 Multi-Timeframe System Engine | MTF Multi-Asset System | **Multi** | 1,435 | **63.2%** | **+$15,359.12** |
| **Group 24** | FollowDiv Trend Capture | FollowDiv | **M15** | 508 | 16.3% | **+$1,171.06** |

---

## 🔍 3. รายละเอียดคู่ผสมและผลลัพธ์แยกตามราย Group (Group 1 - 24 Detailed Analysis)

### 🔹 Group 1: Primary Baseline Setup

- **Timeframe แนะนำที่ดีที่สุด:** **`H1`** ใน Pattern **`GapSweep`** (กำไรสุทธิ **+$1,118.26** | Win Rate `57.6%` | `99` ไม้)
- **ตารางคู่ผสมที่ทำกำไรได้ทั้งหมดใน Group นี้:**

| Pattern | Timeframe (TF) | จำนวนไม้ (Trades) | ชนะ (Wins) | Win Rate (%) | Net PnL ($) |
|---|:---:|---|---|:---:|---|
| GapSweep | `H1` | 99 | 57 | 57.6% | +$1,118.26 |
| FollowDiv | `M15` | 549 | 89 | 16.2% | +$1,075.41 |
| GapSweep | `M15` | 199 | 110 | 55.3% | +$980.27 |
| GapSweep | `H12` | 32 | 16 | 50.0% | +$900.19 |
| GapSweep | `D1` | 27 | 13 | 48.1% | +$898.80 |
| GapSweep | `M30` | 131 | 74 | 56.5% | +$584.70 |
| ATR | `M15` | 177 | 30 | 16.9% | +$544.90 |
| Fibo | `D1` | 1 | 1 | 100.0% | +$249.95 |
| FollowDiv | `H1` | 104 | 14 | 13.5% | +$172.51 |
| FollowDiv | `M30` | 228 | 39 | 17.1% | +$157.35 |
| ATR | `H1` | 58 | 11 | 19.0% | +$89.14 |
| Div/FollowDiv | `M15` | 12 | 1 | 8.3% | +$77.18 |
| Fibo/ATR | `M15` | 1 | 1 | 100.0% | +$33.08 |
| Div/FollowDiv | `H1` | 5 | 1 | 20.0% | +$31.11 |
| Fibo | `M15` | 14 | 6 | 42.9% | +$2.81 |


### 🔹 Group 2: Micro Retest Engine

- **Timeframe แนะนำที่ดีที่สุด:** **`H1`** ใน Pattern **`GapSweep`** (กำไรสุทธิ **+$1,118.26** | Win Rate `57.6%` | `99` ไม้)
- **ตารางคู่ผสมที่ทำกำไรได้ทั้งหมดใน Group นี้:**

| Pattern | Timeframe (TF) | จำนวนไม้ (Trades) | ชนะ (Wins) | Win Rate (%) | Net PnL ($) |
|---|:---:|---|---|:---:|---|
| GapSweep | `H1` | 99 | 57 | 57.6% | +$1,118.26 |
| FollowDiv | `M15` | 549 | 89 | 16.2% | +$1,075.41 |
| GapSweep | `M15` | 199 | 110 | 55.3% | +$980.27 |
| GapSweep | `H12` | 32 | 16 | 50.0% | +$900.19 |
| GapSweep | `D1` | 27 | 13 | 48.1% | +$898.80 |
| GapSweep | `M30` | 131 | 74 | 56.5% | +$584.70 |
| ATR | `M15` | 177 | 30 | 16.9% | +$544.90 |
| Fibo | `D1` | 1 | 1 | 100.0% | +$249.95 |
| FollowDiv | `H1` | 104 | 14 | 13.5% | +$172.51 |
| FollowDiv | `M30` | 228 | 39 | 17.1% | +$157.35 |
| ATR | `H1` | 58 | 11 | 19.0% | +$89.14 |
| Div/FollowDiv | `M15` | 12 | 1 | 8.3% | +$77.18 |
| Fibo/ATR | `M15` | 1 | 1 | 100.0% | +$33.08 |
| Div/FollowDiv | `H1` | 5 | 1 | 20.0% | +$31.11 |
| Fibo | `M15` | 14 | 6 | 42.9% | +$2.81 |


### 🔹 Group 3: Institutional Fibo Zone

- **Timeframe แนะนำที่ดีที่สุด:** **`H12`** ใน Pattern **`Fibo`** (กำไรสุทธิ **+$3,988.50** | Win Rate `33.0%` | `558` ไม้)
- **ตารางคู่ผสมที่ทำกำไรได้ทั้งหมดใน Group นี้:**

| Pattern | Timeframe (TF) | จำนวนไม้ (Trades) | ชนะ (Wins) | Win Rate (%) | Net PnL ($) |
|---|:---:|---|---|:---:|---|
| Fibo | `H12` | 558 | 184 | 33.0% | +$3,988.50 |
| GapSweep | `H1` | 99 | 57 | 57.6% | +$1,118.26 |
| GapSweep | `M15` | 199 | 110 | 55.3% | +$980.27 |
| GapSweep | `H12` | 32 | 16 | 50.0% | +$900.19 |
| GapSweep | `D1` | 27 | 13 | 48.1% | +$898.80 |
| GapSweep | `M30` | 131 | 74 | 56.5% | +$584.70 |
| Div/FollowDiv | `M15` | 1 | 1 | 100.0% | +$297.67 |
| ATR | `M30` | 19 | 6 | 31.6% | +$290.49 |
| FollowDiv | `M15` | 25 | 4 | 16.0% | +$272.21 |
| FollowDiv | `H1` | 15 | 3 | 20.0% | +$255.40 |
| Fibo/ATR | `D1` | 2 | 1 | 50.0% | +$213.55 |
| Fibo | `M15` | 53,597 | 20,924 | 39.0% | +$210.81 |
| Fibo/Fibo | `D1` | 4 | 3 | 75.0% | +$152.33 |
| ATR | `M15` | 27 | 3 | 11.1% | +$80.98 |
| ATR | `H1` | 10 | 3 | 30.0% | +$61.33 |
| Fibo/Fibo | `M15` | 14 | 10 | 71.4% | +$55.36 |
| Fibo/FollowDiv | `M15` | 540 | 149 | 27.6% | +$49.65 |
| Fibo/Fibo | `H1` | 5 | 3 | 60.0% | +$29.29 |
| Fibo/Fibo/ATR | `M15` | 1 | 1 | 100.0% | +$26.03 |
| Fibo/FollowDiv/ATR | `M30` | 2 | 1 | 50.0% | +$15.70 |


### 🔹 Group 4: Liquidity Sweep Cluster

- **Timeframe แนะนำที่ดีที่สุด:** **`H12`** ใน Pattern **`Fibo`** (กำไรสุทธิ **+$1,721.99** | Win Rate `21.8%` | `371` ไม้)
- **ตารางคู่ผสมที่ทำกำไรได้ทั้งหมดใน Group นี้:**

| Pattern | Timeframe (TF) | จำนวนไม้ (Trades) | ชนะ (Wins) | Win Rate (%) | Net PnL ($) |
|---|:---:|---|---|:---:|---|
| Fibo | `H12` | 371 | 81 | 21.8% | +$1,721.99 |
| GapSweep | `H1` | 99 | 57 | 57.6% | +$1,118.26 |
| GapSweep | `M15` | 199 | 110 | 55.3% | +$980.27 |
| GapSweep | `H12` | 32 | 16 | 50.0% | +$900.19 |
| GapSweep | `D1` | 27 | 13 | 48.1% | +$898.80 |
| Fibo | `D1` | 154 | 28 | 18.2% | +$852.49 |
| Fibo/FollowDiv | `M15` | 544 | 104 | 19.1% | +$701.00 |
| Fibo | `M15` | 39,340 | 10,782 | 27.4% | +$645.45 |
| GapSweep | `M30` | 131 | 74 | 56.5% | +$584.70 |
| FollowDiv | `M15` | 18 | 4 | 22.2% | +$493.80 |
| Div/FollowDiv | `M15` | 1 | 1 | 100.0% | +$297.67 |
| ATR | `H1` | 20 | 5 | 25.0% | +$274.25 |
| ATR | `M15` | 59 | 8 | 13.6% | +$241.73 |
| FollowDiv | `H1` | 10 | 2 | 20.0% | +$155.44 |
| Fibo/Fibo | `H1` | 5 | 3 | 60.0% | +$29.29 |
| Fibo/Fibo | `M15` | 13 | 5 | 38.5% | +$26.95 |
| Fibo/FollowDiv/ATR | `M30` | 2 | 1 | 50.0% | +$15.70 |


### 🔹 Group 5: FVG + Fibo Confluence

- **Timeframe แนะนำที่ดีที่สุด:** **`H1`** ใน Pattern **`FVG/Fibo`** (กำไรสุทธิ **+$13,441.73** | Win Rate `50.5%` | `2,555` ไม้)
- **ตารางคู่ผสมที่ทำกำไรได้ทั้งหมดใน Group นี้:**

| Pattern | Timeframe (TF) | จำนวนไม้ (Trades) | ชนะ (Wins) | Win Rate (%) | Net PnL ($) |
|---|:---:|---|---|:---:|---|
| FVG/Fibo | `H1` | 2,555 | 1,290 | 50.5% | +$13,441.73 |
| FVG/Fibo | `M30` | 3,980 | 1,912 | 48.0% | +$11,839.13 |
| FVG/Fibo | `H12` | 141 | 60 | 42.6% | +$4,375.17 |
| FVG/Fibo | `M15` | 4,780 | 2,014 | 42.1% | +$3,926.61 |
| FVG/Fibo | `D1` | 27 | 12 | 44.4% | +$1,923.73 |
| GapSweep | `H1` | 99 | 57 | 57.6% | +$1,118.26 |
| GapSweep | `M15` | 199 | 110 | 55.3% | +$980.27 |
| GapSweep | `H12` | 32 | 16 | 50.0% | +$900.19 |
| GapSweep | `D1` | 27 | 13 | 48.1% | +$898.80 |
| GapSweep | `M30` | 131 | 74 | 56.5% | +$584.70 |
| FollowDiv | `M15` | 23 | 4 | 17.4% | +$331.85 |
| Div/FollowDiv | `M15` | 1 | 1 | 100.0% | +$297.67 |
| FollowDiv | `H1` | 14 | 3 | 21.4% | +$292.85 |
| Fibo/ATR | `D1` | 2 | 1 | 50.0% | +$213.55 |
| FVG | `H1` | 484 | 73 | 15.1% | +$212.07 |
| ATR | `M30` | 18 | 5 | 27.8% | +$208.01 |
| FVG/Fibo/Div | `M30` | 13 | 6 | 46.2% | +$160.85 |
| ATR | `H1` | 7 | 3 | 42.9% | +$156.88 |
| Fibo/Fibo | `D1` | 4 | 3 | 75.0% | +$152.33 |
| FVG/Fibo/FollowDiv | `M15` | 45 | 17 | 37.8% | +$136.72 |
| ATR | `M15` | 25 | 3 | 12.0% | +$116.23 |
| FVG/ATR | `M30` | 1 | 1 | 100.0% | +$82.48 |
| FVG/Div | `H1` | 11 | 2 | 18.2% | +$80.36 |
| FollowDiv | `M30` | 15 | 3 | 20.0% | +$78.74 |
| Fibo/Fibo | `M15` | 14 | 9 | 64.3% | +$41.51 |
| FVG/Div | `M30` | 10 | 2 | 20.0% | +$34.44 |
| FVG/Fibo/FollowDiv/ATR | `M30` | 1 | 1 | 100.0% | +$31.77 |
| Fibo/Fibo | `H1` | 5 | 3 | 60.0% | +$29.29 |
| Fibo/Fibo/ATR | `M15` | 1 | 1 | 100.0% | +$26.03 |
| FVG/Fibo/ATR | `M30` | 24 | 11 | 45.8% | +$12.56 |
| FVG/Fibo/FollowDiv | `M30` | 29 | 13 | 44.8% | +$1.96 |


### 🔹 Group 6: Naiya Doji Volume Trap

- **Timeframe แนะนำที่ดีที่สุด:** **`M30`** ใน Pattern **`Naiya Doji`** (กำไรสุทธิ **+$15,443.00** | Win Rate `12.3%` | `19,354` ไม้)
- **ตารางคู่ผสมที่ทำกำไรได้ทั้งหมดใน Group นี้:**

| Pattern | Timeframe (TF) | จำนวนไม้ (Trades) | ชนะ (Wins) | Win Rate (%) | Net PnL ($) |
|---|:---:|---|---|:---:|---|
| Naiya Doji | `M30` | 19,354 | 2,390 | 12.3% | +$15,443.00 |
| Naiya Doji | `M15` | 40,320 | 4,726 | 11.7% | +$4,090.17 |
| Naiya | `M15` | 5,070 | 997 | 19.7% | +$3,812.69 |
| Naiya | `M30` | 2,602 | 548 | 21.1% | +$3,532.19 |
| Naiya Doji | `H12` | 461 | 49 | 10.6% | +$3,234.15 |
| GapSweep | `H1` | 99 | 57 | 57.6% | +$1,118.26 |
| FollowDiv | `M15` | 548 | 89 | 16.2% | +$1,081.49 |
| GapSweep | `M15` | 199 | 110 | 55.3% | +$980.27 |
| GapSweep | `H12` | 32 | 16 | 50.0% | +$900.19 |
| GapSweep | `D1` | 27 | 13 | 48.1% | +$898.80 |
| Naiya | `H1` | 1,270 | 255 | 20.1% | +$872.39 |
| Naiya Hidden | `M30` | 279 | 73 | 26.2% | +$602.08 |
| GapSweep | `M30` | 131 | 74 | 56.5% | +$584.70 |
| ATR | `M15` | 177 | 30 | 16.9% | +$544.90 |
| Fibo | `D1` | 1 | 1 | 100.0% | +$249.95 |
| FollowDiv | `M30` | 228 | 39 | 17.1% | +$157.35 |
| Div/FollowDiv | `M15` | 12 | 1 | 8.3% | +$77.18 |
| Fibo/Fibo | `M30` | 1 | 1 | 100.0% | +$69.13 |
| Div/FollowDiv | `H1` | 4 | 1 | 25.0% | +$44.14 |
| Naiya Hidden | `H12` | 12 | 2 | 16.7% | +$38.84 |
| Fibo/ATR | `M15` | 1 | 1 | 100.0% | +$33.08 |


### 🔹 Group 7: Institutional Order Flow

- **Timeframe แนะนำที่ดีที่สุด:** **`H12`** ใน Pattern **`Fibo`** (กำไรสุทธิ **+$3,988.50** | Win Rate `33.0%` | `558` ไม้)
- **ตารางคู่ผสมที่ทำกำไรได้ทั้งหมดใน Group นี้:**

| Pattern | Timeframe (TF) | จำนวนไม้ (Trades) | ชนะ (Wins) | Win Rate (%) | Net PnL ($) |
|---|:---:|---|---|:---:|---|
| Fibo | `H12` | 558 | 184 | 33.0% | +$3,988.50 |
| GapSweep | `H1` | 99 | 57 | 57.6% | +$1,118.26 |
| GapSweep | `M15` | 199 | 110 | 55.3% | +$980.27 |
| GapSweep | `H12` | 32 | 16 | 50.0% | +$900.19 |
| GapSweep | `D1` | 27 | 13 | 48.1% | +$898.80 |
| GapSweep | `M30` | 131 | 74 | 56.5% | +$584.70 |
| Div/FollowDiv | `M15` | 1 | 1 | 100.0% | +$297.67 |
| ATR | `M30` | 19 | 6 | 31.6% | +$290.49 |
| FollowDiv | `M15` | 25 | 4 | 16.0% | +$272.21 |
| FollowDiv | `H1` | 15 | 3 | 20.0% | +$255.40 |
| Fibo | `M15` | 53,595 | 20,924 | 39.0% | +$229.26 |
| Fibo/ATR | `D1` | 2 | 1 | 50.0% | +$213.55 |
| Fibo/Fibo | `D1` | 4 | 3 | 75.0% | +$152.33 |
| ATR | `M15` | 27 | 3 | 11.1% | +$80.98 |
| ATR | `H1` | 10 | 3 | 30.0% | +$61.33 |
| Fibo/FollowDiv | `M15` | 540 | 149 | 27.6% | +$49.65 |
| Fibo/Fibo | `M15` | 14 | 9 | 64.3% | +$41.51 |
| Fibo/Fibo | `H1` | 5 | 3 | 60.0% | +$29.29 |
| Fibo/Fibo/ATR | `M15` | 1 | 1 | 100.0% | +$26.03 |
| Fibo/FollowDiv/ATR | `M30` | 2 | 1 | 50.0% | +$15.70 |


### 🔹 Group 8: High-RR Trend Follower

- **Timeframe แนะนำที่ดีที่สุด:** **`M30`** ใน Pattern **`Naiya Doji`** (กำไรสุทธิ **+$15,443.00** | Win Rate `12.3%` | `19,354` ไม้)
- **ตารางคู่ผสมที่ทำกำไรได้ทั้งหมดใน Group นี้:**

| Pattern | Timeframe (TF) | จำนวนไม้ (Trades) | ชนะ (Wins) | Win Rate (%) | Net PnL ($) |
|---|:---:|---|---|:---:|---|
| Naiya Doji | `M30` | 19,354 | 2,390 | 12.3% | +$15,443.00 |
| Naiya Doji | `M15` | 40,319 | 4,726 | 11.7% | +$4,091.36 |
| Naiya | `M15` | 5,070 | 997 | 19.7% | +$3,812.69 |
| Naiya | `M30` | 2,602 | 548 | 21.1% | +$3,532.19 |
| Naiya Doji | `H12` | 461 | 49 | 10.6% | +$3,234.15 |
| GapSweep | `H1` | 99 | 57 | 57.6% | +$1,118.26 |
| FollowDiv | `M15` | 548 | 89 | 16.2% | +$1,081.49 |
| GapSweep | `M15` | 199 | 110 | 55.3% | +$980.27 |
| GapSweep | `H12` | 32 | 16 | 50.0% | +$900.19 |
| GapSweep | `D1` | 27 | 13 | 48.1% | +$898.80 |
| Naiya | `H1` | 1,270 | 255 | 20.1% | +$872.39 |
| Naiya Hidden | `M30` | 279 | 73 | 26.2% | +$602.08 |
| GapSweep | `M30` | 131 | 74 | 56.5% | +$584.70 |
| ATR | `M15` | 177 | 30 | 16.9% | +$544.90 |
| Fibo | `D1` | 1 | 1 | 100.0% | +$249.95 |
| FollowDiv | `M30` | 228 | 39 | 17.1% | +$157.35 |
| Div/FollowDiv | `M15` | 12 | 1 | 8.3% | +$77.18 |
| Div/FollowDiv | `H1` | 4 | 1 | 25.0% | +$44.14 |
| Naiya Hidden | `H12` | 12 | 2 | 16.7% | +$38.84 |
| Fibo/ATR | `M15` | 1 | 1 | 100.0% | +$33.08 |


### 🔹 Group 9: Naiya High Volatility

- **Timeframe แนะนำที่ดีที่สุด:** **`M30`** ใน Pattern **`Naiya Doji`** (กำไรสุทธิ **+$18,858.08** | Win Rate `14.0%` | `19,354` ไม้)
- **ตารางคู่ผสมที่ทำกำไรได้ทั้งหมดใน Group นี้:**

| Pattern | Timeframe (TF) | จำนวนไม้ (Trades) | ชนะ (Wins) | Win Rate (%) | Net PnL ($) |
|---|:---:|---|---|:---:|---|
| Naiya Doji | `M30` | 19,354 | 2,719 | 14.0% | +$18,858.08 |
| Naiya | `M30` | 2,602 | 399 | 15.3% | +$2,952.12 |
| Naiya Doji | `D1` | 196 | 72 | 36.7% | +$2,694.17 |
| Naiya | `H1` | 1,270 | 236 | 18.6% | +$1,667.53 |
| Naiya | `M15` | 5,070 | 675 | 13.3% | +$1,302.69 |
| GapSweep | `H1` | 99 | 57 | 57.6% | +$1,118.26 |
| GapSweep | `M15` | 199 | 110 | 55.3% | +$980.27 |
| Naiya Hidden | `M30` | 279 | 64 | 22.9% | +$973.10 |
| ATR | `H1` | 58 | 17 | 29.3% | +$900.92 |
| GapSweep | `H12` | 32 | 16 | 50.0% | +$900.19 |
| GapSweep | `D1` | 27 | 13 | 48.1% | +$898.80 |
| Naiya Doji | `M15` | 40,318 | 4,763 | 11.8% | +$680.34 |
| GapSweep | `M30` | 131 | 74 | 56.5% | +$584.70 |
| FollowDiv | `M15` | 548 | 61 | 11.1% | +$370.17 |
| Div | `H1` | 302 | 47 | 15.6% | +$224.42 |
| ATR | `M30` | 109 | 19 | 17.4% | +$178.47 |
| Div/FollowDiv | `M30` | 12 | 1 | 8.3% | +$92.55 |
| ATR | `H12` | 2 | 1 | 50.0% | +$67.18 |
| Div/FollowDiv | `H1` | 5 | 1 | 20.0% | +$62.12 |
| Fibo/ATR | `M15` | 1 | 1 | 100.0% | +$52.35 |
| Div/FollowDiv | `M15` | 12 | 1 | 8.3% | +$42.42 |
| Fibo | `D1` | 1 | 1 | 100.0% | +$39.97 |
| Naiya Hidden | `D1` | 7 | 4 | 57.1% | +$5.94 |


### 🔹 Group 10: Quant Fibo Expansion

- **Timeframe แนะนำที่ดีที่สุด:** **`H12`** ใน Pattern **`Fibo`** (กำไรสุทธิ **+$3,988.50** | Win Rate `33.0%` | `558` ไม้)
- **ตารางคู่ผสมที่ทำกำไรได้ทั้งหมดใน Group นี้:**

| Pattern | Timeframe (TF) | จำนวนไม้ (Trades) | ชนะ (Wins) | Win Rate (%) | Net PnL ($) |
|---|:---:|---|---|:---:|---|
| Fibo | `H12` | 558 | 184 | 33.0% | +$3,988.50 |
| GapSweep | `H1` | 99 | 57 | 57.6% | +$1,118.26 |
| GapSweep | `M15` | 199 | 110 | 55.3% | +$980.27 |
| GapSweep | `H12` | 32 | 16 | 50.0% | +$900.19 |
| GapSweep | `D1` | 27 | 13 | 48.1% | +$898.80 |
| GapSweep | `M30` | 131 | 74 | 56.5% | +$584.70 |
| Div/FollowDiv | `M15` | 1 | 1 | 100.0% | +$297.67 |
| ATR | `M30` | 19 | 6 | 31.6% | +$290.49 |
| FollowDiv | `M15` | 25 | 4 | 16.0% | +$272.21 |
| FollowDiv | `H1` | 15 | 3 | 20.0% | +$255.40 |
| Fibo | `M15` | 53,594 | 20,924 | 39.0% | +$235.63 |
| Fibo/ATR | `D1` | 2 | 1 | 50.0% | +$213.55 |
| Fibo/Fibo | `D1` | 4 | 3 | 75.0% | +$152.33 |
| ATR | `M15` | 27 | 3 | 11.1% | +$80.98 |
| ATR | `H1` | 10 | 3 | 30.0% | +$61.33 |
| Fibo/FollowDiv | `M15` | 540 | 149 | 27.6% | +$49.65 |
| Fibo/Fibo | `M15` | 14 | 9 | 64.3% | +$41.51 |
| Fibo/Fibo | `H1` | 5 | 3 | 60.0% | +$29.29 |
| Fibo/Fibo/ATR | `M15` | 1 | 1 | 100.0% | +$26.03 |
| Fibo/FollowDiv/ATR | `M30` | 2 | 1 | 50.0% | +$15.70 |


### 🔹 Group 11: Fibo Multi-Layer Engine

- **Timeframe แนะนำที่ดีที่สุด:** **`H12`** ใน Pattern **`Fibo`** (กำไรสุทธิ **+$3,988.50** | Win Rate `33.0%` | `558` ไม้)
- **ตารางคู่ผสมที่ทำกำไรได้ทั้งหมดใน Group นี้:**

| Pattern | Timeframe (TF) | จำนวนไม้ (Trades) | ชนะ (Wins) | Win Rate (%) | Net PnL ($) |
|---|:---:|---|---|:---:|---|
| Fibo | `H12` | 558 | 184 | 33.0% | +$3,988.50 |
| GapSweep | `H1` | 99 | 57 | 57.6% | +$1,118.26 |
| GapSweep | `M15` | 199 | 110 | 55.3% | +$980.27 |
| GapSweep | `H12` | 32 | 16 | 50.0% | +$900.19 |
| GapSweep | `D1` | 27 | 13 | 48.1% | +$898.80 |
| GapSweep | `M30` | 131 | 74 | 56.5% | +$584.70 |
| Div/FollowDiv | `M15` | 1 | 1 | 100.0% | +$297.67 |
| ATR | `M30` | 19 | 6 | 31.6% | +$290.49 |
| FollowDiv | `M15` | 25 | 4 | 16.0% | +$272.21 |
| FollowDiv | `H1` | 15 | 3 | 20.0% | +$255.40 |
| Fibo | `M15` | 53,593 | 20,924 | 39.0% | +$250.37 |
| Fibo/ATR | `D1` | 2 | 1 | 50.0% | +$213.55 |
| Fibo/Fibo | `D1` | 4 | 3 | 75.0% | +$152.33 |
| ATR | `M15` | 27 | 3 | 11.1% | +$80.98 |
| ATR | `H1` | 10 | 3 | 30.0% | +$61.33 |
| Fibo/FollowDiv | `M15` | 540 | 149 | 27.6% | +$49.65 |
| Fibo/Fibo | `M15` | 14 | 9 | 64.3% | +$41.51 |
| Fibo/Fibo | `H1` | 5 | 3 | 60.0% | +$29.29 |
| Fibo/Fibo/ATR | `M15` | 1 | 1 | 100.0% | +$26.03 |
| Fibo/FollowDiv/ATR | `M30` | 2 | 1 | 50.0% | +$15.70 |
| Fibo/Doji | `M30` | 5 | 1 | 20.0% | +$2.08 |


### 🔹 Group 12: Master Naiya Cashflow Engine

- **Timeframe แนะนำที่ดีที่สุด:** **`H1`** ใน Pattern **`Naiya`** (กำไรสุทธิ **+$498,309.82** | Win Rate `16.9%` | `5,440` ไม้)
- **ตารางคู่ผสมที่ทำกำไรได้ทั้งหมดใน Group นี้:**

| Pattern | Timeframe (TF) | จำนวนไม้ (Trades) | ชนะ (Wins) | Win Rate (%) | Net PnL ($) |
|---|:---:|---|---|:---:|---|
| Naiya | `H1` | 5,440 | 920 | 16.9% | +$498,309.82 |
| Naiya Doji | `M30` | 19,354 | 2,390 | 12.3% | +$15,443.00 |
| Naiya/Div | `H1` | 154 | 12 | 7.8% | +$8,956.42 |
| Naiya Doji | `M15` | 40,317 | 4,726 | 11.7% | +$4,093.74 |
| Naiya | `M15` | 5,070 | 997 | 19.7% | +$3,812.69 |
| Naiya | `M30` | 2,602 | 548 | 21.1% | +$3,532.19 |
| Naiya Doji | `H12` | 461 | 49 | 10.6% | +$3,234.15 |
| Naiya/FollowDiv | `H1` | 33 | 4 | 12.1% | +$3,050.01 |
| Naiya/ATR | `H1` | 30 | 10 | 33.3% | +$2,224.62 |
| Naiya/Doji | `H1` | 2 | 2 | 100.0% | +$1,643.81 |
| GapSweep | `H1` | 99 | 57 | 57.6% | +$1,118.26 |
| GapSweep | `M15` | 199 | 110 | 55.3% | +$980.27 |
| GapSweep | `H12` | 32 | 16 | 50.0% | +$900.19 |
| GapSweep | `D1` | 27 | 13 | 48.1% | +$898.80 |
| ATR | `H1` | 38 | 12 | 31.6% | +$651.72 |
| Naiya Hidden | `M30` | 279 | 73 | 26.2% | +$602.08 |
| GapSweep | `M30` | 131 | 74 | 56.5% | +$584.70 |
| FollowDiv | `M15` | 548 | 124 | 22.6% | +$552.38 |
| FollowDiv | `M30` | 228 | 55 | 24.1% | +$300.20 |
| Fibo | `D1` | 1 | 1 | 100.0% | +$249.95 |
| ATR | `M15` | 177 | 39 | 22.0% | +$143.75 |
| FollowDiv | `H1` | 74 | 13 | 17.6% | +$123.39 |
| Naiya Hidden | `H12` | 12 | 2 | 16.7% | +$38.84 |
| Fibo/ATR | `M15` | 1 | 1 | 100.0% | +$33.08 |


### 🔹 Group 13: Institutional FVG Retest

- **Timeframe แนะนำที่ดีที่สุด:** **`H1`** ใน Pattern **`FVG/FVG`** (กำไรสุทธิ **+$1,988.37** | Win Rate `44.5%` | `119` ไม้)
- **ตารางคู่ผสมที่ทำกำไรได้ทั้งหมดใน Group นี้:**

| Pattern | Timeframe (TF) | จำนวนไม้ (Trades) | ชนะ (Wins) | Win Rate (%) | Net PnL ($) |
|---|:---:|---|---|:---:|---|
| FVG/FVG | `H1` | 119 | 53 | 44.5% | +$1,988.37 |
| FollowDiv | `M15` | 508 | 83 | 16.3% | +$1,171.06 |
| GapSweep | `H1` | 99 | 57 | 57.6% | +$1,118.26 |
| GapSweep | `M15` | 199 | 110 | 55.3% | +$980.27 |
| GapSweep | `H12` | 32 | 16 | 50.0% | +$900.19 |
| GapSweep | `D1` | 27 | 13 | 48.1% | +$898.80 |
| GapSweep | `M30` | 131 | 74 | 56.5% | +$584.70 |
| ATR | `M15` | 163 | 27 | 16.6% | +$457.30 |
| FollowDiv | `M30` | 200 | 35 | 17.5% | +$414.87 |
| FVG/ATR | `H1` | 11 | 4 | 36.4% | +$356.68 |
| FVG/FollowDiv/FVG | `H1` | 2 | 2 | 100.0% | +$297.12 |
| Fibo | `D1` | 1 | 1 | 100.0% | +$249.95 |
| FollowDiv | `H1` | 90 | 12 | 13.3% | +$134.03 |
| FVG/ATR | `M15` | 14 | 3 | 21.4% | +$87.60 |
| ATR/FVG | `H1` | 2 | 1 | 50.0% | +$79.74 |
| Div/FollowDiv | `M15` | 12 | 1 | 8.3% | +$77.18 |
| Fibo/ATR | `M15` | 1 | 1 | 100.0% | +$33.08 |
| Div/FollowDiv | `H1` | 5 | 1 | 20.0% | +$31.11 |
| FVG/ATR | `M30` | 16 | 3 | 18.8% | +$29.40 |


### 🔹 Group 14: GapSweep Momentum Filter

- **Timeframe แนะนำที่ดีที่สุด:** **`H1`** ใน Pattern **`GapSweep`** (กำไรสุทธิ **+$1,118.26** | Win Rate `57.6%` | `99` ไม้)
- **ตารางคู่ผสมที่ทำกำไรได้ทั้งหมดใน Group นี้:**

| Pattern | Timeframe (TF) | จำนวนไม้ (Trades) | ชนะ (Wins) | Win Rate (%) | Net PnL ($) |
|---|:---:|---|---|:---:|---|
| GapSweep | `H1` | 99 | 57 | 57.6% | +$1,118.26 |
| FollowDiv | `M15` | 548 | 89 | 16.2% | +$1,081.49 |
| GapSweep | `M15` | 199 | 110 | 55.3% | +$980.27 |
| GapSweep | `H12` | 32 | 16 | 50.0% | +$900.19 |
| GapSweep | `D1` | 27 | 13 | 48.1% | +$898.80 |
| GapSweep | `M30` | 131 | 74 | 56.5% | +$584.70 |
| ATR | `M15` | 177 | 30 | 16.9% | +$544.90 |
| ATR/FVG | `H1` | 2 | 2 | 100.0% | +$357.33 |
| FollowDiv | `H1` | 81 | 12 | 14.8% | +$303.83 |
| Fibo | `D1` | 1 | 1 | 100.0% | +$249.95 |
| FollowDiv | `M30` | 228 | 39 | 17.1% | +$157.35 |
| ATR | `H1` | 58 | 11 | 19.0% | +$89.14 |
| Div/FollowDiv | `M15` | 12 | 1 | 8.3% | +$77.18 |
| Fibo/ATR | `M15` | 1 | 1 | 100.0% | +$33.08 |


### 🔹 Group 15: Macro Fibo Strategy

- **Timeframe แนะนำที่ดีที่สุด:** **`H12`** ใน Pattern **`Fibo`** (กำไรสุทธิ **+$2,765.22** | Win Rate `26.0%` | `558` ไม้)
- **ตารางคู่ผสมที่ทำกำไรได้ทั้งหมดใน Group นี้:**

| Pattern | Timeframe (TF) | จำนวนไม้ (Trades) | ชนะ (Wins) | Win Rate (%) | Net PnL ($) |
|---|:---:|---|---|:---:|---|
| Fibo | `H12` | 558 | 145 | 26.0% | +$2,765.22 |
| GapSweep | `H1` | 99 | 57 | 57.6% | +$1,118.26 |
| GapSweep | `M15` | 199 | 110 | 55.3% | +$980.27 |
| GapSweep | `H12` | 32 | 16 | 50.0% | +$900.19 |
| GapSweep | `D1` | 27 | 13 | 48.1% | +$898.80 |
| GapSweep | `M30` | 131 | 74 | 56.5% | +$584.70 |
| Div/FollowDiv | `M15` | 1 | 1 | 100.0% | +$297.67 |
| ATR | `M30` | 19 | 6 | 31.6% | +$290.49 |
| FollowDiv | `M15` | 25 | 4 | 16.0% | +$272.21 |
| FollowDiv | `H1` | 15 | 3 | 20.0% | +$255.40 |
| Fibo/Fibo | `D1` | 4 | 3 | 75.0% | +$152.33 |
| Fibo/ATR | `M30` | 114 | 44 | 38.6% | +$101.36 |
| ATR | `M15` | 27 | 3 | 11.1% | +$80.98 |
| ATR | `H1` | 10 | 3 | 30.0% | +$61.33 |
| Fibo/Fibo | `M15` | 13 | 9 | 69.2% | +$47.07 |
| Fibo/Fibo | `H1` | 5 | 3 | 60.0% | +$29.29 |
| Fibo/Fibo/ATR | `M15` | 1 | 1 | 100.0% | +$26.03 |
| Fibo/ATR | `H1` | 60 | 18 | 30.0% | +$25.22 |
| Fibo/FollowDiv/ATR | `M30` | 2 | 1 | 50.0% | +$15.70 |
| Fibo | `D1` | 243 | 47 | 19.3% | +$15.07 |


### 🔹 Group 16: Heavy Volume Scalper

- **Timeframe แนะนำที่ดีที่สุด:** **`M30`** ใน Pattern **`Naiya Doji`** (กำไรสุทธิ **+$15,443.00** | Win Rate `12.3%` | `19,354` ไม้)
- **ตารางคู่ผสมที่ทำกำไรได้ทั้งหมดใน Group นี้:**

| Pattern | Timeframe (TF) | จำนวนไม้ (Trades) | ชนะ (Wins) | Win Rate (%) | Net PnL ($) |
|---|:---:|---|---|:---:|---|
| Naiya Doji | `M30` | 19,354 | 2,390 | 12.3% | +$15,443.00 |
| Naiya Doji | `M15` | 40,313 | 4,726 | 11.7% | +$4,100.46 |
| Naiya | `M15` | 5,069 | 997 | 19.7% | +$3,816.15 |
| Naiya | `M30` | 2,602 | 548 | 21.1% | +$3,532.19 |
| Naiya Doji | `H12` | 461 | 49 | 10.6% | +$3,234.15 |
| GapSweep | `H1` | 99 | 57 | 57.6% | +$1,118.26 |
| FollowDiv | `M15` | 548 | 89 | 16.2% | +$1,081.49 |
| GapSweep | `M15` | 199 | 110 | 55.3% | +$980.27 |
| GapSweep | `H12` | 32 | 16 | 50.0% | +$900.19 |
| GapSweep | `D1` | 27 | 13 | 48.1% | +$898.80 |
| Naiya | `H1` | 1,270 | 255 | 20.1% | +$872.39 |
| Naiya Hidden | `M30` | 279 | 73 | 26.2% | +$602.08 |
| GapSweep | `M30` | 131 | 74 | 56.5% | +$584.70 |
| ATR | `M15` | 177 | 30 | 16.9% | +$544.90 |
| Fibo | `D1` | 1 | 1 | 100.0% | +$249.95 |
| FollowDiv | `H1` | 104 | 14 | 13.5% | +$172.51 |
| FollowDiv | `M30` | 228 | 39 | 17.1% | +$157.35 |
| ATR | `H1` | 58 | 11 | 19.0% | +$89.14 |
| Div/FollowDiv | `M15` | 12 | 1 | 8.3% | +$77.18 |
| Naiya Hidden | `H12` | 12 | 2 | 16.7% | +$38.84 |
| Fibo/ATR | `M15` | 1 | 1 | 100.0% | +$33.08 |
| Div/FollowDiv | `H1` | 5 | 1 | 20.0% | +$31.11 |


### 🔹 Group 17: Low Frequency Precision Engine

- **Timeframe แนะนำที่ดีที่สุด:** **`H12`** ใน Pattern **`Naiya Doji`** (กำไรสุทธิ **+$3,234.15** | Win Rate `10.6%` | `461` ไม้)
- **ตารางคู่ผสมที่ทำกำไรได้ทั้งหมดใน Group นี้:**

| Pattern | Timeframe (TF) | จำนวนไม้ (Trades) | ชนะ (Wins) | Win Rate (%) | Net PnL ($) |
|---|:---:|---|---|:---:|---|
| Naiya Doji | `H12` | 461 | 49 | 10.6% | +$3,234.15 |
| Naiya | `H1` | 1,270 | 255 | 20.1% | +$872.39 |
| Naiya FVG | `D1` | 3 | 1 | 33.3% | +$67.49 |
| Naiya Hidden | `H12` | 12 | 2 | 16.7% | +$38.84 |


### 🔹 Group 18: Divergence Momentum Capture

- **Timeframe แนะนำที่ดีที่สุด:** **`M30`** ใน Pattern **`Naiya Doji`** (กำไรสุทธิ **+$15,443.00** | Win Rate `12.3%` | `19,354` ไม้)
- **ตารางคู่ผสมที่ทำกำไรได้ทั้งหมดใน Group นี้:**

| Pattern | Timeframe (TF) | จำนวนไม้ (Trades) | ชนะ (Wins) | Win Rate (%) | Net PnL ($) |
|---|:---:|---|---|:---:|---|
| Naiya Doji | `M30` | 19,354 | 2,390 | 12.3% | +$15,443.00 |
| Naiya Doji | `M15` | 40,311 | 4,726 | 11.7% | +$4,103.82 |
| Naiya | `M15` | 5,069 | 997 | 19.7% | +$3,816.15 |
| Naiya | `M30` | 2,602 | 548 | 21.1% | +$3,532.19 |
| Naiya Doji | `H12` | 461 | 49 | 10.6% | +$3,234.15 |
| GapSweep | `H1` | 99 | 57 | 57.6% | +$1,118.26 |
| FollowDiv | `M15` | 548 | 89 | 16.2% | +$1,081.49 |
| GapSweep | `M15` | 199 | 110 | 55.3% | +$980.27 |
| GapSweep | `H12` | 32 | 16 | 50.0% | +$900.19 |
| GapSweep | `D1` | 27 | 13 | 48.1% | +$898.80 |
| Naiya | `H1` | 1,270 | 255 | 20.1% | +$872.39 |
| Naiya Hidden | `M30` | 279 | 73 | 26.2% | +$602.08 |
| GapSweep | `M30` | 131 | 74 | 56.5% | +$584.70 |
| ATR | `M15` | 177 | 30 | 16.9% | +$544.90 |
| Fibo | `D1` | 1 | 1 | 100.0% | +$249.95 |
| FollowDiv | `H1` | 104 | 14 | 13.5% | +$172.51 |
| FollowDiv | `M30` | 228 | 39 | 17.1% | +$157.35 |
| ATR | `H1` | 58 | 11 | 19.0% | +$89.14 |
| Div/FollowDiv | `M15` | 12 | 1 | 8.3% | +$77.18 |
| Naiya Hidden | `H12` | 12 | 2 | 16.7% | +$38.84 |
| Fibo/ATR | `M15` | 1 | 1 | 100.0% | +$33.08 |
| Div/FollowDiv | `H1` | 5 | 1 | 20.0% | +$31.11 |


### 🔹 Group 19: Order #34 Dedicated Filter

- **ลักษณะกลยุทธ์:** สคริปต์กรองสัญญาณเฉพาะ Order หมายเลข 34 (`target_orders = [34]`)
- **ผลการทดสอบ Multi-TF:** ไม่พบออเดอร์อื่นเกิดขึ้นในการรันย้อนหลัง 365 วันแบบ standalone ($0.00)

### 🔹 Group 20: GapSweep Reversion Engine

- **Timeframe แนะนำที่ดีที่สุด:** **`H1`** ใน Pattern **`GapSweep`** (กำไรสุทธิ **+$1,118.26** | Win Rate `57.6%` | `99` ไม้)
- **ตารางคู่ผสมที่ทำกำไรได้ทั้งหมดใน Group นี้:**

| Pattern | Timeframe (TF) | จำนวนไม้ (Trades) | ชนะ (Wins) | Win Rate (%) | Net PnL ($) |
|---|:---:|---|---|:---:|---|
| GapSweep | `H1` | 99 | 57 | 57.6% | +$1,118.26 |
| FollowDiv | `M15` | 548 | 89 | 16.2% | +$1,081.49 |
| GapSweep | `M15` | 199 | 110 | 55.3% | +$980.27 |
| GapSweep | `H12` | 32 | 16 | 50.0% | +$900.19 |
| GapSweep | `D1` | 27 | 13 | 48.1% | +$898.80 |
| GapSweep | `M30` | 131 | 74 | 56.5% | +$584.70 |
| ATR | `M15` | 177 | 30 | 16.9% | +$544.90 |
| Fibo | `D1` | 1 | 1 | 100.0% | +$249.95 |
| FollowDiv | `H1` | 104 | 14 | 13.5% | +$172.51 |
| FollowDiv | `M30` | 228 | 39 | 17.1% | +$157.35 |
| ATR | `H1` | 58 | 11 | 19.0% | +$89.14 |
| Div/FollowDiv | `M15` | 12 | 1 | 8.3% | +$77.18 |
| Fibo/ATR | `M15` | 1 | 1 | 100.0% | +$33.08 |
| Div/FollowDiv | `H1` | 5 | 1 | 20.0% | +$31.11 |


### 🔹 Group 21: ATR Volatility Filter

- **Timeframe แนะนำที่ดีที่สุด:** **`H1`** ใน Pattern **`GapSweep`** (กำไรสุทธิ **+$1,118.26** | Win Rate `57.6%` | `99` ไม้)
- **ตารางคู่ผสมที่ทำกำไรได้ทั้งหมดใน Group นี้:**

| Pattern | Timeframe (TF) | จำนวนไม้ (Trades) | ชนะ (Wins) | Win Rate (%) | Net PnL ($) |
|---|:---:|---|---|:---:|---|
| GapSweep | `H1` | 99 | 57 | 57.6% | +$1,118.26 |
| FollowDiv | `M15` | 548 | 89 | 16.2% | +$1,081.49 |
| GapSweep | `M15` | 199 | 110 | 55.3% | +$980.27 |
| GapSweep | `H12` | 32 | 16 | 50.0% | +$900.19 |
| GapSweep | `D1` | 27 | 13 | 48.1% | +$898.80 |
| GapSweep | `M30` | 131 | 74 | 56.5% | +$584.70 |
| ATR | `M15` | 177 | 30 | 16.9% | +$544.90 |
| Fibo | `D1` | 1 | 1 | 100.0% | +$249.95 |
| FollowDiv | `H1` | 104 | 14 | 13.5% | +$172.51 |
| FollowDiv | `M30` | 228 | 39 | 17.1% | +$157.35 |
| ATR | `H1` | 58 | 11 | 19.0% | +$89.14 |
| Div/FollowDiv | `M15` | 12 | 1 | 8.3% | +$77.18 |
| Fibo/ATR | `M15` | 1 | 1 | 100.0% | +$33.08 |
| Div/FollowDiv | `H1` | 5 | 1 | 20.0% | +$31.11 |


### 🔹 Group 22: GapSweep M15 Dynamic Engine

- **Timeframe แนะนำที่ดีที่สุด:** **`M15`** ใน Pattern **`GapSweep`** (กำไรสุทธิ **+$2,582.91** | Win Rate `10.0%` | `230` ไม้)
- **ตารางคู่ผสมที่ทำกำไรได้ทั้งหมดใน Group นี้:**

| Pattern | Timeframe (TF) | จำนวนไม้ (Trades) | ชนะ (Wins) | Win Rate (%) | Net PnL ($) |
|---|:---:|---|---|:---:|---|
| GapSweep | `M15` | 230 | 23 | 10.0% | +$2,582.91 |
| GapSweep | `M30` | 115 | 15 | 13.0% | +$1,877.61 |
| FollowDiv | `M15` | 548 | 89 | 16.2% | +$1,081.49 |
| ATR | `M15` | 177 | 30 | 16.9% | +$544.90 |
| Fibo | `D1` | 1 | 1 | 100.0% | +$249.95 |
| FollowDiv | `H1` | 104 | 14 | 13.5% | +$172.51 |
| FollowDiv | `M30` | 228 | 39 | 17.1% | +$157.35 |
| ATR | `H1` | 58 | 11 | 19.0% | +$89.14 |
| Div/FollowDiv | `M15` | 12 | 1 | 8.3% | +$77.18 |
| Fibo/ATR | `M15` | 1 | 1 | 100.0% | +$33.08 |
| Div/FollowDiv | `H1` | 5 | 1 | 20.0% | +$31.11 |


### 🔹 Group 23: S20.1423 Multi-Timeframe System Engine

- **ลักษณะกลยุทธ์:** สถาปัตยกรรม Multi-Timeframe (MTF) หลักสำหรับ S20.1423
- **ผลการทดสอบย่อย:**
  - โหมด **Standard MTF**: **+$15,359.12** | Trades: 1,435 | Win Rate **63.2%**
  - โหมด **Live Execution**: **+$717.25** | Trades: 1,395 | Win Rate 39.6%
  - โหมด **Limit Retest**: **+$205.55** | Trades: 1,114 | Win Rate 39.6%

### 🔹 Group 24: FollowDiv Trend Capture

- **Timeframe แนะนำที่ดีที่สุด:** **`M15`** ใน Pattern **`FollowDiv`** (กำไรสุทธิ **+$1,171.06** | Win Rate `16.3%` | `508` ไม้)
- **ตารางคู่ผสมที่ทำกำไรได้ทั้งหมดใน Group นี้:**

| Pattern | Timeframe (TF) | จำนวนไม้ (Trades) | ชนะ (Wins) | Win Rate (%) | Net PnL ($) |
|---|:---:|---|---|:---:|---|
| FollowDiv | `M15` | 508 | 83 | 16.3% | +$1,171.06 |
| GapSweep | `H1` | 99 | 57 | 57.6% | +$1,118.26 |
| GapSweep | `M15` | 199 | 110 | 55.3% | +$980.27 |
| GapSweep | `H12` | 32 | 16 | 50.0% | +$900.19 |
| GapSweep | `D1` | 27 | 13 | 48.1% | +$898.80 |
| GapSweep | `M30` | 131 | 74 | 56.5% | +$584.70 |
| ATR | `M15` | 163 | 27 | 16.6% | +$457.30 |
| FollowDiv | `M30` | 200 | 35 | 17.5% | +$414.87 |
| FVG/ATR | `H1` | 11 | 4 | 36.4% | +$356.68 |
| Fibo | `D1` | 1 | 1 | 100.0% | +$249.95 |
| FVG/FollowDiv | `H1` | 11 | 2 | 18.2% | +$88.94 |
| FVG/ATR | `M15` | 14 | 3 | 21.4% | +$87.60 |
| FollowDiv | `H1` | 93 | 12 | 12.9% | +$83.57 |
| Div/FollowDiv | `M15` | 12 | 1 | 8.3% | +$77.18 |
| Fibo/ATR | `M15` | 1 | 1 | 100.0% | +$33.08 |
| Div/FollowDiv | `H1` | 5 | 1 | 20.0% | +$31.11 |
| FVG/ATR | `M30` | 16 | 3 | 18.8% | +$29.40 |
| Group34 | `H1` | 21 | 6 | 28.6% | +$23.86 |


---

## 📋 4. ข้อมูลคู่ผสมทั้งหมด (Master Raw Data 405 Profitable Rows)

| Script | Pattern | TF | Trades | Wins | WinRate (%) | Net PnL ($) |
|---|---|:---:|---|---|:---:|---|
| v38_standalone_group1 | GapSweep | `H1` | 99 | 57 | 57.6% | +$1,118.26 |
| v38_standalone_group1 | FollowDiv | `M15` | 549 | 89 | 16.2% | +$1,075.41 |
| v38_standalone_group1 | GapSweep | `M15` | 199 | 110 | 55.3% | +$980.27 |
| v38_standalone_group1 | GapSweep | `H12` | 32 | 16 | 50.0% | +$900.19 |
| v38_standalone_group1 | GapSweep | `D1` | 27 | 13 | 48.1% | +$898.80 |
| v38_standalone_group1 | GapSweep | `M30` | 131 | 74 | 56.5% | +$584.70 |
| v38_standalone_group1 | ATR | `M15` | 177 | 30 | 16.9% | +$544.90 |
| v38_standalone_group1 | Fibo | `D1` | 1 | 1 | 100.0% | +$249.95 |
| v38_standalone_group1 | FollowDiv | `H1` | 104 | 14 | 13.5% | +$172.51 |
| v38_standalone_group1 | FollowDiv | `M30` | 228 | 39 | 17.1% | +$157.35 |
| v38_standalone_group1 | ATR | `H1` | 58 | 11 | 19.0% | +$89.14 |
| v38_standalone_group1 | Div/FollowDiv | `M15` | 12 | 1 | 8.3% | +$77.18 |
| v38_standalone_group1 | Fibo/ATR | `M15` | 1 | 1 | 100.0% | +$33.08 |
| v38_standalone_group1 | Div/FollowDiv | `H1` | 5 | 1 | 20.0% | +$31.11 |
| v38_standalone_group1 | Fibo | `M15` | 14 | 6 | 42.9% | +$2.81 |
| v38_standalone_group2 | GapSweep | `H1` | 99 | 57 | 57.6% | +$1,118.26 |
| v38_standalone_group2 | FollowDiv | `M15` | 549 | 89 | 16.2% | +$1,075.41 |
| v38_standalone_group2 | GapSweep | `M15` | 199 | 110 | 55.3% | +$980.27 |
| v38_standalone_group2 | GapSweep | `H12` | 32 | 16 | 50.0% | +$900.19 |
| v38_standalone_group2 | GapSweep | `D1` | 27 | 13 | 48.1% | +$898.80 |
| v38_standalone_group2 | GapSweep | `M30` | 131 | 74 | 56.5% | +$584.70 |
| v38_standalone_group2 | ATR | `M15` | 177 | 30 | 16.9% | +$544.90 |
| v38_standalone_group2 | Fibo | `D1` | 1 | 1 | 100.0% | +$249.95 |
| v38_standalone_group2 | FollowDiv | `H1` | 104 | 14 | 13.5% | +$172.51 |
| v38_standalone_group2 | FollowDiv | `M30` | 228 | 39 | 17.1% | +$157.35 |
| v38_standalone_group2 | ATR | `H1` | 58 | 11 | 19.0% | +$89.14 |
| v38_standalone_group2 | Div/FollowDiv | `M15` | 12 | 1 | 8.3% | +$77.18 |
| v38_standalone_group2 | Fibo/ATR | `M15` | 1 | 1 | 100.0% | +$33.08 |
| v38_standalone_group2 | Div/FollowDiv | `H1` | 5 | 1 | 20.0% | +$31.11 |
| v38_standalone_group2 | Fibo | `M15` | 14 | 6 | 42.9% | +$2.81 |
| v38_standalone_group3 | Fibo | `H12` | 558 | 184 | 33.0% | +$3,988.50 |
| v38_standalone_group3 | GapSweep | `H1` | 99 | 57 | 57.6% | +$1,118.26 |
| v38_standalone_group3 | GapSweep | `M15` | 199 | 110 | 55.3% | +$980.27 |
| v38_standalone_group3 | GapSweep | `H12` | 32 | 16 | 50.0% | +$900.19 |
| v38_standalone_group3 | GapSweep | `D1` | 27 | 13 | 48.1% | +$898.80 |
| v38_standalone_group3 | GapSweep | `M30` | 131 | 74 | 56.5% | +$584.70 |
| v38_standalone_group3 | Div/FollowDiv | `M15` | 1 | 1 | 100.0% | +$297.67 |
| v38_standalone_group3 | ATR | `M30` | 19 | 6 | 31.6% | +$290.49 |
| v38_standalone_group3 | FollowDiv | `M15` | 25 | 4 | 16.0% | +$272.21 |
| v38_standalone_group3 | FollowDiv | `H1` | 15 | 3 | 20.0% | +$255.40 |
| v38_standalone_group3 | Fibo/ATR | `D1` | 2 | 1 | 50.0% | +$213.55 |
| v38_standalone_group3 | Fibo | `M15` | 53,597 | 20,924 | 39.0% | +$210.81 |
| v38_standalone_group3 | Fibo/Fibo | `D1` | 4 | 3 | 75.0% | +$152.33 |
| v38_standalone_group3 | ATR | `M15` | 27 | 3 | 11.1% | +$80.98 |
| v38_standalone_group3 | ATR | `H1` | 10 | 3 | 30.0% | +$61.33 |
| v38_standalone_group3 | Fibo/Fibo | `M15` | 14 | 10 | 71.4% | +$55.36 |
| v38_standalone_group3 | Fibo/FollowDiv | `M15` | 540 | 149 | 27.6% | +$49.65 |
| v38_standalone_group3 | Fibo/Fibo | `H1` | 5 | 3 | 60.0% | +$29.29 |
| v38_standalone_group3 | Fibo/Fibo/ATR | `M15` | 1 | 1 | 100.0% | +$26.03 |
| v38_standalone_group3 | Fibo/FollowDiv/ATR | `M30` | 2 | 1 | 50.0% | +$15.70 |
| v38_standalone_group4 | Fibo | `H12` | 371 | 81 | 21.8% | +$1,721.99 |
| v38_standalone_group4 | GapSweep | `H1` | 99 | 57 | 57.6% | +$1,118.26 |
| v38_standalone_group4 | GapSweep | `M15` | 199 | 110 | 55.3% | +$980.27 |
| v38_standalone_group4 | GapSweep | `H12` | 32 | 16 | 50.0% | +$900.19 |
| v38_standalone_group4 | GapSweep | `D1` | 27 | 13 | 48.1% | +$898.80 |
| v38_standalone_group4 | Fibo | `D1` | 154 | 28 | 18.2% | +$852.49 |
| v38_standalone_group4 | Fibo/FollowDiv | `M15` | 544 | 104 | 19.1% | +$701.00 |
| v38_standalone_group4 | Fibo | `M15` | 39,340 | 10,782 | 27.4% | +$645.45 |
| v38_standalone_group4 | GapSweep | `M30` | 131 | 74 | 56.5% | +$584.70 |
| v38_standalone_group4 | FollowDiv | `M15` | 18 | 4 | 22.2% | +$493.80 |
| v38_standalone_group4 | Div/FollowDiv | `M15` | 1 | 1 | 100.0% | +$297.67 |
| v38_standalone_group4 | ATR | `H1` | 20 | 5 | 25.0% | +$274.25 |
| v38_standalone_group4 | ATR | `M15` | 59 | 8 | 13.6% | +$241.73 |
| v38_standalone_group4 | FollowDiv | `H1` | 10 | 2 | 20.0% | +$155.44 |
| v38_standalone_group4 | Fibo/Fibo | `H1` | 5 | 3 | 60.0% | +$29.29 |
| v38_standalone_group4 | Fibo/Fibo | `M15` | 13 | 5 | 38.5% | +$26.95 |
| v38_standalone_group4 | Fibo/FollowDiv/ATR | `M30` | 2 | 1 | 50.0% | +$15.70 |
| v38_standalone_group5 | FVG/Fibo | `H1` | 2,555 | 1,290 | 50.5% | +$13,441.73 |
| v38_standalone_group5 | FVG/Fibo | `M30` | 3,980 | 1,912 | 48.0% | +$11,839.13 |
| v38_standalone_group5 | FVG/Fibo | `H12` | 141 | 60 | 42.6% | +$4,375.17 |
| v38_standalone_group5 | FVG/Fibo | `M15` | 4,780 | 2,014 | 42.1% | +$3,926.61 |
| v38_standalone_group5 | FVG/Fibo | `D1` | 27 | 12 | 44.4% | +$1,923.73 |
| v38_standalone_group5 | GapSweep | `H1` | 99 | 57 | 57.6% | +$1,118.26 |
| v38_standalone_group5 | GapSweep | `M15` | 199 | 110 | 55.3% | +$980.27 |
| v38_standalone_group5 | GapSweep | `H12` | 32 | 16 | 50.0% | +$900.19 |
| v38_standalone_group5 | GapSweep | `D1` | 27 | 13 | 48.1% | +$898.80 |
| v38_standalone_group5 | GapSweep | `M30` | 131 | 74 | 56.5% | +$584.70 |
| v38_standalone_group5 | FollowDiv | `M15` | 23 | 4 | 17.4% | +$331.85 |
| v38_standalone_group5 | Div/FollowDiv | `M15` | 1 | 1 | 100.0% | +$297.67 |
| v38_standalone_group5 | FollowDiv | `H1` | 14 | 3 | 21.4% | +$292.85 |
| v38_standalone_group5 | Fibo/ATR | `D1` | 2 | 1 | 50.0% | +$213.55 |
| v38_standalone_group5 | FVG | `H1` | 484 | 73 | 15.1% | +$212.07 |
| v38_standalone_group5 | ATR | `M30` | 18 | 5 | 27.8% | +$208.01 |
| v38_standalone_group5 | FVG/Fibo/Div | `M30` | 13 | 6 | 46.2% | +$160.85 |
| v38_standalone_group5 | ATR | `H1` | 7 | 3 | 42.9% | +$156.88 |
| v38_standalone_group5 | Fibo/Fibo | `D1` | 4 | 3 | 75.0% | +$152.33 |
| v38_standalone_group5 | FVG/Fibo/FollowDiv | `M15` | 45 | 17 | 37.8% | +$136.72 |
| v38_standalone_group5 | ATR | `M15` | 25 | 3 | 12.0% | +$116.23 |
| v38_standalone_group5 | FVG/ATR | `M30` | 1 | 1 | 100.0% | +$82.48 |
| v38_standalone_group5 | FVG/Div | `H1` | 11 | 2 | 18.2% | +$80.36 |
| v38_standalone_group5 | FollowDiv | `M30` | 15 | 3 | 20.0% | +$78.74 |
| v38_standalone_group5 | Fibo/Fibo | `M15` | 14 | 9 | 64.3% | +$41.51 |
| v38_standalone_group5 | FVG/Div | `M30` | 10 | 2 | 20.0% | +$34.44 |
| v38_standalone_group5 | FVG/Fibo/FollowDiv/ATR | `M30` | 1 | 1 | 100.0% | +$31.77 |
| v38_standalone_group5 | Fibo/Fibo | `H1` | 5 | 3 | 60.0% | +$29.29 |
| v38_standalone_group5 | Fibo/Fibo/ATR | `M15` | 1 | 1 | 100.0% | +$26.03 |
| v38_standalone_group5 | FVG/Fibo/ATR | `M30` | 24 | 11 | 45.8% | +$12.56 |
| v38_standalone_group5 | FVG/Fibo/FollowDiv | `M30` | 29 | 13 | 44.8% | +$1.96 |
| v38_standalone_group6 | Naiya Doji | `M30` | 19,354 | 2,390 | 12.3% | +$15,443.00 |
| v38_standalone_group6 | Naiya Doji | `M15` | 40,320 | 4,726 | 11.7% | +$4,090.17 |
| v38_standalone_group6 | Naiya | `M15` | 5,070 | 997 | 19.7% | +$3,812.69 |
| v38_standalone_group6 | Naiya | `M30` | 2,602 | 548 | 21.1% | +$3,532.19 |
| v38_standalone_group6 | Naiya Doji | `H12` | 461 | 49 | 10.6% | +$3,234.15 |
| v38_standalone_group6 | GapSweep | `H1` | 99 | 57 | 57.6% | +$1,118.26 |
| v38_standalone_group6 | FollowDiv | `M15` | 548 | 89 | 16.2% | +$1,081.49 |
| v38_standalone_group6 | GapSweep | `M15` | 199 | 110 | 55.3% | +$980.27 |
| v38_standalone_group6 | GapSweep | `H12` | 32 | 16 | 50.0% | +$900.19 |
| v38_standalone_group6 | GapSweep | `D1` | 27 | 13 | 48.1% | +$898.80 |
| v38_standalone_group6 | Naiya | `H1` | 1,270 | 255 | 20.1% | +$872.39 |
| v38_standalone_group6 | Naiya Hidden | `M30` | 279 | 73 | 26.2% | +$602.08 |
| v38_standalone_group6 | GapSweep | `M30` | 131 | 74 | 56.5% | +$584.70 |
| v38_standalone_group6 | ATR | `M15` | 177 | 30 | 16.9% | +$544.90 |
| v38_standalone_group6 | Fibo | `D1` | 1 | 1 | 100.0% | +$249.95 |
| v38_standalone_group6 | FollowDiv | `M30` | 228 | 39 | 17.1% | +$157.35 |
| v38_standalone_group6 | Div/FollowDiv | `M15` | 12 | 1 | 8.3% | +$77.18 |
| v38_standalone_group6 | Fibo/Fibo | `M30` | 1 | 1 | 100.0% | +$69.13 |
| v38_standalone_group6 | Div/FollowDiv | `H1` | 4 | 1 | 25.0% | +$44.14 |
| v38_standalone_group6 | Naiya Hidden | `H12` | 12 | 2 | 16.7% | +$38.84 |
| v38_standalone_group6 | Fibo/ATR | `M15` | 1 | 1 | 100.0% | +$33.08 |
| v38_standalone_group7 | Fibo | `H12` | 558 | 184 | 33.0% | +$3,988.50 |
| v38_standalone_group7 | GapSweep | `H1` | 99 | 57 | 57.6% | +$1,118.26 |
| v38_standalone_group7 | GapSweep | `M15` | 199 | 110 | 55.3% | +$980.27 |
| v38_standalone_group7 | GapSweep | `H12` | 32 | 16 | 50.0% | +$900.19 |
| v38_standalone_group7 | GapSweep | `D1` | 27 | 13 | 48.1% | +$898.80 |
| v38_standalone_group7 | GapSweep | `M30` | 131 | 74 | 56.5% | +$584.70 |
| v38_standalone_group7 | Div/FollowDiv | `M15` | 1 | 1 | 100.0% | +$297.67 |
| v38_standalone_group7 | ATR | `M30` | 19 | 6 | 31.6% | +$290.49 |
| v38_standalone_group7 | FollowDiv | `M15` | 25 | 4 | 16.0% | +$272.21 |
| v38_standalone_group7 | FollowDiv | `H1` | 15 | 3 | 20.0% | +$255.40 |
| v38_standalone_group7 | Fibo | `M15` | 53,595 | 20,924 | 39.0% | +$229.26 |
| v38_standalone_group7 | Fibo/ATR | `D1` | 2 | 1 | 50.0% | +$213.55 |
| v38_standalone_group7 | Fibo/Fibo | `D1` | 4 | 3 | 75.0% | +$152.33 |
| v38_standalone_group7 | ATR | `M15` | 27 | 3 | 11.1% | +$80.98 |
| v38_standalone_group7 | ATR | `H1` | 10 | 3 | 30.0% | +$61.33 |
| v38_standalone_group7 | Fibo/FollowDiv | `M15` | 540 | 149 | 27.6% | +$49.65 |
| v38_standalone_group7 | Fibo/Fibo | `M15` | 14 | 9 | 64.3% | +$41.51 |
| v38_standalone_group7 | Fibo/Fibo | `H1` | 5 | 3 | 60.0% | +$29.29 |
| v38_standalone_group7 | Fibo/Fibo/ATR | `M15` | 1 | 1 | 100.0% | +$26.03 |
| v38_standalone_group7 | Fibo/FollowDiv/ATR | `M30` | 2 | 1 | 50.0% | +$15.70 |
| v38_standalone_group8 | Naiya Doji | `M30` | 19,354 | 2,390 | 12.3% | +$15,443.00 |
| v38_standalone_group8 | Naiya Doji | `M15` | 40,319 | 4,726 | 11.7% | +$4,091.36 |
| v38_standalone_group8 | Naiya | `M15` | 5,070 | 997 | 19.7% | +$3,812.69 |
| v38_standalone_group8 | Naiya | `M30` | 2,602 | 548 | 21.1% | +$3,532.19 |
| v38_standalone_group8 | Naiya Doji | `H12` | 461 | 49 | 10.6% | +$3,234.15 |
| v38_standalone_group8 | GapSweep | `H1` | 99 | 57 | 57.6% | +$1,118.26 |
| v38_standalone_group8 | FollowDiv | `M15` | 548 | 89 | 16.2% | +$1,081.49 |
| v38_standalone_group8 | GapSweep | `M15` | 199 | 110 | 55.3% | +$980.27 |
| v38_standalone_group8 | GapSweep | `H12` | 32 | 16 | 50.0% | +$900.19 |
| v38_standalone_group8 | GapSweep | `D1` | 27 | 13 | 48.1% | +$898.80 |
| v38_standalone_group8 | Naiya | `H1` | 1,270 | 255 | 20.1% | +$872.39 |
| v38_standalone_group8 | Naiya Hidden | `M30` | 279 | 73 | 26.2% | +$602.08 |
| v38_standalone_group8 | GapSweep | `M30` | 131 | 74 | 56.5% | +$584.70 |
| v38_standalone_group8 | ATR | `M15` | 177 | 30 | 16.9% | +$544.90 |
| v38_standalone_group8 | Fibo | `D1` | 1 | 1 | 100.0% | +$249.95 |
| v38_standalone_group8 | FollowDiv | `M30` | 228 | 39 | 17.1% | +$157.35 |
| v38_standalone_group8 | Div/FollowDiv | `M15` | 12 | 1 | 8.3% | +$77.18 |
| v38_standalone_group8 | Div/FollowDiv | `H1` | 4 | 1 | 25.0% | +$44.14 |
| v38_standalone_group8 | Naiya Hidden | `H12` | 12 | 2 | 16.7% | +$38.84 |
| v38_standalone_group8 | Fibo/ATR | `M15` | 1 | 1 | 100.0% | +$33.08 |
| v38_standalone_group9 | Naiya Doji | `M30` | 19,354 | 2,719 | 14.0% | +$18,858.08 |
| v38_standalone_group9 | Naiya | `M30` | 2,602 | 399 | 15.3% | +$2,952.12 |
| v38_standalone_group9 | Naiya Doji | `D1` | 196 | 72 | 36.7% | +$2,694.17 |
| v38_standalone_group9 | Naiya | `H1` | 1,270 | 236 | 18.6% | +$1,667.53 |
| v38_standalone_group9 | Naiya | `M15` | 5,070 | 675 | 13.3% | +$1,302.69 |
| v38_standalone_group9 | GapSweep | `H1` | 99 | 57 | 57.6% | +$1,118.26 |
| v38_standalone_group9 | GapSweep | `M15` | 199 | 110 | 55.3% | +$980.27 |
| v38_standalone_group9 | Naiya Hidden | `M30` | 279 | 64 | 22.9% | +$973.10 |
| v38_standalone_group9 | ATR | `H1` | 58 | 17 | 29.3% | +$900.92 |
| v38_standalone_group9 | GapSweep | `H12` | 32 | 16 | 50.0% | +$900.19 |
| v38_standalone_group9 | GapSweep | `D1` | 27 | 13 | 48.1% | +$898.80 |
| v38_standalone_group9 | Naiya Doji | `M15` | 40,318 | 4,763 | 11.8% | +$680.34 |
| v38_standalone_group9 | GapSweep | `M30` | 131 | 74 | 56.5% | +$584.70 |
| v38_standalone_group9 | FollowDiv | `M15` | 548 | 61 | 11.1% | +$370.17 |
| v38_standalone_group9 | Div | `H1` | 302 | 47 | 15.6% | +$224.42 |
| v38_standalone_group9 | ATR | `M30` | 109 | 19 | 17.4% | +$178.47 |
| v38_standalone_group9 | Div/FollowDiv | `M30` | 12 | 1 | 8.3% | +$92.55 |
| v38_standalone_group9 | ATR | `H12` | 2 | 1 | 50.0% | +$67.18 |
| v38_standalone_group9 | Div/FollowDiv | `H1` | 5 | 1 | 20.0% | +$62.12 |
| v38_standalone_group9 | Fibo/ATR | `M15` | 1 | 1 | 100.0% | +$52.35 |
| v38_standalone_group9 | Div/FollowDiv | `M15` | 12 | 1 | 8.3% | +$42.42 |
| v38_standalone_group9 | Fibo | `D1` | 1 | 1 | 100.0% | +$39.97 |
| v38_standalone_group9 | Naiya Hidden | `D1` | 7 | 4 | 57.1% | +$5.94 |
| v38_standalone_group10 | Fibo | `H12` | 558 | 184 | 33.0% | +$3,988.50 |
| v38_standalone_group10 | GapSweep | `H1` | 99 | 57 | 57.6% | +$1,118.26 |
| v38_standalone_group10 | GapSweep | `M15` | 199 | 110 | 55.3% | +$980.27 |
| v38_standalone_group10 | GapSweep | `H12` | 32 | 16 | 50.0% | +$900.19 |
| v38_standalone_group10 | GapSweep | `D1` | 27 | 13 | 48.1% | +$898.80 |
| v38_standalone_group10 | GapSweep | `M30` | 131 | 74 | 56.5% | +$584.70 |
| v38_standalone_group10 | Div/FollowDiv | `M15` | 1 | 1 | 100.0% | +$297.67 |
| v38_standalone_group10 | ATR | `M30` | 19 | 6 | 31.6% | +$290.49 |
| v38_standalone_group10 | FollowDiv | `M15` | 25 | 4 | 16.0% | +$272.21 |
| v38_standalone_group10 | FollowDiv | `H1` | 15 | 3 | 20.0% | +$255.40 |
| v38_standalone_group10 | Fibo | `M15` | 53,594 | 20,924 | 39.0% | +$235.63 |
| v38_standalone_group10 | Fibo/ATR | `D1` | 2 | 1 | 50.0% | +$213.55 |
| v38_standalone_group10 | Fibo/Fibo | `D1` | 4 | 3 | 75.0% | +$152.33 |
| v38_standalone_group10 | ATR | `M15` | 27 | 3 | 11.1% | +$80.98 |
| v38_standalone_group10 | ATR | `H1` | 10 | 3 | 30.0% | +$61.33 |
| v38_standalone_group10 | Fibo/FollowDiv | `M15` | 540 | 149 | 27.6% | +$49.65 |
| v38_standalone_group10 | Fibo/Fibo | `M15` | 14 | 9 | 64.3% | +$41.51 |
| v38_standalone_group10 | Fibo/Fibo | `H1` | 5 | 3 | 60.0% | +$29.29 |
| v38_standalone_group10 | Fibo/Fibo/ATR | `M15` | 1 | 1 | 100.0% | +$26.03 |
| v38_standalone_group10 | Fibo/FollowDiv/ATR | `M30` | 2 | 1 | 50.0% | +$15.70 |
| v38_standalone_group11 | Fibo | `H12` | 558 | 184 | 33.0% | +$3,988.50 |
| v38_standalone_group11 | GapSweep | `H1` | 99 | 57 | 57.6% | +$1,118.26 |
| v38_standalone_group11 | GapSweep | `M15` | 199 | 110 | 55.3% | +$980.27 |
| v38_standalone_group11 | GapSweep | `H12` | 32 | 16 | 50.0% | +$900.19 |
| v38_standalone_group11 | GapSweep | `D1` | 27 | 13 | 48.1% | +$898.80 |
| v38_standalone_group11 | GapSweep | `M30` | 131 | 74 | 56.5% | +$584.70 |
| v38_standalone_group11 | Div/FollowDiv | `M15` | 1 | 1 | 100.0% | +$297.67 |
| v38_standalone_group11 | ATR | `M30` | 19 | 6 | 31.6% | +$290.49 |
| v38_standalone_group11 | FollowDiv | `M15` | 25 | 4 | 16.0% | +$272.21 |
| v38_standalone_group11 | FollowDiv | `H1` | 15 | 3 | 20.0% | +$255.40 |
| v38_standalone_group11 | Fibo | `M15` | 53,593 | 20,924 | 39.0% | +$250.37 |
| v38_standalone_group11 | Fibo/ATR | `D1` | 2 | 1 | 50.0% | +$213.55 |
| v38_standalone_group11 | Fibo/Fibo | `D1` | 4 | 3 | 75.0% | +$152.33 |
| v38_standalone_group11 | ATR | `M15` | 27 | 3 | 11.1% | +$80.98 |
| v38_standalone_group11 | ATR | `H1` | 10 | 3 | 30.0% | +$61.33 |
| v38_standalone_group11 | Fibo/FollowDiv | `M15` | 540 | 149 | 27.6% | +$49.65 |
| v38_standalone_group11 | Fibo/Fibo | `M15` | 14 | 9 | 64.3% | +$41.51 |
| v38_standalone_group11 | Fibo/Fibo | `H1` | 5 | 3 | 60.0% | +$29.29 |
| v38_standalone_group11 | Fibo/Fibo/ATR | `M15` | 1 | 1 | 100.0% | +$26.03 |
| v38_standalone_group11 | Fibo/FollowDiv/ATR | `M30` | 2 | 1 | 50.0% | +$15.70 |
| v38_standalone_group11 | Fibo/Doji | `M30` | 5 | 1 | 20.0% | +$2.08 |
| v38_standalone_group12 | Naiya | `H1` | 5,440 | 920 | 16.9% | +$498,309.82 |
| v38_standalone_group12 | Naiya Doji | `M30` | 19,354 | 2,390 | 12.3% | +$15,443.00 |
| v38_standalone_group12 | Naiya/Div | `H1` | 154 | 12 | 7.8% | +$8,956.42 |
| v38_standalone_group12 | Naiya Doji | `M15` | 40,317 | 4,726 | 11.7% | +$4,093.74 |
| v38_standalone_group12 | Naiya | `M15` | 5,070 | 997 | 19.7% | +$3,812.69 |
| v38_standalone_group12 | Naiya | `M30` | 2,602 | 548 | 21.1% | +$3,532.19 |
| v38_standalone_group12 | Naiya Doji | `H12` | 461 | 49 | 10.6% | +$3,234.15 |
| v38_standalone_group12 | Naiya/FollowDiv | `H1` | 33 | 4 | 12.1% | +$3,050.01 |
| v38_standalone_group12 | Naiya/ATR | `H1` | 30 | 10 | 33.3% | +$2,224.62 |
| v38_standalone_group12 | Naiya/Doji | `H1` | 2 | 2 | 100.0% | +$1,643.81 |
| v38_standalone_group12 | GapSweep | `H1` | 99 | 57 | 57.6% | +$1,118.26 |
| v38_standalone_group12 | GapSweep | `M15` | 199 | 110 | 55.3% | +$980.27 |
| v38_standalone_group12 | GapSweep | `H12` | 32 | 16 | 50.0% | +$900.19 |
| v38_standalone_group12 | GapSweep | `D1` | 27 | 13 | 48.1% | +$898.80 |
| v38_standalone_group12 | ATR | `H1` | 38 | 12 | 31.6% | +$651.72 |
| v38_standalone_group12 | Naiya Hidden | `M30` | 279 | 73 | 26.2% | +$602.08 |
| v38_standalone_group12 | GapSweep | `M30` | 131 | 74 | 56.5% | +$584.70 |
| v38_standalone_group12 | FollowDiv | `M15` | 548 | 124 | 22.6% | +$552.38 |
| v38_standalone_group12 | FollowDiv | `M30` | 228 | 55 | 24.1% | +$300.20 |
| v38_standalone_group12 | Fibo | `D1` | 1 | 1 | 100.0% | +$249.95 |
| v38_standalone_group12 | ATR | `M15` | 177 | 39 | 22.0% | +$143.75 |
| v38_standalone_group12 | FollowDiv | `H1` | 74 | 13 | 17.6% | +$123.39 |
| v38_standalone_group12 | Naiya Hidden | `H12` | 12 | 2 | 16.7% | +$38.84 |
| v38_standalone_group12 | Fibo/ATR | `M15` | 1 | 1 | 100.0% | +$33.08 |
| v38_standalone_group13 | FVG/FVG | `H1` | 119 | 53 | 44.5% | +$1,988.37 |
| v38_standalone_group13 | FollowDiv | `M15` | 508 | 83 | 16.3% | +$1,171.06 |
| v38_standalone_group13 | GapSweep | `H1` | 99 | 57 | 57.6% | +$1,118.26 |
| v38_standalone_group13 | GapSweep | `M15` | 199 | 110 | 55.3% | +$980.27 |
| v38_standalone_group13 | GapSweep | `H12` | 32 | 16 | 50.0% | +$900.19 |
| v38_standalone_group13 | GapSweep | `D1` | 27 | 13 | 48.1% | +$898.80 |
| v38_standalone_group13 | GapSweep | `M30` | 131 | 74 | 56.5% | +$584.70 |
| v38_standalone_group13 | ATR | `M15` | 163 | 27 | 16.6% | +$457.30 |
| v38_standalone_group13 | FollowDiv | `M30` | 200 | 35 | 17.5% | +$414.87 |
| v38_standalone_group13 | FVG/ATR | `H1` | 11 | 4 | 36.4% | +$356.68 |
| v38_standalone_group13 | FVG/FollowDiv/FVG | `H1` | 2 | 2 | 100.0% | +$297.12 |
| v38_standalone_group13 | Fibo | `D1` | 1 | 1 | 100.0% | +$249.95 |
| v38_standalone_group13 | FollowDiv | `H1` | 90 | 12 | 13.3% | +$134.03 |
| v38_standalone_group13 | FVG/ATR | `M15` | 14 | 3 | 21.4% | +$87.60 |
| v38_standalone_group13 | ATR/FVG | `H1` | 2 | 1 | 50.0% | +$79.74 |
| v38_standalone_group13 | Div/FollowDiv | `M15` | 12 | 1 | 8.3% | +$77.18 |
| v38_standalone_group13 | Fibo/ATR | `M15` | 1 | 1 | 100.0% | +$33.08 |
| v38_standalone_group13 | Div/FollowDiv | `H1` | 5 | 1 | 20.0% | +$31.11 |
| v38_standalone_group13 | FVG/ATR | `M30` | 16 | 3 | 18.8% | +$29.40 |
| v38_standalone_group14 | GapSweep | `H1` | 99 | 57 | 57.6% | +$1,118.26 |
| v38_standalone_group14 | FollowDiv | `M15` | 548 | 89 | 16.2% | +$1,081.49 |
| v38_standalone_group14 | GapSweep | `M15` | 199 | 110 | 55.3% | +$980.27 |
| v38_standalone_group14 | GapSweep | `H12` | 32 | 16 | 50.0% | +$900.19 |
| v38_standalone_group14 | GapSweep | `D1` | 27 | 13 | 48.1% | +$898.80 |
| v38_standalone_group14 | GapSweep | `M30` | 131 | 74 | 56.5% | +$584.70 |
| v38_standalone_group14 | ATR | `M15` | 177 | 30 | 16.9% | +$544.90 |
| v38_standalone_group14 | ATR/FVG | `H1` | 2 | 2 | 100.0% | +$357.33 |
| v38_standalone_group14 | FollowDiv | `H1` | 81 | 12 | 14.8% | +$303.83 |
| v38_standalone_group14 | Fibo | `D1` | 1 | 1 | 100.0% | +$249.95 |
| v38_standalone_group14 | FollowDiv | `M30` | 228 | 39 | 17.1% | +$157.35 |
| v38_standalone_group14 | ATR | `H1` | 58 | 11 | 19.0% | +$89.14 |
| v38_standalone_group14 | Div/FollowDiv | `M15` | 12 | 1 | 8.3% | +$77.18 |
| v38_standalone_group14 | Fibo/ATR | `M15` | 1 | 1 | 100.0% | +$33.08 |
| v38_standalone_group15 | Fibo | `H12` | 558 | 145 | 26.0% | +$2,765.22 |
| v38_standalone_group15 | GapSweep | `H1` | 99 | 57 | 57.6% | +$1,118.26 |
| v38_standalone_group15 | GapSweep | `M15` | 199 | 110 | 55.3% | +$980.27 |
| v38_standalone_group15 | GapSweep | `H12` | 32 | 16 | 50.0% | +$900.19 |
| v38_standalone_group15 | GapSweep | `D1` | 27 | 13 | 48.1% | +$898.80 |
| v38_standalone_group15 | GapSweep | `M30` | 131 | 74 | 56.5% | +$584.70 |
| v38_standalone_group15 | Div/FollowDiv | `M15` | 1 | 1 | 100.0% | +$297.67 |
| v38_standalone_group15 | ATR | `M30` | 19 | 6 | 31.6% | +$290.49 |
| v38_standalone_group15 | FollowDiv | `M15` | 25 | 4 | 16.0% | +$272.21 |
| v38_standalone_group15 | FollowDiv | `H1` | 15 | 3 | 20.0% | +$255.40 |
| v38_standalone_group15 | Fibo/Fibo | `D1` | 4 | 3 | 75.0% | +$152.33 |
| v38_standalone_group15 | Fibo/ATR | `M30` | 114 | 44 | 38.6% | +$101.36 |
| v38_standalone_group15 | ATR | `M15` | 27 | 3 | 11.1% | +$80.98 |
| v38_standalone_group15 | ATR | `H1` | 10 | 3 | 30.0% | +$61.33 |
| v38_standalone_group15 | Fibo/Fibo | `M15` | 13 | 9 | 69.2% | +$47.07 |
| v38_standalone_group15 | Fibo/Fibo | `H1` | 5 | 3 | 60.0% | +$29.29 |
| v38_standalone_group15 | Fibo/Fibo/ATR | `M15` | 1 | 1 | 100.0% | +$26.03 |
| v38_standalone_group15 | Fibo/ATR | `H1` | 60 | 18 | 30.0% | +$25.22 |
| v38_standalone_group15 | Fibo/FollowDiv/ATR | `M30` | 2 | 1 | 50.0% | +$15.70 |
| v38_standalone_group15 | Fibo | `D1` | 243 | 47 | 19.3% | +$15.07 |
| v38_standalone_group16 | Naiya Doji | `M30` | 19,354 | 2,390 | 12.3% | +$15,443.00 |
| v38_standalone_group16 | Naiya Doji | `M15` | 40,313 | 4,726 | 11.7% | +$4,100.46 |
| v38_standalone_group16 | Naiya | `M15` | 5,069 | 997 | 19.7% | +$3,816.15 |
| v38_standalone_group16 | Naiya | `M30` | 2,602 | 548 | 21.1% | +$3,532.19 |
| v38_standalone_group16 | Naiya Doji | `H12` | 461 | 49 | 10.6% | +$3,234.15 |
| v38_standalone_group16 | GapSweep | `H1` | 99 | 57 | 57.6% | +$1,118.26 |
| v38_standalone_group16 | FollowDiv | `M15` | 548 | 89 | 16.2% | +$1,081.49 |
| v38_standalone_group16 | GapSweep | `M15` | 199 | 110 | 55.3% | +$980.27 |
| v38_standalone_group16 | GapSweep | `H12` | 32 | 16 | 50.0% | +$900.19 |
| v38_standalone_group16 | GapSweep | `D1` | 27 | 13 | 48.1% | +$898.80 |
| v38_standalone_group16 | Naiya | `H1` | 1,270 | 255 | 20.1% | +$872.39 |
| v38_standalone_group16 | Naiya Hidden | `M30` | 279 | 73 | 26.2% | +$602.08 |
| v38_standalone_group16 | GapSweep | `M30` | 131 | 74 | 56.5% | +$584.70 |
| v38_standalone_group16 | ATR | `M15` | 177 | 30 | 16.9% | +$544.90 |
| v38_standalone_group16 | Fibo | `D1` | 1 | 1 | 100.0% | +$249.95 |
| v38_standalone_group16 | FollowDiv | `H1` | 104 | 14 | 13.5% | +$172.51 |
| v38_standalone_group16 | FollowDiv | `M30` | 228 | 39 | 17.1% | +$157.35 |
| v38_standalone_group16 | ATR | `H1` | 58 | 11 | 19.0% | +$89.14 |
| v38_standalone_group16 | Div/FollowDiv | `M15` | 12 | 1 | 8.3% | +$77.18 |
| v38_standalone_group16 | Naiya Hidden | `H12` | 12 | 2 | 16.7% | +$38.84 |
| v38_standalone_group16 | Fibo/ATR | `M15` | 1 | 1 | 100.0% | +$33.08 |
| v38_standalone_group16 | Div/FollowDiv | `H1` | 5 | 1 | 20.0% | +$31.11 |
| v38_standalone_group17 | Naiya Doji | `H12` | 461 | 49 | 10.6% | +$3,234.15 |
| v38_standalone_group17 | Naiya | `H1` | 1,270 | 255 | 20.1% | +$872.39 |
| v38_standalone_group17 | Naiya FVG | `D1` | 3 | 1 | 33.3% | +$67.49 |
| v38_standalone_group17 | Naiya Hidden | `H12` | 12 | 2 | 16.7% | +$38.84 |
| v38_standalone_group18 | Naiya Doji | `M30` | 19,354 | 2,390 | 12.3% | +$15,443.00 |
| v38_standalone_group18 | Naiya Doji | `M15` | 40,311 | 4,726 | 11.7% | +$4,103.82 |
| v38_standalone_group18 | Naiya | `M15` | 5,069 | 997 | 19.7% | +$3,816.15 |
| v38_standalone_group18 | Naiya | `M30` | 2,602 | 548 | 21.1% | +$3,532.19 |
| v38_standalone_group18 | Naiya Doji | `H12` | 461 | 49 | 10.6% | +$3,234.15 |
| v38_standalone_group18 | GapSweep | `H1` | 99 | 57 | 57.6% | +$1,118.26 |
| v38_standalone_group18 | FollowDiv | `M15` | 548 | 89 | 16.2% | +$1,081.49 |
| v38_standalone_group18 | GapSweep | `M15` | 199 | 110 | 55.3% | +$980.27 |
| v38_standalone_group18 | GapSweep | `H12` | 32 | 16 | 50.0% | +$900.19 |
| v38_standalone_group18 | GapSweep | `D1` | 27 | 13 | 48.1% | +$898.80 |
| v38_standalone_group18 | Naiya | `H1` | 1,270 | 255 | 20.1% | +$872.39 |
| v38_standalone_group18 | Naiya Hidden | `M30` | 279 | 73 | 26.2% | +$602.08 |
| v38_standalone_group18 | GapSweep | `M30` | 131 | 74 | 56.5% | +$584.70 |
| v38_standalone_group18 | ATR | `M15` | 177 | 30 | 16.9% | +$544.90 |
| v38_standalone_group18 | Fibo | `D1` | 1 | 1 | 100.0% | +$249.95 |
| v38_standalone_group18 | FollowDiv | `H1` | 104 | 14 | 13.5% | +$172.51 |
| v38_standalone_group18 | FollowDiv | `M30` | 228 | 39 | 17.1% | +$157.35 |
| v38_standalone_group18 | ATR | `H1` | 58 | 11 | 19.0% | +$89.14 |
| v38_standalone_group18 | Div/FollowDiv | `M15` | 12 | 1 | 8.3% | +$77.18 |
| v38_standalone_group18 | Naiya Hidden | `H12` | 12 | 2 | 16.7% | +$38.84 |
| v38_standalone_group18 | Fibo/ATR | `M15` | 1 | 1 | 100.0% | +$33.08 |
| v38_standalone_group18 | Div/FollowDiv | `H1` | 5 | 1 | 20.0% | +$31.11 |
| v38_standalone_group20 | GapSweep | `H1` | 99 | 57 | 57.6% | +$1,118.26 |
| v38_standalone_group20 | FollowDiv | `M15` | 548 | 89 | 16.2% | +$1,081.49 |
| v38_standalone_group20 | GapSweep | `M15` | 199 | 110 | 55.3% | +$980.27 |
| v38_standalone_group20 | GapSweep | `H12` | 32 | 16 | 50.0% | +$900.19 |
| v38_standalone_group20 | GapSweep | `D1` | 27 | 13 | 48.1% | +$898.80 |
| v38_standalone_group20 | GapSweep | `M30` | 131 | 74 | 56.5% | +$584.70 |
| v38_standalone_group20 | ATR | `M15` | 177 | 30 | 16.9% | +$544.90 |
| v38_standalone_group20 | Fibo | `D1` | 1 | 1 | 100.0% | +$249.95 |
| v38_standalone_group20 | FollowDiv | `H1` | 104 | 14 | 13.5% | +$172.51 |
| v38_standalone_group20 | FollowDiv | `M30` | 228 | 39 | 17.1% | +$157.35 |
| v38_standalone_group20 | ATR | `H1` | 58 | 11 | 19.0% | +$89.14 |
| v38_standalone_group20 | Div/FollowDiv | `M15` | 12 | 1 | 8.3% | +$77.18 |
| v38_standalone_group20 | Fibo/ATR | `M15` | 1 | 1 | 100.0% | +$33.08 |
| v38_standalone_group20 | Div/FollowDiv | `H1` | 5 | 1 | 20.0% | +$31.11 |
| v38_standalone_group21 | GapSweep | `H1` | 99 | 57 | 57.6% | +$1,118.26 |
| v38_standalone_group21 | FollowDiv | `M15` | 548 | 89 | 16.2% | +$1,081.49 |
| v38_standalone_group21 | GapSweep | `M15` | 199 | 110 | 55.3% | +$980.27 |
| v38_standalone_group21 | GapSweep | `H12` | 32 | 16 | 50.0% | +$900.19 |
| v38_standalone_group21 | GapSweep | `D1` | 27 | 13 | 48.1% | +$898.80 |
| v38_standalone_group21 | GapSweep | `M30` | 131 | 74 | 56.5% | +$584.70 |
| v38_standalone_group21 | ATR | `M15` | 177 | 30 | 16.9% | +$544.90 |
| v38_standalone_group21 | Fibo | `D1` | 1 | 1 | 100.0% | +$249.95 |
| v38_standalone_group21 | FollowDiv | `H1` | 104 | 14 | 13.5% | +$172.51 |
| v38_standalone_group21 | FollowDiv | `M30` | 228 | 39 | 17.1% | +$157.35 |
| v38_standalone_group21 | ATR | `H1` | 58 | 11 | 19.0% | +$89.14 |
| v38_standalone_group21 | Div/FollowDiv | `M15` | 12 | 1 | 8.3% | +$77.18 |
| v38_standalone_group21 | Fibo/ATR | `M15` | 1 | 1 | 100.0% | +$33.08 |
| v38_standalone_group21 | Div/FollowDiv | `H1` | 5 | 1 | 20.0% | +$31.11 |
| v38_standalone_group22 | GapSweep | `M15` | 230 | 23 | 10.0% | +$2,582.91 |
| v38_standalone_group22 | GapSweep | `M30` | 115 | 15 | 13.0% | +$1,877.61 |
| v38_standalone_group22 | FollowDiv | `M15` | 548 | 89 | 16.2% | +$1,081.49 |
| v38_standalone_group22 | ATR | `M15` | 177 | 30 | 16.9% | +$544.90 |
| v38_standalone_group22 | Fibo | `D1` | 1 | 1 | 100.0% | +$249.95 |
| v38_standalone_group22 | FollowDiv | `H1` | 104 | 14 | 13.5% | +$172.51 |
| v38_standalone_group22 | FollowDiv | `M30` | 228 | 39 | 17.1% | +$157.35 |
| v38_standalone_group22 | ATR | `H1` | 58 | 11 | 19.0% | +$89.14 |
| v38_standalone_group22 | Div/FollowDiv | `M15` | 12 | 1 | 8.3% | +$77.18 |
| v38_standalone_group22 | Fibo/ATR | `M15` | 1 | 1 | 100.0% | +$33.08 |
| v38_standalone_group22 | Div/FollowDiv | `H1` | 5 | 1 | 20.0% | +$31.11 |
| v38_standalone_group24 | FollowDiv | `M15` | 508 | 83 | 16.3% | +$1,171.06 |
| v38_standalone_group24 | GapSweep | `H1` | 99 | 57 | 57.6% | +$1,118.26 |
| v38_standalone_group24 | GapSweep | `M15` | 199 | 110 | 55.3% | +$980.27 |
| v38_standalone_group24 | GapSweep | `H12` | 32 | 16 | 50.0% | +$900.19 |
| v38_standalone_group24 | GapSweep | `D1` | 27 | 13 | 48.1% | +$898.80 |
| v38_standalone_group24 | GapSweep | `M30` | 131 | 74 | 56.5% | +$584.70 |
| v38_standalone_group24 | ATR | `M15` | 163 | 27 | 16.6% | +$457.30 |
| v38_standalone_group24 | FollowDiv | `M30` | 200 | 35 | 17.5% | +$414.87 |
| v38_standalone_group24 | FVG/ATR | `H1` | 11 | 4 | 36.4% | +$356.68 |
| v38_standalone_group24 | Fibo | `D1` | 1 | 1 | 100.0% | +$249.95 |
| v38_standalone_group24 | FVG/FollowDiv | `H1` | 11 | 2 | 18.2% | +$88.94 |
| v38_standalone_group24 | FVG/ATR | `M15` | 14 | 3 | 21.4% | +$87.60 |
| v38_standalone_group24 | FollowDiv | `H1` | 93 | 12 | 12.9% | +$83.57 |
| v38_standalone_group24 | Div/FollowDiv | `M15` | 12 | 1 | 8.3% | +$77.18 |
| v38_standalone_group24 | Fibo/ATR | `M15` | 1 | 1 | 100.0% | +$33.08 |
| v38_standalone_group24 | Div/FollowDiv | `H1` | 5 | 1 | 20.0% | +$31.11 |
| v38_standalone_group24 | FVG/ATR | `M30` | 16 | 3 | 18.8% | +$29.40 |
| v38_standalone_group24 | Group34 | `H1` | 21 | 6 | 28.6% | +$23.86 |

---

### 💡 บทสรุปและขั้นตอนถัดไป (Actionable Next Steps)

1. **นำ Timeframe ที่ได้กำไรสูงสุดไปอัปเดตใส่ `config.py`**: นำค่า TF แนะนำจากตารางข้อ 2 ของแต่ละ Group ไปตั้งค่า `target_tfs` ในระบบบอทหลัก
2. **โฟกัส Group แถวหน้า**: Group 12 (Naiya H1/M30), Group 5 (FVG/Fibo H1), Group 23 (Standard MTF WinRate 63.2%) และ Group 9 (Naiya M30) เป็นแกนหลักในการสร้าง Cashflow สูงสุดของพอร์ต