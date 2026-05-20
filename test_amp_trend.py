# test_amp_trend.py
# ทดสอบ amp_trend.py — รันตรงๆ ไม่ต้องเปิด bot
# วิธีรัน: python test_amp_trend.py

import MetaTrader5 as mt5
from mt5_utils import connect_mt5
from config import SYMBOL, TF_ACTIVE, TF_OPTIONS
import amp_trend

def main():
    # ── เชื่อมต่อ MT5 ──────────────────────────────────────────────
    print("🔌 กำลังเชื่อมต่อ MT5...")
    if not connect_mt5():
        print("❌ เชื่อมต่อ MT5 ไม่ได้ — เปิด MT5 ทิ้งไว้ก่อนนะคะ")
        return

    info = mt5.account_info()
    print(f"✅ MT5 เชื่อมต่อสำเร็จ | Account: {info.login} | Symbol: {SYMBOL}\n")

    # ── เลือก TF ที่จะทดสอบ ────────────────────────────────────────
    active_tfs = [tf for tf, on in TF_ACTIVE.items() if on]
    print(f"📊 TF ที่จะ scan: {', '.join(active_tfs)}\n")

    # ── Scan ───────────────────────────────────────────────────────
    print("⏳ กำลัง fetch & compute AMP trend...\n")
    results = {}
    for tf in active_tfs:
        ok = amp_trend.fetch_amp_trend(tf, SYMBOL)
        results[tf] = ok

    # ── แสดงผล summary ─────────────────────────────────────────────
    print("=" * 60)
    print(f"{'TF':6} {'Trend':25} {'Slope':>10} {'r':>7} {'PriceMid':>10} {'StdDev':>9} {'Period':>7}")
    print("=" * 60)

    for tf in active_tfs:
        if not results[tf]:
            print(f"{tf:6} {'❌ fetch ไม่ได้':25}")
            continue
        d = amp_trend.get_amp_trend(tf)
        print(
            f"{tf:6} "
            f"{d.get('label','—'):25} "
            f"{d.get('slope', 0):+10.4f} "
            f"{d.get('pearson', 0):7.3f} "
            f"{d.get('price_mid', 0):+10.3f} "
            f"{d.get('stddev', 0):9.3f} "
            f"{d.get('period', 0):7d}"
        )

    print("=" * 60)

    # ── ทดสอบ filter ───────────────────────────────────────────────
    print("\n📋 ทดสอบ amp_trend_allows_signal:")
    for tf in active_tfs:
        if not results[tf]:
            continue
        for sig in ["BUY", "SELL"]:
            allowed, reason = amp_trend.amp_trend_allows_signal(tf, sig)
            mark = "✅" if allowed else "❌"
            msg  = f"  → {reason}" if reason else ""
            print(f"  {tf:4} {sig:4}: {mark}{msg}")

    print("\n✅ ทดสอบเสร็จค่ะ")
    mt5.shutdown()

if __name__ == "__main__":
    main()
