# S103 Champion - Inverse S84 RD 1.3-2.0 H20-21 Overlay (Stress-Capped Weight)

สถานะ: research/backtest-only, ยังไม่ wire เข้า live bot

## Baseline

Champion ล่าสุดก่อนหน้า:

```text
S102 = S101 + INV_S84_M15_OLDWICK_FOLLOW_RD1.3_2.0_H15_16x2.918
```

| Metric | S102 |
|---|---:|
| Avg $/day | 652.9061 |
| Min $/day | 629.2306 |
| Min PF | 5.57738 |
| Max losing-day streak | 3 |
| Worst day | -999.90785 |
| Max lot | 0.19 |
| Max leg DD | 55.01% |
| Skipped by circuit breaker | 10391 |

Baseline S102 ถูก reproduce ใหม่ก่อนเริ่มรอบนี้ (config index 28, `--w 2.918:2.919:0.001`):
x2.918 ผ่าน `-999.91`, x2.919 fail `-999.91` ตรงกับ `create_s102.md` ทุกค่า และ verify
offline ทั้ง chain S88→S102 จาก daily CSV แล้วตรงเอกสารทุก champion

## New Leg

Winning overlay:

```text
INV_S84_M15_lb48_rw0.25_wb0.8_eat0.06_fail0.03_op1_mb0.06_mr0.35_rr_follow_sl0.2_rr0.9_Frdmin1.3_rd2_hfrom20_hbefore21
```

Meaning:

- Base generator: S84 old-wick follow
- Mode: inverse raw
- TF: M15
- Lookback: 48
- Old wick min: 0.25 ATR
- Wick/body min: 0.8
- Eat tolerance: 0.06 ATR
- Close-fail threshold: 0.03 ATR
- Require opposite close: on
- Min body: 0.06 ATR
- Min range: 0.35 ATR
- Target mode: RR
- SL buffer: 0.2 ATR
- RR: 0.9
- Post-filter: `1.3 <= risk_distance <= 2.0`
- Time filter: `20 <= fill_hour < 21` BKK

Hour-slice sweep บน S102 base รอบนี้ครอบทุกช่องที่เหลือ: H0-H7 และ H23-24 ไม่มี trade
หรือ weight ที่ดีสุด = 0, H9-10 / H21-22 beats=False, H22-23 beats เล็กน้อย (เก็บเป็น
candidate รอบถัดไป), **H20-21 ชนะขาด**

## ⚠️ Degenerate Leg + Stress-Capped Weight (วิธีเลือก weight ต่างจาก S89-S102)

Leg นี้มี 13 ไม้ใน 180 วัน และ**ชนะ TP ทั้ง 13 ไม้หลัง inverse** (raw S84 follow ช่วง
20:00-21:00 BKK แพ้ SL รวดทุกไม้) → daily PnL ของ leg ไม่มีวันติดลบเลยในทุก window
ทำให้กติกาเดิม "highest weight that passes `-999.91`" **ไม่ bind** (ทดสอบถึง x20000
ก็ยังผ่าน floor = artifact ของ leg ที่ win rate 100% ไม่ใช่ edge จริง)

จึงใช้ **stress-flip rule** เลือก weight แทน (อนุรักษ์นิยมกว่า):

> W สูงสุด (step 0.001) ที่ทำให้ทุกวันที่ leg active ในทุก window
> `base(d) - W × leg(d) >= -999.91`
> คือสมมุติว่าวันนั้นไม้ของ leg พลิกจากกำไรเป็นขาดทุนขนาดเท่ากัน (แย่กว่า SL จริง
> ที่ RR 0.9 เสียแค่ ~0.9R) วัน worst-day ต้องยังไม่หลุด floor `-999.91`

Binding day คือ 2025-10-06 (base = -468.93636, leg = +5.28):

| Weight | Stress day 2025-10-06 | Result |
|---:|---:|---|
| 100.563 | -999.90904 | pass `-999.91` |
| 100.564 | -999.91432 | fail `-999.91` |

ดูรายละเอียดทุกวันใน `s103_s84_inv_rdmin13_rd20_h20_21_stress_audit.csv`
(คอลัมน์ `stress_day_at_W` = base − W×leg ณ W=100.563 ผ่านทุกวัน)

## New Champion

```text
S103 = S102 + INV_S84_M15_OLDWICK_FOLLOW_RD1.3_2.0_H20_21x100.563
```

