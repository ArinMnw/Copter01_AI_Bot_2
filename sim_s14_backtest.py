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

# HHLL support — inject swing data into hhll_swing when S14_LL_USE_HHLL is True
_USE_HHLL = getattr(config, 'S14_LL_USE_HHLL', False)
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

# PD Fibo Plus fill check — S14 (sid=14) ไม่อยู่ใน skip list (skip เฉพาะ 9, 15)
_PD_ENABLED = getattr(config, 'PDFIBOPLUS_ENABLED', False)

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

def to_bkk(ts: int) -> datetime:
    return datetime.fromtimestamp(ts, tz=UTC) + timedelta(hours=TZ_OFF - SRV_TZ)

def profit(price_diff: float) -> float:
    return round(price_diff * PRICE_TO_USD, 2)

def backtest_tf(tf_name: str, tf_val: int) -> list:
    extra = TF_EXTRA_BARS.get(tf_name, 200)
    total = 5000 + extra

    # ดึง bars จาก MT5 โดยเริ่ม from_pos=0 (newest first internally)
    rates = mt5.copy_rates_from_pos(SYMBOL, tf_val, 0, total)
    if rates is None or len(rates) == 0:
        return []

    bars = [
        {'time': int(r['time']), 'open': float(r['open']),
         'high': float(r['high']), 'low': float(r['low']),
         'close': float(r['close'])}
        for r in rates
    ]
    # Fetch HTF rates for lookup
    from strategy14 import _get_s14_htf, TF_SECONDS
    htf_name = _get_s14_htf(tf_name)
    htf_val = TF_MAP[htf_name]
    htf_rates_raw = mt5.copy_rates_from_pos(SYMBOL, htf_val, 0, total)
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

    since_ts = int(SINCE.timestamp())

    # หา start_idx = bar แรกที่ >= SINCE และ >= WINDOW_NEEDED
    start_idx = None
    for i, b in enumerate(bars):
        if b['time'] >= since_ts and i >= WINDOW_NEEDED + TP_EXTRA:
            start_idx = i
            break
    if start_idx is None:
        return []

    trades   = []
    in_trade = None  # {'signal','entry','sl','tp','entry_time','pattern'}

    for i in range(start_idx, len(bars)):
        b    = bars[i]
        bt   = to_bkk(b['time'])

        # inject HHLL data จาก bars ที่มี ณ จุดนี้ (รวมแท่งล่าสุด b)
        _inject_hhll(tf_name, bars[:i + 1])

        # ── ตรวจ exit ก่อน (ใช้ high/low ของแท่งปัจจุบัน) ──
        if in_trade:
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
                                # H/L เปลี่ยน -> re-check
                                fib_382 = curr_l + (curr_h - curr_l) * 0.382
                                fib_618 = curr_l + (curr_h - curr_l) * 0.618
                                r2_fibo_pct = ((in_trade['entry'] - curr_l) / (curr_h - curr_l)) * 100
                                r2_pass = False
                                if in_trade['signal'] == "BUY":
                                    r2_pass = in_trade['entry'] < fib_382
                                elif in_trade['signal'] == "SELL":
                                    r2_pass = in_trade['entry'] > fib_618
                                
                                # อัปเดต fill_h, fill_l เพื่อไม่ให้ตรวจซ้ำในรอบถัดไปถ้ายังไม่เปลี่ยนอีก
                                in_trade['fill_h'] = curr_h
                                in_trade['fill_l'] = curr_l
                                in_trade['pd_h'] = curr_h
                                in_trade['pd_l'] = curr_l
                                in_trade['pd_h_time'] = int(sh_pt["time"])
                                in_trade['pd_l_time'] = int(sl_pt["time"])
                                in_trade['pd_fibo_pct'] = r2_fibo_pct
                                
                                if not r2_pass:
                                    pnl = profit(b['open'] - in_trade['entry']) if in_trade['signal'] == 'BUY' else profit(in_trade['entry'] - b['open'])
                                    trades.append({**in_trade, 'close_type': 'PD_FAIL',
                                                   'close_price': b['open'], 'close_time': bt, 'pnl': pnl,
                                                   'pd_result': 'FAIL', 'pd_round': 2,
                                                   'pd_h': curr_h, 'pd_l': curr_l,
                                                   'pd_h_time': int(sh_pt["time"]), 'pd_l_time': int(sl_pt["time"])})
                                    in_trade = None
                                    continue
                except Exception:
                    pass

            sig = in_trade['signal']
            # S14 Exit color rule check
            sub_pat = in_trade.get('sub_pattern', '')
            if sub_pat == 'sweep' and 'entry_idx' in in_trade:
                if i >= in_trade['entry_idx'] + 1:
                    entry_bar = bars[in_trade['entry_idx']]
                    ho_ex = entry_bar['open']
                    hc_ex = entry_bar['close']
                    should_exit = False
                    if sig == 'BUY' and hc_ex < ho_ex: # RED
                        should_exit = True
                    elif sig == 'SELL' and hc_ex > ho_ex: # GREEN
                        should_exit = True
                    if should_exit:
                        pnl = profit(b['open'] - in_trade['entry']) if sig == 'BUY' else profit(in_trade['entry'] - b['open'])
                        trades.append({**in_trade, 'close_type': 'EXIT_COLOR',
                                       'close_price': b['open'], 'close_time': bt, 'pnl': pnl})
                        in_trade = None
                        continue
            elif sub_pat == 'engulf':
                htf_name_s14 = _get_s14_htf(tf_name)
                htf_secs_s14 = TF_SECONDS.get(htf_name_s14, 300)
                entry_time_raw = in_trade['entry_time_raw']
                entry_htf_start = (entry_time_raw // htf_secs_s14) * htf_secs_s14
                exit_bar_start = entry_htf_start + htf_secs_s14
                exit_bar_end = exit_bar_start + htf_secs_s14
                if b['time'] >= exit_bar_end:
                    htf_bar = htf_rates_lookup.get(exit_bar_start)
                    if htf_bar:
                        ho_ex = htf_bar['open']
                        hc_ex = htf_bar['close']
                        should_exit = False
                        if sig == 'BUY' and hc_ex < ho_ex: # RED
                            should_exit = True
                        elif sig == 'SELL' and hc_ex > ho_ex: # GREEN
                            should_exit = True
                        if should_exit:
                            pnl = profit(b['open'] - in_trade['entry']) if sig == 'BUY' else profit(in_trade['entry'] - b['open'])
                            trades.append({**in_trade, 'close_type': 'EXIT_COLOR',
                                           'close_price': b['open'], 'close_time': bt, 'pnl': pnl})
                            in_trade = None
                            continue

            h, l = b['high'], b['low']
            if sig == 'BUY':
                if l <= in_trade['sl']:
                    pnl = profit(in_trade['sl'] - in_trade['entry'])
                    trades.append({**in_trade, 'close_type': 'SL',
                                   'close_price': in_trade['sl'], 'close_time': bt, 'pnl': pnl})
                    in_trade = None
                elif h >= in_trade['tp']:
                    pnl = profit(in_trade['tp'] - in_trade['entry'])
                    trades.append({**in_trade, 'close_type': 'TP',
                                   'close_price': in_trade['tp'], 'close_time': bt, 'pnl': pnl})
                    in_trade = None
            else:  # SELL
                if h >= in_trade['sl']:
                    pnl = profit(in_trade['entry'] - in_trade['sl'])
                    trades.append({**in_trade, 'close_type': 'SL',
                                   'close_price': in_trade['sl'], 'close_time': bt, 'pnl': pnl})
                    in_trade = None
                elif l <= in_trade['tp']:
                    pnl = profit(in_trade['entry'] - in_trade['tp'])
                    trades.append({**in_trade, 'close_type': 'TP',
                                   'close_price': in_trade['tp'], 'close_time': bt, 'pnl': pnl})
                    in_trade = None

        # ── ถ้ายังอยู่ใน trade → ข้ามการหา signal ใหม่ ──
        if in_trade:
            continue

        # ── รัน strategy_14 ──
        tp_start = max(0, i - WINDOW_NEEDED - TP_EXTRA + 1)
        full_win  = bars[tp_start:i + 1]
        result    = strategy_14(full_win, tf=tf_name, htf_rates_lookup=htf_rates_lookup)

        sig = result.get('signal', 'WAIT')
        orders = result.get('orders', [result]) if sig == 'MULTI' else ([result] if sig in ('BUY', 'SELL') else [])

        for ord_ in orders:
            # Preserve all fields from the order (including swing reference data)
            if ord_.get('signal') in ('BUY', 'SELL') and ord_.get('entry') is not None and ord_.get('sl') is not None and ord_.get('tp') is not None:
                tf_secs_cur = TF_SECONDS.get(tf_name, 60)
                in_trade = {**ord_, 'entry_time': bt, 'entry_time_raw': int(b['time']) + tf_secs_cur, 'entry_idx': i + 1}
                # ── PD Fibo Plus fill check (round 1) ──
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
                        in_trade = None
                break

    # ── trade ที่ยังเปิดอยู่ → ปิดที่ last close ──
    if in_trade and bars:
        lc  = bars[-1]['close']
        lt  = to_bkk(bars[-1]['time'])
        sig = in_trade['signal']
        pnl = profit(lc - in_trade['entry']) if sig == 'BUY' else profit(in_trade['entry'] - lc)
        trades.append({**in_trade, 'close_type': 'OPEN', 'close_price': lc, 'close_time': lt, 'pnl': pnl})

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
