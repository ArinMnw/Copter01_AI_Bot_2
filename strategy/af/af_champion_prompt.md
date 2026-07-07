Read AGENTS.md first.

สถานะ: AMBFIX LADDER ปิดครบทุกเป้าแล้ว (2026-07-04) — $1000/$1500/$2000 ทั้ง avg และ min
Champion ล่าสุด: AF51 = avg $2,189.5502/day, min $2,001.0534/day, minPF 9.57,
streak 3, worst -999.90946, floors -999.91/-1000 pass

เป้าหมาย session นี้ (2 เฟสตามลำดับ):
PHASE 1 (สำคัญสุด): WALK-FORWARD VALIDATION ของ AF51 — พิสูจน์ว่า edge ไหนเป็นของจริง
  ไม่ใช่ in-sample overfit ก่อนคิดเรื่องเงินจริง
PHASE 2: ไล่ ladder ต่อ AF52+ เป้า $2500 → $3000 จาก s86 screen ที่เหลือ + configs ใหม่
ใช้ framework เดิมเท่านั้น: simulate_equity_substream START_EQUITY=1000,
windows 90/120/150/180, streak <= 3, floors -700/-900/-973.16/-999.91/-1000
ห้าม fixed-lot recompute คนละระบบ

═══ บริบทจาก sessions ก่อน (2026-07-04) ═══

1. ประวัติศาสตร์ที่ต้องรู้:
   - S-LADDER เดิม (S89→S131, avg $1241) = ARTIFACT ทั้งเส้น: กติกา SL-first แจกชัยชนะ
     ให้ inverse ฟรีในแท่งที่แตะทั้ง TP+SL (19.3% ของไม้) — ดู create_ambfix_audit.md
     ห้ามฟื้น ห้ามตีความเป็นเงินจริง
   - AMBFIX resolution (กติกาซื่อสัตย์): แท่ง exit แตะทั้ง TP+SL → M1 replay ตัดสิน
     ตามจริง; ไม่มี M1/M1 กำกวม → pessimistic ต่อ leg เรา (direct→SL, inverse→raw TP)
     M1 ครอบ ~90 วันหลังเท่านั้น
   - Base chain audit ผ่านแล้ว (create_base_chain_audit.md): S88 base สะอาด —
     legs "D1_INV" ใน base จริงๆ เทรด direct, INV S85SIG x0.007 impact ≤$0.52/วัน

