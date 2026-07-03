# S77 - Fine All-in-4S Overlay Champion Above S75/S76

สถานะ: research/backtest-only, ยังไม่ wire เข้า live bot

## เป้าหมาย

หา champion ตัวถัดไปที่ชนะ S75 และ S76 โดยใช้สูตร sizing เดียวกับ P13/P16/S75/S76:

```text
simulate_equity_substream(raw, cfg, START_EQUITY=1000)
-> daily_series_from_trades()
-> sum daily PnL across weighted legs
```

ไม่ใช้ fixed-lot recompute คนละระบบ

## Baseline Reproduction

Reproduce จาก runner เดิมก่อนเริ่ม search:

| Portfolio | Avg $/day | Min $/day | Min PF | Max streak | Worst day | Max lot |
|---|---:|---:|---:|---:|---:|---:|
| S75 = P16 + S63x8 + S69x24 + S64x8 | 333.60 | 312.10 | 4.77 | 3 | -919.26 | 0.19 |
| S76 = P16 + S63x10 + S69x24 + S64x12 | 337.07 | 312.60 | 4.54 | 3 | -973.16 | 0.19 |

## Search

Runner: `optimize_s77_champion_search.py`

ใช้ cache raw trades เดิมใน `tmp/s72_cache`:

- P16 raw trades จาก demo portfolio legs
- All-in-4S raw trades ที่มีจริงใน cache: S63, S64, S69
- Windows: 90/120/150/180 วัน
- Risk floors: -700, -900, -919.26, -973.16, -1000
- Coarse search: P16 full + P16 leave-one-out
- Fine search: รอบแคบใกล้โซนที่ชนะ S76

## S77 Candidate

ตัวที่ชนะ S75/S76 โดย worst day ไม่แย่กว่า S76:

```text
S77 = P16 + S63x11.75 + S69x22.25 + S64x13.25
```

| Window | $/day | PF | Streak | Worst day |
|---|---:|---:|---:|---:|
| 90d | 341.01 | 4.85 | 3 | -929.97 |
| 120d | 364.36 | 4.68 | 3 | -909.80 |
| 150d | 312.82 | 4.43 | 3 | -909.23 |
| 180d | 335.19 | 4.43 | 3 | -973.16 |

Summary:

- Avg $/day = 338.35
- Min $/day = 312.82
- Min PF = 4.43
- Max losing-day streak = 3
- Worst day = -973.16
- Max lot = 0.19
- Max leg DD = 55.01%
- Skipped by circuit breaker = 9727

## Comparison

| Metric | S75 | S76 | S77 |
|---|---:|---:|---:|
| Avg $/day | 333.60 | 337.07 | 338.35 |
| Min $/day | 312.10 | 312.60 | 312.82 |
| Min PF | 4.77 | 4.54 | 4.43 |
| Max streak | 3 | 3 | 3 |
| Worst day | -919.26 | -973.16 | -973.16 |
| Max lot | 0.19 | 0.19 | 0.19 |

S77 ชนะ S75/S76 ด้าน avg $/day และ min $/day, streak ไม่แย่ลง, และ worst day ไม่แย่กว่า S76
แต่ PF ลดลงจาก S76

## Aggressive Variant

ถ้ายอมให้ floor ลงถึง -1000:

```text
S77-A = P16 + S63x12 + S69x22.75 + S64x13.75
```

| Metric | S76 | S77-A |
|---|---:|---:|
| Avg $/day | 337.07 | 339.15 |
| Min $/day | 312.60 | 313.18 |
| Min PF | 4.54 | 4.40 |
| Max streak | 3 | 3 |
| Worst day | -973.16 | -994.18 |

S77-A ชนะกำไรมากกว่า S77 แต่ worst day แย่กว่า S76 ประมาณ -21.02 ดอลลาร์

## Conservative / Risk Audit Variant

ถ้าต้องการลด worst day ให้ดีกว่า S75/S76 มากขึ้น:

```text
S77-C = P16 + S63x8 + S69x23 + S64x5
```

| Metric | S75 | S76 | S77-C |
|---|---:|---:|---:|
| Avg $/day | 333.60 | 337.07 | 332.24 |
| Min $/day | 312.10 | 312.60 | 312.61 |
| Min PF | 4.77 | 4.54 | 4.91 |
| Max streak | 3 | 3 | 3 |
| Worst day | -919.26 | -973.16 | -892.31 |

S77-C ไม่ใช่ champion เพราะ avg $/day แพ้ S75/S76 แต่เป็น risk-audit variant ที่ลด worst day ลงชัดเจน

## Look-Ahead Bias Audit

ตรวจระดับ framework แล้ว:

- S77 ใช้ raw trades/cache เดียวกับ S75/S76 และ sizing helper เดียวกัน
- P16 legs มาจาก `run_single()` / demo portfolio replay เดิม
- S63/S69 detect จาก closed bar แล้ว fill bar ถัดไป
- S64 ใช้ replay แบบ closed-bar ตาม All-in-4S runner เดิม
- HTF lookup ใน framework ใช้ closed HTF bar (`close_times <= entry_time`)
- Search runner ไม่สร้าง signal ใหม่จาก future OHLC; ทำเฉพาะ reweight daily PnL ของ raw trades ที่ถูก simulate ไว้แล้ว

ข้อจำกัด:

- ยังไม่ได้ forensic audit รายไฟล์ของทุก P16 leg ทีละบรรทัด
- All-in raw trades ใน cache ตอนนี้มีเฉพาะ S63/S64/S69; ยังไม่ได้เพิ่ม generator จาก PDF technique ใหม่
- ยังไม่ใช่ live execution simulation และยังไม่ควร wire เข้า bot จริง

## Verdict

S77 เป็น champion candidate ถัดจาก S76:

- ชนะ S75 และ S76 จริงใน avg $/day และ min $/day
- max losing-day streak เท่าเดิมที่ 3
- worst day ไม่แย่กว่า S76
- แต่ PF ลดลง จึงควรถือเป็น aggressive-profit champion มากกว่า conservative champion

หากพี่ต้องการเน้นบัญชี $1000 แบบลด daily shock ให้ใช้ S75 ต่อ หรือพิจารณา S77-C เป็น risk reference

## Files

- `optimize_s77_champion_search.py`
- `s77_champion_search.csv`
- `s77_champion_search_fine.csv`
- `create_s77.md`
