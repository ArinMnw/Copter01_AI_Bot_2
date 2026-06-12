# Filter Checks by Strategy

ตารางเปรียบเทียบว่า filter แต่ละตัวใช้กับ strategy ไหนบ้าง  
อิงจาก skip list ใน `trailing.py` (อัพเดท 2026-06-12)

## ตาราง

| S#  | ท่า                     | Trend Recheck (fill) | Trend Recheck (approach) | PD Fibo Plus | RSI Recheck |
|-----|-------------------------|:--------------------:|:------------------------:|:------------:|:-----------:|
| S1  | Zone / Engulf           | ✗ | ✗ | ✗ | ✗ (zone-based) |
| S2  | FVG                     | ✗ | ✗ | ✗ | ✓ |
| S3  | EMA Bounce              | ✗ | ✗ | ✗ | ✓ |
| S4  | Supply / Demand         | ✓ | ✓ | ✓ | ✓ |
| S5  | BB Squeeze              | ✓ | ✓ | ✓ | ✓ |
| S6  | RSI OB/OS               | ✓ | ✓ | ✓ | ✓ |
| S7  | Candle Pattern          | ✓ | ✓ | ✓ | ✓ |
| S8  | Support / Resistance    | ✓ | ✓ | ✓ | ✓ |
| S9  | RSI Divergence          | ✗ | ✗ | ✗ | ✗ |
| S10 | CRT                     | ✗ | ✗ | ✗ | ✓ |
| S11 | Fibonacci               | ✗ | ✗ | ✗ | ✗ (fibo zone) |
| S12 | Liquidity Sweep         | ✓ | ✓ | ✓ | ✓ |
| S13 | Order Block             | ✓ | ✓ | ✗ | ✓ |
| S14 | Sweep RSI (market)      | ✗ | ✗ | ✗ | ✗ |
| S15 | VP Reversal (counter)   | ✗ | ✗ | ✗ | ✗ |
| S16 | Sideway Breakout        | ✗ | ✓ ⚠️ | ✗ | ✗ |
| S17 | Sweep Sniper (counter)  | ✗ | ✗ | ✗ | ✗ |

## Skip Lists (source)

| Filter | Skip (sid) | Function |
|--------|-----------|----------|
| Trend Recheck (fill) | **1, 2, 3**, 9, 10, **11**, 14, 15, 16, 17 | `check_fill_trend_recheck` ~line 3209 |
| Trend Recheck (approach/pending) | **1, 2, 3**, 9, 10, **11**, 14, 15, 17 | `check_pending_trend_approach` ~line 3567 |
| PD Fibo Plus | **1, 2, 3**, 9, 10, **11**, 13, 14, 15, 16, 17 | `check_fill_pdfiboplus` ~line 3836 |
| RSI Recheck | **1**, 9, **11**, 14, 15, **16**, 17 | `check_fill_rsi_recheck` ~line 2991 |

## หมายเหตุ

- **S1/S2/S3/S11**: ใช้ trend filter ของตัวเองที่ signal generation — ไม่ใช้ Trend Recheck fill/approach และ PD Fibo Plus
- **S16 ⚠️** : approach ผ่านการเช็ค Trend Recheck แต่ fill ข้าม — อาจต้องพิจารณา consistency
- **S10**: ข้าม Trend Recheck (fill+approach) แต่ยังมี RSI Recheck
- **S13**: ไม่มี PD Fibo Plus (เพราะ OB เป็น PD ของตัวเอง) แต่มี Trend + RSI
- **S1, S11**: ข้าม RSI Recheck ด้วย (zone / fibo zone เป็น filter หลัก)
