#!/usr/bin/env python3
"""
export_trend.py
───────────────
Standalone script: fetch HHLL swing data แล้ว export trend_state_<symbol>.txt
สำหรับ TrendFilterLines.mq5 indicator — ไม่ต้อง run bot ทั้งตัว

วิธี run:
    python export_trend.py                  # loop ทุก 10 วินาที (default)
    python export_trend.py --interval 5     # override ช่วงเวลา (วินาที)
    python export_trend.py --once           # export ครั้งเดียวแล้วออก
"""

import os
import sys
import time
import argparse

# ── project root ─────────────────────────────────────────────────────
_ROOT = os.path.dirname(os.path.abspath(__file__))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

# ── import config ─────────────────────────────────────────────────────
try:
    import config as _cfg
    SYMBOL        = _cfg.SYMBOL
    TF_OPTIONS    = _cfg.TF_OPTIONS
    MT5_LOGIN     = _cfg.MT5_LOGIN
    MT5_PASSWORD  = _cfg.MT5_PASSWORD
    MT5_SERVER    = _cfg.MT5_SERVER
    PER_TF_MAP    = getattr(_cfg, "TREND_FILTER_PER_TF", {}) or {}
    TF_ACTIVE     = getattr(_cfg, "TF_ACTIVE",  {}) or {}
    HHLL_LEFT     = int(getattr(_cfg, "HHLL_LEFT",     5)   or 5)
    HHLL_RIGHT    = int(getattr(_cfg, "HHLL_RIGHT",    5)   or 5)
    HHLL_LOOKBACK = int(getattr(_cfg, "HHLL_LOOKBACK", 500) or 500)
except Exception as e:
    print(f"❌ Cannot import config: {e}")
    sys.exit(1)

import MetaTrader5 as mt5
import hhll_swing

# TF ที่ใช้ export
TF_NAMES = [tf for tf, active in TF_ACTIVE.items() if active and tf in TF_OPTIONS]
if not TF_NAMES:
    TF_NAMES = list(TF_OPTIONS.keys())


# ─────────────────────────────────────────────────────────────────────
def _connect() -> bool:
    ok = mt5.initialize(login=MT5_LOGIN, password=MT5_PASSWORD, server=MT5_SERVER)
    if not ok:
        print(f"❌ MT5 initialize failed: {mt5.last_error()}")
        return False
    info = mt5.terminal_info()
    acc  = mt5.account_info()
    name  = getattr(info, "name",  "?") if info else "?"
    login = getattr(acc,  "login", "?") if acc  else "?"
    print(f"✅ MT5 connected | {name} | login={login} | symbol={SYMBOL}")
    return True


def _now_str() -> str:
    from datetime import datetime, timezone, timedelta
    return datetime.now(timezone(timedelta(hours=7))).strftime("%Y-%m-%d %H:%M:%S")


def _pt(pt, is_price: bool) -> str:
    """แปลง swing point เป็น string สำหรับ CSV"""
    if not pt:
        return "0"
    v = pt["price"] if is_price else pt["time"]
    return f"{float(v):.2f}" if is_price else str(int(v))


