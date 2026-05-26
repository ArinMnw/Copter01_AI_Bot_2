"""
sim_s14_full.py — จำลอง S14 พร้อม Trend Recheck + PD Zone + ไม่มี RSI (S14 ยกเว้น)
ตั้งแต่ 24-05-2026 ถึงปัจจุบัน ทุก TF
"""
import sys, os, re, bisect
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')

import MetaTrader5 as mt5
from datetime import datetime, timezone, timedelta
import config
from strategy14 import strategy_14

# ─── Config ───────────────────────────────────────────────────────────────────
SYMBOL        = config.SYMBOL
SINCE         = datetime(2026, 5, 24, 0, 0, 0, tzinfo=timezone.utc)
VOLUME        = 0.01
PRICE_TO_USD  = 100 * VOLUME   # XAUUSD: 1 pt = $1 per 1 lot → 0.01 lot = $0.01/pt... wait
# XAUUSD tick_value=1/tick (0.01) per 1 lot → profit = price_diff * 100 * VOLUME
# e.g. diff=1.0 → 100 ticks × $1/tick × 0.01 lot = $1.00  ✓

S14_LOOKBACK  = int(getattr(config, 'S14_REVERSAL_LOOKBACK', 50))
S14_PERIOD    = int(getattr(config, 'S14_RSI_PERIOD', 14))
WINDOW_NEEDED = S14_LOOKBACK + S14_PERIOD + 15
TP_EXTRA      = 300

LOG_PATH      = 'logs/bot.log'
UTC           = timezone.utc
TZ_OFF        = getattr(config, 'TZ_OFFSET', 7)
SRV_TZ        = getattr(config, 'MT5_SERVER_TZ', 0)

TF_MAP = {
    'M1':  mt5.TIMEFRAME_M1,
    'M5':  mt5.TIMEFRAME_M5,
    'M15': mt5.TIMEFRAME_M15,
    'M30': mt5.TIMEFRAME_M30,
    'H1':  mt5.TIMEFRAME_H1,
    'H4':  mt5.TIMEFRAME_H4,
}
TF_EXTRA_BARS = {'M1': 2000, 'M5': 500, 'M15': 300, 'M30': 200, 'H1': 150, 'H4': 100}

# ─── Helpers ──────────────────────────────────────────────────────────────────
def to_bkk(ts: int) -> datetime:
    return datetime.fromtimestamp(ts, tz=UTC) + timedelta(hours=TZ_OFF - SRV_TZ)

def profit(price_diff: float) -> float:
    return round(price_diff * PRICE_TO_USD, 2)

_MONTHS = {'Jan':1,'Feb':2,'Mar':3,'Apr':4,'May':5,'Jun':6,
           'Jul':7,'Aug':8,'Sep':9,'Oct':10,'Nov':11,'Dec':12}

def parse_pivot_time(s: str, year: int = 2026) -> datetime | None:
    """Parse "HH:MM DD-Mon" → datetime"""
    try:
        parts = s.strip().split()
        hm, dm = parts[0], parts[1]
        h, m = map(int, hm.split(':'))
        day_s, mon_s = dm.split('-')
        return datetime(year, _MONTHS[mon_s], int(day_s), h, m)
    except Exception:
        return None

# ─── STEP 1: Build log timeline (trend + HHLL + swing H/L) ──────────────────
print("Loading log timeline...")
_log_lines = open(LOG_PATH, encoding='utf-8-sig').readlines()

re_ts_line  = re.compile(r'^\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\]')
re_hhll_seq = re.compile(r'🏷️\s*HHLL:\s*([A-Z]+)')          # first = last_label (newest)
re_trend    = re.compile(r'🧭\s*Trend:[^\s]+\s*(\w+)')        # Bull/Bear/SIDEWAY
re_tf_hdr   = re.compile(r'┌─\s*\S+\s+(\w+)')                # TF name
re_hh       = re.compile(r'HH:([\d.]+)\s+([\d:]+\s+[\d]+-\w+)')
re_lh       = re.compile(r'LH:([\d.]+)\s+([\d:]+\s+[\d]+-\w+)')
re_hl       = re.compile(r'HL:([\d.]+)\s+([\d:]+\s+[\d]+-\w+)')
re_ll       = re.compile(r'LL:([\d.]+)\s+([\d:]+\s+[\d]+-\w+)')