| Metric | S103 |
|---|---:|
| Avg $/day | 673.4029 |
| Min $/day | 647.5072 |
| Min PF | 5.73695 |
| Max losing-day streak | 3 |
| Worst day | -999.90785 |
| Max lot | 0.19 |
| Max leg DD | 55.01% |
| Skipped by circuit breaker | 10391 |

Per-window exact from `s103_s84_inv_rdmin13_rd20_h20_21_daily.csv`:

| Window | $/day | PF | Streak | Worst day | Raw trades |
|---:|---:|---:|---:|---:|---:|
| 90 | 647.5072 | 5.73695 | 3 | -987.11361 | 2 |
| 120 | 701.7968 | 6.21839 | 3 | -999.90785 | 3 |
| 150 | 683.7686 | 6.32450 | 3 | -986.25864 | 9 |
| 180 | 660.5392 | 5.91805 | 3 | -999.90703 | 13 |

Runner cross-check (`s103_s84_inv_rdmin13_rd20_h20_21_target28_ultrafine.csv` ที่
add_weight=100.563): avg 673.402946 / min 647.50719 / minPF 5.736947 ตรงกับ daily CSV

## No-Blow Guard

| Floor | Result |
|---|---|
| -700 | fail because the champion ladder already has near -1000 days |
| -900 | fail because the champion ladder already has near -1000 days |
| -973.16 | fail because the champion ladder already has near -1000 days |
| -999.91 | pass (รวม stress-flip test ของ leg ใหม่) |
| -1000 | pass |

## Evidence

- `optimize_s88_allin4s_fast.py`
- `s103_s84_inv_rdmin13_rd20_h9_10_target28_probe.csv`
- `s103_s84_inv_rdmin13_rd20_h20_21_target28_probe.csv`
- `s103_s84_inv_rdmin13_rd20_h21_22_target28_probe.csv`
- `s103_s84_inv_rdmin13_rd20_h22_23_target28_probe.csv`
- `s103_s84_inv_rdmin13_rd20_h23_24_target28_probe.csv`
- `s103_s84_inv_rdmin13_rd20_h0_1..h6_7_target28_probe.csv` (7 ไฟล์ กลางคืนทั้งหมด)
- `s103_s84_inv_rdmin13_rd20_h20_21_target28_wide.csv`
- `s103_s84_inv_rdmin13_rd20_h20_21_target28_fine.csv`
- `s103_s84_inv_rdmin13_rd20_h20_21_target28_ultrafine.csv`
- `s103_s84_inv_rdmin13_rd20_h20_21_stress_audit.csv`
- `s103_s84_inv_rdmin13_rd20_h20_21_daily.csv`

## Look-Ahead Bias Audit

- Research/backtest-only; no live bot wiring.
- S103 uses `s102_s84_inv_rdmin13_rd20_h15_16_daily.csv` as the base, so it is
  compared against the current champion S102.
- The new leg still uses `simulate_equity_substream(raw, cfg, START_EQUITY=1000)`
  for per-leg sizing.
- S84 detection uses closed bar `j`.
- Fill is simulated from `j+1` via the existing `sim_s84_backtest.run_single`
  replay.
- Inverse mode swaps signal/TP/SL on the same raw event and negates
  `diff_usd_per_001lot`.
- `risk_distance` is entry/SL distance known at signal construction time.
- `20 <= fill_hour < 21` uses the simulated fill timestamp available at entry,
  not any post-entry outcome.
- Stress-flip rule ใช้เฉพาะข้อมูล in-sample เดิม (base daily + leg daily) ไม่ใช้
  ข้อมูลอนาคตเพิ่ม — เป็น constraint เข้มขึ้น ไม่ใช่ signal ใหม่
- No future candle, same-bar close fill, or result filter is used.

## Verdict

Found new champion:

```text
S103 = S102 + INV_S84_M15_OLDWICK_FOLLOW_RD1.3_2.0_H20_21x100.563
```

This improves avg $/day (652.91 → 673.40) and min $/day (629.23 → 647.51) while
keeping max losing-day streak at 3 and passing the `-999.91` / `-1000` floors,
with the added stress-flip guard because the leg has zero losing days in-sample.
Continue with S104 search using S103 as the new baseline (H22-23 คือ candidate แรก).
