"""
sim_s14_flip_full.py — S14 + Flip Logic + Trend Recheck + PD Zone
ตั้งแต่ 24-05-2026 ถึงปัจจุบัน ทุก TF
"""
import sys, os, re, bisect
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')

import MetaTrader5 as mt5
from datetime import datetime, timezone, timedelta
import config
from strategy14 import strategy_14

SYMBOL        = config.SYMBOL
SINCE         = datetime(2026, 5, 24, 0, 0, 0, tzinfo=timezone.utc)
VOLUME        = 0.01
PRICE_TO_USD  = 100 * VOLUME

S14_LOOKBACK  = int(getattr(config, 'S14_REVERSAL_LOOKBACK', 50))
S14_PERIOD    = int(getattr(config, 'S14_RSI_PERIOD', 14))
WINDOW_NEEDED = S14_LOOKBACK + S14_PERIOD + 15
TP_EXTRA      = 300

LOG_PATH = 'logs/bot.log'
UTC      = timezone.utc
TZ_OFF   = getattr(config, 'TZ_OFFSET', 7)
SRV_TZ   = getattr(config, 'MT5_SERVER_TZ', 0)

TF_MAP = {
    'M1':  mt5.TIMEFRAME_M1,  'M5':  mt5.TIMEFRAME_M5,
    'M15': mt5.TIMEFRAME_M15, 'M30': mt5.TIMEFRAME_M30,
    'H1':  mt5.TIMEFRAME_H1,  'H4':  mt5.TIMEFRAME_H4,
}
TF_EXTRA_BARS = {'M1':2000,'M5':500,'M15':300,'M30':200,'H1':150,'H4':100}

def to_bkk(ts):
    return datetime.fromtimestamp(ts, tz=UTC) + timedelta(hours=TZ_OFF - SRV_TZ)

def pnl_calc(signal, entry, close):
    diff = (close - entry) if signal == 'BUY' else (entry - close)
    return round(diff * PRICE_TO_USD, 2)

# ── Build timeline from bot.log ──────────────────────────────────────────────
print("Loading log timeline...")
_log_lines = open(LOG_PATH, encoding='utf-8-sig').readlines()

re_ts   = re.compile(r'^\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\]')
re_tfhd = re.compile(r'┌─\s*\S+\s+(\w+)')
re_hhll = re.compile(r'🏷️\s*HHLL:\s*([A-Z]+)')
re_trnd = re.compile(r'🧭\s*Trend:[^\s]+\s*(\w+)')
re_hh   = re.compile(r'HH:([\d.]+)\s+([\d:]+\s+[\d]+-\w+)')
re_lh   = re.compile(r'LH:([\d.]+)\s+([\d:]+\s+[\d]+-\w+)')
re_hl   = re.compile(r'HL:([\d.]+)\s+([\d:]+\s+[\d]+-\w+)')
re_ll   = re.compile(r'LL:([\d.]+)\s+([\d:]+\s+[\d]+-\w+)')
_MONTHS = {'Jan':1,'Feb':2,'Mar':3,'Apr':4,'May':5,'Jun':6,
           'Jul':7,'Aug':8,'Sep':9,'Oct':10,'Nov':11,'Dec':12}

def _pt(s):
    try:
        p = s.strip().split(); hm,dm = p[0],p[1]; h,m = map(int,hm.split(':'))
        d,mn = dm.split('-'); return datetime(2026,_MONTHS[mn],int(d),h,m)
    except: return None

def _px(rx, txt):
    mx = rx.search(txt)
    return (float(mx.group(1)), _pt(mx.group(2))) if mx else (None, None)

SINCE_STR = SINCE.strftime('%Y-%m-%d')
_tl_keys, _tl_data = [], []

