"""
compare_s14_sweep_old_new.py
เปรียบเทียบ S14 sweep old vs new logic ตั้งแต่ 06-06-2026

OLD: sweep bar = rates[-1], entry=s_close, s_close >= ref (BUY) / s_close <= ref (SELL)
NEW: sweep bar = rates[-2], confirm bar = rates[-1] ต้องเขียว/แดง,
     entry=confirm_close, s_close > ref (BUY) / s_close < ref (SELL)
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')

import MetaTrader5 as mt5
from datetime import datetime, timezone, timedelta
import config
import hhll_swing as _hs
import importlib, types

# ── patch strategy14 to expose sweep helpers ──────────────────────────
import strategy14 as _s14mod

# ─────────────────────────── constants ────────────────────────────────
SYMBOL       = config.SYMBOL
SINCE        = datetime(2026, 6, 6, 0, 0, 0, tzinfo=timezone.utc)
VOLUME       = 0.01
PRICE_TO_USD = 100 * VOLUME
UTC          = timezone.utc
TZ_OFF       = getattr(config, 'TZ_OFFSET', 7)
SRV_TZ       = getattr(config, 'MT5_SERVER_TZ', 0)

S14_LOOKBACK  = int(getattr(config, 'S14_REVERSAL_LOOKBACK', 50))
S14_PERIOD    = int(getattr(config, 'S14_RSI_PERIOD', 14))
WINDOW_NEEDED = S14_LOOKBACK + S14_PERIOD + 15
TP_EXTRA      = 300

_USE_HHLL = getattr(config, 'S14_LL_USE_HHLL', False)
_HHLL_LB  = int(getattr(config, 'HHLL_LEFT',     5) or 5)
_HHLL_RB  = int(getattr(config, 'HHLL_RIGHT',    5) or 5)
_HHLL_LBK = int(getattr(config, 'HHLL_LOOKBACK', 500) or 500)

TF_MAP = {
    'M1':  mt5.TIMEFRAME_M1,
    'M5':  mt5.TIMEFRAME_M5,
    'M15': mt5.TIMEFRAME_M15,
    'M30': mt5.TIMEFRAME_M30,
    'H1':  mt5.TIMEFRAME_H1,
    'H4':  mt5.TIMEFRAME_H4,
    'D1':  mt5.TIMEFRAME_D1,
}
TF_EXTRA_BARS = {
    'M1': 2000, 'M5': 500, 'M15': 300,
    'M30': 200, 'H1': 150, 'H4': 100, 'D1': 50,
}

def to_bkk(ts): return datetime.fromtimestamp(ts, tz=UTC) + timedelta(hours=TZ_OFF - SRV_TZ)
def profit(diff): return round(diff * PRICE_TO_USD, 2)


def _inject_hhll(tf_name, bars_slice):
    if not _USE_HHLL: return
    max_bars = _HHLL_LBK + _HHLL_LB + _HHLL_RB + 5
    rates = bars_slice[-max_bars:]
    if len(rates) < _HHLL_LB + _HHLL_RB + 10: return
    zz = _hs._build_zz(rates, _HHLL_LB, _HHLL_RB)
    if len(zz) < 5: return
    buckets = {"HH": None, "HL": None, "LH": None, "LL": None}
    prev_b  = {"HH": None, "HL": None, "LH": None, "LL": None}
    structure = []
    for k in range(len(zz)):
        lbl = _hs._classify_pt(zz, k)
        if not lbl: continue
        pt = {"price": zz[k]["price"], "time": zz[k]["time"], "label": lbl}
        prev_b[lbl] = buckets[lbl]
        buckets[lbl] = pt
        structure.append(lbl)
    _hs._hhll_data[tf_name] = {
        "hh": buckets["HH"], "hl": buckets["HL"],
        "lh": buckets["LH"], "ll": buckets["LL"],
        "prev_hh": prev_b["HH"], "prev_hl": prev_b["HL"],
        "prev_lh": prev_b["LH"], "prev_ll": prev_b["LL"],
        "last_label": structure[-1] if structure else "",
        "structure": list(reversed(structure[-6:])),
    }


# ── wrapper ที่รัน strategy_14 แต่ override sweep logic ────────────────
def _run_strategy_with_sweep_mode(rates, tf, htf_rates_lookup, *, old_mode):
    """
    รัน strategy_14 แต่ patch sweep detection ณ runtime
    old_mode=True  → sweep_idx=[-1], entry=s_close, >= /<= ref
    old_mode=False → ใช้โค้ดปัจจุบัน (confirm bar)
    """
    if old_mode:
        # patch _build_buy_results / _build_sell_results ด้วย monkey-patch
        # ทำโดยสลับฟังก์ชันชั่วคราว
        orig_buy  = _s14mod._build_buy_results
        orig_sell = _s14mod._build_sell_results

        def _old_buy(rates, rsi_vals, tf, tp_rates=None, htf_rates_lookup=None):
            res_new = orig_buy(rates, rsi_vals, tf, tp_rates=tp_rates, htf_rates_lookup=htf_rates_lookup)
            res_old_sweep = _old_sweep_buy(rates, tf, htf_rates_lookup=htf_rates_lookup, tp_rates=tp_rates)
            non_sweep = [r for r in res_new if r.get('sub_pattern') != 'sweep']
            return non_sweep + res_old_sweep

        def _old_sell(rates, rsi_vals, tf, tp_rates=None, htf_rates_lookup=None):
            res_new = orig_sell(rates, rsi_vals, tf, tp_rates=tp_rates, htf_rates_lookup=htf_rates_lookup)
            res_old_sweep = _old_sweep_sell(rates, tf, htf_rates_lookup=htf_rates_lookup, tp_rates=tp_rates)
            non_sweep = [r for r in res_new if r.get('sub_pattern') != 'sweep']
            return non_sweep + res_old_sweep

        _s14mod._build_buy_results  = _old_buy
        _s14mod._build_sell_results = _old_sell
        try:
            result = _s14mod.strategy_14(rates, tf=tf, htf_rates_lookup=htf_rates_lookup)
        finally:
            _s14mod._build_buy_results  = orig_buy
            _s14mod._build_sell_results = orig_sell
    else:
        result = _s14mod.strategy_14(rates, tf=tf, htf_rates_lookup=htf_rates_lookup)
    return result


def _old_sweep_buy(rates, tf, htf_rates_lookup=None, tp_rates=None):
    """OLD sweep BUY: rates[-1]=sweep, entry=s_close, s_close >= ref_low"""
    from strategy14 import (
        _pivot_rsi_buy, _tp_from_window, calc_atr, SL_BUFFER,
        _get_s14_htf, TF_SECONDS
    )
    import config as _cfg
    results = []
    want_sweep = getattr(_cfg, "S14_SWEEP", True)
    if not want_sweep or len(rates) < 6:
        return results

    # RSI
    rsi_period = int(getattr(_cfg, 'S14_RSI_PERIOD', 14))
    prices = [float(r['close']) for r in rates]
    rsi_vals = _rsi(prices, rsi_period)

    # get_ref_low_list (แบบง่าย — ใช้ local 3-bar pivot หรือ HHLL)
    ref_list = _get_ref_low_list_helper(rates, rsi_vals, tf)
    if not ref_list:
        return results

    sweep_idx = len(rates) - 1
    sweep_bar = rates[sweep_idx]
    s_low   = float(sweep_bar['low'])
    s_open  = float(sweep_bar['open'])
    s_close = float(sweep_bar['close'])

    for ref in ref_list:
        ref_idx = ref['idx']
        ref_low = ref['low']
        ref_rsi = _pivot_rsi_buy(rates, rsi_vals, ref_idx)
        if ref_rsi is None or sweep_idx - ref_idx < 2:
            continue
        if any(float(r['close']) < ref_low for r in rates[ref_idx + 1:sweep_idx]):
            continue
        if s_low < ref_low and s_open > ref_low and s_close >= ref_low:
            s_rsi = _pivot_rsi_buy(rates, rsi_vals, sweep_idx)
            _rsi_min_diff = float(getattr(_cfg, "S14_RSI_MIN_DIFF", 1.0))
            if s_rsi is not None and s_rsi < 50.0 and (s_rsi - ref_rsi) > _rsi_min_diff:
                entry = round(s_close, 2)
                sl    = round(s_low - SL_BUFFER(calc_atr(rates, 14)), 2)
                if entry > sl:
                    tp = _tp_from_window(tp_rates if tp_rates else rates, "BUY", entry, sl)
                    if tp is not None:
                        results.append({
                            "signal": "BUY", "entry": entry, "sl": sl, "tp": tp,
                            "pattern": "ท่าที่ 14 Sweep RSI BUY [OLD]",
                            "reason": f"[OLD Sweep] ref={ref_low:.2f} s_close={s_close:.2f}>=ref",
                            "order_mode": "market",
                            "entry_label": "BUY MARKET (Sweep OLD)",
                            "sub_pattern": "sweep",
                            "ref_low": ref_low, "ref_time": ref["time"],
                            "ref_source": ref.get("source", ""),
                            "rsi_at_ref": round(ref_rsi, 2),
                            "rsi_at_rej": round(s_rsi, 2),
                            "sweep_bar_time": int(sweep_bar["time"]),
                            "sweep_bar_price": s_low,
                        })
    return results


def _old_sweep_sell(rates, tf, htf_rates_lookup=None, tp_rates=None):
    """OLD sweep SELL: rates[-1]=sweep, entry=s_close, s_close <= ref_high"""
    from strategy14 import (
        _pivot_rsi_sell, _tp_from_window, calc_atr, SL_BUFFER,
    )
    import config as _cfg
    results = []
    want_sweep = getattr(_cfg, "S14_SWEEP", True)
    if not want_sweep or len(rates) < 6:
        return results

    rsi_period = int(getattr(_cfg, 'S14_RSI_PERIOD', 14))
    prices = [float(r['close']) for r in rates]
    rsi_vals = _rsi(prices, rsi_period)

    ref_list = _get_ref_high_list_helper(rates, rsi_vals, tf)
    if not ref_list:
        return results

    sweep_idx = len(rates) - 1
    sweep_bar = rates[sweep_idx]
    s_high  = float(sweep_bar['high'])
    s_open  = float(sweep_bar['open'])
    s_close = float(sweep_bar['close'])

    for ref in ref_list:
        ref_idx  = ref['idx']
        ref_high = ref['high']
        ref_rsi  = _pivot_rsi_sell(rates, rsi_vals, ref_idx)
        if ref_rsi is None or sweep_idx - ref_idx < 2:
            continue
        if any(float(r['close']) > ref_high for r in rates[ref_idx + 1:sweep_idx]):
            continue
        if s_high > ref_high and s_open < ref_high and s_close <= ref_high:
            s_rsi = _pivot_rsi_sell(rates, rsi_vals, sweep_idx)
            _rsi_min_diff = float(getattr(_cfg, "S14_RSI_MIN_DIFF", 1.0))
            if s_rsi is not None and s_rsi > 50.0 and (ref_rsi - s_rsi) > _rsi_min_diff:
                entry = round(s_close, 2)
                sl    = round(s_high + SL_BUFFER(calc_atr(rates, 14)), 2)
                if entry < sl:
                    tp = _tp_from_window(tp_rates if tp_rates else rates, "SELL", entry, sl)
                    if tp is not None:
                        results.append({
                            "signal": "SELL", "entry": entry, "sl": sl, "tp": tp,
                            "pattern": "ท่าที่ 14 Sweep RSI SELL [OLD]",
                            "reason": f"[OLD Sweep] ref={ref_high:.2f} s_close={s_close:.2f}<=ref",
                            "order_mode": "market",
                            "entry_label": "SELL MARKET (Sweep OLD)",
                            "sub_pattern": "sweep",
                            "ref_high": ref_high, "ref_time": ref["time"],
                            "ref_source": ref.get("source", ""),
                            "rsi_at_ref": round(ref_rsi, 2),
                            "rsi_at_rej": round(s_rsi, 2),
                            "sweep_bar_time": int(sweep_bar["time"]),
                            "sweep_bar_price": s_high,
                        })
    return results


def _rsi(closes, period=14):
    """Wilder RSI"""
    if len(closes) < period + 1:
        return [None] * len(closes)
    vals = [None] * period
    gains, losses = [], []
    for i in range(1, period + 1):
        d = closes[i] - closes[i - 1]
        gains.append(max(d, 0)); losses.append(max(-d, 0))
    avg_g = sum(gains) / period
    avg_l = sum(losses) / period
    rs = avg_g / avg_l if avg_l > 0 else float('inf')
    vals.append(100 - 100 / (1 + rs))
    for i in range(period + 1, len(closes)):
        d = closes[i] - closes[i - 1]
        avg_g = (avg_g * (period - 1) + max(d, 0)) / period
        avg_l = (avg_l * (period - 1) + max(-d, 0)) / period
        rs = avg_g / avg_l if avg_l > 0 else float('inf')
        vals.append(100 - 100 / (1 + rs))
    return vals


def _get_ref_low_list_helper(rates, rsi_vals, tf):
    """สร้าง ref_low list โดยเลียน get_ref_low_list จาก strategy14"""
    try:
        # monkey-call ผ่านฟังก์ชัน helper ใน strategy14 module
        # สร้าง partial window แล้วเรียก _build_buy_results เพื่อดึง ref
        # แต่เราต้องการแค่ ref list — ใช้วิธีดึง local pivot แทน
        from strategy14 import _pivot_rsi_buy
        import config as _cfg
        lb = int(getattr(_cfg, 'S14_REVERSAL_LOOKBACK', 50))
        n = len(rates)
        refs = []
        # local 3-bar pivot lows
        for idx in range(1, n - 1):
            lo = float(rates[idx]['low'])
            if float(rates[idx - 1]['low']) > lo and float(rates[idx + 1]['low']) > lo:
                rsi_v = rsi_vals[idx] if idx < len(rsi_vals) else None
                refs.append({
                    'idx': idx, 'low': lo,
                    'time': int(rates[idx]['time']),
                    'source': 'local_pivot',
                    'rsi': rsi_v,
                })
        # ถ้า USE_HHLL ให้เพิ่ม HHLL ref ด้วย
        if _USE_HHLL:
            d = _hs._hhll_data.get(tf)
            if d:
                for key in ('ll', 'hl'):
                    pt = d.get(key)
                    if pt:
                        pt_time = int(pt['time'])
                        for idx in range(n):
                            if idx < n - 2 and int(rates[idx]['time']) == pt_time:
                                rsi_v = rsi_vals[idx] if idx < len(rsi_vals) else None
                                refs.append({
                                    'idx': idx, 'low': float(pt['price']),
                                    'time': pt_time, 'source': f'hhll_{key}',
                                    'rsi': rsi_v,
                                })
                                break
        # filter: ref ต้องอยู่ห่างจาก sweep_idx >= 2
        sweep_idx = n - 1
        valid = [r for r in refs if sweep_idx - r['idx'] >= 2]
        # dedup โดยเอาที่ใหม่สุดต่อ source
        seen = set()
        out = []
        for r in sorted(valid, key=lambda x: x['idx'], reverse=True):
            key = (round(r['low'], 2), r['source'])
            if key not in seen:
                seen.add(key)
                out.append(r)
        return out
    except Exception as e:
        return []


def _get_ref_high_list_helper(rates, rsi_vals, tf):
    """สร้าง ref_high list"""
    import config as _cfg
    n = len(rates)
    refs = []
    for idx in range(1, n - 1):
        hi = float(rates[idx]['high'])
        if float(rates[idx - 1]['high']) < hi and float(rates[idx + 1]['high']) < hi:
            rsi_v = rsi_vals[idx] if idx < len(rsi_vals) else None
            refs.append({
                'idx': idx, 'high': hi,
                'time': int(rates[idx]['time']),
                'source': 'local_pivot',
                'rsi': rsi_v,
            })
    if _USE_HHLL:
        d = _hs._hhll_data.get(tf)
        if d:
            for key in ('lh', 'hh'):
                pt = d.get(key)
                if pt:
                    pt_time = int(pt['time'])
                    for idx in range(n):
                        if idx < n - 2 and int(rates[idx]['time']) == pt_time:
                            rsi_v = rsi_vals[idx] if idx < len(rsi_vals) else None
                            refs.append({
                                'idx': idx, 'high': float(pt['price']),
                                'time': pt_time, 'source': f'hhll_{key}',
                                'rsi': rsi_v,
                            })
                            break
    sweep_idx = n - 1
    valid = [r for r in refs if sweep_idx - r['idx'] >= 2]
    seen = set()
    out = []
    for r in sorted(valid, key=lambda x: x['idx'], reverse=True):
        key = (round(r['high'], 2), r['source'])
        if key not in seen:
            seen.add(key)
            out.append(r)
    return out


# ─────────────────── backtest per TF ──────────────────────────────────
def backtest_tf(tf_name, tf_val):
    extra = TF_EXTRA_BARS.get(tf_name, 200)
    total = 5000 + extra

    rates_raw = mt5.copy_rates_from_pos(SYMBOL, tf_val, 0, total)
    if rates_raw is None or len(rates_raw) == 0:
        return [], []

    bars = sorted([
        {'time': int(r['time']), 'open': float(r['open']),
         'high': float(r['high']), 'low': float(r['low']), 'close': float(r['close'])}
        for r in rates_raw
    ], key=lambda r: r['time'])

    from strategy14 import _get_s14_htf, TF_SECONDS
    htf_name = _get_s14_htf(tf_name)
    htf_val  = TF_MAP[htf_name]
    htf_raw  = mt5.copy_rates_from_pos(SYMBOL, htf_val, 0, total)
    htf_rates_lookup = {}
    if htf_raw is not None:
        htf_rates_lookup = {
            int(r['time']): {
                'time': int(r['time']), 'open': float(r['open']),
                'high': float(r['high']), 'low': float(r['low']), 'close': float(r['close'])
            } for r in htf_raw
        }

    since_ts  = int(SINCE.timestamp())
    start_idx = None
    for i, b in enumerate(bars):
        if b['time'] >= since_ts and i >= WINDOW_NEEDED + TP_EXTRA:
            start_idx = i
            break
    if start_idx is None:
        return [], []

    def _close_row(trade, close_type, close_price, close_time):
        sig = trade['signal']
        if sig == 'BUY':
            pnl = profit(float(close_price) - float(trade['entry']))
        else:
            pnl = profit(float(trade['entry']) - float(close_price))
        return {**trade, 'close_type': close_type, 'close_price': close_price,
                'close_time': close_time, 'pnl': round(pnl, 2)}

    def _check_exit(trade, b, bt):
        sig = trade['signal']
        h, l = float(b['high']), float(b['low'])
        if sig == 'BUY':
            if l <= float(trade['sl']): return _close_row(trade, 'SL', trade['sl'], bt)
            if h >= float(trade['tp']): return _close_row(trade, 'TP', trade['tp'], bt)
        else:
            if h >= float(trade['sl']): return _close_row(trade, 'SL', trade['sl'], bt)
            if l <= float(trade['tp']): return _close_row(trade, 'TP', trade['tp'], bt)
        return None

    def run_loop(use_old):
        trades = []
        open_t = []
        for i in range(start_idx, len(bars)):
            b  = bars[i]
            bt = to_bkk(b['time'])
            _inject_hhll(tf_name, bars[:i + 1])

            still = []
            for tr in open_t:
                closed = _check_exit(tr, b, bt)
                if closed: trades.append(closed)
                else:       still.append(tr)
            open_t = still

            tp_start = max(0, i - WINDOW_NEEDED - TP_EXTRA + 1)
            full_win = bars[tp_start:i + 1]
            result   = _run_strategy_with_sweep_mode(
                full_win, tf_name, htf_rates_lookup, old_mode=use_old
            )

            sig = result.get('signal', 'WAIT')
            orders = result.get('orders', [result]) if sig == 'MULTI' else (
                [result] if sig in ('BUY', 'SELL') else []
            )
            for ord_ in orders:
                if ord_.get('signal') in ('BUY', 'SELL') and ord_.get('entry') and ord_.get('sl') and ord_.get('tp'):
                    tr = {
                        **ord_,
                        'entry_time': bt,
                        'entry_time_raw': int(b['time']),
                        'tf': tf_name,
                        'sid': 14,
                    }
                    # flip
                    kept = []
                    for op in open_t:
                        if op.get('signal') != tr['signal']:
                            trades.append(_close_row(op, 'FLIP', float(tr['entry']), bt))
                        else:
                            kept.append(op)
                    open_t = kept
                    open_t.append(tr)

        lc = bars[-1]['close']
        lt = to_bkk(bars[-1]['time'])
        for tr in open_t:
            trades.append(_close_row(tr, 'OPEN', lc, lt))
        return trades

    trades_old = run_loop(use_old=True)
    trades_new = run_loop(use_old=False)
    return trades_old, trades_new


def _summarize(label, trades):
    tp  = sum(1 for t in trades if t['close_type'] == 'TP')
    sl  = sum(1 for t in trades if t['close_type'] == 'SL')
    op  = sum(1 for t in trades if t['close_type'] == 'OPEN')
    pnl = sum(t['pnl'] for t in trades)
    wr  = tp / (tp + sl) * 100 if (tp + sl) > 0 else 0
    return tp, sl, op, pnl, wr


def main():
    if not mt5.initialize():
        print('MT5 init failed:', mt5.last_error())
        return

    print(f'Symbol  : {SYMBOL}')
    print(f'Since   : {SINCE.strftime("%d-%m-%Y")}')
    print(f'Volume  : {VOLUME} lot')
    print('=' * 75)

    all_old, all_new = [], []

    for tf_name, tf_val in TF_MAP.items():
        trades_old, trades_new = backtest_tf(tf_name, tf_val)
        all_old.extend(trades_old)
        all_new.extend(trades_new)

        if not trades_old and not trades_new:
            print(f'\n{tf_name}: ไม่พบ signal ทั้งสองฝั่ง')
            continue

        tp_o, sl_o, op_o, pnl_o, wr_o = _summarize('old', trades_old)
        tp_n, sl_n, op_n, pnl_n, wr_n = _summarize('new', trades_new)

        print(f'\n── {tf_name} {"─"*55}')
        print(f'{"":20} {"OLD":>12}  {"NEW":>12}  {"DIFF":>10}')
        print(f'  Trades            {len(trades_old):>12}  {len(trades_new):>12}')
        print(f'  TP                {tp_o:>12}  {tp_n:>12}')
        print(f'  SL                {sl_o:>12}  {sl_n:>12}')
        print(f'  OPEN              {op_o:>12}  {op_n:>12}')
        print(f'  WR%              {wr_o:>11.0f}%  {wr_n:>11.0f}%')
        diff_pnl = pnl_n - pnl_o
        pnl_o_s = f'{"+" if pnl_o>=0 else ""}{pnl_o:.2f}'
        pnl_n_s = f'{"+" if pnl_n>=0 else ""}{pnl_n:.2f}'
        diff_s  = f'{"+" if diff_pnl>=0 else ""}{diff_pnl:.2f}'
        print(f'  P&L (USD)        {pnl_o_s:>12}  {pnl_n_s:>12}  {diff_s:>10}')

        # แสดง sweep trades ที่ต่างกัน
        sweep_old = [t for t in trades_old if t.get('sub_pattern') == 'sweep']
        sweep_new = [t for t in trades_new if t.get('sub_pattern') == 'sweep']
        if sweep_old or sweep_new:
            print(f'  --- Sweep trades ---')
            print(f'  {"Time":<14} {"Side":<5} {"E":>8} {"SL":>8} {"TP":>8} {"Close":>7} {"Type":<10} {"P&L":>8}  Version')
            shown = set()
            for t in sweep_old:
                key = (t['entry_time'].strftime('%d-%m %H:%M'), t['signal'])
                shown.add(key)
                dt  = t['entry_time'].strftime('%d-%m %H:%M')
                ct  = t['close_time'].strftime('%H:%M') if t['close_type'] != 'OPEN' else 'OPEN'
                pnl_s = f'{"+" if t["pnl"]>=0 else ""}{t["pnl"]:.2f}'
                print(f'  {dt:<14} {t["signal"]:<5} {t["entry"]:>8.2f} {t["sl"]:>8.2f} {t["tp"]:>8.2f} '
                      f'{t.get("close_price",0):>7.2f} {t["close_type"]:<10} {pnl_s:>8}  [OLD]')
            for t in sweep_new:
                key = (t['entry_time'].strftime('%d-%m %H:%M'), t['signal'])
                marker = '    ' if key in shown else '[+NEW]'
                dt  = t['entry_time'].strftime('%d-%m %H:%M')
                ct  = t['close_time'].strftime('%H:%M') if t['close_type'] != 'OPEN' else 'OPEN'
                pnl_s = f'{"+" if t["pnl"]>=0 else ""}{t["pnl"]:.2f}'
                print(f'  {dt:<14} {t["signal"]:<5} {t["entry"]:>8.2f} {t["sl"]:>8.2f} {t["tp"]:>8.2f} '
                      f'{t.get("close_price",0):>7.2f} {t["close_type"]:<10} {pnl_s:>8}  [NEW] {marker}')

    total_old = sum(t['pnl'] for t in all_old)
    total_new = sum(t['pnl'] for t in all_new)
    diff_total = total_new - total_old

    print('\n' + '=' * 75)
    print(f'GRAND TOTAL  OLD: {"+" if total_old>=0 else ""}{total_old:.2f} USD')
    print(f'GRAND TOTAL  NEW: {"+" if total_new>=0 else ""}{total_new:.2f} USD')
    diff_s = f'{"+" if diff_total>=0 else ""}{diff_total:.2f}'
    print(f'DIFFERENCE       {diff_s} USD  (new - old)')
    print()

    # สรุปตาราง
    print(f'{"TF":<6} {"OLD trades":>10} {"OLD P&L":>10} {"NEW trades":>10} {"NEW P&L":>10} {"DIFF":>10}')
    print('-' * 62)
    for tf_name in TF_MAP:
        to = [t for t in all_old if t.get('tf') == tf_name]
        tn = [t for t in all_new if t.get('tf') == tf_name]
        po = sum(t['pnl'] for t in to)
        pn = sum(t['pnl'] for t in tn)
        d  = pn - po
        print(f'{tf_name:<6} {len(to):>10} {po:>+10.2f} {len(tn):>10} {pn:>+10.2f} {d:>+10.2f}')
    print('-' * 62)
    print(f'{"TOTAL":<6} {len(all_old):>10} {total_old:>+10.2f} {len(all_new):>10} {total_new:>+10.2f} {diff_total:>+10.2f}')

    mt5.shutdown()


if __name__ == '__main__':
    main()