SINCE_STR = SINCE.strftime('%Y-%m-%d')

# timeline: sorted list of (datetime_bkk, {tf: state})
_tl_keys   = []  # datetime objects (sorted)
_tl_data   = []  # corresponding dicts {tf: {...}}

for _ln in _log_lines:
    if 'SCAN_SUMMARY' not in _ln or 'Scan Swing' not in _ln:
        continue
    m = re_ts_line.match(_ln)
    if not m:
        continue
    ts_str = m.group(1)
    if ts_str < SINCE_STR:
        continue
    dt_bkk = datetime.strptime(ts_str, '%Y-%m-%d %H:%M:%S')

    sw_part = _ln[_ln.find('Scan Swing'):]
    sections = re.split(r'(?=┌─)', sw_part)

    tf_data = {}
    for sec in sections:
        if not sec.strip():
            continue
        tf_m = re_tf_hdr.match(sec)
        if not tf_m:
            continue
        tf = tf_m.group(1)

        trend_m = re_trend.search(sec)
        if not trend_m:
            continue
        t_raw = trend_m.group(1).strip()
        trend = ('SIDEWAY' if 'SIDEWAY' in t_raw else
                 ('BULL' if 'ull' in t_raw else
                 ('BEAR' if 'ear' in t_raw else t_raw)))

        hhll_m = re_hhll_seq.search(sec)
        last_label = hhll_m.group(1) if hhll_m else ''

        # Parse HH/LH/HL/LL prices + times
        def _price_time(rx, txt):
            mx = rx.search(txt)
            if not mx:
                return None, None
            return float(mx.group(1)), parse_pivot_time(mx.group(2))

        hh_p, hh_t = _price_time(re_hh, sec)
        lh_p, lh_t = _price_time(re_lh, sec)
        hl_p, hl_t = _price_time(re_hl, sec)
        ll_p, ll_t = _price_time(re_ll, sec)

        # swing H = more recent of (HH, LH)
        if hh_p and lh_p and hh_t and lh_t:
            swing_h = hh_p if hh_t >= lh_t else lh_p
        else:
            swing_h = hh_p or lh_p or 0.0

        # swing L = more recent of (HL, LL)
        if hl_p and ll_p and hl_t and ll_t:
            swing_l = hl_p if hl_t >= ll_t else ll_p
        else:
            swing_l = hl_p or ll_p or 0.0

        eq = (swing_h + swing_l) / 2 if swing_h > 0 and swing_l > 0 else 0.0

        tf_data[tf] = {
            'trend': trend,
            'last_label': last_label,
            'swing_h': swing_h,
            'swing_l': swing_l,
            'eq': eq,
        }

    if tf_data:
        _tl_keys.append(dt_bkk)
        _tl_data.append(tf_data)

print(f"Timeline: {len(_tl_keys)} snapshots  [{_tl_keys[0] if _tl_keys else '-'}  →  {_tl_keys[-1] if _tl_keys else '-'}]")


def lookup_state(signal_dt: datetime, tf: str) -> dict | None:
    """หา state ล่าสุด ≤ signal_dt สำหรับ TF นี้"""
    # signal_dt เป็น aware-datetime (BKK) หรือ naive ก็ได้ — เราใช้ naive ตลอด
    sdt = signal_dt.replace(tzinfo=None) if signal_dt.tzinfo else signal_dt
    idx = bisect.bisect_right(_tl_keys, sdt) - 1
    # ค้นย้อนหลังสูงสุด 20 snapshot เพื่อหา TF
    for j in range(idx, max(idx - 20, -1), -1):
        if j < 0:
            break
        if tf in _tl_data[j]:
            return _tl_data[j][tf]
    return None


