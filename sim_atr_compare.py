"""
sim_atr_compare.py — เปรียบเทียบ P&L ก่อน/หลังเปลี่ยน ATR เป็น True Range + RMA
ช่วง: 24-05-2026 ถึงปัจจุบัน | ท่า: S1, S2, S3, S4, S9, S14 | ทุก TF

OLD ATR: simple H-L average (14 bars) — แบบเดิม
NEW ATR: True Range + RMA (Wilder's, period=14) — เหมือน ATR_TrueRange.mq5
"""
import sys, os, inspect
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')

import MetaTrader5 as mt5
from datetime import datetime, timezone, timedelta
import config
import mt5_utils

# ─── import strategies ────────────────────────────────────────────────────────
from strategy1  import strategy_1
from strategy2  import strategy_2
from strategy3  import strategy_3
from strategy4  import strategy_4
from strategy9  import strategy_9
from strategy14 import strategy_14
import strategy3  as _s3
import strategy9  as _s9
import strategy14 as _s14

# ─── constants ────────────────────────────────────────────────────────────────
SYMBOL       = config.SYMBOL
SINCE        = datetime(2026, 5, 24, 0, 0, 0, tzinfo=timezone.utc)
VOLUME       = 0.01
PRICE_TO_USD = 100 * VOLUME   # price_diff × factor = USD (XAUUSD, 0.01 lot)

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

# จำนวน bars เพิ่มเติมก่อน SINCE เพื่อให้ lookback และ RMA warm-up
TF_EXTRA = {
    'M1': 3000, 'M5': 1000, 'M15': 500,
    'M30': 300, 'H1': 200, 'H4': 150,
}

WIN_SIZE     = 400   # bars ที่ส่งให้ strategy function
MAX_PENDING  = 30    # bars สูงสุดรอ limit fill ก่อน expire
MAX_OPEN_BAR = 500   # bars สูงสุดของ trade ที่เปิดค้างอยู่

# ─── ATR implementations ──────────────────────────────────────────────────────

def old_calc_atr(rates, period: int = 14) -> float:
    """ATR แบบเก่า: simple H-L average (14 bars)"""
    n = min(period, len(rates))
    if n == 0:
        return 0.0
    return sum(float(r['high']) - float(r['low']) for r in rates[-n:]) / n


def new_calc_atr(rates, period: int = 14) -> float:
    """ATR แบบใหม่: True Range + RMA (Wilder's) — เหมือน ATR_TrueRange.mq5"""
    return mt5_utils.calc_atr(rates, period)


# ─── monkey-patch helpers ─────────────────────────────────────────────────────

_original_atr = {
    'mt5_utils': mt5_utils.calc_atr,
    's3':  _s3.calc_atr,
    's9':  _s9.calc_atr,
    's14': _s14.calc_atr,
}

def _patch(fn):
    mt5_utils.calc_atr = fn
    _s3.calc_atr  = fn
    _s9.calc_atr  = fn
    _s14.calc_atr = fn

def _restore():
    mt5_utils.calc_atr = _original_atr['mt5_utils']
    _s3.calc_atr  = _original_atr['s3']
    _s9.calc_atr  = _original_atr['s9']
    _s14.calc_atr = _original_atr['s14']


# ─── helpers ──────────────────────────────────────────────────────────────────

def to_bkk(ts: int) -> str:
    dt = datetime.fromtimestamp(ts, tz=UTC) + timedelta(hours=TZ_OFF - SRV_TZ)
    return dt.strftime('%d/%m %H:%M')

def pnl(diff: float) -> float:
    return round(diff * PRICE_TO_USD, 2)

def call_strategy(fn, win, tf):
    """เรียก strategy ตาม signature จริง — บางท่า (S3) รับแค่ rates ไม่รับ tf
    (เดิม sim เรียก fn(win, tf) เสมอ → S3 โยน TypeError → ถูก except กลืน → n=0)"""
    try:
        nparams = len(inspect.signature(fn).parameters)
    except (TypeError, ValueError):
        nparams = 2
    return fn(win, tf) if nparams >= 2 else fn(win)


def extract_orders(result: dict) -> list:
    """แปลง result dict → list of {signal, entry, sl, tp}"""
    sig = result.get('signal', 'WAIT')
    if sig == 'MULTI':
        return result.get('orders', [])
    if sig in ('BUY', 'SELL'):
        return [result]
    return []


# ─── backtest per strategy per TF ─────────────────────────────────────────────

