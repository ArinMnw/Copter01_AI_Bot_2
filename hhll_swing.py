# hhll_swing.py
# Python port of HHLLStrategy.mq5
# Pivot detection + Zigzag + HH / HL / LH / LL classification
# Mirror structure of amp_trend.py  (fetch / get / scan_all)
# ──────────────────────────────────────────────────────────────────────

import MetaTrader5 as mt5

try:
    from config import TF_OPTIONS, SYMBOL
    import config as _cfg
    HHLL_LEFT     = int(getattr(_cfg, "HHLL_LEFT",     5)   or 5)
    HHLL_RIGHT    = int(getattr(_cfg, "HHLL_RIGHT",    5)   or 5)
    HHLL_LOOKBACK = int(getattr(_cfg, "HHLL_LOOKBACK", 500) or 500)
except ImportError:
    TF_OPTIONS    = {}
    SYMBOL        = ""
    HHLL_LEFT     = 5
    HHLL_RIGHT    = 5
    HHLL_LOOKBACK = 500

# ── State ─────────────────────────────────────────────────────────────
# Format ต่อ TF:
#   {
#     "hh":   {"price": float, "time": int} | None,
#     "hl":   {"price": float, "time": int} | None,
#     "lh":   {"price": float, "time": int} | None,
#     "ll":   {"price": float, "time": int} | None,
#     "last_label": "HH"|"HL"|"LH"|"LL"|"",
#     "structure":  ["HH","LH","HL","LL", ...]   # ล่าสุดก่อน
#   }
_hhll_data: dict[str, dict] = {}


# ══════════════════════════════════════════════════════════════════════
# Internal — pivot detection (forward-indexed: rates[0]=oldest)
# Left  bars : pivot must be strictly greater (>= blocks)
# Right bars : equal allowed — strict > blocks
#   matches HHLLStrategy.mq5 IsPH / IsPL
# ══════════════════════════════════════════════════════════════════════

def _is_ph(rates, i: int, lb: int, rb: int) -> bool:
    n = len(rates)
    if i - lb < 0 or i + rb >= n:
        return False
    h = rates[i]["high"]
    for j in range(i - lb, i):
        if rates[j]["high"] >= h:
            return False
    for j in range(i + 1, i + rb + 1):
        if rates[j]["high"] > h:
            return False
    return True


def _is_pl(rates, i: int, lb: int, rb: int) -> bool:
    n = len(rates)
    if i - lb < 0 or i + rb >= n:
        return False
    l = rates[i]["low"]
    for j in range(i - lb, i):
        if rates[j]["low"] <= l:
            return False
    for j in range(i + 1, i + rb + 1):
        if rates[j]["low"] < l:
            return False
    return True


# ══════════════════════════════════════════════════════════════════════
# Internal — zigzag builder
#   Filter 1/2: consecutive same-direction → keep more extreme
#   Filter 3  : alternating but price wrong side → skip
# ══════════════════════════════════════════════════════════════════════

def _build_zz(rates, lb: int, rb: int) -> list[dict]:
    """Return list of {"price", "time", "dir"} sorted oldest→newest"""
    n = len(rates)
    zz: list[dict] = []

    for i in range(lb, n - rb):
        ph = _is_ph(rates, i, lb, rb)
        pl = _is_pl(rates, i, lb, rb)
        if not ph and not pl:
            continue

        # Both PH and PL at same bar — prefer continuation direction
        if ph and pl:
            if zz and zz[-1]["dir"] == 1:
                ph = False
            else:
                pl = False

        price = float(rates[i]["high"] if ph else rates[i]["low"])
        d     = 1 if ph else -1
        t     = int(rates[i]["time"])

        # Filter 1/2: consecutive same-direction → skip less extreme (Pine Script behavior)
        # ไม่ pop ตัวเก่าออก — keep both เหมือน Pine Script
        # (Pine Script: set zz=na สำหรับตัวที่ extreme น้อยกว่า แต่ไม่ลบตัวที่ extreme กว่า)
        if zz and zz[-1]["dir"] == d:
            if d == 1  and price < zz[-1]["price"]:
                continue  # PH ใหม่ต่ำกว่าเก่า → skip ตัวใหม่
            if d == -1 and price > zz[-1]["price"]:
                continue  # PL ใหม่สูงกว่าเก่า → skip ตัวใหม่
            # ตัวใหม่ extreme กว่าหรือเท่ากัน → keep both เหมือน Pine Script (ไม่ pop เก่าออก)

        # Filter 3: wrong side after direction alternated
        if zz:
            if d == -1 and price > zz[-1]["price"]:
                continue  # low above prev high
            if d == 1  and price < zz[-1]["price"]:
                continue  # high below prev low

        zz.append({"price": price, "time": t, "dir": d})

    return zz