2. AMBFIX LADDER เต็ม (base = S88 = s88_s86run_ratr3_daily.csv, 481.6235/449.1242):
   [config 28 = S84_M15 target28 เดิม]
   AF1  INV c28 RD4.0-5.0 H17 x172.759  → 522.98/465.20
   AF2  DIR c28 RD2.7-3.4 H10 x196.726  → 561.67/508.87
   AF3  DIR c28 RD2.7-3.4 H12 x123.035  → 598.02/531.58
   AF4  DIR c28 RD5.0-7.0 H17 x92.141   → 628.65/556.37
   AF5  INV c28 RD3.4-4.0 H11 x325.852  → 658.68/582.60
   AF6  DIR c28 RD5.0-7.0 H14 x222.360  → 688.14/606.22
   AF7  INV c28 RD4.0-5.0 H22 x258.309  → 705.78/632.25
   AF8  DIR c28 RD5.0-7.0 H15 x116.366  → 730.40/649.35
   AF9  INV c28 RD3.4-4.0 H19 x232.335  → 746.88/667.41
   AF10 DIR c28 RD5.0-7.0 H11 x212.057  → 762.71/707.18
   AF11 DIR c28 RD3.4-4.0 H22 x274.789  → 781.71/716.11
   AF12 DIR c28 RD5.0-7.0 H20 x54.139   → 791.80/728.67
   AF13 DIR c28 RD0.8-1.3 H18 x414.033  → 800.44/731.80 (บาง 1 ไม้@90d)
   AF14 DIR c28 RD4.0-5.0 H18 x138.139  → 805.57/732.37
   AF15 INV c28 RD4.0-5.0 H15 x156.917  → 808.86/735.82
   AF16 INV c28 RD2.0-2.7 H9  x158.086  → 827.59/747.50
   AF17 INV c28 RD5.0-7.0 H8  x86.290   → 830.78/754.80
   AF18 DIR c28 RD4.0-5.0 H14 x85.289   → 842.31/763.54
   AF19 INV c28 RD3.4-4.0 H10 x46.265   → 842.76/764.35 (ปิด space c28)
   [config screen s84 ทั้ง 8,192 เปิด configs ใหม่ — labels:]
   c6017=S84_M30_lb48_rw0.35_wb1_eat0.12_fail0.08_op1_mb0.06_mr0.25_mid_revisit_sl0.2_rr1.2
   c5505=เหมือน c6017 แต่ wb0.8 / c4369=S84_M30_lb48_rw0.25_wb0.8_eat0.12_fail0.03_op1_mb0.06_mr0.35_mid_revisit_sl0.2_rr1.2
   c3057=S84_M15_lb72_rw0.25_wb1_eat0.12_fail0.08_op0_mb0.12_mr0.35_mid_revisit_sl0.2_rr1.2
   c889 =S84_M15_lb48_rw0.25_wb1_eat0.12_fail0.03_op0_mb0.12_mr0.35_rr_revisit_sl0.2_rr1.2
   AF20 DIR c6017 RD5.0-7.0 H17 x584.897 → 928.24/865.15
   AF21 DIR c6017 RD5.0-7.0 H10 x344.492 → 961.37/907.16
   AF22 DIR c6017 RD5.0-7.0 H14 x244.089 → 1003.83/963.65   🎯 $1000 avg
   AF23 INV c6017 RD5.0-7.0 H16 x344.837 → 1017.94/995.10
   AF24 DIR c6017 ALL H12 x23.911        → 1038.76/1008.80  🎯 $1000 min
   AF25 INV c5505 RD5.0-7.0 H11 x121.543 → 1047.28/1017.38
   AF26 DIR c5505 RD5.0-7.0 H14 x114.571 → 1061.47/1039.86
   AF27 INV c4369 RD5.0-7.0 H11 x415.734 → 1134.11/1103.98
   AF28 INV c4369 RD5.0-7.0 H22 x222.978 → 1149.17/1109.33
   AF29 DIR c3057 RD4.0-5.0 H19 x733.281 → 1291.67/1244.62
   AF30 INV c3057 RD2.7-3.4 H13 x525.853 → 1349.79/1305.09
   AF31 INV c3057 RD3.4-4.0 H11 x321.025 → 1383.31/1326.21
   AF32 DIR c889 RD2.7-3.4 H9 x491.628   → 1448.92/1375.97
   AF33 DIR c889 RD3.4-4.0 H13 x437.129  → 1477.71/1406.55
   AF34 INV c889 RD2.7-3.4 H13 x273.830  → 1504.91/1439.41  🎯 $1500 avg
   AF35 DIR c889 RD4.0-5.0 H19 x70.685   → 1522.25/1454.45
   AF36 DIR c889 RD4.0-5.0 H17 x215.498  → 1533.60/1471.51
   AF37 DIR c889 RD2.7-3.4 H18 x434.774  → 1557.91/1494.69
   AF38 DIR c889 RD2.7-3.4 H11 x888.785  → 1609.52/1536.32  🎯 $1500 min
   AF39 DIR c889 RD2.7-3.4 H20 x286.625  → 1631.74/1558.80
   AF40 INV c889 RD2.0-2.7 H18 x168.714  → 1642.87/1573.35
   AF41 INV c889 RD2.7-3.4 H16 x106.536  → 1653.13/1586.94
   AF42 DIR c889 RD5.0-7.0 H15 x32.734   → 1662.15/1591.92
   [s86 screen (partial) เปิด s86c7171=S86RUN_M30_lb72_imp2.2_zt0.06_body0.08_ratio0.2_tr1_tl12_tm0.6_swing_rr_sl0.2_rr1.3
    — dir PF 1.66, ambiguity 0 ไม้ = โปรไฟล์สะอาดแบบ P13/P16]
   AF43 DIR s86c7171 ALL H22 x124.801 → 1846.11/1768.82
   AF44 DIR s86c7171 ALL H14 x125.633 → 1899.58/1799.32
   AF45 DIR s86c7171 ALL H15 x31.539  → 1948.15/1848.19
   AF46 DIR s86c7171 ALL H11 x23.755  → 1983.06/1867.05
   AF47 DIR s86c7171 ALL H13 x145.720 → 2120.52/1913.20     🎯 $2000 avg
   AF48 INV s86c7171 ALL H17 x35.801  → 2145.48/1948.23
   AF49 DIR s86c7171 ALL H10 x17.894  → 2161.20/1967.19
   AF50 DIR s86c7171 ALL H20 x7.112   → 2177.70/1985.36
   AF51 INV s86c7171 ALL H18 x20.491  → 2189.55/2001.05     🎯 $2000 min
   AF52 DIR s86c7187 ALL H11 x24.114  → 2225.09/2053.53
   AF53 DIR s86c4227 ALL H16 x56.402  → 2265.25/2097.70
   AF54 DIR s86c6275 ALL H14 x136.450 → 2340.79/2111.20
   AF55 INV s84c889 RD3.4-4.0 H12 x402.161 → 2357.84/2120.72
   AF56 INV s84c4369 RD5.0-7.0 H8 x587.714 → 2452.03/2270.46
   AF57 DIR s84c5505 RD5.0-7.0 H14 x428.643 → 2500.35/2300.13  🎯 $2500 avg
   AF58 INV s84c3057 RD4.0-5.0 H14 x432.389 → 2534.43/2334.53
   AF59 INV s84c28 RD2.0-2.7 H11 x227.609 → 2609.54/2425.37
   AF60 DIR s84c6017 RD5.0-7.0 H18 x159.220 → 2627.05/2449.96
   AF61 INV s84c889 RD3.4-4.0 H11 x392.288 → 2672.14/2496.30
   AF62 DIR s84c5505 RD5.0-7.0 H18 x221.915 → 2713.71/2541.38
   AF63 INV s84c3057 RD3.4-4.0 H8 x2000.000 → 2941.80/2706.25
   AF64 INV s84c28 RD1.3-2.0 H18 x361.049 → 3051.09/2800.00
   [AF65 - AF169 generated via auto-ladder...]
   AF170 INV s84c3057 RD4.0-5.0 H8 x300.000 → 10035.47/8680.66  🎯 $10000 avg — ล่าสุด
   evidence: create_af1.md...create_af64.md + auto_ladder_log.md + afN_*_daily.csv + afN_*_probe.csv

