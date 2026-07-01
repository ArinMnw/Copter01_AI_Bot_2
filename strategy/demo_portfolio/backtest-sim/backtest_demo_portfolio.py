"""
backtest_demo_portfolio.py — รัน backtest ของ P13 (Champion) / P16 (Max-Yield Blend) โดยตรง
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ดึง leg composition + cfg จาก demo_portfolio.py โดยตรง (single source of truth — เทียบเท่ากับที่
รันอยู่บน live เป๊ะๆ ไม่มี config แยกที่อาจ drift ไปคนละทางกัน) แล้วรัน sim_s<N>_backtest ของแต่ละ
leg รวมกันเป็น blend เหมือน scratch/blend_17way.py เดิม ออกเป็น CSV สไตล์เดียวกับ
s20_6_backtest_summary.csv เพื่อเทียบกับ export_demo_portfolio_compare.py (ผลจริงจาก MT5)

รัน:  python backtest_demo_portfolio.py [P13|P16|all] [--days 30,60,90,120,150,180] [--env demo|real]
ผลลัพธ์: ../excel/demo_portfolio_backtest_summary.csv
"""

import argparse
import csv
import os
import sys

# ไฟล์นี้อยู่ที่ strategy/p13/backtest-sim/ — ต้องขึ้นไป 3 ชั้นถึง project root เพื่อ import
# config/demo_portfolio/sim_s*_backtest ได้ (pattern เดียวกับ strategy/s20.6/backtest-sim/)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

import MetaTrader5 as mt5
import config

import demo_portfolio as dp
import sim_s30_backtest as s30sim
import sim_s31_backtest as s31sim
import sim_s34_backtest as s34sim
import sim_s36_backtest as s36sim
import sim_s37_backtest as s37sim
import sim_s38_backtest as s38sim
import sim_s39_backtest as s39sim
import sim_s40_backtest as s40sim
import sim_s41_backtest as s41sim
import sim_s42_backtest as s42sim
import sim_s44_backtest as s44sim
import sim_s45_backtest as s45sim
import sim_s46_backtest as s46sim
import sim_s47_backtest as s47sim
import sim_s49_backtest as s49sim
import sim_s51_backtest as s51sim
import sim_s56_backtest as s56sim

# key (letter) -> sim module ที่มี run_single(entry_bars, htf_bars, cfg, days, spread)
_SIM_MODULES = {
    "A": s31sim, "B": s34sim, "C": s36sim, "D": s37sim, "E": s38sim, "F": s39sim,
    "G": s40sim, "H": s41sim, "I": s42sim, "K": s44sim, "L": s45sim, "M": s46sim,
    "N": s47sim, "P": s49sim, "Q": s51sim, "R": s56sim,
}


def run_portfolio_backtest(portfolio_name, days, spread=0.20):
    keys = dp.PORTFOLIOS[portfolio_name]
    entry_bars = s30sim.fetch_bars(config.SYMBOL, "M5", days, extra_bars=600)
    htf_bars = s30sim.fetch_bars(config.SYMBOL, "M15", days, extra_bars=200)

    days_series = {}
    for key in keys:
        label, _, cfg, _, _ = dp._LEG_DEFS[key]
        sim = _SIM_MODULES[key]
        raw = sim.run_single(entry_bars, htf_bars, cfg, days, spread)
        twp, eq = s31sim.simulate_equity_substream(raw, cfg, s31sim.START_EQUITY)
        days_series[key] = s31sim.daily_series_from_trades(twp)

    all_days = set()
    for key in keys:
        all_days |= set(days_series[key])
    combined = {d: sum(days_series[k].get(d, 0.0) for k in keys) for d in all_days}
    c = s31sim.consistency_metrics(combined)
    total = sum(combined.values())
    return {
        "days": days, "trading_days": len(combined),
        "mo": total / days * 30 if days else 0.0,
        "day": total / days if days else 0.0,
        "sharpe": c["sharpe_like"], "pos_day_pct": c["pct_pos_days"],
        "max_losing_streak": c["max_losing_day_streak"],
    }


