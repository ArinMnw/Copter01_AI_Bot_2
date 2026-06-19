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

# bar time (ของแท่งกำลังก่อตัว) ล่าสุดที่ fetch_hhll คำนวณสำเร็จ ต่อ TF
# ใช้กันคำนวณ HH/HL/LH/LL ซ้ำเมื่อแท่งยังไม่ปิด (ค่าไม่เปลี่ยนระหว่างแท่งเดียวกัน)
_hhll_last_bar_time: dict[str, int] = {}


def clear_cache():
    """ล้าง _hhll_data ทั้งหมด — เรียกตอนสลับ symbol (XAU<->BTC)
    กัน HH/HL/LH/LL level ของ symbol เก่าค้างปนเข้า scan ของ symbol ใหม่
    (scan_one_tf จะ fetch_hhll ใหม่ทุกรอบ → cache repopulate เองทันที)"""
    _hhll_data.clear()
    _hhll_last_bar_time.clear()


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
               lookback: int | None = None,
               current_bar_time: int | None = None) -> bool:
    """Fetch ราคาจาก MT5 → classify HH/HL/LH/LL → เก็บใน _hhll_data

    current_bar_time (optional): bar time ของแท่งกำลังก่อตัวที่ caller ดึงมาแล้ว
    (เช่น scan_one_tf) — ถ้าตรงกับรอบก่อนหน้า แปลว่าแท่งยังไม่ปิด โครงสร้าง HH/HL/LH/LL
    ยังไม่เปลี่ยน จะข้าม fetch+recompute ก้อนใหญ่ (ลด MT5 IPC call ที่ทำให้ scan ช้า/ลาก
    event loop ค้าง — ดู §External Supervisor / Event-Loop Stall ใน AGENTS.md)
    ผู้เรียกที่ไม่ส่ง current_bar_time มา (เช่น force-fetch ใน trailing.py) ยัง fetch สดทุกครั้งเหมือนเดิม"""
    sym      = symbol  or SYMBOL
    tf_val   = TF_OPTIONS.get(tf_name)
    if tf_val is None:
        return False

    if (current_bar_time is not None and tf_name in _hhll_data
            and _hhll_last_bar_time.get(tf_name) == current_bar_time):
        return True

    _lb  = lb       if lb       is not None else HHLL_LEFT
    _rb  = rb       if rb       is not None else HHLL_RIGHT
    _lbk = lookback if lookback is not None else HHLL_LOOKBACK

    rates = mt5.copy_rates_from_pos(sym, tf_val, 0, _lbk + _lb + _rb + 5)
    if rates is None or len(rates) < _lb + _rb + 10:
        return False

    zz = _build_zz(rates, _lb, _rb)
    if len(zz) < 5:
        return False

    # Classify all → collect most recent + previous per type + full structure list
    buckets: dict[str, dict | None]      = {"HH": None, "HL": None, "LH": None, "LL": None}
    prev_buckets: dict[str, dict | None] = {"HH": None, "HL": None, "LH": None, "LL": None}
    structure: list[str] = []

    for k in range(len(zz)):
        lbl = _classify_pt(zz, k)
        if not lbl:
            continue
        pt = {"price": zz[k]["price"], "time": zz[k]["time"], "label": lbl}
        prev_buckets[lbl] = buckets[lbl]   # shift current → prev (oldest→newest loop)
        buckets[lbl] = pt                  # most recent of this label type
        structure.append(lbl)

    _hhll_data[tf_name] = {
        "hh":      buckets["HH"],
        "hl":      buckets["HL"],
        "lh":      buckets["LH"],
        "ll":      buckets["LL"],
        "prev_hh": prev_buckets["HH"],
        "prev_hl": prev_buckets["HL"],
        "prev_lh": prev_buckets["LH"],
        "prev_ll": prev_buckets["LL"],
        "last_label": structure[-1] if structure else "",
        "structure":  list(reversed(structure[-6:])),   # 6 ล่าสุด เรียง newest→oldest
    }
    if current_bar_time is not None:
        _hhll_last_bar_time[tf_name] = current_bar_time
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


def get_prev_swing_hl_pts(tf_name: str) -> tuple:
    """คืน (prev_sh_pt, prev_sl_pt) — swing H/L ก่อนหน้า (อีกตัวที่ไม่ถูกเลือก)
    ใช้สำหรับ PD Zone fallback "1 swing back"

    - prev_sh_pt = อีกตัวระหว่าง HH/LH ที่ไม่ใช่ตัวที่ใหม่ที่สุด
    - prev_sl_pt = อีกตัวระหว่าง HL/LL ที่ไม่ใช่ตัวที่ใหม่ที่สุด
    คืน None ถ้ามีแค่ตัวเดียว (ไม่มี prev)
    """
    d = _hhll_data.get(tf_name) or {}
    hh = d.get("hh")
    lh = d.get("lh")
    hl = d.get("hl")
    ll = d.get("ll")

    # prev_sh = อีกตัวที่ไม่ใช่ H ล่าสุด
    if hh and lh:
        prev_sh_pt = lh if hh["time"] >= lh["time"] else hh
    else:
        prev_sh_pt = None   # มีแค่ตัวเดียว ไม่มี prev

    # prev_sl = อีกตัวที่ไม่ใช่ L ล่าสุด
    if hl and ll:
        prev_sl_pt = ll if hl["time"] >= ll["time"] else hl
    else:
        prev_sl_pt = None   # มีแค่ตัวเดียว ไม่มี prev

    return prev_sh_pt, prev_sl_pt