3. กติกาที่ต้องรักษา (สะสมจากทุกรอบ):
   - ห้าม re-weight leg เดิม (เช็ค candidate กับ AF1-AF51 + band/hour/mode/config)
   - Degenerate leg (ชน weight cap ไม่ bind, มักเป็น leg 1-4 ไม้ชนะรวด) → ข้าม;
     ถ้าจะใช้ต้องผ่าน stress-flip rule (W max ที่ base(d)-W*leg(d) >= -999.91) และ
     ระวังเคส stress-cap≈0 เมื่อ leg fire ตรงวัน floor-edge ของ base (ใช้ไม่ได้)
   - Leg บาง (1-3 ไม้@90d) ใช้ได้แต่ระบุคำเตือนใน doc
   - ถ้า threshold ชนขอบ w-hi ที่ตั้ง → sweep กว้าง (2000/5) หาขอบจริงก่อน rebuild
   - beats อาจ fail ที่ threshold เต็มแม้ผ่านที่ w ต่ำกว่า → เลือก leg อื่นที่ margin ชัด

4. เครื่องมือ (scratchpad หายเมื่อ session เปลี่ยน — เขียนใหม่ได้จาก create_af1/af20.md):
   - ambfix_sweep2.py <base_daily> [w_max] [w_step] [family] [cfg_idx] —
     sweep 8 RD bands (all,0.8-1.3,...,5.0-7.0) × (day+H0-23) × dir/inv
   - ambfix_build2.py --base X --out-prefix Y --mode dir/inv [--rd-min --rd-max]
     [--h H] --w-lo A --w-hi B --family s84/s86 --cfg-idx N [--stress]
   - screen_configs.py --family s84/s86 --cache bars_cache_180.pkl --out X.csv
     [--start N --end M] — screen configs ใต้ ambfix @180d (per-trade PF dir/inv)
   - หลัก: run_s84/run_s86 + _grid_s84/_grid_s86("micro") จาก optimize_s88_allin4s_fast.py
     → แก้ outcome แท่งกำกวมด้วย M1 → filter → (invert) → _simulate_leg(raw, OVERLAY_CFG)
   - ⚠️ background workers ตายเมื่อ Claude Code restart — relaunch ด้วย PowerShell
     Start-Process + resume จาก idx สุดท้ายใน CSV; ใช้ bars cache กัน MT5 ชนกัน
   - s86 screen ค้างที่ ~35% (scratchpad/screen_s86_*.csv อาจหาย — รันใหม่ได้)