def _apply_env_credentials(env: str):
    """เลือกบัญชี MT5 ที่จะใช้ backtest — 'demo' ใช้ MT5_LOGIN/PASSWORD/SERVER เดิมใน config.py
    ตรงๆ, 'real' อ่านจาก environment variable แยก (MT5_LOGIN_REAL/MT5_PASSWORD_REAL/
    MT5_SERVER_REAL) เท่านั้น — ไม่ hardcode credential บัญชีจริงไว้ในโค้ดเด็ดขาด ผู้ใช้ต้องตั้ง
    env var เองบนเครื่อง/VPS ก่อนถึงจะรัน --env real ได้"""
    if env == "demo":
        return True
    login = os.getenv("MT5_LOGIN_REAL", "")
    password = os.getenv("MT5_PASSWORD_REAL", "")
    server = os.getenv("MT5_SERVER_REAL", "")
    if not (login and password and server):
        print("❌ --env real ต้องตั้ง environment variable ก่อน:\n"
              "   MT5_LOGIN_REAL, MT5_PASSWORD_REAL, MT5_SERVER_REAL\n"
              "   (ไม่เก็บ credential บัญชีจริงไว้ในโค้ด ต้องตั้งเองทุกครั้งที่จะรันจริง)")
        return False
    config.MT5_LOGIN = int(login)
    config.MT5_PASSWORD = password
    config.MT5_SERVER = server
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("portfolio", nargs="?", default="all", choices=["P13", "P16", "all"])
    ap.add_argument("--days", default="30,60,90,120,150,180")
    ap.add_argument("--spread", type=float, default=0.20)
    ap.add_argument("--env", choices=["demo", "real"], default="demo",
                     help="เลือกบัญชี MT5 ที่จะดึงข้อมูลราคามา backtest (default: demo)")
    args = ap.parse_args()

    portfolios = ["P13", "P16"] if args.portfolio == "all" else [args.portfolio]
    day_windows = [int(d) for d in args.days.split(",")]

    if not _apply_env_credentials(args.env):
        return

    # ใช้ config.mt5_initialize() แทน mt5.initialize() ตรงๆ — บังคับ login เข้าบัญชีที่เลือกไว้
    # (demo หรือ real ตาม --env) เสมอ ไม่สนใจว่า terminal จะเปิดบัญชีไหนค้างอยู่
    # + resolve SYMBOL (เช่น "XAUUSD" -> "XAUUSD.iux") ให้ถูกต้องอัตโนมัติ
    if not config.mt5_initialize(mt5):
        print(f"MT5 initialize ล้มเหลว: {mt5.last_error()}")
        return
    print(f"เชื่อมต่อ [{args.env}]: {config.SYMBOL} @ {config.MT5_SERVER} (login={config.MT5_LOGIN})")

    rows = []
    for portfolio in portfolios:
        for days in day_windows:
            print(f"--- {portfolio} @ {days}d ---")
            r = run_portfolio_backtest(portfolio, days, args.spread)
            print(f"  $/day={r['day']:.1f}  $/mo={r['mo']:.1f}  sharpe={r['sharpe']:.3f} "
                  f"posDay={r['pos_day_pct']:.1f}%  maxStreak={r['max_losing_streak']}d")
            rows.append({
                "Env": args.env, "Portfolio": portfolio, "Days": days,
                "TradingDays": r["trading_days"],
                "$/Day": round(r["day"], 2), "$/Month": round(r["mo"], 2),
                "Sharpe": round(r["sharpe"], 4), "PosDay(%)": round(r["pos_day_pct"], 1),
                "MaxLosingStreak": r["max_losing_streak"],
            })
    mt5.shutdown()

    excel_dir = os.path.join(os.path.dirname(__file__), "..", "excel")
    os.makedirs(excel_dir, exist_ok=True)
    out_path = os.path.join(excel_dir, f"demo_portfolio_backtest_summary_{args.env}.csv")
    fields = ["Env", "Portfolio", "Days", "TradingDays", "$/Day", "$/Month", "Sharpe",
              "PosDay(%)", "MaxLosingStreak"]
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    print(f"\n-> {out_path} ({len(rows)} rows)")


if __name__ == "__main__":
    main()