def backtest_tf(strategy_fn, tf_name, bars, entry_type: str, since_ts: int) -> list:
    """
    entry_type:
      'market' — fill immediately on signal bar (S14)
      'limit'  — รอ price มาแตะ entry (S1,S2,S3,S4,S9), expire หลัง MAX_PENDING bars
    Returns list of trade dicts
    """
    trades   = []
    pending  = None   # รอ fill: {signal,entry,sl,tp,bar_idx,sub_pattern}
    in_trade = None   # กำลัง trade: {signal,entry_price,sl,tp,fill_idx,sub_pattern}

    for i in range(WIN_SIZE, len(bars)):
        b = bars[i]

        # ── 1. ตรวจ fill pending (limit) ─────────────────────────────────────
        if pending and in_trade is None:
            if i > pending['bar_idx'] + MAX_PENDING:
                pending = None   # expired
            else:
                sig = pending['signal']
                filled = False
                if   sig == 'BUY'  and b['low']  <= pending['entry']:
                    filled = True
                elif sig == 'SELL' and b['high'] >= pending['entry']:
                    filled = True

                if filled:
                    in_trade = {
                        'signal':      pending['signal'],
                        'entry_price': pending['entry'],
                        'sl':          pending['sl'],
                        'tp':          pending['tp'],
                        'fill_idx':    i,
                        'entry_time':  to_bkk(b['time']),
                        'sub_pattern': pending.get('sub_pattern', ''),
                    }
                    pending = None
                    # ไม่ตรวจ SL/TP บนแท่ง fill เดียวกัน (รอแท่งถัดไป)
                    continue

        # ── 2. ตรวจ exit ──────────────────────────────────────────────────────
        if in_trade:
            sig = in_trade['signal']
            h, l = b['high'], b['low']
            close_type = None
            close_price = None

            if sig == 'BUY':
                if l <= in_trade['sl'] and h >= in_trade['tp']:
                    close_type, close_price = 'SL', in_trade['sl']   # SL ก่อน (conservative)
                elif l <= in_trade['sl']:
                    close_type, close_price = 'SL', in_trade['sl']
                elif h >= in_trade['tp']:
                    close_type, close_price = 'TP', in_trade['tp']
                elif i - in_trade['fill_idx'] >= MAX_OPEN_BAR:
                    close_type, close_price = 'OPEN', b['close']
            else:  # SELL
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
                cp = close_price
                p  = pnl(cp - ep) if sig == 'BUY' else pnl(ep - cp)
                trades.append({
                    'signal':      sig,
                    'entry_price': ep,
                    'sl':          in_trade['sl'],
                    'tp':          in_trade['tp'],
                    'close_type':  close_type,
                    'close_price': cp,
                    'close_time':  to_bkk(b['time']),
                    'entry_time':  in_trade['entry_time'],
                    'pnl':         p,
                    'sub_pattern': in_trade.get('sub_pattern', ''),
                })
                in_trade = None
            else:
                continue  # ยัง in trade, ไม่หา signal ใหม่

        # ── 3. หา signal ──────────────────────────────────────────────────────
        if pending or in_trade:
            continue

        if b['time'] < since_ts:
            continue

        win = bars[max(0, i - WIN_SIZE + 1): i + 1]
        try:
            result = call_strategy(strategy_fn, win, tf_name)
        except Exception:
            continue

        orders = extract_orders(result)
        for ord_ in orders:
            s  = ord_.get('signal')
            e  = ord_.get('entry')
            sl = ord_.get('sl')
            tp = ord_.get('tp')
            if s in ('BUY', 'SELL') and e and sl and tp:
                if entry_type == 'market':
                    # market: fill immediately
                    in_trade = {
                        'signal':      s,
                        'entry_price': e,
                        'sl':          sl,
                        'tp':          tp,
                        'fill_idx':    i,
                        'entry_time':  to_bkk(b['time']),
                        'sub_pattern': ord_.get('sub_pattern', ''),
                    }
                else:
                    pending = {
                        'signal':      s,
                        'entry':       e,
                        'sl':          sl,
                        'tp':          tp,
                        'bar_idx':     i,
                        'sub_pattern': ord_.get('sub_pattern', ''),
                    }
                break

    # trade ที่ยังเปิดอยู่ → ปิดที่ last bar
    if in_trade and bars:
        lb  = bars[-1]
        sig = in_trade['signal']
        ep  = in_trade['entry_price']
        cp  = lb['close']
        p   = pnl(cp - ep) if sig == 'BUY' else pnl(ep - cp)
        trades.append({
            'signal':      sig,
            'entry_price': ep,
            'sl':          in_trade['sl'],
            'tp':          in_trade['tp'],
            'close_type':  'OPEN',
            'close_price': cp,
            'close_time':  to_bkk(lb['time']),
            'entry_time':  in_trade['entry_time'],
            'pnl':         p,
            'sub_pattern': in_trade.get('sub_pattern', ''),
        })

    return trades