def _check_price_violation(tf_name: str) -> str | None:
    """
    ตรวจว่าราคาของ swing ล่าสุดขัดแย้งกับ label หรือไม่
    (rule 4-11 จาก user spec — เช็คเฉพาะเมื่อมี prev ครบ)

    คืน "BEAR", "BULL", หรือ None (ไม่มี violation = ปกติ)

    กฎ (1=prev, 2=curr — curr=ล่าสุด):
      Lows:
        HL→HL: curr < prev → BEAR   (rule 4)
        LL→LL: curr > prev → BULL   (rule 7)
        LL→HL: curr < prev → BEAR   (rule 10)
        HL→LL: curr > prev → BULL   (rule 11)
      Highs:
        HH→HH: curr < prev → BEAR   (rule 5)
        LH→LH: curr > prev → BULL   (rule 6)
        HH→LH: curr > prev → BULL   (rule 8)
        LH→HH: curr < prev → BEAR   (rule 9)

    Rule 12: ถ้าราคาเป็นปกติตาม label → return None (ไม่ override)
    """
    d = _hhll_data.get(tf_name) or {}

    # ── Low swing pair ────────────────────────────────────────────────
    # หา swing low ล่าสุดและก่อนหน้า (แยก HL/LL โดยดูจาก time)
    curr_l  = None  # low swing ล่าสุด
    prev_l  = None  # low swing ก่อนหน้า
    hl, ll  = d.get("hl"), d.get("ll")
    p_hl, p_ll = d.get("prev_hl"), d.get("prev_ll")

    if hl and ll:
        if hl["time"] >= ll["time"]:
            curr_l, prev_l = hl, ll
        else:
            curr_l, prev_l = ll, hl
    elif hl:
        curr_l = hl
        prev_l = p_hl  # เดิม HL เป็น curr ก่อนถูกแทนที่
    elif ll:
        curr_l = ll
        prev_l = p_ll

    # ── High swing pair ───────────────────────────────────────────────
    curr_h  = None
    prev_h  = None
    hh, lh  = d.get("hh"), d.get("lh")
    p_hh, p_lh = d.get("prev_hh"), d.get("prev_lh")

    if hh and lh:
        if hh["time"] >= lh["time"]:
            curr_h, prev_h = hh, lh
        else:
            curr_h, prev_h = lh, hh
    elif hh:
        curr_h = hh
        prev_h = p_hh
    elif lh:
        curr_h = lh
        prev_h = p_lh

    # ── ตรวจ violation ────────────────────────────────────────────────
    violations = []

    if curr_l and prev_l:
        cl, pl = curr_l["label"], prev_l["label"]
        cp, pp = curr_l["price"], prev_l["price"]
        pair = (pl, cl)
        if   pair == ("HL", "HL") and cp < pp: violations.append("BEAR")   # rule 4
        elif pair == ("LL", "LL") and cp > pp: violations.append("BULL")   # rule 7
        elif pair == ("LL", "HL") and cp < pp: violations.append("BEAR")   # rule 10
        elif pair == ("HL", "LL") and cp > pp: violations.append("BULL")   # rule 11

    if curr_h and prev_h:
        cl, pl = curr_h["label"], prev_h["label"]
        cp, pp = curr_h["price"], prev_h["price"]
        pair = (pl, cl)
        if   pair == ("HH", "HH") and cp < pp: violations.append("BEAR")   # rule 5
        elif pair == ("LH", "LH") and cp > pp: violations.append("BULL")   # rule 6
        elif pair == ("HH", "LH") and cp > pp: violations.append("BULL")   # rule 8
        elif pair == ("LH", "HH") and cp < pp: violations.append("BEAR")   # rule 9

    if not violations:
        return None
    # ถ้า violations ขัดแย้งกัน (1 BULL, 1 BEAR) → ถือ SIDEWAY
    if "BEAR" in violations and "BULL" in violations:
        return "SIDEWAY"
    return violations[0]


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
            label_trend = {"trend": "BULL", "strength": "strong", "label": "🟢 Bull (strong)"}
        else:
            label_trend = {"trend": "BULL", "strength": "weak",   "label": "🟢 Bull (weak)"}
    elif h0 == "LH" and l0 == "LL":
        if h1 == "LH" and l1 == "LL":
            label_trend = {"trend": "BEAR", "strength": "strong", "label": "🔴 Bear (strong)"}
        else:
            label_trend = {"trend": "BEAR", "strength": "weak",   "label": "🔴 Bear (weak)"}
    else:
        label_trend = {"trend": "SIDEWAY", "strength": "-", "label": "⚪ SIDEWAY"}

    # ── Price violation check (rules 4-11) ───────────────────────────
    # ตรวจว่าราคาจริงขัดแย้ง label หรือไม่ → override trend ถ้าพบ
    # Rule 12: ถ้าราคาปกติ → ใช้ label_trend เดิม
    violation = _check_price_violation(tf_name)
    if violation is None:
        return label_trend   # ปกติ ไม่มี violation

    # มี violation — override ตาม direction ที่ขัดแย้ง
    if violation == "BEAR":
        # price บอก bear → ไม่ว่า label จะบอกอะไร → force BEAR
        # ถ้า label เดิมเป็น BEAR อยู่แล้ว → ไม่ลด strength
        if label_trend["trend"] == "BEAR":
            return label_trend
        return {"trend": "BEAR", "strength": "weak",
                "label": "🔴 Bear (weak) [price override]"}
    if violation == "BULL":
        if label_trend["trend"] == "BULL":
            return label_trend
        return {"trend": "BULL", "strength": "weak",
                "label": "🟢 Bull (weak) [price override]"}
    # violation == "SIDEWAY" (ขัดแย้งทั้งสองทิศ)
    return {"trend": "SIDEWAY", "strength": "-",
            "label": "⚪ SIDEWAY [price override]"}
