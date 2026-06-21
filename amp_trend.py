# amp_trend.py
# Adaptive Market Profile — Trend detection per Timeframe
# Mirror structure of trendFilterLine (_swing_data / get_trend_label / trend_allows_signal)
# คำนวณ linear regression + Pearson r ตรงใน Python ไม่ต้องอ่าน file จาก MT5 indicator
# ──────────────────────────────────────────────────────────────────────

import numpy as np
import mt5_worker as mt5

# ── Config (import เหมือน scanner.py) ─────────────────────────────────
try:
    from config import TF_OPTIONS, SYMBOL
except ImportError:
    TF_OPTIONS = {}
    SYMBOL = ""

# ── Adaptive periods (ตรงกับ PERIODS[] ใน AdaptiveMarketProfile.mq5) ──
_PERIODS = [50, 60, 70, 80, 90, 100, 115, 130, 145,
            160, 180, 200, 220, 250, 280, 310, 340, 370, 400]

# ── Thresholds ─────────────────────────────────────────────────────────
PEARSON_STRONG  = 0.7   # r ≥ 0.7 → Strong trend
PEARSON_SIDEWAY = 0.3   # r < 0.3 → Sideways (ใช้ slope เป็น direction หลัก)

# ── State (keyed by tf_name) ───────────────────────────────────────────
# Format ต่อ TF:
#   {
#     "trend":     "BULL" | "BEAR" | "SIDEWAY",
#     "strength":  "strong" | "weak" | "-",
#     "label":     "🟢 Bull (strong)",
#     "slope":     float,   # + = uptrend, - = downtrend
#     "price_mid": float,   # close - midline  (+ = bull bias, - = bear bias)
#     "pearson":   float,   # 0–1  trend strength
#     "stddev":    float,   # residual std dev
#     "period":    int,     # best-fit period selected
#   }
_amp_data: dict[str, dict] = {}

# bar time (ของแท่งกำลังก่อตัว) ล่าสุดที่ fetch_amp_trend คำนวณสำเร็จ ต่อ TF
_amp_last_bar_time: dict[str, int] = {}


def clear_cache():
    """ล้าง _amp_data ทั้งหมด — เรียกตอนสลับ symbol (XAU<->BTC)
    กัน trend label ของ symbol เก่าค้างปนเข้า scan ของ symbol ใหม่
    (scan_one_tf จะ fetch_amp_trend ใหม่ทุกรอบ → cache repopulate เองทันที)"""
    _amp_data.clear()
    _amp_last_bar_time.clear()


# ══════════════════════════════════════════════════════════════════════
# Internal — regression
# ══════════════════════════════════════════════════════════════════════

def _calc_reg(closes: np.ndarray, length: int) -> dict | None:
    """
    Linear regression ของ `length` แท่งล่าสุด
    x: 0=oldest, length-1=newest  (เหมือน MQ5 CalcReg)
    Return: {slope, intercept, pearson, stddev, mid_current, period}
    """
    if len(closes) < length or length < 2:
        return None

    y = closes[-length:]                        # oldest → newest
    x = np.arange(length, dtype=float)         # 0 … length-1

    n     = float(length)
    sumX  = x.sum()
    sumY  = y.sum()
    sumXX = (x * x).sum()
    sumXY = (x * y).sum()
    sumYY = (y * y).sum()

    denom = n * sumXX - sumX * sumX
    if denom == 0.0:
        return None

    slope     = (n * sumXY - sumX * sumY) / denom
    intercept = (sumY - slope * sumX) / n

    # Pearson r (ตรงกับ Pine — ใช้ abs เสมอ)
    xAvg = sumX / n
    yAvg = sumY / n
    varX = sumXX / n - xAvg * xAvg
    varY = sumYY / n - yAvg * yAvg
    if varX > 0 and varY > 0:
        pearson = abs((sumXY / n - xAvg * yAvg) / np.sqrt(varX * varY))
    else:
        pearson = 0.0

    # StdDev of residuals
    fit      = intercept + slope * x
    residuals = y - fit
    stddev   = float(np.sqrt((residuals ** 2).sum() / (length - 1)))

    # Midline value ที่แท่งปัจจุบัน (x = length-1)
    mid_current = intercept + slope * (length - 1)

    return {
        "slope":       float(slope),
        "intercept":   float(intercept),
        "pearson":     float(pearson),
        "stddev":      stddev,
        "mid_current": float(mid_current),
        "period":      length,
    }


def _adaptive_reg(closes: np.ndarray) -> dict | None:
    """
    ลอง period ทุกค่าใน _PERIODS แล้วเลือกอันที่ให้ Pearson r สูงสุด
    """
    best_pearson = -1.0
    best_reg     = None

    for period in _PERIODS:
        reg = _calc_reg(closes, period)
        if reg and reg["pearson"] > best_pearson:
            best_pearson = reg["pearson"]
            best_reg     = reg

    return best_reg


# ══════════════════════════════════════════════════════════════════════
# Internal — trend label
# ══════════════════════════════════════════════════════════════════════

def _compute_trend(slope: float, price_mid: float, pearson: float) -> dict:
    """
    ตัดสิน trend จาก slope + pearson
    - pearson < PEARSON_SIDEWAY → Sideways (noisy, ไม่มี trend ชัด)
    - slope > 0                 → Bull
    - slope < 0                 → Bear
    ใช้ slope เป็น direction หลัก ไม่ใช้ price_mid (มักสวนทาง slope ระยะสั้น)
    """
    if pearson < PEARSON_SIDEWAY:
        return {"trend": "SIDEWAY", "strength": "-", "label": "⚪ SIDEWAY"}

    strength = "strong" if pearson >= PEARSON_STRONG else "weak"

    if slope > 0:
        return {"trend": "BULL", "strength": strength, "label": f"🟢 Bull ({strength})"}
    else:
        return {"trend": "BEAR", "strength": strength, "label": f"🔴 Bear ({strength})"}


