# 🏆 quant-verification-v3: ผลหลังแก้ Checklist Item #10 (TF-Proportional Pending Expiry)

เอกสารนี้เปรียบเทียบผล **live-deployed combos** (24 groups, top-10 pattern/TF/round ต่อ group ที่ผูกจริงใน `config.py: S20_14_GROUP_COMBOS`)
ระหว่าง **v2 (ก่อนแก้ #10)** กับ **v3 (หลังแก้ #10: max_bars_map เปลี่ยนจาก ~1 สัปดาห์-เดือน เหลือ 1-30 แท่งตาม TF)**

> Item #10 คือ: pending order ต้องหมดอายุตามสัดส่วน TF จริง (เช่น M1=30 บาร์, D1=2 บาร์) แทนที่จะปล่อยรอเป็นสัปดาห์/เดือนแบบเดิม ซึ่งเป็นพฤติกรรมที่ broker จริงไม่ทำ (unrealistic pending fill)

## สรุปเชิงบริหาร (Executive Verdict)

จากทั้งหมด **234 deployed combos** (group × pattern × TF × round ที่ผูกไว้ใน live จริง):

- **WEAKENED_STILL_PROFIT**: 91 combos (38.9%)
- **BROKEN_BY_FIX**: 63 combos (26.9%)
- **STILL_LOSS**: 32 combos (13.7%)
- **ZERO_FILL_AFTER_FIX**: 24 combos (10.3%)
- **OK_STILL_PROFIT**: 18 combos (7.7%)
- **NO_DATA**: 5 combos (2.1%)
- **FIXED_BY_ITEM10**: 1 combos (0.4%)

⚠️ **87 combos (37.2%) พังทันทีหลังแก้ #10** (จากกำไร→ขาดทุน หรือไม่มีไม้เปิดเลยเพราะ pending หมดอายุเร็วเกินก่อนราคาย้อนมาแตะ)
⚠️ อีก **91 combos (38.9%) กำไรลดลงเกิน 30%** แม้ยังเป็นบวกอยู่
✅ มีแค่ **18 combos** ที่ผลแทบไม่เปลี่ยน และ **1 combo** ที่กลับดีขึ้นจากขาดทุนเป็นกำไร

**สรุป: การแก้ #10 กระทบรุนแรงต่อ combo ที่ deploy อยู่บน live ส่วนใหญ่ (>60% แย่ลงหรือพังทันที)** เพราะตัวเลข v2 เดิมส่วนใหญ่พึ่งพา pending order ที่รอข้ามวัน/สัปดาห์ได้ ซึ่งไม่ realistic — นี่คือหลักฐานว่ากำไรเดิมจำนวนมากเป็น **pending-window artifact** ไม่ใช่ edge จริงของ pattern

---

## 📊 ภาพรวมระดับ Group (ผลรวม P&L ของ combo ที่ deploy อยู่จริงต่อ group)

| Group | ชื่อกลยุทธ์ | Net P&L รวม (v2) | Net P&L รวม (v3) | Δ | Verdict สรุป |
|---:|---|---:|---:|---:|---|
| 1 | Primary Baseline Setup | 4,216.22 | -328.88 | -4,545.10 | BROKEN_BY_FIX |
| 2 | Micro Retest Engine | 60,461.30 | 41,715.11 | -18,746.19 | WEAKENED_STILL_PROFIT |
| 3 | Institutional Fibo Zone | 31,521.59 | -15,294.57 | -46,816.16 | BROKEN_BY_FIX |
| 4 | Liquidity Sweep Cluster | 7,708.65 | -16,441.46 | -24,150.11 | BROKEN_BY_FIX |
| 5 | FVG + Fibo Confluence | -42,941.92 | -52,613.46 | -9,671.54 | STILL_LOSS |
| 6 | Naiya Doji Volume Trap | 2,026,990.95 | 19,346.69 | -2,007,644.26 | ZERO_FILL_AFTER_FIX |
| 7 | Institutional Order Flow | 31,433.72 | -15,388.92 | -46,822.64 | BROKEN_BY_FIX |
| 8 | High-RR Trend Follower | 2,081,728.75 | 247,790.27 | -1,833,938.48 | WEAKENED_STILL_PROFIT |
| 9 | Naiya High Volatility | 508,198.34 | 75,404.08 | -432,794.26 | WEAKENED_STILL_PROFIT |
| 10 | Quant Fibo Expansion | 32,816.33 | -15,274.24 | -48,090.57 | BROKEN_BY_FIX |
| 11 | Fibo Multi-Layer Engine | 33,043.89 | -15,375.84 | -48,419.73 | BROKEN_BY_FIX |
| 12 | Master Naiya Cashflow Engine | 1,939,495.04 | 235,542.14 | -1,703,952.90 | WEAKENED_STILL_PROFIT |
| 13 | Institutional FVG Retest | 34,835.39 | 4,030.58 | -30,804.81 | BROKEN_BY_FIX |
| 14 | GapSweep Momentum Filter | -1,578.52 | -7,557.88 | -5,979.36 | BROKEN_BY_FIX |
| 15 | Macro Fibo Strategy | 32,607.39 | -15,473.32 | -48,080.71 | BROKEN_BY_FIX |
| 16 | Heavy Volume Scalper | 1,551,452.94 | 237,630.23 | -1,313,822.71 | WEAKENED_STILL_PROFIT |
| 17 | Low Frequency Precision Engine | 1,544,615.19 | 238,436.79 | -1,306,178.40 | WEAKENED_STILL_PROFIT |
| 18 | Divergence Momentum Capture | 627,256.22 | 94,531.48 | -532,724.74 | WEAKENED_STILL_PROFIT |
| 19 | Order #34 Dedicated Filter | 27,073.02 | 4,084.42 | -22,988.60 | BROKEN_BY_FIX |
| 20 | GapSweep Reversion Engine | 4,384.50 | -328.88 | -4,713.38 | BROKEN_BY_FIX |
| 21 | ATR Volatility Filter | 4,384.50 | -328.88 | -4,713.38 | BROKEN_BY_FIX |
| 22 | GapSweep M15 Dynamic Engine | 24,424.48 | 18,255.71 | -6,168.77 | OK_STILL_PROFIT |
| 24 | FollowDiv Trend Capture | 31,700.92 | 6,182.75 | -25,518.17 | BROKEN_BY_FIX |

---

## 📋 รายละเอียดทุก Combo ที่ Deploy อยู่จริง (Group × Pattern × TF × Round)

| Group | Pattern | TF | Round | Old Trades | Old P&L | Old WR% | New Trades | New P&L | New WR% | Verdict |
|---:|---|---|:---:|---:|---:|---:|---:|---:|---:|---|
| 1 | FollowDiv | M15 | R4 | 549 | 1,383.24 | 8.6 | 110 | 275.13 | 9.3 | WEAKENED_STILL_PROFIT |
| 1 | ATR | M15 | R4 | 176 | 593.35 | 8.5 | 38 | -128.34 | 10.5 | BROKEN_BY_FIX |
| 1 | FollowDiv | H4 | R2 | 23 | 560.39 | 20.0 | 0 | N/A | N/A | ZERO_FILL_AFTER_FIX |
| 1 | FollowDiv | M30 | R3 | 226 | 473.32 | 24.8 | 23 | -16.36 | 26.1 | BROKEN_BY_FIX |
| 1 | GapSweep | H1 | R4 | 88 | 461.76 | 19.5 | 40 | 642.93 | 25.0 | OK_STILL_PROFIT |
| 1 | GapSweep | H12 | R3 | 26 | 436.48 | 30.4 | 19 | 596.24 | 33.3 | OK_STILL_PROFIT |
| 1 | Div | M15 | R4 | 397 | -439.79 | 9.1 | 233 | -1,693.22 | 6.9 | STILL_LOSS |
| 1 | ATR | M30 | R3 | 111 | 261.87 | 38.7 | 19 | 28.74 | 47.4 | WEAKENED_STILL_PROFIT |
| 1 | Fibo | D1 | R1 | 1 | 249.95 | 100.0 | 0 | N/A | N/A | ZERO_FILL_AFTER_FIX |
| 1 | GapSweep | D1 | R3 | 20 | 235.65 | 41.2 | 17 | -34.00 | 35.7 | BROKEN_BY_FIX |
| 2 | Inst_Gap | D1 | R3 | 327 | 27,743.93 | 27.8 | 289 | 24,187.01 | 24.8 | OK_STILL_PROFIT |
| 2 | Inst_Gap | H12 | R1 | 669 | 11,343.87 | 32.0 | 543 | 3,704.58 | 28.4 | WEAKENED_STILL_PROFIT |
| 2 | Inst_Gap | H4 | R1 | 2050 | 8,118.72 | 31.4 | 1449 | 8,017.17 | 25.1 | OK_STILL_PROFIT |
| 2 | Inst_Gap | H1 | R1 | 369 | 5,039.27 | 43.9 | 205 | 2,405.99 | 37.3 | WEAKENED_STILL_PROFIT |
| 2 | Inst_Gap | M30 | R1 | 368 | 2,868.64 | 40.2 | 198 | 1,751.52 | 37.4 | WEAKENED_STILL_PROFIT |
| 2 | Inst_Gap | M15 | R4 | 370 | 2,751.23 | 17.0 | 202 | 1,595.67 | 16.3 | WEAKENED_STILL_PROFIT |
| 2 | FollowDiv | M15 | R1 | 549 | 857.03 | 15.7 | 96 | -1.84 | 10.4 | BROKEN_BY_FIX |
| 2 | FollowDiv | H4 | R2 | 23 | 653.93 | 20.0 | 0 | N/A | N/A | ZERO_FILL_AFTER_FIX |
| 2 | FollowDiv | M30 | R3 | 226 | 585.57 | 22.1 | 23 | -64.92 | 21.7 | BROKEN_BY_FIX |
| 2 | ATR | M15 | R1 | 176 | 499.11 | 16.5 | 37 | 119.93 | 21.6 | WEAKENED_STILL_PROFIT |
| 3 | Fibo | M15 | R4 | 53583 | 34,951.49 | 10.0 | 32621 | -3,129.03 | 9.5 | BROKEN_BY_FIX |
| 3 | Fibo | M30 | R3 | 25284 | 5,626.76 | 36.0 | 12925 | -1,124.99 | 34.2 | BROKEN_BY_FIX |
| 3 | Fibo | H12 | R1 | 562 | 4,154.37 | 33.7 | 395 | 544.36 | 34.1 | WEAKENED_STILL_PROFIT |
| 3 | Div | M15 | R4 | 216 | -1,968.78 | 5.6 | 143 | -1,749.26 | 4.9 | STILL_LOSS |
| 3 | Fibo | D1 | R2 | 247 | 1,302.58 | 39.9 | 197 | -270.71 | 39.2 | BROKEN_BY_FIX |
| 3 | Fibo | H4 | R4 | 2441 | -10,973.37 | 27.1 | 1282 | -7,694.44 | 28.5 | STILL_LOSS |
| 3 | Div | H4 | R4 | 50 | -2,836.51 | 4.0 | 30 | -2,032.50 | 0.0 | STILL_LOSS |
| 3 | FollowDiv | M15 | R4 | 25 | 765.41 | 12.0 | 2 | -76.77 | 0.0 | BROKEN_BY_FIX |
| 3 | FollowDiv | H4 | R2 | 2 | -169.97 | 0.0 | 0 | N/A | N/A | ZERO_FILL_AFTER_FIX |
| 3 | ATR | H4 | R1 | 4 | 669.61 | 66.7 | 2 | 238.77 | 100.0 | WEAKENED_STILL_PROFIT |
| 3 | ATR | D1 | R3 | 0 | N/A | N/A | 0 | N/A | N/A | NO_DATA |
| 4 | Fibo | M30 | R2 | 18478 | 3,906.08 | 38.8 | 8765 | -3,514.44 | 40.6 | BROKEN_BY_FIX |
| 4 | Fibo | H12 | R1 | 373 | 2,291.99 | 29.1 | 251 | 280.96 | 31.3 | WEAKENED_STILL_PROFIT |
| 4 | Fibo | H4 | R1 | 1703 | 1,969.68 | 33.4 | 826 | 433.42 | 34.9 | WEAKENED_STILL_PROFIT |
| 4 | Fibo | M15 | R3 | 39264 | 1,645.63 | 34.5 | 22247 | -7,466.96 | 32.4 | BROKEN_BY_FIX |
| 4 | Fibo | D1 | R3 | 156 | 1,387.74 | 35.7 | 121 | -2,253.18 | 30.8 | BROKEN_BY_FIX |
| 4 | Div | H4 | R4 | 50 | -2,836.51 | 4.0 | 30 | -2,032.50 | 0.0 | STILL_LOSS |
| 4 | Div | M15 | R4 | 247 | -1,538.61 | 6.9 | 166 | -1,833.05 | 5.4 | STILL_LOSS |
| 4 | FollowDiv | M15 | R4 | 18 | 1,061.57 | 16.7 | 1 | -55.71 | 0.0 | BROKEN_BY_FIX |
| 4 | FollowDiv | M30 | R3 | 13 | -178.92 | 23.1 | 0 | N/A | N/A | ZERO_FILL_AFTER_FIX |
| 5 | FVG | M15 | R4 | 1286 | -6,927.50 | 7.3 | 186 | -195.57 | 7.7 | STILL_LOSS |
| 5 | Fibo | M15 | R4 | 48754 | 14,971.82 | 9.8 | 29680 | -10,328.48 | 9.4 | BROKEN_BY_FIX |
| 5 | FVG | H1 | R3 | 477 | 1,125.28 | 32.3 | 49 | -390.09 | 14.3 | BROKEN_BY_FIX |
| 5 | Fibo | H1 | R3 | 9698 | -20,811.69 | 32.3 | 5118 | -12,981.29 | 31.0 | STILL_LOSS |
| 5 | FVG | M30 | R4 | 866 | 5,857.00 | 14.1 | 79 | 977.19 | 19.2 | WEAKENED_STILL_PROFIT |
| 5 | Fibo | M30 | R4 | 21254 | -26,114.96 | 12.9 | 11045 | -18,216.68 | 13.0 | STILL_LOSS |
| 5 | FVG | H4 | R3 | 162 | 5,231.17 | 36.4 | 29 | 2.94 | 14.8 | WEAKENED_STILL_PROFIT |
| 5 | FVG | H12 | R2 | 30 | -1,286.51 | 13.6 | 9 | -795.35 | 12.5 | STILL_LOSS |
| 5 | Fibo | H12 | R2 | 425 | -3,217.13 | 36.1 | 321 | -2,504.58 | 38.5 | STILL_LOSS |
| 5 | Fibo | H4 | R2 | 1782 | -8,419.70 | 43.2 | 926 | -4,831.20 | 43.6 | STILL_LOSS |
| 5 | FVG | D1 | R2 | 6 | -780.10 | 0.0 | 2 | -164.44 | 0.0 | STILL_LOSS |
| 5 | Fibo | D1 | R2 | 218 | -2,569.60 | 36.0 | 174 | -3,185.91 | 35.8 | STILL_LOSS |
| 6 | Naiya Doji | H1 | R3 | 8996 | 1,536,258.83 | 11.4 | 0 | N/A | N/A | ZERO_FILL_AFTER_FIX |
| 6 | Naiya Doji | M15 | R1 | 40261 | 244,498.20 | 15.9 | 0 | N/A | N/A | ZERO_FILL_AFTER_FIX |
| 6 | Naiya Doji | M30 | R1 | 19316 | 163,011.90 | 17.8 | 2178 | 16,219.99 | 18.0 | WEAKENED_STILL_PROFIT |
| 6 | Naiya Doji | H4 | R2 | 1828 | 33,579.39 | 20.2 | 280 | 2,201.37 | 17.9 | WEAKENED_STILL_PROFIT |
| 6 | Naiya Doji | D1 | R3 | 192 | 31,687.76 | 28.9 | 0 | N/A | N/A | ZERO_FILL_AFTER_FIX |
| 6 | Naiya Doji | H12 | R3 | 456 | 10,319.53 | 26.7 | 0 | N/A | N/A | ZERO_FILL_AFTER_FIX |
| 6 | Naiya | M30 | R3 | 2601 | 3,081.68 | 20.7 | 0 | N/A | N/A | ZERO_FILL_AFTER_FIX |
| 6 | Naiya | M15 | R3 | 5063 | 3,027.61 | 19.2 | 3010 | 925.33 | 17.9 | WEAKENED_STILL_PROFIT |
| 6 | FollowDiv | M15 | R1 | 549 | 857.03 | 15.7 | 0 | N/A | N/A | ZERO_FILL_AFTER_FIX |
| 6 | Naiya | H1 | R1 | 1270 | 669.02 | 19.7 | 0 | N/A | N/A | ZERO_FILL_AFTER_FIX |
| 7 | Fibo | M15 | R4 | 53583 | 34,951.49 | 10.0 | 32621 | -3,129.03 | 9.5 | BROKEN_BY_FIX |
| 7 | Fibo | M30 | R3 | 25284 | 5,538.89 | 36.0 | 12925 | -1,124.99 | 34.2 | BROKEN_BY_FIX |
| 7 | Fibo | H12 | R1 | 562 | 4,154.37 | 33.7 | 395 | 450.01 | 34.0 | WEAKENED_STILL_PROFIT |
| 7 | Div | M15 | R4 | 216 | -1,968.78 | 5.6 | 143 | -1,749.26 | 4.9 | STILL_LOSS |
| 7 | Fibo | D1 | R2 | 247 | 1,302.58 | 39.9 | 197 | -270.71 | 39.2 | BROKEN_BY_FIX |
| 7 | Fibo | H4 | R4 | 2441 | -10,973.37 | 27.1 | 1282 | -7,694.44 | 28.5 | STILL_LOSS |
| 7 | Div | H4 | R4 | 50 | -2,836.51 | 4.0 | 30 | -2,032.50 | 0.0 | STILL_LOSS |
| 7 | FollowDiv | M15 | R4 | 25 | 765.41 | 12.0 | 2 | -76.77 | 0.0 | BROKEN_BY_FIX |
| 7 | FollowDiv | H4 | R2 | 2 | -169.97 | 0.0 | 0 | N/A | N/A | ZERO_FILL_AFTER_FIX |
| 7 | ATR | H4 | R1 | 4 | 669.61 | 66.7 | 2 | 238.77 | 100.0 | WEAKENED_STILL_PROFIT |
| 7 | ATR | D1 | R3 | 0 | N/A | N/A | 0 | N/A | N/A | NO_DATA |
| 8 | Naiya Doji | H1 | R4 | 9015 | 1,605,461.92 | 8.5 | 1181 | 169,914.11 | 10.3 | WEAKENED_STILL_PROFIT |
| 8 | Naiya Doji | M15 | R1 | 40261 | 239,859.61 | 15.9 | 7797 | 39,175.63 | 17.3 | WEAKENED_STILL_PROFIT |
| 8 | Naiya Doji | M30 | R1 | 19316 | 155,827.16 | 17.7 | 2175 | 15,533.42 | 17.9 | WEAKENED_STILL_PROFIT |
| 8 | Naiya Doji | H4 | R2 | 1828 | 32,166.85 | 20.2 | 280 | 2,201.37 | 17.9 | WEAKENED_STILL_PROFIT |
| 8 | Naiya Doji | D1 | R3 | 192 | 31,573.61 | 28.9 | 85 | 14,837.15 | 28.9 | WEAKENED_STILL_PROFIT |
| 8 | Naiya Doji | H12 | R3 | 456 | 9,204.26 | 26.7 | 169 | 4,790.19 | 25.5 | WEAKENED_STILL_PROFIT |
| 8 | Naiya | M30 | R3 | 2601 | 3,081.68 | 20.7 | 1214 | 62.80 | 17.4 | WEAKENED_STILL_PROFIT |
| 8 | Naiya | M15 | R3 | 5063 | 3,027.61 | 19.2 | 3010 | 925.33 | 17.9 | WEAKENED_STILL_PROFIT |
| 8 | FollowDiv | M15 | R1 | 549 | 857.03 | 15.7 | 96 | -1.84 | 10.4 | BROKEN_BY_FIX |
| 8 | Naiya | H1 | R1 | 1270 | 669.02 | 19.7 | 591 | 352.11 | 20.6 | WEAKENED_STILL_PROFIT |
| 9 | Naiya Doji | M15 | R2 | 40264 | 223,138.86 | 15.1 | 8775 | 29,269.78 | 14.1 | WEAKENED_STILL_PROFIT |
| 9 | Naiya Doji | M30 | R1 | 19314 | 116,404.84 | 16.9 | 2176 | 11,550.67 | 15.7 | WEAKENED_STILL_PROFIT |
| 9 | Naiya Doji | H1 | R4 | 9009 | 93,662.75 | 18.1 | 1181 | 7,910.25 | 19.3 | WEAKENED_STILL_PROFIT |
| 9 | Naiya Doji | D1 | R3 | 192 | 33,918.37 | 39.1 | 85 | 15,836.94 | 37.6 | WEAKENED_STILL_PROFIT |
| 9 | Naiya Doji | H4 | R1 | 1830 | 25,169.91 | 22.4 | 269 | 4,311.80 | 23.9 | WEAKENED_STILL_PROFIT |
| 9 | Naiya Doji | H12 | R3 | 456 | 9,882.10 | 29.6 | 169 | 5,516.19 | 32.7 | WEAKENED_STILL_PROFIT |
| 9 | Naiya | M30 | R3 | 2601 | 2,450.34 | 15.0 | 1214 | -419.01 | 12.5 | BROKEN_BY_FIX |
| 9 | Naiya | H1 | R1 | 1270 | 1,510.15 | 18.3 | 591 | 467.33 | 19.0 | WEAKENED_STILL_PROFIT |
| 9 | FollowDiv | M15 | R3 | 549 | 1,092.82 | 20.8 | 110 | 508.30 | 17.3 | WEAKENED_STILL_PROFIT |
| 9 | Naiya Hidden | M30 | R4 | 276 | 968.20 | 23.2 | 51 | 451.83 | 25.5 | WEAKENED_STILL_PROFIT |
| 10 | Fibo | M15 | R4 | 53546 | 36,013.53 | 9.9 | 32621 | -3,129.03 | 9.5 | BROKEN_BY_FIX |
| 10 | Fibo | M30 | R3 | 25284 | 5,516.80 | 36.0 | 12925 | -1,124.99 | 34.2 | BROKEN_BY_FIX |
| 10 | Fibo | H12 | R1 | 562 | 4,154.37 | 33.7 | 396 | 564.69 | 34.2 | WEAKENED_STILL_PROFIT |
| 10 | Div | M15 | R4 | 216 | -1,968.78 | 5.6 | 143 | -1,749.26 | 4.9 | STILL_LOSS |
| 10 | Fibo | D1 | R2 | 247 | 1,302.58 | 39.9 | 197 | -270.71 | 39.2 | BROKEN_BY_FIX |
| 10 | Fibo | H4 | R4 | 2441 | -10,630.71 | 27.2 | 1282 | -7,694.44 | 28.5 | STILL_LOSS |
| 10 | Div | H4 | R4 | 50 | -2,836.51 | 4.0 | 30 | -2,032.50 | 0.0 | STILL_LOSS |
| 10 | FollowDiv | M15 | R4 | 25 | 765.41 | 12.0 | 2 | -76.77 | 0.0 | BROKEN_BY_FIX |
| 10 | FollowDiv | H4 | R2 | 2 | -169.97 | 0.0 | 0 | N/A | N/A | ZERO_FILL_AFTER_FIX |
| 10 | ATR | H4 | R1 | 4 | 669.61 | 66.7 | 2 | 238.77 | 100.0 | WEAKENED_STILL_PROFIT |
| 10 | ATR | D1 | R3 | 0 | N/A | N/A | 0 | N/A | N/A | NO_DATA |
| 11 | Fibo | M15 | R4 | 53545 | 36,033.28 | 9.9 | 32621 | -3,129.03 | 9.5 | BROKEN_BY_FIX |
| 11 | Fibo | M30 | R3 | 25278 | 5,724.61 | 36.0 | 12924 | -1,184.69 | 34.2 | BROKEN_BY_FIX |
| 11 | Fibo | H12 | R1 | 562 | 4,154.37 | 33.7 | 395 | 522.79 | 34.3 | WEAKENED_STILL_PROFIT |
| 11 | Div | M15 | R4 | 216 | -1,968.78 | 5.6 | 143 | -1,749.26 | 4.9 | STILL_LOSS |
| 11 | Fibo | D1 | R2 | 247 | 1,302.58 | 39.9 | 197 | -270.71 | 39.2 | BROKEN_BY_FIX |
| 11 | Fibo | H4 | R4 | 2441 | -10,630.71 | 27.2 | 1282 | -7,694.44 | 28.5 | STILL_LOSS |
| 11 | Div | H4 | R4 | 50 | -2,836.51 | 4.0 | 30 | -2,032.50 | 0.0 | STILL_LOSS |
| 11 | FollowDiv | M15 | R4 | 25 | 765.41 | 12.0 | 2 | -76.77 | 0.0 | BROKEN_BY_FIX |
| 11 | FollowDiv | H4 | R2 | 2 | -169.97 | 0.0 | 0 | N/A | N/A | ZERO_FILL_AFTER_FIX |
| 11 | ATR | H4 | R1 | 4 | 669.61 | 66.7 | 2 | 238.77 | 100.0 | WEAKENED_STILL_PROFIT |
| 11 | ATR | D1 | R3 | 0 | N/A | N/A | 0 | N/A | N/A | NO_DATA |
| 12 | Naiya Doji | H1 | R3 | 9011 | 1,466,438.69 | 20.5 | 1181 | 150,584.98 | 23.9 | WEAKENED_STILL_PROFIT |
| 12 | Naiya Doji | M15 | R1 | 40263 | 234,758.99 | 15.9 | 7803 | 42,781.50 | 17.3 | WEAKENED_STILL_PROFIT |
| 12 | Naiya Doji | M30 | R1 | 19314 | 155,832.32 | 17.7 | 2178 | 17,946.24 | 17.9 | WEAKENED_STILL_PROFIT |
| 12 | Naiya Doji | H4 | R1 | 1830 | 34,158.79 | 17.7 | 270 | 3,739.87 | 18.4 | WEAKENED_STILL_PROFIT |
| 12 | Naiya Doji | D1 | R3 | 192 | 31,687.76 | 28.9 | 85 | 14,858.52 | 28.9 | WEAKENED_STILL_PROFIT |
| 12 | Naiya Doji | H12 | R3 | 456 | 9,204.26 | 26.7 | 169 | 4,790.19 | 25.5 | WEAKENED_STILL_PROFIT |
| 12 | Naiya | M30 | R3 | 2601 | 3,081.68 | 20.7 | 1214 | 62.80 | 17.4 | WEAKENED_STILL_PROFIT |
| 12 | Naiya | M15 | R4 | 5063 | 3,029.70 | 19.2 | 3010 | 925.33 | 17.9 | WEAKENED_STILL_PROFIT |
| 12 | ATR | H1 | R3 | 38 | 717.28 | 36.8 | 3 | -82.37 | 0.0 | BROKEN_BY_FIX |
| 12 | FollowDiv | M30 | R3 | 226 | 585.57 | 22.1 | 23 | -64.92 | 21.7 | BROKEN_BY_FIX |
| 13 | FVG | M15 | R4 | 5401 | 13,502.30 | 10.0 | 575 | 6,212.00 | 12.4 | WEAKENED_STILL_PROFIT |
| 13 | FVG | H4 | R1 | 528 | 8,364.38 | 18.7 | 65 | -1,119.21 | 13.3 | BROKEN_BY_FIX |
| 13 | FVG | H12 | R3 | 66 | 4,193.94 | 48.5 | 19 | -455.70 | 26.3 | BROKEN_BY_FIX |
| 13 | FVG | H1 | R4 | 2506 | 4,123.59 | 15.0 | 382 | -1,099.70 | 17.5 | BROKEN_BY_FIX |
| 13 | FVG | M30 | R4 | 4033 | 3,826.87 | 12.2 | 261 | 655.26 | 14.7 | WEAKENED_STILL_PROFIT |
| 13 | FollowDiv | M15 | R4 | 509 | 217.98 | 7.9 | 106 | -33.73 | 8.7 | BROKEN_BY_FIX |
| 13 | FollowDiv | H4 | R2 | 18 | 581.91 | 20.0 | 0 | N/A | N/A | ZERO_FILL_AFTER_FIX |
| 13 | ATR | M15 | R4 | 162 | 24.42 | 7.4 | 38 | -128.34 | 10.5 | BROKEN_BY_FIX |
| 14 | FollowDiv | M15 | R4 | 549 | 1,265.49 | 8.5 | 110 | 275.13 | 9.3 | WEAKENED_STILL_PROFIT |
| 14 | ATR | M15 | R4 | 176 | 593.35 | 8.5 | 38 | -128.34 | 10.5 | BROKEN_BY_FIX |
| 14 | FollowDiv | H4 | R2 | 23 | 560.39 | 20.0 | 0 | N/A | N/A | ZERO_FILL_AFTER_FIX |
| 14 | FollowDiv | M30 | R3 | 226 | 473.32 | 24.8 | 23 | -16.36 | 26.1 | BROKEN_BY_FIX |
| 14 | GapSweep | H1 | R4 | 88 | 461.76 | 19.5 | 40 | 642.93 | 25.0 | OK_STILL_PROFIT |
| 14 | ATR | H1 | R4 | 58 | 192.67 | 16.1 | 9 | -352.57 | 0.0 | BROKEN_BY_FIX |
| 14 | FVG | H1 | R4 | 671 | -5,947.89 | 19.0 | 671 | -6,605.37 | 18.5 | STILL_LOSS |
| 14 | GapSweep | H12 | R3 | 26 | 436.48 | 30.4 | 19 | 596.24 | 33.3 | OK_STILL_PROFIT |
| 14 | FollowDiv | H1 | R1 | 81 | 296.93 | 14.8 | 8 | -305.06 | 0.0 | BROKEN_BY_FIX |
| 14 | Div | M15 | R4 | 397 | -172.89 | 9.3 | 233 | -1,693.22 | 6.9 | STILL_LOSS |
| 14 | ATR | M30 | R3 | 112 | 261.87 | 38.7 | 19 | 28.74 | 47.4 | WEAKENED_STILL_PROFIT |
| 15 | Fibo | M15 | R4 | 53545 | 35,965.76 | 9.9 | 32621 | -3,129.03 | 9.5 | BROKEN_BY_FIX |
| 15 | Fibo | M30 | R3 | 25280 | 5,731.10 | 36.0 | 12925 | -1,124.99 | 34.2 | BROKEN_BY_FIX |
| 15 | Fibo | H12 | R1 | 562 | 3,778.90 | 33.7 | 395 | 365.61 | 34.3 | WEAKENED_STILL_PROFIT |
| 15 | Div | M15 | R4 | 216 | -1,968.78 | 5.6 | 143 | -1,749.26 | 4.9 | STILL_LOSS |
| 15 | Fibo | D1 | R2 | 247 | 1,302.58 | 39.9 | 197 | -270.71 | 39.2 | BROKEN_BY_FIX |
| 15 | Fibo | H4 | R4 | 2441 | -10,630.71 | 27.2 | 1282 | -7,694.44 | 28.5 | STILL_LOSS |
| 15 | Div | H4 | R4 | 50 | -2,836.51 | 4.0 | 30 | -2,032.50 | 0.0 | STILL_LOSS |
| 15 | FollowDiv | M15 | R4 | 25 | 765.41 | 12.0 | 2 | -76.77 | 0.0 | BROKEN_BY_FIX |
| 15 | FollowDiv | H4 | R2 | 2 | -169.97 | 0.0 | 0 | N/A | N/A | ZERO_FILL_AFTER_FIX |
| 15 | ATR | H4 | R1 | 4 | 669.61 | 66.7 | 2 | 238.77 | 100.0 | WEAKENED_STILL_PROFIT |
| 15 | ATR | D1 | R3 | 0 | N/A | N/A | 0 | N/A | N/A | NO_DATA |
| 16 | Naiya Doji | M15 | R2 | 40263 | 674,714.24 | 9.4 | 8775 | 111,152.50 | 10.5 | WEAKENED_STILL_PROFIT |
| 16 | Naiya Doji | M30 | R2 | 19316 | 410,390.53 | 11.4 | 2449 | 42,524.01 | 11.6 | WEAKENED_STILL_PROFIT |
| 16 | Naiya Doji | H1 | R2 | 8998 | 289,562.97 | 10.7 | 1181 | 29,338.38 | 11.6 | WEAKENED_STILL_PROFIT |
| 16 | Naiya Doji | H4 | R2 | 1828 | 90,083.11 | 5.5 | 280 | 14,178.65 | 7.1 | WEAKENED_STILL_PROFIT |
| 16 | Naiya Doji | D1 | R2 | 192 | 43,077.16 | 6.3 | 85 | 20,095.13 | 4.8 | WEAKENED_STILL_PROFIT |
| 16 | Naiya Doji | H12 | R2 | 456 | 35,593.23 | 4.2 | 169 | 18,726.19 | 5.6 | WEAKENED_STILL_PROFIT |
| 16 | Naiya | M30 | R3 | 2601 | 3,081.68 | 20.7 | 1214 | 62.80 | 17.4 | WEAKENED_STILL_PROFIT |
| 16 | Naiya | M15 | R3 | 5063 | 3,029.70 | 19.2 | 3010 | 925.33 | 17.9 | WEAKENED_STILL_PROFIT |
| 16 | FollowDiv | M15 | R4 | 549 | 1,265.49 | 8.5 | 110 | 275.13 | 9.3 | WEAKENED_STILL_PROFIT |
| 16 | Naiya | H1 | R1 | 1270 | 654.83 | 19.6 | 591 | 352.11 | 20.6 | WEAKENED_STILL_PROFIT |
| 17 | Naiya Doji | M15 | R2 | 40262 | 664,634.91 | 9.4 | 8775 | 111,152.50 | 10.5 | WEAKENED_STILL_PROFIT |
| 17 | Naiya Doji | M30 | R2 | 19315 | 412,971.37 | 11.4 | 2449 | 42,524.01 | 11.6 | WEAKENED_STILL_PROFIT |
| 17 | Naiya Doji | H1 | R2 | 8997 | 289,565.36 | 10.7 | 1181 | 29,338.38 | 11.6 | WEAKENED_STILL_PROFIT |
| 17 | Naiya Doji | H4 | R2 | 1828 | 90,488.24 | 5.5 | 280 | 14,178.65 | 7.1 | WEAKENED_STILL_PROFIT |
| 17 | Naiya Doji | D1 | R2 | 192 | 43,191.31 | 6.3 | 85 | 20,095.13 | 4.8 | WEAKENED_STILL_PROFIT |
| 17 | Naiya Doji | H12 | R2 | 456 | 35,585.16 | 4.2 | 169 | 19,082.89 | 5.6 | WEAKENED_STILL_PROFIT |
| 17 | Naiya | M30 | R4 | 2602 | 3,081.68 | 20.7 | 1214 | 62.80 | 17.4 | WEAKENED_STILL_PROFIT |
| 17 | Naiya | M15 | R4 | 5063 | 3,029.70 | 19.2 | 3010 | 925.33 | 17.9 | WEAKENED_STILL_PROFIT |
| 17 | FollowDiv | M15 | R4 | 549 | 1,265.49 | 8.5 | 110 | 275.13 | 9.3 | WEAKENED_STILL_PROFIT |
| 17 | Naiya FVG | D1 | R1 | 3 | 801.97 | 100.0 | 3 | 801.97 | 100.0 | OK_STILL_PROFIT |
| 18 | Naiya Doji | M15 | R1 | 40265 | 258,004.31 | 15.9 | 7790 | 37,960.40 | 17.3 | WEAKENED_STILL_PROFIT |
| 18 | Naiya Doji | M30 | R1 | 19318 | 166,171.18 | 17.8 | 2179 | 17,289.96 | 17.9 | WEAKENED_STILL_PROFIT |
| 18 | Naiya Doji | H1 | R1 | 8999 | 119,477.08 | 17.2 | 1095 | 9,649.35 | 18.2 | WEAKENED_STILL_PROFIT |
| 18 | Naiya Doji | H4 | R1 | 1828 | 34,021.98 | 17.7 | 270 | 3,816.05 | 18.2 | WEAKENED_STILL_PROFIT |
| 18 | Naiya Doji | D1 | R3 | 192 | 31,687.76 | 28.9 | 85 | 14,898.31 | 28.9 | WEAKENED_STILL_PROFIT |
| 18 | Naiya Doji | H12 | R3 | 456 | 10,270.67 | 26.7 | 169 | 9,602.74 | 25.5 | OK_STILL_PROFIT |
| 18 | Naiya | M30 | R4 | 2602 | 3,081.68 | 20.7 | 1214 | 62.80 | 17.4 | WEAKENED_STILL_PROFIT |
| 18 | Naiya | M15 | R4 | 5063 | 3,029.70 | 19.2 | 3010 | 925.33 | 17.9 | WEAKENED_STILL_PROFIT |
| 18 | FollowDiv | M15 | R1 | 549 | 857.03 | 15.7 | 97 | -1.84 | 10.4 | BROKEN_BY_FIX |
| 18 | Naiya | H1 | R1 | 1270 | 654.83 | 19.6 | 590 | 328.38 | 20.5 | WEAKENED_STILL_PROFIT |
| 19 | FVG | M15 | R4 | 5401 | 13,502.30 | 10.0 | 575 | 6,212.00 | 12.4 | WEAKENED_STILL_PROFIT |
| 19 | Group26 | H1 | R1 | 2295 | -533.68 | 44.9 | 974 | -2,254.76 | 42.9 | STILL_LOSS |
| 19 | FVG | H1 | R1 | 1254 | -5,796.91 | 22.4 | 122 | 21.14 | 27.0 | FIXED_BY_ITEM10 |
| 19 | FVG | H12 | R1 | 66 | 8,604.56 | 39.3 | 17 | 454.62 | 17.6 | WEAKENED_STILL_PROFIT |
| 19 | FVG | H4 | R3 | 527 | 6,298.20 | 35.8 | 65 | -472.84 | 20.0 | BROKEN_BY_FIX |
| 19 | FVG | M30 | R4 | 4028 | 3,902.05 | 12.2 | 261 | 655.26 | 14.7 | WEAKENED_STILL_PROFIT |
| 19 | FollowDiv | M15 | R4 | 509 | 217.98 | 7.9 | 106 | -33.73 | 8.7 | BROKEN_BY_FIX |
| 19 | ATR | H1 | R4 | 38 | 357.76 | 18.4 | 9 | -352.57 | 0.0 | BROKEN_BY_FIX |
| 19 | ATR | M15 | R4 | 162 | 24.42 | 7.4 | 38 | -128.34 | 10.5 | BROKEN_BY_FIX |
| 19 | FollowDiv | M30 | R3 | 198 | 496.34 | 25.3 | 23 | -16.36 | 26.1 | BROKEN_BY_FIX |
| 20 | FollowDiv | M15 | R4 | 549 | 1,265.49 | 8.5 | 110 | 275.13 | 9.3 | WEAKENED_STILL_PROFIT |
| 20 | ATR | M15 | R4 | 176 | 593.35 | 8.5 | 38 | -128.34 | 10.5 | BROKEN_BY_FIX |
| 20 | FollowDiv | H4 | R2 | 23 | 560.39 | 20.0 | 0 | N/A | N/A | ZERO_FILL_AFTER_FIX |
| 20 | FollowDiv | M30 | R3 | 226 | 491.08 | 24.8 | 23 | -16.36 | 26.1 | BROKEN_BY_FIX |
| 20 | GapSweep | H1 | R4 | 88 | 461.76 | 19.5 | 40 | 642.93 | 25.0 | OK_STILL_PROFIT |
| 20 | GapSweep | H12 | R3 | 26 | 436.48 | 30.4 | 19 | 596.24 | 33.3 | OK_STILL_PROFIT |
| 20 | Div | M15 | R4 | 397 | -172.89 | 9.3 | 233 | -1,693.22 | 6.9 | STILL_LOSS |
| 20 | ATR | M30 | R3 | 112 | 263.24 | 38.7 | 19 | 28.74 | 47.4 | WEAKENED_STILL_PROFIT |
| 20 | Fibo | D1 | R1 | 1 | 249.95 | 100.0 | 0 | N/A | N/A | ZERO_FILL_AFTER_FIX |
| 20 | GapSweep | D1 | R3 | 20 | 235.65 | 41.2 | 17 | -34.00 | 35.7 | BROKEN_BY_FIX |
| 21 | FollowDiv | M15 | R4 | 549 | 1,265.49 | 8.5 | 110 | 275.13 | 9.3 | WEAKENED_STILL_PROFIT |
| 21 | ATR | M15 | R4 | 176 | 593.35 | 8.5 | 38 | -128.34 | 10.5 | BROKEN_BY_FIX |
| 21 | FollowDiv | H4 | R2 | 23 | 560.39 | 20.0 | 0 | N/A | N/A | ZERO_FILL_AFTER_FIX |
| 21 | FollowDiv | M30 | R3 | 226 | 491.08 | 24.8 | 23 | -16.36 | 26.1 | BROKEN_BY_FIX |
| 21 | GapSweep | H1 | R4 | 88 | 461.76 | 19.5 | 40 | 642.93 | 25.0 | OK_STILL_PROFIT |
| 21 | GapSweep | H12 | R3 | 26 | 436.48 | 30.4 | 19 | 596.24 | 33.3 | OK_STILL_PROFIT |
| 21 | Div | M15 | R4 | 397 | -172.89 | 9.3 | 233 | -1,693.22 | 6.9 | STILL_LOSS |
| 21 | ATR | M30 | R3 | 112 | 263.24 | 38.7 | 19 | 28.74 | 47.4 | WEAKENED_STILL_PROFIT |
| 21 | Fibo | D1 | R1 | 1 | 249.95 | 100.0 | 0 | N/A | N/A | ZERO_FILL_AFTER_FIX |
| 21 | GapSweep | D1 | R3 | 20 | 235.65 | 41.2 | 17 | -34.00 | 35.7 | BROKEN_BY_FIX |
| 22 | GapSweep | M15 | R2 | 230 | 8,487.73 | 17.0 | 231 | 7,826.98 | 16.9 | OK_STILL_PROFIT |
| 22 | GapSweep | M30 | R2 | 118 | 5,864.46 | 17.1 | 118 | 4,661.67 | 16.9 | OK_STILL_PROFIT |
| 22 | GapSweep | H1 | R2 | 49 | 5,497.62 | 24.5 | 48 | 5,492.60 | 25.0 | OK_STILL_PROFIT |
| 22 | GapSweep | H4 | R1 | 12 | 1,394.85 | 16.7 | 12 | 1,394.85 | 16.7 | OK_STILL_PROFIT |
| 22 | FollowDiv | M15 | R4 | 549 | 1,265.49 | 8.5 | 110 | 275.13 | 9.3 | WEAKENED_STILL_PROFIT |
| 22 | ATR | M15 | R4 | 176 | 593.35 | 8.5 | 38 | -128.34 | 10.5 | BROKEN_BY_FIX |
| 22 | FollowDiv | H4 | R2 | 23 | 560.39 | 20.0 | 0 | N/A | N/A | ZERO_FILL_AFTER_FIX |
| 22 | FollowDiv | M30 | R3 | 226 | 491.08 | 24.8 | 23 | -16.36 | 26.1 | BROKEN_BY_FIX |
| 22 | GapSweep | D1 | R3 | 2 | 442.40 | 50.0 | 2 | 442.40 | 50.0 | OK_STILL_PROFIT |
| 22 | Div | M15 | R4 | 397 | -172.89 | 9.3 | 233 | -1,693.22 | 6.9 | STILL_LOSS |
| 24 | FVG | M15 | R4 | 5401 | 13,502.30 | 10.0 | 575 | 6,212.00 | 12.4 | WEAKENED_STILL_PROFIT |
| 24 | FVG | H4 | R1 | 528 | 8,364.38 | 18.7 | 65 | -1,119.21 | 13.3 | BROKEN_BY_FIX |
| 24 | FVG | H12 | R3 | 66 | 4,193.94 | 48.5 | 19 | -455.70 | 26.3 | BROKEN_BY_FIX |
| 24 | FVG | M30 | R4 | 4033 | 3,826.87 | 12.2 | 261 | 655.26 | 14.7 | WEAKENED_STILL_PROFIT |
| 24 | FollowDiv | M15 | R4 | 509 | 217.98 | 7.9 | 106 | -33.73 | 8.7 | BROKEN_BY_FIX |
| 24 | FollowDiv | H4 | R2 | 18 | 581.91 | 20.0 | 0 | N/A | N/A | ZERO_FILL_AFTER_FIX |
| 24 | ATR | M15 | R4 | 162 | 24.42 | 7.4 | 38 | -128.34 | 10.5 | BROKEN_BY_FIX |
| 24 | FollowDiv | M30 | R3 | 198 | 514.10 | 25.3 | 23 | -16.36 | 26.1 | BROKEN_BY_FIX |
| 24 | FVG | D1 | R3 | 8 | 475.02 | 25.0 | 3 | 1,068.83 | 66.7 | OK_STILL_PROFIT |