# ══════════════════════════════════════════════════════════════════════
# Internal — classification
#   ported directly from HHLLStrategy.mq5 ClassifyPt()
# ══════════════════════════════════════════════════════════════════════

def _classify_pt(zz: list[dict], k: int) -> str:
    if k < 4:
        return ""

    a  = zz[k]["price"]
    ad = zz[k]["dir"]
    opp = -ad

    b = c = d = e = 0.0
    step = 0
    need = opp

    for j in range(k - 1, -1, -1):
        if zz[j]["dir"] != need:
            continue
        if   step == 0: b = zz[j]["price"]; need = ad
        elif step == 1: c = zz[j]["price"]; need = opp
        elif step == 2: d = zz[j]["price"]; need = ad
        elif step == 3: e = zz[j]["price"]
        step += 1
        if step == 4:
            break

    if step < 4:
        return ""

    is_hh = (a > b) and (a > c) and (c > b) and (c > d)
    is_ll = (a < b) and (a < c) and (c < b) and (c < d)
    is_hl = ((a >= c and b > c and b > d and d > c and d > e) or
             (a <  b and a > c and b < d))
    is_lh = ((a <= c and b < c and b < d and d < c and d < e) or
             (a >  b and a < c and b > d))

    if is_hh: return "HH"
    if is_ll: return "LL"
    if is_hl: return "HL"
    if is_lh: return "LH"
    return ""


# ══════════════════════════════════════════════════════════════════════
# Public — fetch / scan
# ══════════════════════════════════════════════════════════════════════

def fetch_hhll(tf_name: str, symbol: str | None = None,
               lb: int | None = None, rb: int | None = None,
               lookback: int | None = None) -> bool:
    """Fetch ราคาจาก MT5 → classify HH/HL/LH/LL → เก็บใน _hhll_data"""
    sym      = symbol  or SYMBOL
    tf_val   = TF_OPTIONS.get(tf_name)
    if tf_val is None:
        return False

    _lb  = lb       if lb       is not None else HHLL_LEFT
    _rb  = rb       if rb       is not None else HHLL_RIGHT
    _lbk = lookback if lookback is not None else HHLL_LOOKBACK

    rates = mt5.copy_rates_from_pos(sym, tf_val, 0, _lbk + _lb + _rb + 5)
    if rates is None or len(rates) < _lb + _rb + 10:
        return False

    zz = _build_zz(rates, _lb, _rb)
    if len(zz) < 5:
        return False

    # Classify all → collect most recent per type + full structure list
    buckets: dict[str, dict | None] = {"HH": None, "HL": None, "LH": None, "LL": None}
    structure: list[str] = []

    for k in range(len(zz)):
        lbl = _classify_pt(zz, k)
        if not lbl:
            continue
        pt = {"price": zz[k]["price"], "time": zz[k]["time"], "label": lbl}
        buckets[lbl] = pt
        structure.append(lbl)

    _hhll_data[tf_name] = {
        "hh": buckets["HH"],
        "hl": buckets["HL"],
        "lh": buckets["LH"],
        "ll": buckets["LL"],
        "last_label": structure[-1] if structure else "",
        "structure":  list(reversed(structure[-6:])),   # 6 ล่าสุด เรียง newest→oldest
    }
    return True


