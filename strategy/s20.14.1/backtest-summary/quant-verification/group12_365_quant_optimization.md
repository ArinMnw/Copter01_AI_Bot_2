# Group 12 Quant Verification & 365-Day Backtest Optimization Summary

## 1. Overview & Setup

- **Script**: `v38_standalone_group12.py`
- **Backtest Period**: 365 Days
- **Symbol**: `XAUUSD.iux` (Spread 14 points / $0.14)
- **Quant Strategy Checklist Optional Rules Implemented**:
  - **Rule #7 Limit Penetration**: `ENABLE_LIMIT_PENETRATION = True` (Limit Orders require price to penetrate by $0.10 to execute)
  - **Rule #9 Negative Slippage**: `ENABLE_SL_SLIPPAGE = True` ($0.10 negative slippage penalty added on Stop-Loss exits)
  - **Rule #17 Friday Force Close**: `ENABLE_FRIDAY_FORCE_CLOSE = True` (Positions force-closed Friday late night before market close)
- **Tested Timeframes (`target_tfs`)**: `M1`, `M5`, `M15`, `M30`, `H1`, `H4`, `H12`, `D1`
- **Filter**: All internal strategy combinations unblocked (`target_orders = None`)

---

## 2. Overall Summary

| Metric | Value |
|---|---|
| **Total Trades** | 88,676 |
| **Total Winning Trades** | 11,490 |
| **Total Losing Trades** | 77,116 |
| **Overall Win Rate** | **13.0%** |
| **Total Net P&L** | **+$489,817.26** |

---

## 3. Summary by Timeframe (TF)

| Timeframe | Trades | Wins | Losses | Win Rate (%) | Net P&L ($) |
|---|---|---|---|---|---|
| **H1** | 15,186 | 2,045 | 13,141 | **13.5%** | **+$494,161.14** |
| **M30** | 23,020 | 3,095 | 19,925 | **13.4%** | **+$8,902.17** |
| **H12** | 625 | 83 | 542 | **13.3%** | **+$1,561.09** |
| **M15** | 47,216 | 5,931 | 41,285 | **12.6%** | -$2,420.19 |
| **D1** | 288 | 47 | 241 | **16.3%** | -$3,340.36 |
| **H4** | 2,341 | 289 | 2,052 | **12.3%** | -$9,046.59 |

---

## 4. Top Profitable Strategy & Timeframe Combinations

| Rank | Pattern / Strategy | TF | Trades | Wins | Win Rate (%) | Net P&L ($) |
|---|---|---|---|---|---|---|
| 1 | **Naiya** | **H1** | 5,435 | 911 | 16.8% | **+$488,913.68** |
| 2 | **Naiya Doji** | **M30** | 19,338 | 2,305 | 11.9% | **+$9,011.99** |
| 3 | **Naiya/Div** | **H1** | 155 | 12 | 7.7% | **+$8,938.40** |
| 4 | **Naiya Doji** | **H12** | 460 | 49 | 10.7% | **+$3,217.83** |
| 5 | **Naiya/FollowDiv** | **H1** | 33 | 4 | 12.1% | **+$3,043.29** |
| 6 | **Naiya** | **M30** | 2,600 | 534 | 20.5% | **+$2,996.73** |
| 7 | **Naiya** | **M15** | 5,066 | 970 | 19.1% | **+$2,903.68** |
| 8 | **Naiya/ATR** | **H1** | 30 | 10 | 33.3% | **+$2,222.62** |
| 9 | **Naiya/Doji** | **H1** | 2 | 2 | 100.0% | **+$1,643.81** |
| 10 | **GapSweep** | **H1** | 100 | 57 | 57.0% | **+$1,114.06** |
| 11 | **GapSweep** | **M15** | 199 | 110 | 55.3% | **+$971.37** |
| 12 | **GapSweep** | **H12** | 32 | 16 | 50.0% | **+$898.69** |
| 13 | **GapSweep** | **D1** | 27 | 13 | 48.1% | **+$897.80** |
| 14 | **ATR** | **H1** | 38 | 12 | 31.6% | **+$649.12** |
| 15 | **GapSweep** | **M30** | 131 | 74 | 56.5% | **+$579.00** |
| 16 | **Naiya Hidden** | **M30** | 278 | 72 | 25.9% | **+$554.24** |
| 17 | **GapSweep** | **H4** | 48 | 24 | 50.0% | **+$481.62** |
| 18 | **FollowDiv** | **M15** | 548 | 123 | 22.4% | **+$474.32** |
| 19 | **Fibo** | **D1** | 1 | 1 | 100.0% | **+$249.95** |
| 20 | **Fibo** | **H4** | 8 | 4 | 50.0% | **+$210.15** |
| 21 | **FollowDiv** | **M30** | 226 | 51 | 22.6% | **+$160.50** |
| 22 | **FollowDiv** | **H4** | 23 | 5 | 21.7% | **+$131.24** |
| 23 | **ATR** | **M15** | 177 | 39 | 22.0% | **+$130.05** |
| 24 | **FollowDiv** | **H1** | 74 | 13 | 17.6% | **+$117.29** |
| 25 | **Naiya Hidden** | **H12** | 12 | 2 | 16.7% | **+$38.04** |
| 26 | **Fibo/ATR** | **M15** | 1 | 1 | 100.0% | **+$33.08** |
| 27 | **Fibo** | **M15** | 8 | 3 | 37.5% | **+$0.65** |

---

## 5. Key Findings & Recommendations

1. **Top Performer**: `Naiya` ใน TF **H1** สร้างกำไรได้สูงสุดอย่างโดดเด่นถึง **+$488,913.68** (จากกำไรสุทธิรวม $489,817.26)
2. **Best Win Rate Strategy**: `GapSweep` แสดง Win Rate สูงสม่ำเสมอทุก TF (**48.1% - 57.0%**) ทำกำไรบวกทุก TF (H1, M15, H12, D1, M30, H4)
3. **Best Timeframe**: **H1** เป็น TF ที่ทำกำไรสุทธิสูงที่สุด (**+$494,161.14**) ตามมาด้วย **M30** (**+$8,902.17**)
4. **Quant Checklist Stability**: การเปิดใช้ **Rule #7 Penetration Guard**, **Rule #9 SL Slippage**, และ **Rule #17 Friday Force Close** ทำให้ระบบมีความสมจริงสูง ป้องกัน Over-optimistic fill และรองรับ Gap วันหยุดได้อย่างมั่นคง
