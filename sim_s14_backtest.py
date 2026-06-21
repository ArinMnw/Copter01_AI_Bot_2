"""
sim_s14_backtest.py — จำลอง S14 (Sweep RSI) ทุก TF ตั้งแต่ 24-05-2026
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')

import MetaTrader5 as mt5
from datetime import datetime, timezone, timedelta
import config
from strategy14 import strategy_14

# HHLL support — S14 swing modes read hhll_swing refs, so replay must inject
# historical HHLL unless a legacy config explicitly disables it.
_USE_HHLL = bool(getattr(config, 'S14_LL_USE_HHLL', True))
if _USE_HHLL:
    import hhll_swing as _hs
    _HHLL_LB  = int(getattr(config, 'HHLL_LEFT',     5) or 5)
    _HHLL_RB  = int(getattr(config, 'HHLL_RIGHT',    5) or 5)
    _HHLL_LBK = int(getattr(config, 'HHLL_LOOKBACK', 500) or 500)

def _inject_hhll(tf_name: str, bars_slice: list):
    """คำนวณ HHLL จาก bars_slice แล้ว inject เข้า hhll_swing._hhll_data[tf_name]
    เลียนแบบ fetch_hhll() — จำกัด bars เท่ากับ HHLL_LOOKBACK + LB + RB + 5"""
    if not _USE_HHLL:
        return
    # จำกัดจำนวน bars ให้เหมือน fetch_hhll จริง
    max_bars = _HHLL_LBK + _HHLL_LB + _HHLL_RB + 5
    rates = bars_slice[-max_bars:] if len(bars_slice) > max_bars else bars_slice
    if len(rates) < _HHLL_LB + _HHLL_RB + 10:
        return
    zz = _hs._build_zz(rates, _HHLL_LB, _HHLL_RB)
    if len(zz) < 5:
        return
    buckets      = {"HH": None, "HL": None, "LH": None, "LL": None}
    prev_buckets = {"HH": None, "HL": None, "LH": None, "LL": None}
    structure    = []
    for k in range(len(zz)):
        lbl = _hs._classify_pt(zz, k)
        if not lbl:
            continue
        pt = {"price": zz[k]["price"], "time": zz[k]["time"], "label": lbl}
        prev_buckets[lbl] = buckets[lbl]
        buckets[lbl] = pt
        structure.append(lbl)
    _hs._hhll_data[tf_name] = {
        "hh": buckets["HH"], "hl": buckets["HL"],
        "lh": buckets["LH"], "ll": buckets["LL"],
        "prev_hh": prev_buckets["HH"], "prev_hl": prev_buckets["HL"],
        "prev_lh": prev_buckets["LH"], "prev_ll": prev_buckets["LL"],
        "last_label": structure[-1] if structure else "",
        "structure": list(reversed(structure[-6:])),
    }

# Runtime currently skips PD Fibo Plus for S14.
_PD_ENABLED = False

def _check_pd_fibo(signal: str, entry: float, tf_name: str) -> tuple:
    """เช็ค PD Fibo Plus round 1 — คืน (pd_pass, fibo_pct, h, l, h_time, l_time)
    BUY: entry < fib_382 (Discount) → PASS
    SELL: entry > fib_618 (Premium) → PASS
    อื่น → FAIL"""
    if not _USE_HHLL:
        return True, None, None, None, None, None  # ไม่มี HHLL data → pass
    try:
        sh_pt, sl_pt = _hs.get_swing_hl_pts(tf_name)
    except Exception:
        return True, None, None, None, None, None
    if not sh_pt or not sl_pt:
        return True, None, None, None, None, None
    h = float(sh_pt["price"])
    l = float(sl_pt["price"])
    h_time = int(sh_pt["time"])
    l_time = int(sl_pt["time"])
    if h <= l:
        return True, None, None, None, None, None
    fib_382 = l + (h - l) * 0.382
    fib_618 = l + (h - l) * 0.618
    fibo_pct = ((entry - l) / (h - l)) * 100
    if signal == "BUY":
        return entry < fib_382, fibo_pct, h, l, h_time, l_time
    elif signal == "SELL":
        return entry > fib_618, fibo_pct, h, l, h_time, l_time
    return True, fibo_pct, h, l, h_time, l_time


def _strong_trend_blocks_signal(tf_name: str, signal: str) -> tuple[bool, str]:
    if not (
        getattr(config, "STRONG_TREND_BLOCK_ENABLED", False)
        and 14 in getattr(config, "STRONG_TREND_BLOCK_SIDS", (9, 10, 11, 13, 14, 15, 16))
    ):
        return False, ""
    if not _USE_HHLL:
        return False, ""
    try:
        trend = _hs.get_trend_from_structure(tf_name) or {}
    except Exception:
        trend = {}
    if trend.get("strength") != "strong":
        return False, ""
    if trend.get("trend") == "BULL" and signal == "SELL":
        return True, f"{tf_name} BULL strong"
    if trend.get("trend") == "BEAR" and signal == "BUY":
        return True, f"{tf_name} BEAR strong"
    return False, ""



SYMBOL       = config.SYMBOL
SINCE        = datetime(2026, 5, 24, 0, 0, 0, tzinfo=timezone.utc)
VOLUME       = 0.01     # lot size สำหรับคำนวณ P&L
# XAUUSD: 1 pip (0.01) = $1.00 per 1 lot → 0.01 lot = $0.01 per pip
# price diff 1.0 = 100 pips × $0.01 = $1.00 per 0.01 lot ✓
PRICE_TO_USD = 100 * VOLUME   # price_diff × PRICE_TO_USD = profit USD

S14_LOOKBACK  = int(getattr(config, 'S14_REVERSAL_LOOKBACK', 50))
S14_PERIOD    = int(getattr(config, 'S14_RSI_PERIOD', 14))
WINDOW_NEEDED = S14_LOOKBACK + S14_PERIOD + 15
TP_EXTRA      = 300

UTC = timezone.utc
TZ_OFF = getattr(config, 'TZ_OFFSET', 7)
SRV_TZ = getattr(config, 'MT5_SERVER_TZ', 0)

TF_MAP = {
    'M1':  mt5.TIMEFRAME_M1,
    'M5':  mt5.TIMEFRAME_M5,
    'M15': mt5.TIMEFRAME_M15,
    'M30': mt5.TIMEFRAME_M30,
    'H1':  mt5.TIMEFRAME_H1,
    'H4':  mt5.TIMEFRAME_H4,
    'D1':  mt5.TIMEFRAME_D1,
}

# ดึง bars มากกว่า SINCE เพื่อให้ได้ lookback ก่อนเริ่ม
TF_EXTRA_BARS = {
    'M1': 2000, 'M5': 500, 'M15': 300,
    'M30': 200, 'H1': 150, 'H4': 100, 'D1': 50,
}

TF_SECONDS_LOCAL = {
    'M1': 60,
    'M5': 5 * 60,
    'M15': 15 * 60,
    'M30': 30 * 60,
    'H1': 60 * 60,
    'H4': 4 * 60 * 60,
    'D1': 24 * 60 * 60,
}

def to_bkk(ts: int) -> datetime:
    return datetime.fromtimestamp(ts, tz=UTC) + timedelta(hours=TZ_OFF - SRV_TZ)

def profit(price_diff: float) -> float:
    return round(price_diff * PRICE_TO_USD, 2)


def _fetch_rates(tf_name: str, tf_val: int, range_end_utc: datetime | None = None):
    extra = TF_EXTRA_BARS.get(tf_name, 200)
    total = 5000 + extra
    if range_end_utc is None:
        return mt5.copy_rates_from_pos(SYMBOL, tf_val, 0, total)

    pad_bars = max(
        extra,
        WINDOW_NEEDED + TP_EXTRA + 50,
        int(getattr(config, "HHLL_LOOKBACK", 500) or 500)
        + int(getattr(config, "HHLL_LEFT", 5) or 5)
        + int(getattr(config, "HHLL_RIGHT", 5) or 5)
        + 20,
    )
    start_utc = SINCE - timedelta(seconds=TF_SECONDS_LOCAL.get(tf_name, 60) * pad_bars)
    return mt5.copy_rates_range(SYMBOL, tf_val, start_utc, range_end_utc)


def s14_runtime_feature_coverage() -> list[dict]:
    """Describe S14 runtime feature coverage for replay reports."""
    return [
        {
            "name": "S14 Sweep/Engulf detect",
            "config_on": bool(config.active_strategies.get(14, False)),
            "runtime": "apply",
            "replay": "apply",
            "note": "Replay calls shared strategy14.strategy_14()",
        },
        {
            "name": "S14 market fill",
            "config_on": True,
            "runtime": "apply",
            "replay": "partial",
            "note": "Replay fills at strategy market reference price on the detect bar; live fills at broker tick price",
        },
        {
            "name": "S14 Flip",
            "config_on": getattr(config, "S14_FLIP_ENABLED", True),
            "runtime": "apply",
            "replay": "apply",
            "note": "Close opposite S14 exposure on same TF before new order",
        },
        {
            "name": "S14 exit color rule",
            "config_on": True,
            "runtime": "apply",
            "replay": "apply",
            "note": "Sweep checks entry TF; engulf checks mapped HTF/secondary HTF",
        },
        {
            "name": "Trail SL",
            "config_on": getattr(config, "TRAIL_SL_ENABLED", False),
            "runtime": "apply",
            "replay": "partial",
            "note": "Replay models engulf trail across TRAIL_GROUPS with granular price path; focus/reversal nuances can still drift",
        },
        {
            "name": "SL Guard Group overlay",
            "config_on": getattr(config, "SL_GUARD_GROUP_ENABLED", False),
            "runtime": "apply",
            "replay": "partial",
            "note": "Replay approximates close-on-activate from replayed TF context",
        },
        {
            "name": "PD Fibo Plus",
            "config_on": getattr(config, "PDFIBOPLUS_ENABLED", False),
            "runtime": "skip_s14",
            "replay": "skip_s14",
            "note": "Runtime skip SIDs: 9,10,13,14,15,16",
        },
        {
            "name": "Trend Recheck",
            "config_on": getattr(config, "LIMIT_TREND_RECHECK", False),
            "runtime": "skip_s14",
            "replay": "skip_s14",
            "note": "Runtime skip sid 14",
        },
        {
            "name": "RSI Fill Recheck",
            "config_on": getattr(config, "PENDING_RSI_RECHECK_ENABLED", False),
            "runtime": "skip_s14",
            "replay": "skip_s14",
            "note": "Runtime skip sid 14",
        },
        {
            "name": "Entry Candle",
            "config_on": getattr(config, "ENTRY_CANDLE_ENABLED", False),
            "runtime": "skip_s14",
            "replay": "skip_s14",
            "note": "Runtime skips sid 14 because S14 is standalone/market",
        },
        {
            "name": "Opposite Order",
            "config_on": getattr(config, "OPPOSITE_ORDER_ENABLED", False),
            "runtime": "skip_s14",
            "replay": "skip_s14",
            "note": "Runtime filters sid 14 positions/orders",
        },
        {
            "name": "Limit Guard",
            "config_on": getattr(config, "LIMIT_GUARD", False),
            "runtime": "skip_s14",
            "replay": "skip_s14",
            "note": "S14 uses market orders; limit guard does not apply",
        },
        {
            "name": "Delay SL",
            "config_on": getattr(config, "DELAY_SL_MODE", "off") != "off",
            "runtime": "skip_s14",
            "replay": "skip_s14",
            "note": "S14 is market order and does not use delayed pending SL",
        },
        {
            "name": "Strong Trend Block",
            "config_on": (
                getattr(config, "STRONG_TREND_BLOCK_ENABLED", False)
                and 14 in getattr(config, "STRONG_TREND_BLOCK_SIDS", (9, 10, 11, 13, 14, 15, 16))
            ),
            "runtime": "apply",
            "replay": "ready",
            "note": "Replay blocks counter-strong-trend S14 signals when config is enabled; no effect while config is OFF",
        },
    ]


def s14_unreplayed_active_features() -> list[dict]:
    return [
        item for item in s14_runtime_feature_coverage()
        if item["config_on"] and item["runtime"] == "apply" and item["replay"] not in ("apply", "partial")
    ]


def _trade_pnl_at_price(trade: dict, close_price: float) -> float:
    realized = float(trade.get('realized_pnl', 0.0) or 0.0)
    remaining_units = int(trade.get('remaining_units', 1) or 0)
    if remaining_units <= 0:
        return round(realized, 2)
    if trade.get('signal') == 'BUY':
        close_pnl = profit(float(close_price) - float(trade['entry'])) * remaining_units
    else:
        close_pnl = profit(float(trade['entry']) - float(close_price)) * remaining_units
    return round(realized + close_pnl, 2)


def apply_sl_guard_group_overlay(tf_trades: list[tuple[str, dict]]) -> list[tuple[str, dict]]:
    """Approximate runtime SL Guard Group close-on-activate across replayed TFs."""
    if not getattr(config, "SL_GUARD_GROUP_ENABLED", False):
        return tf_trades
    if not getattr(config, "SL_GUARD_CLOSE_ON_ACTIVATE", True):
        return tf_trades

    groups = list(getattr(config, "SL_GUARD_GROUP_GROUPS", []) or [])
    threshold = max(1, int(getattr(config, "SL_GUARD_GROUP_COUNT", 2) or 2))
    if not groups:
        return tf_trades

    rows = []
    for idx, (tf_name, trade) in enumerate(tf_trades):
        trade.setdefault("tf", tf_name)
        rows.append({"idx": idx, "tf": tf_name, "trade": trade})

    state: dict[tuple[str, str], dict] = {}

    def _close_time(row: dict) -> datetime:
        return row["trade"].get("close_time") or row["trade"].get("entry_time")

    def _is_open_at(row: dict, when: datetime) -> bool:
        trade = row["trade"]
        entry_time = trade.get("entry_time")
        close_time = trade.get("close_time")
        if not entry_time or not close_time:
            return False
        return entry_time <= when < close_time

    def _is_loss_trigger(trade: dict) -> bool:
        close_type = str(trade.get("close_type", ""))
        pnl = float(trade.get("pnl", 0.0) or 0.0)
        if close_type == "SL" and pnl < 0:
            return True
        if getattr(config, "SL_GUARD_LOSS_ENABLED", False):
            threshold_usd = float(getattr(config, "SL_GUARD_LOSS_THRESHOLD", 5.0) or 5.0)
            return pnl < -abs(threshold_usd)
        return False

    for trigger in sorted(rows, key=_close_time):
        tr = trigger["trade"]
        if not _is_loss_trigger(tr):
            continue

        tf_name = trigger["tf"]
        side = str(tr.get("signal", "")).upper()
        if side not in ("BUY", "SELL"):
            continue
        trigger_time = tr.get("close_time")
        if not trigger_time:
            continue

        for group in groups:
            if tf_name not in group:
                continue
            gkey = "+".join(group)
            key = (side, gkey)
            sg = state.setdefault(key, {"count": 0, "active": False})
            if sg.get("active"):
                continue
            sg["count"] = int(sg.get("count", 0) or 0) + 1
            if sg["count"] < threshold:
                continue

            sg["active"] = True
            close_price = float(tr.get("close_price", tr.get("entry", 0.0)) or 0.0)
            closed_tickets = []
            for row in rows:
                other = row["trade"]
                if row is trigger:
                    continue
                if str(other.get("signal", "")).upper() != side:
                    continue
                if not _is_open_at(row, trigger_time):
                    continue
                other["close_type"] = "SL_GUARD_GROUP"
                other["close_price"] = close_price
                other["close_time"] = trigger_time
                other["pnl"] = _trade_pnl_at_price(other, close_price)
                other["sl_guard_group"] = gkey
                other["sl_guard_trigger_tf"] = tf_name
                closed_tickets.append(other.get("ticket") or other.get("flow_id") or other.get("entry_time_raw"))
            tr.setdefault("sl_guard_group_activated", gkey)
            tr.setdefault("sl_guard_group_closed_count", len(closed_tickets))

    return [(row["tf"], row["trade"]) for row in sorted(rows, key=lambda r: r["idx"])]

def backtest_tf(
    tf_name: str,
    tf_val: int,
    range_end_utc: datetime | None = None,
    *,
    fill_next_bar: bool = False,
) -> list:
    # ดึง bars จาก MT5 โดยเริ่ม from_pos=0 (newest first internally)
    rates = _fetch_rates(tf_name, tf_val, range_end_utc=range_end_utc)
    if rates is None or len(rates) == 0:
        return []

    bars = sorted([
        {'time': int(r['time']), 'open': float(r['open']),
         'high': float(r['high']), 'low': float(r['low']),
         'close': float(r['close'])}
        for r in rates
    ], key=lambda r: int(r["time"]))
    # Fetch HTF rates for lookup
    from strategy14 import _get_s14_htf, TF_SECONDS
    htf_name = _get_s14_htf(tf_name)
    htf_val = TF_MAP[htf_name]
    htf_rates_raw = _fetch_rates(htf_name, htf_val, range_end_utc=range_end_utc)
    htf_rates_lookup = {}
    if htf_rates_raw is not None:
        htf_rates_lookup = {
            int(r['time']): {
                'time': int(r['time']), 'open': float(r['open']),
                'high': float(r['high']), 'low': float(r['low']),
                'close': float(r['close'])
            }
            for r in htf_rates_raw
        }

    trail_rates_by_tf = {}
    lifecycle_group = list(getattr(config, "TRAIL_GROUPS", {}).get(tf_name, [tf_name]))
    if tf_name not in lifecycle_group:
        lifecycle_group.append(tf_name)
    for trail_tf in lifecycle_group:
        trail_val = TF_MAP.get(trail_tf)
        if trail_val is None:
            continue
        raw_trail = _fetch_rates(trail_tf, trail_val, range_end_utc=range_end_utc)
        if raw_trail is None:
            continue
        trail_rates_by_tf[trail_tf] = sorted([
            {'time': int(r['time']), 'open': float(r['open']),
             'high': float(r['high']), 'low': float(r['low']),
             'close': float(r['close'])}
            for r in raw_trail
        ], key=lambda r: int(r["time"]))
    lifecycle_tf = min(
        (tf for tf in lifecycle_group if tf in trail_rates_by_tf),
        key=lambda tf: TF_SECONDS.get(tf, TF_SECONDS.get(tf_name, 60)),
        default=tf_name,
    )
    lifecycle_rates = trail_rates_by_tf.get(lifecycle_tf, bars)

    since_ts = int(SINCE.timestamp())

    # หา start_idx = bar แรกที่ >= SINCE และ >= WINDOW_NEEDED
    start_idx = None
    for i, b in enumerate(bars):
        if b['time'] >= since_ts and i >= WINDOW_NEEDED + TP_EXTRA:
            start_idx = i
            break
    if start_idx is None:
        return []

    trades = []
    open_trades = []

    def _trade_pnl(trade: dict, close_price: float) -> float:
        realized = float(trade.get('realized_pnl', 0.0) or 0.0)
        remaining_units = int(trade.get('remaining_units', 1) or 0)
        if remaining_units <= 0:
            return round(realized, 2)
        if trade['signal'] == 'BUY':
            close_pnl = profit(close_price - trade['entry']) * remaining_units
        else:
            close_pnl = profit(trade['entry'] - close_price) * remaining_units
        return round(realized + close_pnl, 2)

    def _close_row(trade: dict, close_type: str, close_price: float, close_time: datetime, extra: dict | None = None) -> dict:
        row = {
            **trade,
            'close_type': close_type,
            'close_price': close_price,
            'close_time': close_time,
            'pnl': _trade_pnl(trade, close_price),
        }
        if extra:
            row.update(extra)
        return row

    def _init_scale_out(trade: dict) -> None:
        trade['scale_units'] = 1
        trade['remaining_units'] = 1
        trade['tso_step'] = 0
        trade['realized_pnl'] = 0.0
        if not getattr(config, 'SCALE_OUT_ENABLED', False):
            return
        try:
            if str(trade.get('sid', 14)) == "13":
                return
            if trade['signal'] == 'BUY':
                tp_dist = float(trade['tp']) - float(trade['entry'])
            else:
                tp_dist = float(trade['entry']) - float(trade['tp'])
            distances = list(config.compute_tso_effective_steps(tp_dist, sid=14))
        except Exception:
            distances = []
        if not distances:
            return
        trade['scale_units'] = len(distances)
        trade['remaining_units'] = len(distances)
        trade['tso_distances'] = distances
        for idx in range(1, len(distances) + 1):
            trade[f'scale_out_{idx}_pnl'] = 0.0

    def _s14_market_fill(order: dict, i: int, bt: datetime) -> dict | None:
        fill_idx = i + 1 if fill_next_bar else i
        if fill_idx >= len(bars):
            return None
        fill_bar = bars[fill_idx]
        strategy_entry = float(order['entry'])
        return {
            **order,
            'strategy_entry': strategy_entry,
            'entry': round(strategy_entry, 2),
            'entry_time': to_bkk(fill_bar['time']),
            'entry_time_raw': int(fill_bar['time']),
            'entry_idx': fill_idx,
            'signal_time': bt,
            'signal_time_raw': int(bars[i]['time']),
        }

    def _open_price_at_trade_time(trade: dict) -> float:
        return float(trade['entry'])

    def _apply_scale_out(trade: dict, b: dict) -> dict | None:
        distances = list(trade.get('tso_distances') or [])
        if not distances or int(trade.get('remaining_units', 1) or 0) <= 0:
            return None
        step = int(trade.get('tso_step', 0) or 0)
        if step >= len(distances):
            return None

        entry = float(trade['entry'])
        if trade['signal'] == 'BUY':
            passed = float(b['high']) - entry
            target_price = lambda dist: entry + float(dist)
        else:
            passed = entry - float(b['low'])
            target_price = lambda dist: entry - float(dist)

        while step < len(distances) and passed >= float(distances[step]):
            close_price = target_price(distances[step])
            if trade['signal'] == 'BUY':
                step_pnl = profit(close_price - entry)
            else:
                step_pnl = profit(entry - close_price)
            trade['realized_pnl'] = round(float(trade.get('realized_pnl', 0.0) or 0.0) + step_pnl, 2)
            trade[f'scale_out_{step + 1}_pnl'] = round(step_pnl, 2)
            trade['remaining_units'] = int(trade.get('remaining_units', 1) or 1) - 1
            step += 1
            trade['tso_step'] = step
            if int(trade.get('remaining_units', 0) or 0) <= 0:
                return _close_row(trade, 'TP', close_price, to_bkk(b['time']))
        return None

    def _apply_trail_sl(trade: dict, upto_ts: int) -> None:
        if not getattr(config, "TRAIL_SL_ENABLED", True):
            return
        if int(trade.get("sid", 14) or 14) in (10, 12, 13, 15, 16):
            return
        if not getattr(config, "TRAIL_SL_IMMEDIATE", True):
            return

        group = getattr(config, "TRAIL_GROUPS", {}).get(tf_name, [tf_name])
        current_sl = float(trade.get("sl", 0.0) or 0.0)
        best_sl = current_sl
        best_tf = ""
        entry_ts = int(trade.get("entry_time_raw", 0) or 0)
        if entry_ts <= 0:
            return

        for trail_tf in group:
            tf_rates = trail_rates_by_tf.get(trail_tf)
            if not tf_rates:
                continue
            bars_after = [r for r in tf_rates if entry_ts <= int(r["time"]) < int(upto_ts)]
            if len(bars_after) < 2:
                continue

            tf_sl = current_sl
            found = False
            for j in range(1, len(bars_after)):
                cur = bars_after[j]
                prev = bars_after[j - 1]
                cur_o = float(cur["open"])
                cur_c = float(cur["close"])
                cur_h = float(cur["high"])
                cur_l = float(cur["low"])
                prev_h = float(prev["high"])
                prev_l = float(prev["low"])
                bull = cur_c > cur_o

                if trade["signal"] == "BUY" and bull and cur_c > prev_h:
                    candidate = round(cur_l - 1.0, 2)
                    if candidate > tf_sl:
                        tf_sl = candidate
                        found = True
                elif trade["signal"] == "SELL" and not bull and cur_c < prev_l:
                    candidate = round(cur_h + 1.0, 2)
                    if tf_sl == 0 or candidate < tf_sl:
                        tf_sl = candidate
                        found = True

            if not found or tf_sl == current_sl:
                continue
            if trade["signal"] == "BUY" and tf_sl > best_sl:
                best_sl = tf_sl
                best_tf = trail_tf
            elif trade["signal"] == "SELL" and (best_sl == 0 or tf_sl < best_sl):
                best_sl = tf_sl
                best_tf = trail_tf

        if best_tf:
            trade.setdefault("trail_events", []).append({
                "time": to_bkk(upto_ts),
                "tf": best_tf,
                "old_sl": current_sl,
                "new_sl": best_sl,
            })
            trade["sl"] = best_sl

    def _check_trade_exit(
        in_trade: dict,
        b: dict,
        i: int,
        bt: datetime,
        *,
        check_price: bool = True,
        apply_price_lifecycle: bool = True,
    ) -> dict | None:
        if apply_price_lifecycle:
            _apply_trail_sl(in_trade, int(b['time']))
            tso_closed = _apply_scale_out(in_trade, b)
            if tso_closed:
                return tso_closed

        # ── PD Fibo Plus fill check (round 2) ──
        if _PD_ENABLED and _USE_HHLL and in_trade.get('pd_result') == 'PASS':
            try:
                sh_pt, sl_pt = _hs.get_swing_hl_pts(tf_name)
                if sh_pt and sl_pt:
                    curr_h = float(sh_pt["price"])
                    curr_l = float(sl_pt["price"])
                    fill_h = in_trade.get('fill_h')
                    fill_l = in_trade.get('fill_l')
                    if fill_h is not None and fill_l is not None:
                        if abs(curr_h - fill_h) > 0.01 or abs(curr_l - fill_l) > 0.01:
                            fib_382 = curr_l + (curr_h - curr_l) * 0.382
                            fib_618 = curr_l + (curr_h - curr_l) * 0.618
                            r2_fibo_pct = ((in_trade['entry'] - curr_l) / (curr_h - curr_l)) * 100
                            r2_pass = False
                            if in_trade['signal'] == "BUY":
                                r2_pass = in_trade['entry'] < fib_382
                            elif in_trade['signal'] == "SELL":
                                r2_pass = in_trade['entry'] > fib_618

                            in_trade['fill_h'] = curr_h
                            in_trade['fill_l'] = curr_l
                            in_trade['pd_h'] = curr_h
                            in_trade['pd_l'] = curr_l
                            in_trade['pd_h_time'] = int(sh_pt["time"])
                            in_trade['pd_l_time'] = int(sl_pt["time"])
                            in_trade['pd_fibo_pct'] = r2_fibo_pct

                            if not r2_pass:
                                return _close_row(in_trade, 'PD_FAIL', b['open'], bt, {
                                    'pd_result': 'FAIL',
                                    'pd_round': 2,
                                    'pd_h': curr_h,
                                    'pd_l': curr_l,
                                    'pd_h_time': int(sh_pt["time"]),
                                    'pd_l_time': int(sl_pt["time"]),
                                })
            except Exception:
                pass

        sig = in_trade['signal']
        sub_pat = in_trade.get('sub_pattern', '')
        if sub_pat == 'sweep' and 'entry_idx' in in_trade:
            if i >= in_trade['entry_idx'] + 1:
                entry_bar = bars[in_trade['entry_idx']]
                ho_ex = entry_bar['open']
                hc_ex = entry_bar['close']
                should_exit = False
                if sig == 'BUY' and hc_ex < ho_ex:
                    should_exit = True
                elif sig == 'SELL' and hc_ex > ho_ex:
                    should_exit = True
                if should_exit:
                    return _close_row(in_trade, 'EXIT_COLOR', b['open'], bt)
        elif sub_pat == 'engulf':
            htf_name_s14 = _get_s14_htf(tf_name)
            htf_secs_s14 = TF_SECONDS.get(htf_name_s14, 300)
            entry_time_raw = in_trade['entry_time_raw']
            entry_htf_start = (entry_time_raw // htf_secs_s14) * htf_secs_s14
            exit_bar_start = entry_htf_start
            exit_bar_end = exit_bar_start + htf_secs_s14
            if b['time'] >= exit_bar_end:
                htf_bar = htf_rates_lookup.get(exit_bar_start)
                if htf_bar:
                    ho_ex = htf_bar['open']
                    hc_ex = htf_bar['close']
                    should_exit = False
                    if sig == 'BUY' and hc_ex < ho_ex:
                        should_exit = True
                    elif sig == 'SELL' and hc_ex > ho_ex:
                        should_exit = True
                    if should_exit:
                        return _close_row(in_trade, 'EXIT_COLOR', b['open'], bt)

        if not check_price:
            return None

        h, l = b['high'], b['low']
        if sig == 'BUY':
            if l <= in_trade['sl']:
                return _close_row(in_trade, 'SL', in_trade['sl'], bt)
            if h >= in_trade['tp']:
                return _close_row(in_trade, 'TP', in_trade['tp'], bt)
        else:
            if h >= in_trade['sl']:
                return _close_row(in_trade, 'SL', in_trade['sl'], bt)
            if l <= in_trade['tp']:
                return _close_row(in_trade, 'TP', in_trade['tp'], bt)
        return None

    def _check_trade_price_path(in_trade: dict, base_bar: dict) -> tuple[dict | None, bool]:
        base_ts = int(base_bar["time"])
        base_secs = TF_SECONDS.get(tf_name, 60)
        end_ts = base_ts + base_secs
        entry_ts = int(in_trade.get("entry_time_raw", 0) or 0)
        price_bars = [
            r for r in lifecycle_rates
            if base_ts <= int(r["time"]) < end_ts and int(r["time"]) >= entry_ts
        ]
        if not price_bars:
            return None, False

        for price_bar in price_bars:
            bar_ts = int(price_bar["time"])
            h = float(price_bar["high"])
            l = float(price_bar["low"])
            sig = in_trade["signal"]
            close_time = to_bkk(bar_ts)
            if sig == "BUY":
                if l <= float(in_trade["sl"]):
                    return _close_row(in_trade, "SL", float(in_trade["sl"]), close_time), True
                if h >= float(in_trade["tp"]):
                    return _close_row(in_trade, "TP", float(in_trade["tp"]), close_time), True
            else:
                if h >= float(in_trade["sl"]):
                    return _close_row(in_trade, "SL", float(in_trade["sl"]), close_time), True
                if l <= float(in_trade["tp"]):
                    return _close_row(in_trade, "TP", float(in_trade["tp"]), close_time), True

            tso_closed = _apply_scale_out(in_trade, price_bar)
            if tso_closed:
                return tso_closed, True

            # Trail decisions are based on closed candles; apply them after the
            # current price bar so the new SL protects the next bar onward.
            _apply_trail_sl(in_trade, bar_ts)
        return None, True

    for i in range(start_idx, len(bars)):
        b    = bars[i]
        bt   = to_bkk(b['time'])

        # inject HHLL data จาก bars ที่มี ณ จุดนี้ (รวมแท่งล่าสุด b)
        _inject_hhll(tf_name, bars[:i + 1])

        # ── ตรวจ exit ก่อน (ใช้แท่งย่อยสำหรับราคา/Trail แล้วค่อย fallback TF หลัก) ──
        if open_trades:
            still_open = []
            for in_trade in open_trades:
                closed = _check_trade_exit(
                    in_trade,
                    b,
                    i,
                    bt,
                    check_price=False,
                    apply_price_lifecycle=False,
                )
                path_used = False
                if closed is None:
                    closed, path_used = _check_trade_price_path(in_trade, b)
                if closed is None and not path_used:
                    closed = _check_trade_exit(in_trade, b, i, bt)
                if closed:
                    trades.append(closed)
                else:
                    still_open.append(in_trade)
            open_trades = still_open

        # ── รัน strategy_14 ──
        tp_start = max(0, i - WINDOW_NEEDED - TP_EXTRA + 1)
        full_win  = bars[tp_start:i + 1]
        result    = strategy_14(full_win, tf=tf_name, htf_rates_lookup=htf_rates_lookup)

        sig = result.get('signal', 'WAIT')
        orders = result.get('orders', [result]) if sig == 'MULTI' else ([result] if sig in ('BUY', 'SELL') else [])

        for ord_ in orders:
            # Preserve all fields from the order (including swing reference data)
            if ord_.get('signal') in ('BUY', 'SELL') and ord_.get('entry') is not None and ord_.get('sl') is not None and ord_.get('tp') is not None:
                blocked, _block_reason = _strong_trend_blocks_signal(tf_name, ord_.get('signal'))
                if blocked:
                    continue
                in_trade = _s14_market_fill(ord_, i, bt)
                if in_trade is None:
                    continue
                _init_scale_out(in_trade)

                if getattr(config, 'S14_FLIP_ENABLED', True):
                    kept = []
                    for open_trade in open_trades:
                        if open_trade.get('signal') != in_trade['signal']:
                            trades.append(_close_row(open_trade, 'S14_FLIP', _open_price_at_trade_time(in_trade), in_trade['entry_time']))
                        else:
                            kept.append(open_trade)
                    open_trades = kept

                # ── PD Fibo Plus fill check (round 1) ──
                pd_failed = False
                if _PD_ENABLED and _USE_HHLL:
                    pd_pass, fibo_pct, fill_h, fill_l, fill_h_time, fill_l_time = _check_pd_fibo(in_trade['signal'], in_trade['entry'], tf_name)
                    in_trade['pd_result'] = 'PASS' if pd_pass else 'FAIL'
                    in_trade['pd_round'] = 1
                    if fibo_pct is not None:
                        in_trade['pd_fibo_pct'] = fibo_pct
                    if fill_h is not None:
                        in_trade['fill_h'] = fill_h
                        in_trade['fill_l'] = fill_l
                        in_trade['pd_h'] = fill_h
                        in_trade['pd_l'] = fill_l
                        in_trade['pd_h_time'] = fill_h_time
                        in_trade['pd_l_time'] = fill_l_time
                    if not pd_pass:
                        # ปิดทันทีที่ entry price (PnL = 0)
                        trades.append({**in_trade, 'close_type': 'PD_FAIL',
                                       'close_price': in_trade['entry'], 'close_time': bt, 'pnl': 0.0})
                        pd_failed = True
                if not pd_failed:
                    open_trades.append(in_trade)

    # ── trade ที่ยังเปิดอยู่ → ปิดที่ last close ──
    if open_trades and bars:
        lc  = bars[-1]['close']
        lt  = to_bkk(bars[-1]['time'])
        for in_trade in open_trades:
            trades.append(_close_row(in_trade, 'OPEN', lc, lt))

    return trades


def main():
    if not mt5.initialize():
        print('MT5 init failed:', mt5.last_error())
        return

    print(f'Symbol : {SYMBOL}')
    print(f'Since  : {SINCE.strftime("%d-%m-%Y")}  Volume: {VOLUME} lot')
    print(f'S14 settings: lookback={S14_LOOKBACK}  rsi_period={S14_PERIOD}')
    print(f'  ENGULF={getattr(config,"S14_ENGULF",True)}  SWEEP={getattr(config,"S14_SWEEP",True)}')
    print('=' * 65)

    grand_total = 0.0
    all_trades  = []

    for tf_name, tf_val in TF_MAP.items():
        trades = backtest_tf(tf_name, tf_val)
        all_trades.extend([(tf_name, t) for t in trades])

        if not trades:
            print(f'\n{tf_name}: ไม่พบ signal')
            continue

        tp_cnt  = sum(1 for t in trades if t['close_type'] == 'TP')
        sl_cnt  = sum(1 for t in trades if t['close_type'] == 'SL')
        op_cnt  = sum(1 for t in trades if t['close_type'] == 'OPEN')
        total   = sum(t['pnl'] for t in trades)
        wr      = tp_cnt / (tp_cnt + sl_cnt) * 100 if (tp_cnt + sl_cnt) > 0 else 0
        grand_total += total

        print(f'\n── {tf_name} ─────────────────────────────────────────')
        print(f'   trades={len(trades)}  TP={tp_cnt}  SL={sl_cnt}  OPEN={op_cnt}  WR={wr:.0f}%')
        print(f'   P&L total: {"+" if total>=0 else ""}{total:.2f} USD')

        # แสดง trade list
        for t in trades:
            dt  = t['entry_time'].strftime('%d-%m %H:%M')
            ct  = t['close_time'].strftime('%H:%M') if t['close_type'] != 'OPEN' else 'OPEN'
            pnl_s = f'{"+" if t["pnl"]>=0 else ""}{t["pnl"]:.2f}'
            print(f'   {dt} {t["signal"]:<4} E={t["entry"]:.2f} SL={t["sl"]:.2f} TP={t["tp"]:.2f} '
                  f'→ {t["close_type"]:<4} @ {t.get("close_price", 0):.2f} [{ct}]  {pnl_s} USD  [{t["pattern"]}] '
                  f'Ref={t.get("ref_low", t.get("ref_high", None)):.2f}')

    print('\n' + '=' * 65)
    print(f'GRAND TOTAL: {"+" if grand_total>=0 else ""}{grand_total:.2f} USD  (ทุก TF รวมกัน, volume={VOLUME} lot each)')

    # สรุปแบบตาราง
    print('\n── สรุปตาม TF ─────────────────────────────────────────────')
    print(f'{"TF":<6} {"Trades":>7} {"TP":>5} {"SL":>5} {"WR%":>6} {"P&L":>10}')
    print('-' * 45)
    for tf_name in TF_MAP:
        tf_trades = [t for n, t in all_trades if n == tf_name]
        if not tf_trades:
            print(f'{tf_name:<6} {"0":>7}')
            continue
        tp = sum(1 for t in tf_trades if t['close_type'] == 'TP')
        sl = sum(1 for t in tf_trades if t['close_type'] == 'SL')
        wr = tp / (tp + sl) * 100 if (tp + sl) > 0 else 0
        pnl = sum(t['pnl'] for t in tf_trades)
        print(f'{tf_name:<6} {len(tf_trades):>7} {tp:>5} {sl:>5} {wr:>5.0f}% {pnl:>+10.2f}')
    print('-' * 45)
    print(f'{"TOTAL":<6} {len(all_trades):>7} '
          f'{sum(1 for _,t in all_trades if t["close_type"]=="TP"):>5} '
          f'{sum(1 for _,t in all_trades if t["close_type"]=="SL"):>5} '
          f'{"":>6} {grand_total:>+10.2f}')

    mt5.shutdown()

if __name__ == '__main__':
    main()