for ln in _log_lines:
    if 'SCAN_SUMMARY' not in ln or 'Scan Swing' not in ln: continue
    m = re_ts.match(ln)
    if not m: continue
    ts = m.group(1)
    if ts < SINCE_STR: continue
    dt_bkk = datetime.strptime(ts, '%Y-%m-%d %H:%M:%S')
    sw = ln[ln.find('Scan Swing'):]
    tf_data = {}
    for sec in re.split(r'(?=┌─)', sw):
        if not sec.strip(): continue
        tm = re_tfhd.match(sec)
        if not tm: continue
        tf = tm.group(1)
        trm = re_trnd.search(sec)
        if not trm: continue
        t_raw = trm.group(1).strip()
        trend = ('SIDEWAY' if 'SIDEWAY' in t_raw else
                 ('BULL' if 'ull' in t_raw else ('BEAR' if 'ear' in t_raw else t_raw)))
        hm = re_hhll.search(sec); last_label = hm.group(1) if hm else ''
        hh_p,hh_t = _px(re_hh, sec); lh_p,lh_t = _px(re_lh, sec)
        hl_p,hl_t = _px(re_hl, sec); ll_p,ll_t = _px(re_ll, sec)
        sh = (hh_p if hh_t>=lh_t else lh_p) if (hh_p and lh_p and hh_t and lh_t) else (hh_p or lh_p or 0.0)
        sl = (hl_p if hl_t>=ll_t else ll_p) if (hl_p and ll_p and hl_t and ll_t) else (hl_p or ll_p or 0.0)
        eq = (sh+sl)/2 if sh>0 and sl>0 else 0.0
        tf_data[tf] = {'trend':trend,'last_label':last_label,'eq':eq}
    if tf_data:
        _tl_keys.append(dt_bkk); _tl_data.append(tf_data)

print(f"Timeline: {len(_tl_keys)} snapshots  [{_tl_keys[0] if _tl_keys else '-'}  →  {_tl_keys[-1] if _tl_keys else '-'}]")

def _lookup(dt, tf):
    sdt = dt.replace(tzinfo=None) if dt.tzinfo else dt
    idx = bisect.bisect_right(_tl_keys, sdt) - 1
    for j in range(idx, max(idx-20,-1), -1):
        if j < 0: break
        if tf in _tl_data[j]: return _tl_data[j][tf]
    return None

def passes_filters(dt, tf, signal, entry):
    st = _lookup(dt, tf)
    if st is None: return True, ''
    trend, last_label, eq = st['trend'], st['last_label'], st['eq']
    # Trend Recheck
    if trend == 'BULL'   and signal == 'SELL': return False, f'TREND:BULL+SELL'
    if trend == 'BEAR'   and signal == 'BUY':  return False, f'TREND:BEAR+BUY'
    if trend == 'SIDEWAY' and last_label:
        if last_label in ('LH','LL') and signal == 'BUY':  return False, f'TREND:SIDEWAY/{last_label}+BUY'
        if last_label in ('HH','HL') and signal == 'SELL': return False, f'TREND:SIDEWAY/{last_label}+SELL'
    # PD Zone
    if eq > 0:
        if signal == 'SELL' and entry < eq: return False, f'PD:SELL {entry:.2f}<eq{eq:.2f}'
        if signal == 'BUY'  and entry > eq: return False, f'PD:BUY {entry:.2f}>eq{eq:.2f}'
    return True, ''

