# S84 Attempt - Old Wick Eat Close-Fail Revisit

สถานะ: research/backtest-only, ยังไม่ wire เข้า live bot

## Baseline

Champion ล่าสุดยังเป็น:

```text
S81 = P16 + S63x12.8 + S69x22.1925 + S64x13.875
```

| Metric | S81 |
|---|---:|
| Avg $/day | 339.82 |
| Min $/day | 313.60 |
| Min PF | 4.37 |
| Max streak | 3 |
| Worst day | -999.91 |

## Candidate

```text
S84 = Old Wick Eat Close-Fail Revisit / Follow
```

ที่มาจาก PDF All-in-4S:

- กินไส้เก่า + ปิดไม่คลุม
- กินไส้ไม่จำเป็นต้องกินจนมิด
- กินไส้แล้วถอย M5/M15
- ถ้าปิดไม่คลุม อาจย้อนคืนหรือแตก

## Implementation

ไฟล์:

- `strategy84.py`
- `sim_s84_backtest.py`
- `optimize_s84_wick_revisit.py`

หลักการคำนวณ:

1. หา old wick ที่เด่นใน lookback
2. แท่งปัจจุบันแทง/กินไส้เก่า
3. แต่ปิดไม่คลุม extreme ของ wick
4. ทดสอบ 2 mode:
   - `revisit`: เล่นกลับเข้า defect/inside wick
   - `follow`: เล่นตามทางที่กินไส้
5. fill ที่แท่งถัดไปเท่านั้น
6. ใช้ `simulate_equity_substream(raw, cfg, START_EQUITY=1000)` สำหรับ exact sizing

## 90d Scout Results

ไฟล์ผล:

- `s84_wick_revisit_micro_scout_90.csv`
- `s84_wick_revisit_follow_micro_scout_90.csv`

Best 90d:

| Candidate | Avg $/day | PF | Max streak | Worst day | Trades |
|---|---:|---:|---:|---:|---:|
| S84 revisit best | -5.12 | 0.68 | 8 | -86.77 | 1518 |
| S84 follow best | -6.95 | 0.46 | 9 | -55.34 | 1284 |

## Verdict

S84 ไม่ผ่าน:

- 90d best ยังติดลบหนัก
- PF ต่ำกว่า 1 ชัดเจน
- max losing-day streak 8-17
- จำนวน trade สูงเกินไป แปลว่า definition จับ noise มากกว่า edge
- ไม่ควรนำไป overlay กับ S81

Champion ล่าสุดยังเป็น S81.

## Look-Ahead Bias Audit

- `strategy84._detect_closed()` ใช้ closed bar index `j`
- `sim_s84_backtest.replay84()` fill ที่ `j + 1`
- TP/SL exit ใช้ข้อมูลหลัง fill เท่านั้น
- optimizer ทำ fixed/raw scout แล้ว exact validation ด้วย sizing เดิม
- ไม่ wire เข้า live bot

## Next Direction

ควรเปลี่ยนไป generator ที่มี anchor ชัดกว่า S84 เช่น:

- Significant levels / old H-L break
- doji/support-resistance rejection
- Fibo 50-60 RUN decision
- HTF daily/H12 future-read filter
