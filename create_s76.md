# S76 - Wider All-in-4S Overlay Search Above S75

สถานะ: research/backtest-only, ยังไม่ wire เข้า live bot

## เป้าหมาย

หา champion ตัวถัดไปที่ชนะ S75 โดยใช้สูตร sizing เดียวกับ P13/P16/S75:

```text
simulate_equity_substream(raw, cfg, START_EQUITY=1000)
-> daily_series_from_trades()
-> sum daily PnL across weighted legs
```

## Baseline

S75:

```text
S75 = P16 + S63x8 + S69x24 + S64x8
```

| Metric | S75 |
|---|---:|
| Avg $/day | 333.60 |
| Min $/day | 312.10 |
| Min PF | 4.77 |
| Max losing-day streak | 3 |
| Worst day | -919.26 |
| Max lot | 0.19 |

## Search

Runner: `optimize_s76_champion_search.py`

Search space:

- Base variants: P16 full, P16 leave-one-out, P16 leave-two-out for selected low/risk legs
- All-in-4S overlay:
  - S63: 0, 2, 4, 6, 8, 10, 12, 16
  - S69: 0, 8, 16, 20, 24, 28, 32, 36, 40, 48
  - S64: 0, 1, 2, 4, 6, 8, 10, 12
- Windows: 90/120/150/180 วัน
- Primary guard: worst day >= -1000, max streak <= S75
- Conservative audit: worst day >= S75 worst day (-919.26)

## S76 Candidate

ตัวที่ชนะ S75 ภายใต้ guard -1000:

```text
S76 = P16 + S63x10 + S69x24 + S64x12
```

| Window | $/day | PF | Streak | Worst day |
|---|---:|---:|---:|---:|
| 90d | 339.06 | 4.99 | 3 | -857.98 |
| 120d | 362.25 | 4.84 | 3 | -854.76 |
| 150d | 312.60 | 4.57 | 3 | -854.19 |
| 180d | 334.34 | 4.54 | 3 | -973.16 |

Summary:

- Avg $/day = 337.07
- Min $/day = 312.60
- Min PF = 4.54
- Max losing-day streak = 3
- Worst day = -973.16

## Comparison

| Metric | S75 | S76 |
|---|---:|---:|
| Avg $/day | 333.60 | 337.07 |
| Min $/day | 312.10 | 312.60 |
| Min PF | 4.77 | 4.54 |
| Max streak | 3 | 3 |
| Worst day | -919.26 | -973.16 |

S76 ชนะ S75 ด้าน avg/min $/day และไม่ทำ streak แย่ลง แต่แลกกับ:

- PF ต่ำลง
- worst day แย่ขึ้นประมาณ -53.90 ดอลลาร์

## Conservative Variant

เมื่อตั้ง guard เข้มว่า worst day ต้องไม่แย่กว่า S75 (`>= -919.26`):

```text
S76-C = P16 + S63x8 + S69x24 + S64x12
```

| Metric | S75 | S76-C |
|---|---:|---:|
| Avg $/day | 333.60 | 334.43 |
| Min $/day | 312.10 | 310.62 |
| Min PF | 4.77 | 4.59 |
| Max streak | 3 | 3 |
| Worst day | -919.26 | -919.26 |

S76-C ชนะเฉพาะ avg $/day แต่แพ้ S75 ที่ min $/day และ PF จึงไม่ใช่ champion หลัก

## Look-Ahead Bias Audit

ใช้ framework เดียวกับ S75:

- P16 raw trades มาจาก cache เดิมที่ replay ด้วย `run_single()` ของ P16 legs
- All-in-4S raw trades มาจาก S63/S64/S69 research runner เดิม
- S63/S69 detect จาก closed bar แล้ว fill bar ถัดไป
- HTF lookup ใน framework ใช้ closed HTF bar (`close_times <= entry_time`)

ข้อจำกัด:

- ยังไม่ได้ forensic audit ทุกไฟล์ของ P16 legs ทีละบรรทัด
- ยังไม่ใช่ live execution simulation
- ยังไม่ควร wire เข้า live bot

## Verdict

S76 เป็น champion candidate ถัดจาก S75 แบบ aggressive เล็กน้อย:

- ชนะ S75 จริงใน avg $/day และ min $/day
- max streak เท่าเดิม
- worst day ยังอยู่ใน no-blow guard -1000
- แต่ PF ลดลงและ worst day แย่กว่า S75

หากพี่ต้องการ conservative-only ที่ worst day ไม่แย่กว่า S75 ให้คง S75 เป็น champion ต่อ

## Files

- `optimize_s76_champion_search.py`
- `s76_champion_search.csv`
- `s76_champion_search_conservative.csv`
- `create_s76.md`
