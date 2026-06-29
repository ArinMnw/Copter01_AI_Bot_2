# S28 — Asian Range Liquidity Sweep + Session Breakout

## แนวคิดหลัก
กลยุทธ์ XAUUSD intraday ที่อิงจากพฤติกรรม institutional ในตลาดทอง:

1. **Asian Session** (02:00-09:00 BKK) สร้าง liquidity pool — retail traders วาง stop loss
   เหนือ High และใต้ Low ของ Asian range
2. **London/NY Session** (11:00-23:00 BKK) — institutional players "sweep" liquidity เหล่านี้
   (fakeout ทะลุ range แล้วกลับตัว) ก่อนจะวิ่งทิศจริง
3. เราเข้า **reversal trade** หลัง sweep: BUY เมื่อ sweep low (wick ทะลุ Asian Low แล้ว
   body กลับเหนือ), SELL เมื่อ sweep high (wick ทะลุ Asian High แล้ว body กลับใต้)

### แหล่งข้อมูล
- Asian Range Breakout Strategy (ForexFactory, QuantifiedStrategies, various)
- ICT Liquidity Sweep + FVG (institutional concepts)
- Session-based scalping research for XAUUSD 2024-2025

## ไฟล์ที่สร้าง
- `strategy28.py` — standalone strategy module (ไม่ wire เข้า live bot)
- `sim_s28_backtest.py` — backtester with look-ahead bias protection
- `optimize_s28.py` — grid search ~136 combinations

## Timeline

### Round 1: Baseline (defaults tight)
- **Config:** sweep_min=0.1, body_rev=0.5, trade_window=14:00-23:00, max_trades=3, min_gap=5
- **ผล M5 30d:** 10 trades, WR=30%, PF=0.83, avgR=-0.112, total P/L=-$26.29
- **ปัญหา:** signal frequency ต่ำมาก (0.33 trades/day) — sweep detection เข้มเกินไป

### Round 2: Relaxed defaults
- **เปลี่ยน:** sweep_min→0.02, body_rev→0.3, trade_window→11:00-23:00,
  max_trades→10, min_gap→2, max_range_atr→20, max_risk_atr→8
- **ผล M5 30d:** 148 trades, WR=25.7%, PF=0.73, avgR=-0.252, total P/L=-$550.71
- **สรุป:** frequency ดีขึ้นมาก (5.3 trades/day) แต่ WR ต่ำ → sweep ดิบไม่มี edge

### Round 3: Grid Search (กำลังรัน)
- ~136 combinations covering: sweep_min × body_rev × SL × RR × TF × filters × sessions
- จะรายงานผลเมื่อเสร็จ

## Exhaustion Checklist

1. [ ] รัน grid search อย่างน้อย 50 combination ตามกฎข้อ 2
2. [ ] ลอง edge-improvement อย่างน้อย 2 แนวทางที่ต่างกัน
3. [ ] sanity-check โค้ด: print trade ตัวอย่าง 5-10 ไม้
4. [ ] คำนวณ expectancy ที่ต้องการ vs ที่หาได้จริง
5. [ ] เขียนสรุปทั้งหมดนี้ลงท้าย create_s28.md
