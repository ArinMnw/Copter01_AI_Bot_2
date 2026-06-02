"""
sim_trend_mode_compare.py — เปรียบเทียบ Trend Filter mode "breakout" vs "basic"
ช่วง: 24-05-2026 ถึงปัจจุบัน | ทุกท่า ทุก TF

breakout (ปัจจุบัน): BULL/BEAR strong เท่านั้นที่ block — weak ผ่านทั้งคู่
basic             : BULL ทุก strength block SELL, BEAR ทุก strength block BUY
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')

import MetaTrader5 as mt5
from datetime import datetime, timezone, timedelta
import config
import scanner as _scanner

from strategy1  import strategy_1
from strategy2  import strategy_2
from strategy3  import strategy_3
from strategy4  import strategy_4
from strategy9  import strategy_9
from strategy14 import strategy_14

# ─── constants ────────────────────────────────────────────────────────────────
SYMBOL       = config.SYMBOL
SINCE        = datetime(2026, 5, 24, 0, 0, 0, tzinfo=timezone.utc)
VOLUME       = 0.01
PRICE_TO_USD = 100 * VOLUME

UTC    = timezone.utc
TZ_OFF = getattr(config, 'TZ_OFFSET', 7)
SRV_TZ = getattr(config, 'MT5_SERVER_TZ', 0)

TF_MAP = {
    'M1':  mt5.TIMEFRAME_M1,
    'M5':  mt5.TIMEFRAME_M5,
    'M15': mt5.TIMEFRAME_M15,
    'M30': mt5.TIMEFRAME_M30,
    'H1':  mt5.TIMEFRAME_H1,
    'H4':  mt5.TIMEFRAME_H4,
}
TF_EXTRA = {
    'M1': 3000, 'M5': 1000, 'M15': 500,
    'M30': 300, 'H1': 200, 'H4': 150,
}

WIN_SIZE     = 400
MAX_PENDING  = 30
MAX_OPEN_BAR = 500
PIVOT_LEFT   = 5     # bars ซ้ายสำหรับ pivot detection

# ─── Simplified pivot-based swing detection ───────────────────────────────────

def _find_pivots(bars, end_idx, n_pivots=3):
    """
    หา pivot highs & lows ย้อนหลังจาก bars[0..end_idx]
    pivot high: bars[j].high > bars[j±k].high สำหรับ k=1..PIVOT_LEFT
    (ต้องมี bars ขวาอีก PIVOT_LEFT แท่งเพื่อยืนยัน → ใช้ end_idx - PIVOT_LEFT เป็น limit)
    """
    limit = end_idx - PIVOT_LEFT
    swing_h, swing_l = [], []
    j = max(PIVOT_LEFT, 0)
    while j <= limit:
        h = bars[j]['high']
        l = bars[j]['low']
        is_ph = all(h > bars[j - k]['high'] for k in range(1, PIVOT_LEFT + 1)) and \
                all(h > bars[j + k]['high'] for k in range(1, PIVOT_LEFT + 1))
        is_pl = all(l < bars[j - k]['low']  for k in range(1, PIVOT_LEFT + 1)) and \
                all(l < bars[j + k]['low']  for k in range(1, PIVOT_LEFT + 1))
        if is_ph:
            swing_h.append({'price': h, 'time': bars[j]['time']})
        if is_pl:
            swing_l.append({'price': l, 'time': bars[j]['time']})
        j += 1
    return swing_h[-n_pivots:], swing_l[-n_pivots:]


def _hhll_last_label(sh_list: list, sl_list: list) -> str:
    """
    คำนวณ last_label (HH/HL/LH/LL) จาก swing high/low list
    เหมือน HHLL module — ดูว่า swing event ล่าสุดคืออะไร
    """
    events = []
    if len(sh_list) >= 2:
        label = 'HH' if sh_list[-1]['price'] > sh_list[-2]['price'] else 'LH'
        events.append((sh_list[-1]['time'], label))
    if len(sl_list) >= 2:
        label = 'HL' if sl_list[-1]['price'] > sl_list[-2]['price'] else 'LL'
        events.append((sl_list[-1]['time'], label))
    if not events:
        return ''
    events.sort(key=lambda x: x[0])
    return events[-1][1]


def inject_swing(tf_name: str, bars: list, end_idx: int):
    """คำนวณ swing data แบบ simplified แล้ว inject เข้า scanner._swing_data"""
    win = bars[max(0, end_idx - 120): end_idx + 1]
    abs_end = len(win) - 1

    sh_list, sl_list = _find_pivots(win, abs_end, n_pivots=3)

    def _fmt(lst, idx):
        if idx < len(lst):
            return lst[-(idx + 1)]
        return None

    sh      = _fmt(sh_list, 0)
    prev_sh = _fmt(sh_list, 1)
    pp_sh   = _fmt(sh_list, 2)
    sl      = _fmt(sl_list, 0)
    prev_sl = _fmt(sl_list, 1)
    pp_sl   = _fmt(sl_list, 2)

    trend_info    = _scanner._compute_trend_info(sh, prev_sh, pp_sh, sl, prev_sl, pp_sl)
    breakout_info = _scanner._compute_breakout_info(win, sh, sl)
    last_label    = _hhll_last_label(sh_list, sl_list)

    _scanner._swing_data[tf_name] = {
        "trend":      trend_info,
        "breakout":   breakout_info,
        "last_label": last_label,   # สำหรับ SIDEWAY_HHLL check
    }


def trend_ok(tf_name: str, signal: str, mode: str) -> bool:
    """ตรวจว่า signal ผ่าน trend filter หรือไม่ — ใช้ config ทุกอย่าง เปลี่ยนแค่ mode"""
    per_tf = getattr(config, 'TREND_FILTER_PER_TF', {}) or {}
    if not per_tf.get(tf_name, False):
        return True

    sw = _scanner._swing_data.get(tf_name, {})
    t  = (sw.get('trend') or {}).get('trend', 'UNKNOWN')
    s  = (sw.get('trend') or {}).get('strength', '-')

    def _sideway_hhll_ok() -> bool:
        """คืน False ถ้า SIDEWAY_HHLL block signal นี้"""
        if t == 'SIDEWAY' and getattr(config, 'TREND_FILTER_SIDEWAY_HHLL', False):
            last_label = sw.get('last_label', '')
            if last_label in ('LH', 'LL') and signal == 'BUY':
                return False
            if last_label in ('HH', 'HL') and signal == 'SELL':
                return False
        return True

    if mode == 'basic':
        if t == 'BULL' and signal == 'SELL':
            return False
        if t == 'BEAR' and signal == 'BUY':
            return False
        return _sideway_hhll_ok()

    if mode == 'breakout_strict':
        # เหมือน breakout แต่ weak ก็ block ด้วย (ไม่ผ่านทั้งคู่)
        # ยังคง exception ตอน strong+break flip direction
        if t == 'BULL':
            brk = sw.get('breakout') or {}
            if s == 'strong' and brk.get('break_down'):
                return signal != 'BUY'    # strong+break_down → block BUY (flip)
            return signal != 'SELL'       # strong ปกติ หรือ weak → block SELL
        if t == 'BEAR':
            brk = sw.get('breakout') or {}
            if s == 'strong' and brk.get('break_up'):
                return signal != 'SELL'   # strong+break_up → block SELL (flip)
            return signal != 'BUY'        # strong ปกติ หรือ weak → block BUY
        return _sideway_hhll_ok()

    # breakout (original): weak ผ่านทั้งคู่, strong เท่านั้นที่ block
    if t == 'BULL':
        if s != 'strong':
            return True   # weak → ผ่านทั้งคู่
        brk = sw.get('breakout') or {}
        if brk.get('break_down'):
            return signal != 'BUY'    # break_down → block BUY
        return signal != 'SELL'       # ปกติ → block SELL
    if t == 'BEAR':
        if s != 'strong':
            return True
        brk = sw.get('breakout') or {}
        if brk.get('break_up'):
            return signal != 'SELL'   # break_up → block SELL
        return signal != 'BUY'        # ปกติ → block BUY
    # SIDEWAY / UNKNOWN → ผ่าน เว้นแต่ SIDEWAY_HHLL block
    return _sideway_hhll_ok()


# ─── helpers ──────────────────────────────────────────────────────────────────

def to_bkk(ts: int) -> str:
    dt = datetime.fromtimestamp(ts, tz=UTC) + timedelta(hours=TZ_OFF - SRV_TZ)
    return dt.strftime('%d/%m %H:%M')

def pnl_usd(diff: float) -> float:
    return round(diff * PRICE_TO_USD, 2)

def extract_orders(result: dict) -> list:
    sig = result.get('signal', 'WAIT')
    if sig == 'MULTI':
        return result.get('orders', [])
    if sig in ('BUY', 'SELL'):
        return [result]
    return []


# ─── backtest core ────────────────────────────────────────────────────────────

def backtest_tf(strategy_fn, tf_name, bars, entry_type, since_ts, trend_mode) -> list:
    trades   = []
    pending  = None
    in_trade = None

    for i in range(WIN_SIZE, len(bars)):
        b = bars[i]

        # ── 1. fill pending ───────────────────────────────────────────────────
        if pending and in_trade is None:
            if i > pending['bar_idx'] + MAX_PENDING:
                pending = None
            else:
                sig    = pending['signal']
                filled = (sig == 'BUY' and b['low'] <= pending['entry']) or \
                         (sig == 'SELL' and b['high'] >= pending['entry'])
                if filled:
                    in_trade = {**pending, 'entry_price': pending['entry'],
                                'fill_idx': i, 'entry_time': to_bkk(b['time'])}
                    pending = None
                    continue

        # ── 2. exit ───────────────────────────────────────────────────────────
        if in_trade:
            sig = in_trade['signal']
            h, l = b['high'], b['low']
            close_type = close_price = None

            if sig == 'BUY':
                if l <= in_trade['sl'] and h >= in_trade['tp']:
                    close_type, close_price = 'SL', in_trade['sl']
                elif l <= in_trade['sl']:
                    close_type, close_price = 'SL', in_trade['sl']
                elif h >= in_trade['tp']:
                    close_type, close_price = 'TP', in_trade['tp']
                elif i - in_trade['fill_idx'] >= MAX_OPEN_BAR:
                    close_type, close_price = 'OPEN', b['close']
            else:
                if h >= in_trade['sl'] and l <= in_trade['tp']:
                    close_type, close_price = 'SL', in_trade['sl']
                elif h >= in_trade['sl']:
                    close_type, close_price = 'SL', in_trade['sl']
                elif l <= in_trade['tp']:
                    close_type, close_price = 'TP', in_trade['tp']
                elif i - in_trade['fill_idx'] >= MAX_OPEN_BAR:
                    close_type, close_price = 'OPEN', b['close']

            if close_type:
                ep = in_trade['entry_price']
                p  = pnl_usd(close_price - ep) if sig == 'BUY' else pnl_usd(ep - close_price)
                trades.append({'signal': sig, 'entry_price': ep,
                               'sl': in_trade['sl'], 'tp': in_trade['tp'],
                               'close_type': close_type, 'close_price': close_price,
                               'pnl': p, 'entry_time': in_trade['entry_time']})
                in_trade = None
            else:
                continue

        if pending or in_trade:
            continue
        if b['time'] < since_ts:
            continue

        # ── 3. swing inject + signal ──────────────────────────────────────────
        inject_swing(tf_name, bars, i)

        win = bars[max(0, i - WIN_SIZE + 1): i + 1]
        try:
            result = strategy_fn(win, tf_name)
        except Exception:
            continue

        for ord_ in extract_orders(result):
            s  = ord_.get('signal')
            e  = ord_.get('entry')
            sl = ord_.get('sl')
            tp = ord_.get('tp')
            if s in ('BUY', 'SELL') and e and sl and tp:
                if not trend_ok(tf_name, s, trend_mode):
                    break   # signal blocked by trend filter
                if entry_type == 'market':
                    in_trade = {'signal': s, 'entry': e, 'sl': sl, 'tp': tp,
                                'entry_price': e, 'fill_idx': i,
                                'entry_time': to_bkk(b['time'])}
                else:
                    pending = {'signal': s, 'entry': e, 'sl': sl, 'tp': tp,
                               'bar_idx': i}
                break

    # trade ที่ยังเปิดอยู่
    if in_trade and bars:
        lb  = bars[-1]
        sig = in_trade['signal']
        ep  = in_trade['entry_price']
        cp  = lb['close']
        p   = pnl_usd(cp - ep) if sig == 'BUY' else pnl_usd(ep - cp)
        trades.append({'signal': sig, 'entry_price': ep,
                       'sl': in_trade['sl'], 'tp': in_trade['tp'],
                       'close_type': 'OPEN', 'close_price': cp, 'pnl': p,
                       'entry_time': in_trade.get('entry_time', '')})
    return trades


def summarize(trades):
    tp_n = sum(1 for t in trades if t['close_type'] == 'TP')
    sl_n = sum(1 for t in trades if t['close_type'] == 'SL')
    op_n = sum(1 for t in trades if t['close_type'] == 'OPEN')
    tot  = sum(t['pnl'] for t in trades)
    wr   = tp_n / (tp_n + sl_n) * 100 if (tp_n + sl_n) > 0 else 0
    return {'n': len(trades), 'tp': tp_n, 'sl': sl_n, 'open': op_n,
            'wr': wr, 'total': tot}


# ─── main ─────────────────────────────────────────────────────────────────────

STRATEGIES = [
    (1,  'S1',  strategy_1,  'limit'),
    (2,  'S2',  strategy_2,  'limit'),
    (3,  'S3',  strategy_3,  'limit'),
    (4,  'S4',  strategy_4,  'limit'),
    (9,  'S9',  strategy_9,  'limit'),
    (14, 'S14', strategy_14, 'market'),
]

def main():
    if not mt5.initialize():
        print('MT5 init failed:', mt5.last_error())
        return

    since_ts = int(SINCE.timestamp())
    sideway_hhll = getattr(config, 'TREND_FILTER_SIDEWAY_HHLL', False)
    print(f'Symbol : {SYMBOL}')
    print(f'Since  : {SINCE.strftime("%d-%m-%Y")}')
    print(f'Trend filter per-TF: {dict(getattr(config,"TREND_FILTER_PER_TF",{}))}')
    print(f'SIDEWAY_HHLL: {sideway_hhll}')
    print(f'Modes: BREAKOUT | BRK_STRICT (weak block) | BASIC')
    print(f'  BREAKOUT    : strong block+exception, weak ผ่านทั้งคู่')
    print(f'  BRK_STRICT  : strong block+exception, weak block ด้วย')
    print(f'  BASIC       : BULL/BEAR block ทุก strength')
    print('=' * 88)

    MODES = ['breakout', 'breakout_strict', 'basic']
    grand = {m: 0.0 for m in MODES}

    def _ds(v): return f'{"+" if v >= 0 else ""}{v:.2f}'

    for sid, sname, fn, etype in STRATEGIES:
        sid_tot = {m: 0.0 for m in MODES}

        print(f'\n{"━"*88}')
        print(f'  ท่า {sid}: {sname}  (entry_type={etype})')
        print(f'{"━"*88}')
        print(f'  {"TF":<6} {"BREAK":>8} {"BRK_STR":>8} {"BASIC":>8}  '
              f'{"D(str-brk)":>10} {"D(bas-brk)":>10}')
        print(f'  {"-"*86}')

        for tf_name, tf_val in TF_MAP.items():
            extra = TF_EXTRA.get(tf_name, 300)
            rates = mt5.copy_rates_from_pos(SYMBOL, tf_val, 0, 5000 + extra)
            if rates is None or len(rates) == 0:
                continue

            bars = [{'time': int(r['time']), 'open': float(r['open']),
                     'high': float(r['high']), 'low': float(r['low']),
                     'close': float(r['close'])} for r in rates]

            results = {}
            for m in MODES:
                results[m] = summarize(backtest_tf(fn, tf_name, bars, etype, since_ts, m))
                sid_tot[m] += results[m]['total']

            d_str = round(results['breakout_strict']['total'] - results['breakout']['total'], 2)
            d_bas = round(results['basic']['total']           - results['breakout']['total'], 2)

            print(
                f'  {tf_name:<6} {results["breakout"]["total"]:>+8.2f} '
                f'{results["breakout_strict"]["total"]:>+8.2f} '
                f'{results["basic"]["total"]:>+8.2f}  '
                f'{_ds(d_str):>10} {_ds(d_bas):>10}'
                f'   | brk n={results["breakout"]["n"]} TP={results["breakout"]["tp"]} SL={results["breakout"]["sl"]} WR={results["breakout"]["wr"]:.0f}%'
                f' | str n={results["breakout_strict"]["n"]} TP={results["breakout_strict"]["tp"]} SL={results["breakout_strict"]["sl"]} WR={results["breakout_strict"]["wr"]:.0f}%'
                f' | bas n={results["basic"]["n"]} TP={results["basic"]["tp"]} SL={results["basic"]["sl"]} WR={results["basic"]["wr"]:.0f}%'
            )

        d_str_sid = round(sid_tot['breakout_strict'] - sid_tot['breakout'], 2)
        d_bas_sid = round(sid_tot['basic']           - sid_tot['breakout'], 2)
        print(f'  {"-"*86}')
        print(f'  {"TOTAL":<6} {sid_tot["breakout"]:>+8.2f} '
              f'{sid_tot["breakout_strict"]:>+8.2f} '
              f'{sid_tot["basic"]:>+8.2f}  '
              f'{_ds(d_str_sid):>10} {_ds(d_bas_sid):>10}')
        for m in MODES:
            grand[m] += sid_tot[m]

    grand_d_str = round(grand['breakout_strict'] - grand['breakout'], 2)
    grand_d_bas = round(grand['basic']           - grand['breakout'], 2)
    print(f'\n{"="*88}')
    print(f'  GRAND TOTAL (ทุกท่า ทุก TF)')
    print(f'  BREAKOUT            : {grand["breakout"]:>+10.2f} USD')
    print(f'  BRK_STRICT          : {grand["breakout_strict"]:>+10.2f} USD  DIFF vs BREAK: {_ds(grand_d_str)} USD')
    print(f'  BASIC               : {grand["basic"]:>+10.2f} USD  DIFF vs BREAK: {_ds(grand_d_bas)} USD')
    print(f'{"="*88}')

    mt5.shutdown()


if __name__ == '__main__':
    main()