# ─── STEP 2: Filter function (Trend Recheck + PD Zone) ───────────────────────
def passes_filters(signal_dt: datetime, tf: str, signal: str, entry: float) -> tuple[bool, str]:
    """
    Returns (passed, reason_blocked)
    - Trend Recheck: BULL→block SELL, BEAR→block BUY,
                     SIDEWAY+HH/HL→block SELL, SIDEWAY+LH/LL→block BUY
    - PD Zone:       SELL→entry>eq (premium), BUY→entry<eq (discount)
    - RSI Recheck:   ยกเว้นสำหรับ S14 (sid=14)
    """
    state = lookup_state(signal_dt, tf)
    if state is None:
        return True, ''   # ไม่มีข้อมูล → ปล่อยผ่าน (conservative)

    trend      = state.get('trend', '')
    last_label = state.get('last_label', '')
    eq         = state.get('eq', 0.0)

    # ── Trend Recheck ──
    if trend == 'BULL' and signal == 'SELL':
        return False, f'TREND:BULL+SELL'
    if trend == 'BEAR' and signal == 'BUY':
        return False, f'TREND:BEAR+BUY'
    if trend == 'SIDEWAY' and last_label:
        if last_label in ('LH', 'LL') and signal == 'BUY':
            return False, f'TREND:SIDEWAY/{last_label}+BUY'
        if last_label in ('HH', 'HL') and signal == 'SELL':
            return False, f'TREND:SIDEWAY/{last_label}+SELL'

    # ── PD Zone ──
    if eq > 0:
        if signal == 'SELL' and entry < eq:
            return False, f'PD:SELL entry {entry:.2f} < eq {eq:.2f}'
        if signal == 'BUY' and entry > eq:
            return False, f'PD:BUY entry {entry:.2f} > eq {eq:.2f}'

    return True, ''


# ─── STEP 3: Backtest per TF ─────────────────────────────────────────────────
def backtest_tf(tf_name: str, tf_val: int) -> list:
    extra     = TF_EXTRA_BARS.get(tf_name, 200)
    rates     = mt5.copy_rates_from_pos(SYMBOL, tf_val, 0, 5000 + extra)
    if rates is None or len(rates) == 0:
        return []

    bars = [{'time': int(r['time']), 'open': float(r['open']),
             'high': float(r['high']), 'low': float(r['low']),
             'close': float(r['close'])} for r in rates]

    since_ts = int(SINCE.timestamp())
    start_idx = None
    for i, b in enumerate(bars):
        if b['time'] >= since_ts and i >= WINDOW_NEEDED + TP_EXTRA:
            start_idx = i
            break
    if start_idx is None:
        return []

    trades   = []
    in_trade = None
    blocked_log = []   # เก็บ signal ที่ถูก block

    for i in range(start_idx, len(bars)):
        b   = bars[i]
        bt  = to_bkk(b['time'])

        # ── Exit ──
        if in_trade:
            sig = in_trade['signal']
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
            else:
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

        if in_trade:
            continue

        # ── Signal ──
        tp_start = max(0, i - WINDOW_NEEDED - TP_EXTRA + 1)
        full_win  = bars[tp_start:i + 1]
        result    = strategy_14(full_win, tf=tf_name)

        sig = result.get('signal', 'WAIT')
        orders = (result.get('orders', [result]) if sig == 'MULTI'
                  else ([result] if sig in ('BUY', 'SELL') else []))

        for ord_ in orders:
            s  = ord_.get('signal')
            e  = ord_.get('entry')
            sl = ord_.get('sl')
            tp = ord_.get('tp')
            if not (s in ('BUY', 'SELL') and e and sl and tp):
                continue

            # ── Apply filters ──
            passed, reason = passes_filters(bt, tf_name, s, e)
            if not passed:
                blocked_log.append({
                    'time': bt, 'signal': s, 'entry': e, 'reason': reason,
                    'pattern': ord_.get('sub_pattern', '?'),
                })
                continue

            in_trade = {
                'signal': s, 'entry': e, 'sl': sl, 'tp': tp,
                'entry_time': bt,
                'pattern': ord_.get('sub_pattern', '?'),
            }
            break

    # ── Open trade → close at last bar ──
    if in_trade and bars:
        lc  = bars[-1]['close']
        lt  = to_bkk(bars[-1]['time'])
        pnl = profit(lc - in_trade['entry']) if in_trade['signal'] == 'BUY' \
              else profit(in_trade['entry'] - lc)
        trades.append({**in_trade, 'close_type': 'OPEN',
                       'close_price': lc, 'close_time': lt, 'pnl': pnl})

    return trades, blocked_log