# ── Backtest per TF ───────────────────────────────────────────────────────────
def backtest_tf(tf_name, tf_val):
    extra = TF_EXTRA_BARS.get(tf_name, 200)
    rates = mt5.copy_rates_from_pos(SYMBOL, tf_val, 0, 5000+extra)
    if rates is None or len(rates) == 0: return [], []

    bars = [{'time':int(r['time']),'open':float(r['open']),
             'high':float(r['high']),'low':float(r['low']),'close':float(r['close'])} for r in rates]

    since_ts = int(SINCE.timestamp())
    start_idx = next((i for i,b in enumerate(bars)
                      if b['time']>=since_ts and i>=WINDOW_NEEDED+TP_EXTRA), None)
    if start_idx is None: return [], []

    trades, in_trade, blocked_log = [], None, []

    for i in range(start_idx, len(bars)):
        b  = bars[i]
        bt = to_bkk(b['time'])
        h, l, c = b['high'], b['low'], b['close']

        # ── SL/TP exit ──
        if in_trade:
            sig = in_trade['signal']
            if sig == 'BUY':
                if l <= in_trade['sl']:
                    trades.append({**in_trade,'close_type':'SL','close_price':in_trade['sl'],
                                   'close_time':bt,'pnl':pnl_calc('BUY',in_trade['entry'],in_trade['sl'])}); in_trade=None
                elif h >= in_trade['tp']:
                    trades.append({**in_trade,'close_type':'TP','close_price':in_trade['tp'],
                                   'close_time':bt,'pnl':pnl_calc('BUY',in_trade['entry'],in_trade['tp'])}); in_trade=None
            else:
                if h >= in_trade['sl']:
                    trades.append({**in_trade,'close_type':'SL','close_price':in_trade['sl'],
                                   'close_time':bt,'pnl':pnl_calc('SELL',in_trade['entry'],in_trade['sl'])}); in_trade=None
                elif l <= in_trade['tp']:
                    trades.append({**in_trade,'close_type':'TP','close_price':in_trade['tp'],
                                   'close_time':bt,'pnl':pnl_calc('SELL',in_trade['entry'],in_trade['tp'])}); in_trade=None

        # ── Signal ──
        tp_start = max(0, i-WINDOW_NEEDED-TP_EXTRA+1)
        result   = strategy_14(bars[tp_start:i+1], tf=tf_name)
        sig      = result.get('signal','WAIT')
        orders   = (result.get('orders',[result]) if sig=='MULTI'
                    else ([result] if sig in ('BUY','SELL') else []))

        new_trade = None
        for ord_ in orders:
            s,e,sl,tp = ord_.get('signal'),ord_.get('entry'),ord_.get('sl'),ord_.get('tp')
            if not (s in ('BUY','SELL') and e and sl and tp): continue
            passed, reason = passes_filters(bt, tf_name, s, e)
            if not passed:
                blocked_log.append({'time':bt,'signal':s,'entry':e,'reason':reason,
                                    'pattern':ord_.get('sub_pattern','?')}); continue
            new_trade = {'signal':s,'entry':e,'sl':sl,'tp':tp,
                         'entry_time':bt,'pattern':ord_.get('sub_pattern','?')}
            break

        if new_trade is None: continue

        # ── Flip: ปิดตัวเก่าถ้าทิศตรงข้าม ──
        if in_trade and in_trade['signal'] != new_trade['signal']:
            flip_pnl = pnl_calc(in_trade['signal'], in_trade['entry'], c)
            trades.append({**in_trade,'close_type':'FLIP','close_price':c,
                           'close_time':bt,'pnl':flip_pnl})
            in_trade = None

        if in_trade is None:
            in_trade = new_trade

    if in_trade and bars:
        lc = bars[-1]['close']; lt = to_bkk(bars[-1]['time'])
        trades.append({**in_trade,'close_type':'OPEN','close_price':lc,'close_time':lt,
                       'pnl':pnl_calc(in_trade['signal'],in_trade['entry'],lc)})

    return trades, blocked_log