def summarize(trades: list) -> dict:
    tp_n = sum(1 for t in trades if t['close_type'] == 'TP')
    sl_n = sum(1 for t in trades if t['close_type'] == 'SL')
    op_n = sum(1 for t in trades if t['close_type'] == 'OPEN')
    total_pnl = sum(t['pnl'] for t in trades)
    wr = tp_n / (tp_n + sl_n) * 100 if (tp_n + sl_n) > 0 else 0
    return {'n': len(trades), 'tp': tp_n, 'sl': sl_n, 'open': op_n,
            'wr': wr, 'total': total_pnl}


# ─── main ─────────────────────────────────────────────────────────────────────

STRATEGIES = [
    # (sid, name, fn,          entry_type)
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
    print(f'Symbol : {SYMBOL}')
    print(f'Since  : {SINCE.strftime("%d-%m-%Y")}')
    print(f'Volume : {VOLUME} lot  |  SL_ATR_MULT={config.SL_ATR_MULT}')
    print(f'ATR OLD: simple H-L avg (14 bars)')
    print(f'ATR NEW: True Range + RMA (Wilder\'s, period=14)')
    print('=' * 72)

    grand_old = 0.0
    grand_new = 0.0

    # per-strategy summary: {sid: {tf: {old: summary, new: summary}}}
    all_results = {}

    for sid, sname, fn, etype in STRATEGIES:
        all_results[sid] = {}
        sid_old_total = 0.0
        sid_new_total = 0.0

        print(f'\n{"━"*72}')
        print(f'  ท่า {sid}: {sname}  (entry_type={etype})')
        print(f'{"━"*72}')
        print(f'  {"TF":<6} {"":>3} {"OLD":>8} {"NEW":>8} {"DIFF":>8}  |  '
              f'OLD [n/TP/SL/WR%]     NEW [n/TP/SL/WR%]')
        print(f'  {"-"*70}')

        for tf_name, tf_val in TF_MAP.items():
            extra = TF_EXTRA.get(tf_name, 300)
            total = 5000 + extra

            rates = mt5.copy_rates_from_pos(SYMBOL, tf_val, 0, total)
            if rates is None or len(rates) == 0:
                print(f'  {tf_name:<6}: ดึง rates ไม่ได้')
                continue

            bars = [
                {'time': int(r['time']), 'open': float(r['open']),
                 'high': float(r['high']), 'low':  float(r['low']),
                 'close': float(r['close'])}
                for r in rates
            ]

            # ── OLD ATR ──────────────────────────────────────────────────────
            _patch(old_calc_atr)
            try:
                trades_old = backtest_tf(fn, tf_name, bars, etype, since_ts)
            except Exception as ex:
                trades_old = []
                print(f'  {tf_name} OLD error: {ex}')
            finally:
                _restore()

            # ── NEW ATR ──────────────────────────────────────────────────────
            # (ใช้ calc_atr จริง ไม่ต้อง patch)
            try:
                trades_new = backtest_tf(fn, tf_name, bars, etype, since_ts)
            except Exception as ex:
                trades_new = []
                print(f'  {tf_name} NEW error: {ex}')

            s_old = summarize(trades_old)
            s_new = summarize(trades_new)
            diff  = round(s_new['total'] - s_old['total'], 2)
            diff_s = f'{"+" if diff >= 0 else ""}{diff:.2f}'

            all_results[sid][tf_name] = {'old': s_old, 'new': s_new}
            sid_old_total += s_old['total']
            sid_new_total += s_new['total']

            old_str = f'{s_old["total"]:+.2f}'
            new_str = f'{s_new["total"]:+.2f}'

            print(
                f'  {tf_name:<6} {"":>3} {old_str:>8} {new_str:>8} {diff_s:>8}  |  '
                f'n={s_old["n"]} TP={s_old["tp"]} SL={s_old["sl"]} WR={s_old["wr"]:.0f}%'
                f'   |  '
                f'n={s_new["n"]} TP={s_new["tp"]} SL={s_new["sl"]} WR={s_new["wr"]:.0f}%'
            )

        sid_diff = round(sid_new_total - sid_old_total, 2)
        print(f'  {"-"*70}')
        print(f'  {"TOTAL":<6} {"":>3} {sid_old_total:>+8.2f} {sid_new_total:>+8.2f} '
              f'{("+" if sid_diff>=0 else "")+f"{sid_diff:.2f}":>8}')
        grand_old += sid_old_total
        grand_new += sid_new_total

    # ─── Grand total ──────────────────────────────────────────────────────────
    grand_diff = round(grand_new - grand_old, 2)
    print(f'\n{"="*72}')
    print(f'  GRAND TOTAL (ทุกท่า ทุก TF)')
    print(f'  OLD ATR : {grand_old:+.2f} USD')
    print(f'  NEW ATR : {grand_new:+.2f} USD')
    print(f'  DIFF    : {"+" if grand_diff>=0 else ""}{grand_diff:.2f} USD')
    print(f'{"="*72}')

    mt5.shutdown()


if __name__ == '__main__':
    main()