# ─────────────────────────────────────────────────────────────────────
def export_once() -> bool:
    """Fetch HHLL → เขียน trend_state ใน MT5 Common\\Files"""
    # ตรวจ MT5 connection
    info = mt5.terminal_info()
    if not info:
        print(f"[{_now_str()}] ⚠️  MT5 disconnected — trying reconnect")
        if not _connect():
            return False
        info = mt5.terminal_info()

    common_path = getattr(info, "commondata_path", None)
    if not common_path:
        print(f"[{_now_str()}] ⚠️  commondata_path not found")
        return False

    files_dir = os.path.join(common_path, "Files")
    os.makedirs(files_dir, exist_ok=True)

    # ── Fetch HHLL ทุก TF ─────────────────────────────────────────
    hhll_swing.scan_hhll_all_tfs(TF_NAMES, SYMBOL)

    now_s = _now_str()
    lines = [
        f"# generated_at={now_s}",
        f"# symbol={SYMBOL}",
        (
            "# tf,trend,strength,"
            "sh_time,sh_price,prev_sh_time,prev_sh_price,"
            "sl_time,sl_price,prev_sl_time,prev_sl_price,"
            "break_flag,per_tf_on"
        ),
        "# trend determined from HH/HL/LH/LL (HHLLStrategy algorithm)",
    ]

    summary_parts: list[str] = []

    for tf_name in TF_NAMES:
        hhll = hhll_swing.get_hhll_data(tf_name)
        if not hhll:
            continue

        hh = hhll.get("hh")
        lh = hhll.get("lh")
        hl = hhll.get("hl")
        ll = hhll.get("ll")

        # swing highs — newer = sh, older = prev_sh
        if hh and lh:
            pt_sh, pt_psh = (hh, lh) if hh["time"] >= lh["time"] else (lh, hh)
        elif hh:
            pt_sh, pt_psh = hh, None
        elif lh:
            pt_sh, pt_psh = lh, None
        else:
            pt_sh = pt_psh = None

        # swing lows — newer = sl, older = prev_sl
        if hl and ll:
            pt_sl, pt_psl = (hl, ll) if hl["time"] >= ll["time"] else (ll, hl)
        elif hl:
            pt_sl, pt_psl = hl, None
        elif ll:
            pt_sl, pt_psl = ll, None
        else:
            pt_sl = pt_psl = None

        # trend ตรงกับ bot filter
        trend_info = hhll_swing.get_trend_from_structure(tf_name) or {}
        t        = trend_info.get("trend",    "UNKNOWN") or "UNKNOWN"
        strength = trend_info.get("strength", "-")       or "-"

        # break flag — close แท่งล่าสุด vs swing H/L
        break_flag = "-"
        try:
            rates = mt5.copy_rates_from_pos(SYMBOL, TF_OPTIONS[tf_name], 0, 2)
            if rates is not None and len(rates) >= 1:
                close = float(rates[-1]["close"])
                if pt_sh and close > float(pt_sh["price"]):
                    break_flag = "break_up"
                elif pt_sl and close < float(pt_sl["price"]):
                    break_flag = "break_down"
        except Exception:
            pass

        per_tf_on = 1 if PER_TF_MAP.get(tf_name, False) else 0

        lines.append(
            f"{tf_name},{t},{strength},"
            f"{_pt(pt_sh,False)},{_pt(pt_sh,True)},"
            f"{_pt(pt_psh,False)},{_pt(pt_psh,True)},"
            f"{_pt(pt_sl,False)},{_pt(pt_sl,True)},"
            f"{_pt(pt_psl,False)},{_pt(pt_psl,True)},"
            f"{break_flag},{per_tf_on}"
        )
        icon = {"BULL": "🟢", "BEAR": "🔴", "SIDEWAY": "⚪"}.get(t, "❓")
        summary_parts.append(f"{tf_name}={icon}")

    payload = "\n".join(lines) + "\n"

    # ── เขียนทั้ง trend_state.txt และ trend_state_<symbol>.txt ──────
    sym_name = str(SYMBOL or "").strip() or "UNKNOWN"
    targets = [
        os.path.join(files_dir, "trend_state.txt"),
        os.path.join(files_dir, f"trend_state_{sym_name}.txt"),
    ]

    success = True
    for target in targets:
        tmp = target + ".tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                f.write(payload)
            replaced = False
            for _ in range(5):
                try:
                    os.replace(tmp, target)
                    replaced = True
                    break
                except PermissionError:
                    time.sleep(0.1)
            if not replaced:
                try:
                    os.remove(tmp)
                except OSError:
                    pass
                # fallback: direct write (ใช้ได้เมื่อ MT5 เปิด FILE_SHARE_WRITE)
                with open(target, "w", encoding="utf-8") as f:
                    f.write(payload)
        except Exception as e:
            print(f"[{now_s}] ⚠️  {os.path.basename(target)}: {e}")
            success = False

    if success:
        print(f"[{now_s}] ✅  {' | '.join(summary_parts)}")
    return success


# ─────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description="Export HHLL trend state for TrendFilterLines.mq5"
    )
    parser.add_argument(
        "--interval", type=int, default=10,
        help="Refresh interval in seconds (default: 10)"
    )
    parser.add_argument(
        "--once", action="store_true",
        help="Export once and exit"
    )
    args = parser.parse_args()

    print("=== export_trend.py ===")
    print(f"  symbol   : {SYMBOL}")
    print(f"  TFs      : {', '.join(TF_NAMES)}")
    if not args.once:
        print(f"  interval : {args.interval}s  |  Press Ctrl+C to stop")
    print()

    if not _connect():
        sys.exit(1)

    if args.once:
        ok = export_once()
        mt5.shutdown()
        sys.exit(0 if ok else 1)

    try:
        while True:
            export_once()
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print("\n🛑 Stopped")
    finally:
        mt5.shutdown()


if __name__ == "__main__":
    main()
