# Shortlist สำหรับ Forward Demo — 62 กลยุทธ์ / 65 แถว

- คัดจาก `S20_306_to_1519_365_day.md` เฉพาะ 🏆 WINNER (final_gate WINNER + mix_check ผ่านถ้าเป็นตัวผสม) และ 🟡 BORDERLINE (ตกแค่ null p=0.010 เฉียดเกณฑ์ <0.01)
- **ไม่รวม**: FAILED_GATE, NEAR_MISS (mix_check ไม่ผ่าน), WINNER_OTHER_TF, INSUFFICIENT_DATA — เพราะ in-sample บอกแล้วว่าไม่มี edge จริงหรือไม่ชัดพอ ไม่คุ้มเปลือง demo
- ⚠️ ทั้งหมดยังเป็น in-sample ล้วน (คัดจากการลองนับพันครั้ง) **ห้าม wire เข้า live ก่อนผ่าน forward demo จริง**
- หมายเหตุคอลัมน์: 🔁 ซ้ำ = คู่นี้ให้ไม้/net/PF เท่ากันเป๊ะกับอีกตัว (สัญญาณเดียวกัน เลือกใช้แค่ 1) | ⚠️ ชน live = ต้องเปลี่ยนเลข sid ก่อน wire จริง (ไม่ใช่ตัดกลยุทธ์ทิ้ง)