# ─── STEP 4: Main ─────────────────────────────────────────────────────────────
def main():
    if not mt5.initialize():
        print('MT5 init failed:', mt5.last_error())
        return

    print(f'\nSymbol : {SYMBOL}')
    print(f'Since  : {SINCE.strftime("%d-%m-%Y")}  Volume: {VOLUME} lot')
    print(f'Filters: Trend Recheck ✓ | PD Zone ✓ | RSI Recheck ✗ (S14 exempt)')
    print('=' * 70)

    grand_total = 0.0
    summary_rows = []
    all_blocked  = 0

    for tf_name, tf_val in TF_MAP.items():
        result = backtest_tf(tf_name, tf_val)
        trades, blocked_log = result

        tp_cnt = sum(1 for t in trades if t['close_type'] == 'TP')
        sl_cnt = sum(1 for t in trades if t['close_type'] == 'SL')
        op_cnt = sum(1 for t in trades if t['close_type'] == 'OPEN')
        total  = sum(t['pnl'] for t in trades)
        wr     = tp_cnt / (tp_cnt + sl_cnt) * 100 if (tp_cnt + sl_cnt) > 0 else 0
        grand_total += total
        all_blocked += len(blocked_log)

        summary_rows.append((tf_name, len(trades), tp_cnt, sl_cnt, op_cnt, wr, total, len(blocked_log)))

        if not trades and not blocked_log:
            print(f'\n{tf_name}: ไม่พบ signal')
            continue

        print(f'\n── {tf_name} ─────────────────────────────────────────────')
        print(f'   trades={len(trades)}  TP={tp_cnt}  SL={sl_cnt}  OPEN={op_cnt}'
              f'  WR={wr:.0f}%   blocked={len(blocked_log)}')
        print(f'   P&L: {"+" if total>=0 else ""}{total:.2f} USD')

        for t in trades:
            dt    = t['entry_time'].strftime('%d-%m %H:%M')
            ct    = t['close_time'].strftime('%H:%M') if t['close_type'] != 'OPEN' else 'OPEN'
            pnl_s = f'{"+" if t["pnl"]>=0 else ""}{t["pnl"]:.2f}'
            print(f'   {dt} {t["signal"]:<4} E={t["entry"]:.2f} SL={t["sl"]:.2f} TP={t["tp"]:.2f}'
                  f' → {t["close_type"]:<4} @ {t.get("close_price",0):.2f} [{ct}]'
                  f'  {pnl_s} USD  [{t["pattern"]}]')

        if blocked_log:
            print(f'   --- Blocked signals ({len(blocked_log)}) ---')
            for b in blocked_log:
                dt = b['time'].strftime('%d-%m %H:%M')
                print(f'   {dt} {b["signal"]:<4} E={b["entry"]:.2f}  ✗ {b["reason"]}  [{b["pattern"]}]')

    print('\n' + '=' * 70)
    print(f'GRAND TOTAL: {"+" if grand_total>=0 else ""}{grand_total:.2f} USD  '
          f'(volume={VOLUME} lot each TF)   blocked={all_blocked} signals')

    print('\n── สรุปตาม TF ──────────────────────────────────────────────────────')
    print(f'{"TF":<6} {"Trades":>7} {"TP":>5} {"SL":>5} {"WR%":>6} {"P&L":>10} {"Blocked":>8}')
    print('-' * 52)
    for tf_name, n, tp, sl, op, wr, pnl, blk in summary_rows:
        print(f'{tf_name:<6} {n:>7} {tp:>5} {sl:>5} {wr:>5.0f}% {pnl:>+10.2f} {blk:>8}')
    print('-' * 52)
    tp_tot = sum(r[2] for r in summary_rows)
    sl_tot = sum(r[3] for r in summary_rows)
    n_tot  = sum(r[1] for r in summary_rows)
    print(f'{"TOTAL":<6} {n_tot:>7} {tp_tot:>5} {sl_tot:>5} {"":>6} {grand_total:>+10.2f} {all_blocked:>8}')

    mt5.shutdown()

if __name__ == '__main__':
    main()
