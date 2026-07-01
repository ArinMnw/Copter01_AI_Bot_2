"""
CLI ดู HHLL Trend ณ เวลาย้อนหลัง
usage: python trend_lookup.py <TF> <DD-MM-YYYY> <HH:MM>
ex:    python trend_lookup.py M5 05-06-2026 11:15
"""
import sys, os, re
from datetime import datetime, timezone, timedelta

def main():
    if len(sys.argv) != 4:
        print("usage: python trend_lookup.py <TF> <DD-MM-YYYY> <HH:MM>")
        print("  ex:  python trend_lookup.py M5 05-06-2026 11:15")
        sys.exit(1)

    tf_str   = sys.argv[1].upper()
    date_str = sys.argv[2]
    time_str = sys.argv[3]

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)

    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

    import MetaTrader5 as mt5
    import config
    from hhll_swing import _build_zz, _classify_pt

    _TF_MT5  = {"M1":1,"M5":5,"M15":15,"M30":30,"H1":16385,"H4":16388,"H12":16396,"D1":16408}
    _TF_SECS = {"M1":60,"M5":300,"M15":900,"M30":1800,"H1":3600,"H4":14400,"H12":43200,"D1":86400}

    if tf_str not in _TF_MT5:
        print(f"ERROR: ไม่พบ TF '{tf_str}' รองรับ: {', '.join(_TF_MT5)}")
        sys.exit(1)

    try:
        dt_naive = datetime.strptime(f"{date_str} {time_str}", "%d-%m-%Y %H:%M")
    except ValueError:
        print("ERROR: รูปแบบวันเวลาไม่ถูกต้อง ใช้ DD-MM-YYYY HH:MM เช่น 05-06-2026 11:15")
        sys.exit(1)

    BKK      = timezone(timedelta(hours=config.TZ_OFFSET))
    dt_bkk   = dt_naive.replace(tzinfo=BKK)
    ts_query = int(dt_bkk.timestamp()) + config.MT5_SERVER_TZ * 3600

    if not config.mt5_initialize(mt5):
        print(f"ERROR: MT5 initialize ไม่สำเร็จ: {mt5.last_error()}")
        sys.exit(1)

    tf_const   = _TF_MT5[tf_str]
    tf_secs    = _TF_SECS[tf_str]
    hhll_lb    = int(getattr(config, "HHLL_LOOKBACK", 500))
    hhll_left  = int(getattr(config, "HHLL_LEFT",    5))
    hhll_right = int(getattr(config, "HHLL_RIGHT",   5))
    need       = hhll_lb + hhll_left + hhll_right + 10

    rates_raw = mt5.copy_rates_range(config.SYMBOL, tf_const,
                                     ts_query - need * tf_secs,
                                     ts_query + tf_secs)
    mt5.shutdown()

    if rates_raw is None or len(rates_raw) == 0:
        print(f"ERROR: ไม่พบข้อมูลราคา {tf_str} ในช่วงเวลาที่ระบุ")
        sys.exit(1)

    rates = [r for r in rates_raw if int(r["time"]) <= ts_query]

    zz = _build_zz(rates, hhll_left, hhll_right)
    if len(zz) < 5:
        print("ERROR: Zigzag ไม่พอสำหรับ classify")
        sys.exit(1)

    # เก็บ list ทั้งหมด (oldest→newest) เพื่อ display ครบทุกจุดใน structure
    zz_pts = []  # (lbl, price, time)
    for k in range(len(zz)):
        lbl = _classify_pt(zz, k)
        if not lbl:
            continue
        zz_pts.append((lbl, float(zz[k]["price"]), int(zz[k]["time"])))

    # newest → oldest
    pts_new = list(reversed(zz_pts))

    h_labels = [l for l, _, _ in pts_new if l in ("HH", "LH")]
    l_labels = [l for l, _, _ in pts_new if l in ("HL", "LL")]

    last_label, last_price, last_time = pts_new[0] if pts_new else ("--", 0, 0)

    if not h_labels or not l_labels:
        trend_str = "UNKNOWN"
    else:
        h0, l0 = h_labels[0], l_labels[0]
        h1 = h_labels[1] if len(h_labels) > 1 else None
        l1 = l_labels[1] if len(l_labels) > 1 else None
        if h0 == "HH" and l0 == "HL":
            trend_str = f"BULL ({'strong' if h1 == 'HH' and l1 == 'HL' else 'weak'})"
        elif h0 == "LH" and l0 == "LL":
            trend_str = f"BEAR ({'strong' if h1 == 'LH' and l1 == 'LL' else 'weak'})"
        else:
            trend_str = f"SIDEWAY (h0={h0} l0={l0})"

    def fmt_ts(ts, sec=False):
        bkk = config.mt5_ts_to_bkk(int(ts))
        return bkk.strftime("%d-%m %H:%M:%S" if sec else "%d-%m %H:%M") if bkk else "?"

    # ── Batch log search ──────────────────────────────────────────────
    # สร้าง windows ทุก confirm ที่ต้องค้นหา แล้ว scan log ครั้งเดียว
    def batch_find_detect(tf: str, windows: list[tuple]) -> dict[int, str]:
        """
        windows: [(confirm_ts_mt5, deadline_ts_mt5), ...]  keyed by confirm_ts_mt5
        returns: {confirm_ts_mt5: "YYYY-MM-DD HH:MM:SS" or None}
        """
        result = {cn: None for cn, _ in windows}
        remaining = set(cn for cn, _ in windows)
        if not remaining:
            return result

        win_map = {cn: dl for cn, dl in windows}  # confirm_naive → deadline_naive

        # แปลง timestamp → naive datetime สำหรับ compare
        def ts_to_naive(ts_mt5: int) -> datetime:
            bkk = config.mt5_ts_to_bkk(ts_mt5)
            if bkk is None:
                return datetime.utcfromtimestamp(ts_mt5)
            return bkk.replace(tzinfo=None)

        win_naive = {}
        for cn_ts, dl_ts in windows:
            cn_naive = ts_to_naive(cn_ts)
            dl_naive = ts_to_naive(dl_ts)
            win_naive[cn_ts] = (cn_naive, dl_naive)

        global_start = min(v[0] for v in win_naive.values())
        global_end   = max(v[1] for v in win_naive.values())

        log_dir     = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
        old_log_dir = os.path.join(log_dir, "old_logs")
        log_paths   = []
        for d in [old_log_dir, log_dir]:
            if not os.path.isdir(d):
                continue
            for fn in sorted(os.listdir(d)):
                if fn.startswith("bot") and ".log" in fn:
                    p = os.path.join(d, fn)
                    if p not in log_paths:
                        log_paths.append(p)

        tf_pat = re.compile(rf'\b{re.escape(tf)}\b')
        ts_pat = re.compile(r'^\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\]')

        for path in log_paths:
            if not remaining:
                break
            try:
                with open(path, "r", encoding="utf-8", errors="replace") as f:
                    for line in f:
                        if not remaining:
                            break
                        m = ts_pat.match(line)
                        if not m:
                            continue
                        line_ts = datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S")
                        if line_ts > global_end:
                            break
                        if line_ts < global_start:
                            continue
                        if "SCAN" not in line or not tf_pat.search(line):
                            continue
                        # จับคู่กับ windows ที่ยังรอ
                        for cn_ts in list(remaining):
                            cn_naive, dl_naive = win_naive[cn_ts]
                            if cn_naive <= line_ts <= dl_naive:
                                result[cn_ts] = m.group(1)
                                remaining.discard(cn_ts)
                                break
            except Exception:
                continue

        return result

    # SIDEWAY แสดงแค่ h0+l0+h1+l1 (4 จุดที่กำหนด trend)
    # BULL/BEAR แสดง 8 จุดเพื่อดู structure ย้อนหลัง
    n_display   = 4 if trend_str.startswith("SIDEWAY") else 8
    display_pts = pts_new[:n_display]
    windows = []
    for _, _, bar_ts in display_pts:
        confirm_ts = bar_ts + hhll_right * tf_secs
        deadline_ts = confirm_ts + 2 * 3600  # +2h เผื่อ bot restart
        windows.append((confirm_ts, deadline_ts))

    detect_map = batch_find_detect(tf_str, windows)

    # ── Output ───────────────────────────────────────────────────────
    struct_display = " > ".join(l for l, _, _ in pts_new[:8])
    last_info = f"  {last_price:.2f}  bar={fmt_ts(last_time)}" if last_time else ""

    print(f"HHLL Trend Lookup [{tf_str}] @ BKK {date_str} {time_str}")
    print(f"Trend     : {trend_str}")
    print(f"Last label: {last_label}{last_info}")
    print(f"Structure : {struct_display}")
    print()
    print("Swing Points (newest → oldest):")
    for lbl, price, bar_ts in display_pts:
        confirm_ts  = bar_ts + hhll_right * tf_secs
        confirm_bkk = config.mt5_ts_to_bkk(confirm_ts)
        detect      = detect_map.get(confirm_ts)
        detect_str  = detect if detect else fmt_ts(confirm_ts) + " (est)"
        print(f"  {lbl}  {price:.2f}  bar={fmt_ts(bar_ts)}  confirm={fmt_ts(confirm_ts)}  detect={detect_str}")

if __name__ == "__main__":
    main()