| # | S20 | ชื่อ | ชนิด | TF | ไม้ | กำไร 365 วัน $ | PF | OOS PF | สถานะ | หมายเหตุ |
|---:|---|---|---|---|---:|---:|---:|---:|---|---|
| 1 | 194 | Chande Kroll Stop Flip | เดี่ยว | M5 | 6488 | +9,813 | 1.298 | 1.309 | 🏆 WINNER | – |
| 2 | 143 | Elder Impulse System Color Shift | เดี่ยว | M5 | 6218 | +6,125 | 1.184 | 1.139 | 🏆 WINNER | ชน S20.14 Grp3 |
| 3 | 242 | Rainbow MA Full Alignment | เดี่ยว | M5 | 5295 | +4,864 | 1.17 | 1.174 | 🏆 WINNER | – |
| 4 | 194 | Chande Kroll Stop Flip | เดี่ยว | H1 | 492 | +3,175 | 1.379 | 1.273 | 🏆 WINNER | – |
| 5 | 685 | S20.158 x S20.194 (CONFIRM w15) | ผสม | M5 | 4050 | +2,979 | 1.179 | 1.241 | 🏆 WINNER | – |
| 6 | 242 | Rainbow MA Full Alignment | เดี่ยว | M30 | 838 | +2,153 | 1.195 | 1.108 | 🏆 WINNER | – |
| 7 | 194 | Chande Kroll Stop Flip | เดี่ยว | M30 | 962 | +1,993 | 1.158 | 1.175 | 🏆 WINNER | – |
| 8 | 210 | Bill Williams Accelerator Oscillator Two-Green | เดี่ยว | M30 | 389 | +1,778 | 1.387 | 1.485 | 🏆 WINNER | float=20.21 ชน S20.21 |
| 9 | 277 | Quadratic-Regression Curvature Turn | เดี่ยว | M30 | 276 | +1,552 | 1.476 | 1.342 | 🏆 WINNER | – |
| 10 | 255 | Hikkake Inside-Bar False Breakout | เดี่ยว | H4 | 47 | +1,552 | 2.624 | 1.878 | 🏆 WINNER | – |
| 11 | 168 | Ehlers Super Smoother Crossover | เดี่ยว | M30 | 208 | +1,551 | 1.647 | 1.285 | 🏆 WINNER | – |
| 12 | 751 | S20.277 x S20.242 (CONFIRM w15) | ผสม | M5 | 2315 | +1,531 | 1.154 | 1.145 | 🏆 WINNER | – |
| 13 | 753 | S20.277 x S20.242 (FILTER w15) | ผสม | M5 | 2315 | +1,531 | 1.154 | 1.145 | 🏆 WINNER | ซ้ำกับ S20.751 |
| 14 | 648 | S20.148 x S20.237 (CONFIRM) | ผสม | M30 | 144 | +1,326 | 2.14 | 1.896 | 🏆 WINNER | – |
| 15 | 689 | S20.158 x S20.242 (CONFIRM w10) | ผสม | H1 | 197 | +1,323 | 1.527 | 1.945 | 🏆 WINNER | – |
| 16 | 237 | Ehlers FRAMA Cross | เดี่ยว | M15 | 848 | +1,308 | 1.172 | 1.1 | 🏆 WINNER | – |
| 17 | 339 | Inside Bar MACD Continuation Breakout | เดี่ยว | M30 | 174 | +1,257 | 1.827 | 1.272 | 🏆 WINNER | – |
| 18 | 148 | Inside-Bar Mother-Bar Breakout with EMA50 Trend | เดี่ยว | M30 | 285 | +1,246 | 1.439 | 1.238 | 🏆 WINNER | ชน S20.14 Grp8 |
| 19 | 637 | S20.148 x S20.277 (FILTER) | ผสม | M30 | 200 | +1,153 | 1.63 | 1.646 | 🏆 WINNER | – |
| 20 | 732 | S20.205 x S20.143 (CONFIRM w15) | ผสม | H4 | 81 | +1,050 | 1.482 | 1.411 | 🏆 WINNER | – |
| 21 | 512 | MACD Divergence HalfTrend Confirm | ผสม | M30 | 115 | +1,031 | 2.217 | 2.108 | 🏆 WINNER | – |
| 22 | 422 | Triple MA Volatility Breakout | เดี่ยว | M15 | 342 | +1,012 | 1.398 | 1.312 | 🏆 WINNER | – |
| 23 | 937 | Mixed 169 x 177 FILTER | ผสม | H1 | 69 | +958 | 1.934 | 2.846 | 🏆 WINNER | – |
| 24 | 1092 | Hull Kroll x Cycle Recovery | ผสม | M30 | 195 | +901 | 1.487 | 1.329 | 🏆 WINNER | – |
| 25 | 854 | Rainbow MA x KST Confirm | ผสม | H1 | 115 | +883 | 1.634 | 1.206 | 🏆 WINNER | – |
| 26 | 888 | Mix 339 + 266 (FILTER) | ผสม | M30 | 67 | +797 | 2.559 | 2.158 | 🏆 WINNER | – |
| 27 | 708 | S20.196 x S20.143 (CONFIRM w15) | ผสม | M15 | 318 | +791 | 1.343 | 1.141 | 🏆 WINNER | – |
| 28 | 778 | Mixed 422 x 765 FILTER | ผสม | M15 | 206 | +781 | 1.502 | 2.17 | 🏆 WINNER | – |
| 29 | 471 | Mix 422 + 158 (CONFIRM) | ผสม | M15 | 118 | +659 | 1.901 | 2.385 | 🏆 WINNER | – |
| 30 | 1118 | Hull Kroll x Inside Curvature | ผสม | M30 | 132 | +650 | 1.528 | 1.407 | 🏆 WINNER | – |
| 31 | 1185 | Inside Curvature x Cycle Recovery | ผสม | M5 | 220 | +612 | 1.806 | 1.413 | 🏆 WINNER | – |
| 32 | 1475 | CMO Impulse x Random Walk Separation | ผสม | M15 | 117 | +558 | 1.707 | 1.883 | 🏆 WINNER | – |
| 33 | 1474 | CMO Impulse x Leading OBV | ผสม | M15 | 74 | +519 | 1.922 | 4.213 | 🏆 WINNER | – |
| 34 | 161 | Ultimate Oscillator Williams Buy Setup | เดี่ยว | H1 | 62 | +499 | 1.629 | 1.547 | 🏆 WINNER | – |
| 35 | 950 | Mixed 854 x 168 CONFIRM 48 | ผสม | M5 | 537 | +497 | 1.222 | 1.349 | 🏆 WINNER | – |
| 36 | 356 | Bollinger Volatility Z-Score Breakout | เดี่ยว | M5 | 504 | +484 | 1.199 | 1.035 | 🏆 WINNER | – |
| 37 | 1378 | Inside Curvature x Period Open Cross | ผสม | M5 | 151 | +439 | 1.962 | 1.682 | 🏆 WINNER | – |
| 38 | 342 | ADX Low Volatility Breakout | เดี่ยว | M5 | 297 | +425 | 1.362 | 1.315 | 🏆 WINNER | – |
| 39 | 1062 | Hull Kroll x Volume MACD | ผสม | M15 | 166 | +411 | 1.383 | 2.051 | 🏆 WINNER | – |
| 40 | 724 | S20.196 x S20.406 (CONFIRM w15) | ผสม | M15 | 160 | +408 | 1.378 | 1.283 | 🏆 WINNER | – |
| 41 | 1186 | Inside Curvature x Volume MACD | ผสม | M5 | 112 | +350 | 2.006 | 1.921 | 🏆 WINNER | – |
| 42 | 1499 | CMO Histogram x Fractal Acceptance | ผสม | M15 | 89 | +344 | 1.663 | 1.715 | 🏆 WINNER | – |
| 43 | 1244 | CMO Impulse x ABC Defense | ผสม | M5 | 86 | +313 | 1.791 | 1.357 | 🏆 WINNER | – |
| 44 | 1453 | CMO Impulse x Mother Range Break | ผสม | M5 | 168 | +305 | 1.442 | 1.404 | 🏆 WINNER | – |
| 45 | 1509 | CMO Histogram x Easy Movement | ผสม | M15 | 66 | +296 | 1.776 | 4.05 | 🏆 WINNER | – |
| 46 | 1519 | CMO Histogram x Random Walk Separation | ผสม | M5 | 98 | +262 | 1.711 | 1.681 | 🏆 WINNER | – |
| 47 | 614 | S20.339 x S20.409 (CONFIRM) | ผสม | M5 | 101 | +228 | 1.589 | 2.079 | 🏆 WINNER | – |
| 48 | 795 | Mixed 194 x 237 CONFIRM | ผสม | H1 | 219 | +1,243 | 1.485 | 1.302 | 🟡 BORDERLINE | – |
| 49 | 701 | S20.165 x S20.143 (CONFIRM w15) | ผสม | H4 | 53 | +958 | 1.834 | 2.562 | 🟡 BORDERLINE | – |
| 50 | 690 | S20.158 x S20.153 (CONFIRM w10) | ผสม | M15 | 489 | +948 | 1.271 | 1.157 | 🟡 BORDERLINE | – |
| 51 | 705 | S20.153 x S20.210 (FILTER w5) | ผสม | M30 | 214 | +842 | 1.414 | 1.447 | 🟡 BORDERLINE | – |
| 52 | 679 | S20.153 x S20.143 (SIMULTANEOUS) | ผสม | M15 | 603 | +733 | 1.165 | 1.144 | 🟡 BORDERLINE | – |
| 53 | 837 | Chande Kroll x KST Confirm | ผสม | H1 | 141 | +722 | 1.436 | 1.696 | 🟡 BORDERLINE | – |
| 54 | 774 | Mixed 422 x 766 FILTER | ผสม | M15 | 251 | +689 | 1.352 | 1.033 | 🟡 BORDERLINE | – |
| 55 | 935 | Mixed 168 x 177 FILTER | ผสม | M30 | 102 | +686 | 1.544 | 1.154 | 🟡 BORDERLINE | – |
| 56 | 857 | Rainbow MA x Weekly Retest Confirm | ผสม | H1 | 51 | +499 | 1.666 | 1.742 | 🟡 BORDERLINE | – |
| 57 | 1315 | Inside Curvature x Chaikin Pressure | ผสม | M5 | 414 | +483 | 1.278 | 1.441 | 🟡 BORDERLINE | – |
| 58 | 379 | DMI Strong Trend Re-entry | เดี่ยว | M30 | 62 | +464 | 1.736 | 1.161 | 🟡 BORDERLINE | – |
| 59 | 1149 | Inside MACD x Exhaustion Reclaim State | ผสม | M30 | 67 | +461 | 1.764 | 2.065 | 🟡 BORDERLINE | – |
| 60 | 1505 | CMO Histogram x Confirmed Pivot Break | ผสม | M15 | 54 | +284 | 2.106 | 1.714 | 🟡 BORDERLINE | – |
| 61 | 1253 | CMO Histogram x Force Recovery | ผสม | M15 | 54 | +283 | 1.946 | 1.148 | 🟡 BORDERLINE | – |
| 62 | 1454 | CMO Impulse x NR7 Release | ผสม | M5 | 445 | +279 | 1.15 | 1.131 | 🟡 BORDERLINE | – |
| 63 | 1265 | CMO Histogram x HiLo Acceptance | ผสม | M15 | 31 | +251 | 2.522 | 1.526 | 🟡 BORDERLINE | – |
| 64 | 1463 | CMO Impulse x Hikkake Reclaim | ผสม | M30 | 34 | +214 | 1.457 | 3.396 | 🟡 BORDERLINE | – |
| 65 | 1427 | Inside Fractal x Choppiness Exit | ผสม | M5 | 77 | +172 | 1.556 | 2.552 | 🟡 BORDERLINE | – |

**รวม 65 แถว / 62 กลยุทธ์** (WINNER 47 แถว + BORDERLINE 18 แถว)