# ══════════════════════════════════════════════════════════════════════
# Public — fetch / scan
# ══════════════════════════════════════════════════════════════════════

def fetch_amp_trend(tf_name: str, symbol: str | None = None,
                     current_bar_time: int | None = None) -> bool:
    """
    Fetch ราคาจาก MT5 → คำนวณ AMP trend → เก็บใน _amp_data[tf_name]
    Return True ถ้าสำเร็จ

    current_bar_time (optional): ถ้า caller (scan_one_tf) ส่งมาและตรงกับรอบก่อนหน้า
    (แท่งยังไม่ปิด) จะข้าม fetch+regression ก้อนใหญ่ (สูงสุด ~410 แท่ง/รอบ) — ใช้ label
    ที่คำนวณไว้ล่าสุดต่อแทน ใช้แสดงผลใน Scan Summary เท่านั้น ไม่กระทบ trading logic
    (amp_trend ไม่ถูกใช้ตัดสิน order ที่จุดใดในระบบปัจจุบัน)"""
    sym    = symbol or SYMBOL
    tf_val = TF_OPTIONS.get(tf_name)
    if tf_val is None:
        return False

    if (current_bar_time is not None and tf_name in _amp_data
            and _amp_last_bar_time.get(tf_name) == current_bar_time):
        return True

    max_period = max(_PERIODS)
    rates = mt5.copy_rates_from_pos(sym, tf_val, 0, max_period + 10)
    if rates is None or len(rates) < 52:
        return False

    closes = np.array([r["close"] for r in rates], dtype=float)

    best = _adaptive_reg(closes)
    if best is None:
        return False

    current_close = float(closes[-1])
    price_mid     = current_close - best["mid_current"]

    trend_info = _compute_trend(best["slope"], price_mid, best["pearson"])

    _amp_data[tf_name] = {
        "slope":     best["slope"],
        "price_mid": price_mid,
        "pearson":   best["pearson"],
        "stddev":    best["stddev"],
        "period":    best["period"],
        **trend_info,
    }
    if current_bar_time is not None:
        _amp_last_bar_time[tf_name] = current_bar_time
    return True


def scan_amp_all_tfs(tf_names: list[str], symbol: str | None = None) -> None:
    """Fetch AMP trend สำหรับทุก TF ที่ให้มา"""
    for tf in tf_names:
        fetch_amp_trend(tf, symbol)


# ══════════════════════════════════════════════════════════════════════
# Public — query  (mirror trendFilterLine pattern)
# ══════════════════════════════════════════════════════════════════════

def get_amp_trend_label(tf_name: str) -> str:
    """
    คืน label เช่น 'Bull (strong)', 'Bear (weak)', 'SIDEWAY'
    เหมือน get_trend_label() ใน scanner.py
    """
    d = _amp_data.get(tf_name)
    if not d:
        return "—"
    t = d.get("trend", "—")
    s = d.get("strength", "")
    return f"{t} ({s})" if s and s != "-" else t


def get_amp_trend(tf_name: str) -> dict:
    """คืน dict ข้อมูลครบ สำหรับ TF นั้น"""
    return dict(_amp_data.get(tf_name) or {})


def get_amp_data_all() -> dict[str, dict]:
    """คืน snapshot ของทุก TF"""
    return dict(_amp_data)


def amp_trend_allows_signal(tf_name: str, signal: str) -> tuple[bool, str]:
    """
    ตรวจว่า AMP trend อนุญาต signal นี้หรือไม่
    signal: "BUY" | "SELL"
    คืน (allowed: bool, reason: str)

    กฎ:
      BULL strong → BUY ผ่าน / SELL blocked
      BULL weak   → BUY ผ่าน / SELL blocked
      BEAR strong → SELL ผ่าน / BUY blocked
      BEAR weak   → SELL ผ่าน / BUY blocked
      SIDEWAY     → ทั้งคู่ผ่าน (ไม่บล็อก)
      Transition  → ทั้งคู่ผ่าน
    """
    d = _amp_data.get(tf_name)
    if not d:
        return True, ""   # ไม่มีข้อมูล → ไม่บล็อก

    trend    = d.get("trend", "SIDEWAY")
    strength = d.get("strength", "-")
    label    = d.get("label", "")
    sig      = signal.upper()

    if trend == "BULL" and sig == "SELL":
        return False, f"AMP {tf_name}: {label} → block SELL"
    if trend == "BEAR" and sig == "BUY":
        return False, f"AMP {tf_name}: {label} → block BUY"

    return True, ""


# ══════════════════════════════════════════════════════════════════════
# Debug helper
# ══════════════════════════════════════════════════════════════════════

def print_amp_summary() -> None:
    """พิมพ์สรุป AMP trend ทุก TF (ใช้ debug)"""
    if not _amp_data:
        print("[AMP] ไม่มีข้อมูล")
        return
    print("[AMP] ─── Trend Summary ───")
    for tf, d in _amp_data.items():
        print(
            f"  {tf:4s}  {d.get('label','—'):25s}"
            f"  slope={d.get('slope', 0):+.4f}"
            f"  r={d.get('pearson', 0):.3f}"
            f"  period={d.get('period', 0)}"
        )
