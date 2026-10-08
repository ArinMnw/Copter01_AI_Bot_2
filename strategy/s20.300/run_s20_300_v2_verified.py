# -*- coding: utf-8 -*-
"""run_s20_300_v2_verified.py
Backtest runner สำหรับ S20.300 v2 (โซน TF ใหญ่ + M5 ยืนยัน) — 365 วัน XAUUSD.iux
รันคู่กับ v1 เดิม (run_s20_300_m5_verified.py) เพื่อดูเทียบ ไม่ได้มาแทนที่ v1 อัตโนมัติ
"""
import os, sys
from datetime import datetime, timedelta, timezone
import MetaTrader5 as mt5

sys.path.insert(0, os.path.dirname(__file__))
from v2_zone_ltf_trigger import init_mt5, fetch_data, build_merged_zones, generate_setups, run_backtest, DEFAULT_CFG  # noqa: E402


def main():
    if not init_mt5():
        print("MT5 Init Failed")
        return
    symbol = "XAUUSD.iux"
    now = datetime.now(timezone.utc)
    start_dt = now - timedelta(days=365)

    print("=" * 110, flush=True)
    print(" S20.300 v2 — ZONE (TF ใหญ่ ที่ปิดแล้ว) + M5 CONFIRMATION (STRICT LOT 0.01)", flush=True)
    print(f" Asset: {symbol} | Period: 365 Days", flush=True)
    print("=" * 110, flush=True)

    rates_zone, m5 = fetch_data(symbol, start_dt, now)
    mt5.shutdown()
    _, merged_per_tf = build_merged_zones(rates_zone, m5)
    setups = generate_setups(merged_per_tf)
    print(f"Total confluent M5 signals (dedup ข้าม TF): {len(setups)}", flush=True)

    res = run_backtest(m5, setups)

    print("=" * 110, flush=True)
    print(" S20.300 v2 VERIFIED PERFORMANCE SUMMARY (STRICT 0.01 LOT)", flush=True)
    print("=" * 110, flush=True)
    print(f" Total Trades Executed:   {res['trades']:,}", flush=True)
    print(f" Wins:                   {res['wins']:,} ({res['wr']:.1f}%)", flush=True)
    print(f"   └─ Full TP: {res['full_tp']:,} | Trail TP (ratchet lock): {res['trail_tp']:,} | Timeout Win: {res['timeout_win']:,}", flush=True)
    print(f" Losses:                 {res['losses']:,}", flush=True)
    print(f" Profit Factor:          {res['pf']:.2f}", flush=True)
    print(f" Net Profit:             ${res['pnl']:,.2f}", flush=True)
    print(f" Max Drawdown:           ${res['max_dd']:,.2f}", flush=True)
    print("=" * 110, flush=True)


if __name__ == "__main__":
    main()