def scan_hhll_all_tfs(tf_names: list[str], symbol: str | None = None) -> None:
    """Fetch HHLL สำหรับทุก TF"""
    for tf in tf_names:
        fetch_hhll(tf, symbol)


# ══════════════════════════════════════════════════════════════════════
# Public — query
# ══════════════════════════════════════════════════════════════════════

def get_hhll_data(tf_name: str) -> dict:
    """คืน dict ข้อมูลครบ สำหรับ TF นั้น"""
    return dict(_hhll_data.get(tf_name) or {})


def get_hhll_structure_label(tf_name: str, n: int = 4) -> str:
    """คืน structure string เช่น 'HH ▸ LH ▸ HL ▸ LL' (newest→oldest, n จุด)"""
    d = _hhll_data.get(tf_name) or {}
    struct = d.get("structure") or []
    if not struct:
        return "—"
    return " ▸ ".join(struct[:n])


def get_hhll_price(tf_name: str, label: str) -> float | None:
    """คืนราคาล่าสุดของ label นั้น (HH/HL/LH/LL) หรือ None"""
    d = _hhll_data.get(tf_name) or {}
    pt = d.get(label.lower()) or d.get(label)
    return float(pt["price"]) if pt else None


def get_swing_hl_pts(tf_name: str) -> tuple:
    """คืน (sh_pt, sl_pt) จาก HHLL data
    - sh_pt = ที่ใหม่กว่าระหว่าง HH กับ LH  (swing HIGH ล่าสุด)
    - sl_pt = ที่ใหม่กว่าระหว่าง HL กับ LL  (swing LOW ล่าสุด)
    แต่ละ pt เป็น {"price": float, "time": int} หรือ None
    """
    d = _hhll_data.get(tf_name) or {}
    hh = d.get("hh")
    lh = d.get("lh")
    hl = d.get("hl")
    ll = d.get("ll")

    if hh and lh:
        sh_pt = hh if hh["time"] >= lh["time"] else lh
    else:
        sh_pt = hh or lh

    if hl and ll:
        sl_pt = hl if hl["time"] >= ll["time"] else ll
    else:
        sl_pt = hl or ll

    return sh_pt, sl_pt


def get_trend_from_structure(tf_name: str) -> dict | None:
    """คำนวณ trend จาก HHLL structure list — เหมือน TrendFilterLines.mq5
    อ่านจาก _hhll_data[tf]["structure"] (newest→oldest)
    คืน {"trend", "strength", "label"} หรือ None ถ้าไม่มีข้อมูล
    """
    d = _hhll_data.get(tf_name) or {}
    struct = d.get("structure") or []
    if not struct:
        return None

    # แยก swing-high labels และ swing-low labels (newest first)
    h_labels = [s for s in struct if s in ("HH", "LH")]
    l_labels = [s for s in struct if s in ("HL", "LL")]

    if not h_labels or not l_labels:
        return {"trend": "UNKNOWN", "strength": "-", "label": "❓ —"}

    h0 = h_labels[0]
    h1 = h_labels[1] if len(h_labels) > 1 else None
    l0 = l_labels[0]
    l1 = l_labels[1] if len(l_labels) > 1 else None

    if h0 == "HH" and l0 == "HL":
        if h1 == "HH" and l1 == "HL":
            return {"trend": "BULL", "strength": "strong", "label": "🟢 Bull (strong)"}
        return {"trend": "BULL", "strength": "weak", "label": "🟢 Bull (weak)"}
    if h0 == "LH" and l0 == "LL":
        if h1 == "LH" and l1 == "LL":
            return {"trend": "BEAR", "strength": "strong", "label": "🔴 Bear (strong)"}
        return {"trend": "BEAR", "strength": "weak", "label": "🔴 Bear (weak)"}
    return {"trend": "SIDEWAY", "strength": "-", "label": "⚪ SIDEWAY"}