# ── Main ─────────────────────────────────────────────────────────────────────
def main():
    if not mt5.initialize():
        print('MT5 init failed:', mt5.last_error()); return

    print(f'\nSymbol : {SYMBOL}')
    print(f'Since  : {SINCE.strftime("%d-%m-%Y")}  Volume: {VOLUME} lot')
    print(f'Filters: Trend Recheck ✓ | PD Zone ✓ | RSI Recheck ✗   Flip: ✓')
    print('=' * 70)

    grand_total, summary_rows, all_blocked = 0.0, [], 0

    for tf_name, tf_val in TF_MAP.items():
        trades, blocked_log = backtest_tf(tf_name, tf_val)
        tp_cnt   = sum(1 for t in trades if t['close_type']=='TP')
        sl_cnt   = sum(1 for t in trades if t['close_type']=='SL')
        flip_cnt = sum(1 for t in trades if t['close_type']=='FLIP')
        op_cnt   = sum(1 for t in trades if t['close_type']=='OPEN')
        total    = sum(t['pnl'] for t in trades)
        wr       = tp_cnt/(tp_cnt+sl_cnt)*100 if (tp_cnt+sl_cnt)>0 else 0
        grand_total += total; all_blocked += len(blocked_log)
        summary_rows.append((tf_name,len(trades),tp_cnt,sl_cnt,flip_cnt,op_cnt,wr,total,len(blocked_log)))

        if not trades and not blocked_log:
            print(f'\n{tf_name}: ไม่พบ signal'); continue

        print(f'\n── {tf_name} ─────────────────────────────────────────────')
        print(f'   trades={len(trades)}  TP={tp_cnt}  SL={sl_cnt}  FLIP={flip_cnt}  OPEN={op_cnt}'
              f'  WR={wr:.0f}%   blocked={len(blocked_log)}')
        print(f'   P&L: {"+" if total>=0 else ""}{total:.2f} USD')

        for t in trades:
            dt    = t['entry_time'].strftime('%d-%m %H:%M')
            ct    = t['close_time'].strftime('%H:%M') if t['close_type']!='OPEN' else 'OPEN'
            pnl_s = f'{"+" if t["pnl"]>=0 else ""}{t["pnl"]:.2f}'
            icon  = {'TP':'🎯','SL':'🛑','FLIP':'↔️','OPEN':'⏳'}.get(t['close_type'],'')
            print(f'   {dt} {t["signal"]:<4} E={t["entry"]:.2f} SL={t["sl"]:.2f}'
                  f' TP={t["tp"]:.2f} → {icon}{t["close_type"]:<4}'
                  f' @ {t.get("close_price",0):.2f} [{ct}]  {pnl_s} USD  [{t["pattern"]}]')

        if blocked_log:
            print(f'   --- Blocked ({len(blocked_log)}) ---')
            for b in blocked_log:
                print(f'   {b["time"].strftime("%d-%m %H:%M")} {b["signal"]:<4}'
                      f' E={b["entry"]:.2f}  ✗ {b["reason"]}  [{b["pattern"]}]')

    print('\n' + '='*70)
    print(f'GRAND TOTAL: {"+" if grand_total>=0 else ""}{grand_total:.2f} USD  '
          f'(volume={VOLUME} lot each TF)   blocked={all_blocked}')

    print('\n── สรุปตาม TF ──────────────────────────────────────────────────────')
    print(f'{"TF":<6} {"Trades":>7} {"TP":>5} {"SL":>5} {"FLIP":>5} {"WR%":>6} {"P&L":>10} {"Blk":>5}')
    print('-'*56)
    for r in summary_rows:
        tf_name,n,tp,sl,flip,op,wr,pnl,blk = r
        print(f'{tf_name:<6} {n:>7} {tp:>5} {sl:>5} {flip:>5} {wr:>5.0f}% {pnl:>+10.2f} {blk:>5}')
    print('-'*56)
    print(f'{"TOTAL":<6} {sum(r[1] for r in summary_rows):>7}'
          f' {sum(r[2] for r in summary_rows):>5} {sum(r[3] for r in summary_rows):>5}'
          f' {sum(r[4] for r in summary_rows):>5} {"":>6} {grand_total:>+10.2f} {all_blocked:>5}')

    print('\n── เปรียบเทียบทุก mode ──────────────────────────────────────────────')
    print(f'  Raw (ไม่มีอะไร):               52 trades  +124.63 USD')
    print(f'  Flip only:                      79 trades  +137.04 USD')
    print(f'  PD Zone only:                   50 trades   +93.82 USD')
    print(f'  Trend+PD (ไม่มี flip):          28 trades   +87.91 USD')
    print(f'  Flip+Trend+PD (this run):  {sum(r[1] for r in summary_rows):>3} trades  '
          f'{"+" if grand_total>=0 else ""}{grand_total:.2f} USD')

    mt5.shutdown()

if __name__ == '__main__':
    main()