═══ PHASE 1: WALK-FORWARD VALIDATION (ทำก่อน) ═══

คำถามที่ต้องตอบ: legs/weights ของ AF51 ที่เลือกจากข้อมูล 180 วันชุดเดียว
รอดนอกข้อมูลที่ใช้เลือกมันหรือไม่?

วิธีที่แนะนำ (ปรับได้ตามข้อมูลที่มี):
1. IN-SAMPLE/OUT-OF-SAMPLE SPLIT: ใช้ 120 วันแรกเป็น IS, 60 วันหลังเป็น OOS
   - รัน generator แต่ละ leg (config+filter ตาม AF1-AF51) บน IS เท่านั้น
   - เช็คว่า leg ยังกำไร/ยังผ่านเกณฑ์บน IS ไหม (ถ้า leg เกิดจาก pattern ใน OOS
     เท่านั้น = red flag)
   - แล้ววัดผลของ portfolio AF51 (weights ล็อกเดิม) เฉพาะช่วง OOS 60 วัน:
     avg/min/PF/streak/worst รายวัน — เทียบกับ in-sample
2. รายงานผลตรงๆ: legs ไหนบวกใน OOS, ไหนลบ, portfolio รวมเหลือเท่าไหร่/วัน
   ห้ามปรับ weight ตาม OOS (นั่นคือ overfit ซ้ำ) — รายงานอย่างเดียว
3. เขียน create_af51_walkforward.md + CSV หลักฐาน
4. ถ้า OOS แย่มาก (ติดลบ/พอร์ตแตก) ให้สรุปว่า legs แบบไหนรอด (คาด: legs เนื้อแน่น
   ไม้เยอะ ambiguity ต่ำ จะรอดกว่า legs บาง 1-3 ไม้) แล้วเสนอ ladder v2 ที่ใช้เฉพาะ
   leg โปรไฟล์รอด

═══ PHASE 2: ไล่ LADDER ต่อ (หลัง Phase 1 ได้ข้อสรุป) ═══

- Reproduce AF51 ก่อน (avg 2189.5502 / min 2001.0534 / worst -999.90946)
  + spot-check chain จาก daily CSV
- ทำ s86 screen ให้จบ (เหลือ ~65%) → เก็บ configs ใหม่ (คิวที่เห็นแล้ว: s86
  7187/4227/6275 PF~1.65-1.66)
- ไล่ AF52+ เป้า $2500 → $3000 ด้วยวินัยเดิมทุกข้อ
- ถ้า space ตัน: preset tiny (M5/H1), generator ใหม่จาก PDF อออิน4s
  (โปรไฟล์ที่พิสูจน์แล้วว่ารอด: SL กว้าง, RR สูง, ambiguity ≈ 0, ไม้เนื้อแน่น)

ข้อควรระวัง:
- ตัวเลข ladder ทั้งหมด = in-sample upper bound — Phase 1 คือตัวตัดสินมูลค่าจริง
- Weight ชิดขอบ -999.91 ทุกชั้น ห้ามเพิ่มสุ่มๆ ต้องพิสูจน์ floor+streak ทุกครั้ง
- Weight ใน framework = ตัวคูณ daily PnL ของ substream $1000 ไม่ใช่ position size
  จริง — ก่อน deploy ต้องแปลงเป็น lot จริงและเช็ค margin
- ห้าม wire เข้า live bot — research/backtest-only
- memory มีสรุปครบ: ambfix_ladder_progress.md (ladder เต็ม), s103_s116_ladder_progress.md
ลุยครับ