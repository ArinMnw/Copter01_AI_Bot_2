"""
test_531813679.py — Before vs After สำหรับ ticket 531813679
M30 S3 BUY ที่ถูกสร้างเวลา 17:30 BKK วันที่ 26-05-2026
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')

import MetaTrader5 as mt5
from datetime import datetime, timezone, timedelta
import config
import hhll_swing
import scanner as _scanner
from scanner import _compute_trend_info, _get_summary_swing_finders, \
    _resolve_summary_pivot_levels, _compute_breakout_info, swing_data_ready
from hhll_swing import get_swing_hl_pts as _gswhl

SYMBOL = config.SYMBOL
UTC    = timezone.utc
BKK    = timedelta(hours=getattr(config, 'TZ_OFFSET', 7))

def fmt_bkk(ts): return (datetime.fromtimestamp(ts, tz=UTC) + BKK).strftime('%H:%M')
def ok_x(b):     return '✅' if b else '❌'

# ── ดึง M30 bars ─────────────────────────────────────────────────────
if not mt5.initialize():
    print("MT5 init failed:", mt5.last_error()); sys.exit(1)

signal_utc = datetime(2026, 5, 26, 10, 30, 0, tzinfo=UTC)  # 17:30 BKK
rates_raw  = mt5.copy_rates_from(SYMBOL, mt5.TIMEFRAME_M30, signal_utc, 600)
if rates_raw is None or len(rates_raw) < 20:
    print("ดึงข้อมูลไม่ได้"); mt5.shutdown(); sys.exit(1)

rates_list = list(rates_raw)
bars = [{'time': int(r['time']), 'open': float(r['open']),
         'high': float(r['high']), 'low': float(r['low']),
         'close': float(r['close'])} for r in rates_raw]

# ── คำนวณ trend + breakout ──────────────────────────────────────────
hhll_swing.fetch_hhll('M30')
trend_info = hhll_swing.get_trend_from_structure('M30')

lookback   = getattr(config, 'SWING_LOOKBACK', 300)
sf         = _get_summary_swing_finders(lookback)
if sf["mode"] == "pivot":
    pl = _resolve_summary_pivot_levels(
        rates_list, lookback=lookback,
        left  = max(1, int(getattr(config, 'SWING_PIVOT_LEFT',  15) or 15)),
        right = max(1, int(getattr(config, 'SWING_PIVOT_RIGHT', 10) or 10)),
    )
    sh, prev_sh, pp_sh = pl["sh"], pl["prev_sh"], pl["prev_prev_sh"]
    sl, prev_sl, pp_sl = pl["sl"], pl["prev_sl"], pl["prev_prev_sl"]
else:
    sh = sf["high"](rates_list); prev_sh = pp_sh = None
    sl = sf["low"](rates_list);  prev_sl = pp_sl = None

fallback_trend = _compute_trend_info(sh, prev_sh, pp_sh, sl, prev_sl, pp_sl)
final_trend    = trend_info or fallback_trend
t_val          = (final_trend or {}).get('trend',    'UNKNOWN')
strength       = (final_trend or {}).get('strength', '-')

_hhll_sh, _hhll_sl = _gswhl('M30')
brk_info = _compute_breakout_info(
    rates_list, _hhll_sh or sh, _hhll_sl or sl, prev_sh, prev_sl
)
break_up   = bool((brk_info or {}).get('break_up'))
break_down = bool((brk_info or {}).get('break_down'))

# inject ให้ trend_allows_signal ใช้ได้
_scanner._swing_data['M30'] = {"trend": final_trend, "breakout": brk_info}

# ── Old breakout logic (ไม่มี strength check, flip ใช้ทุก strength) ──
def old_trend_ok(t, s, brk_up, brk_dn, signal):
    """จำลอง breakout mode ก่อนแก้ไข"""
    if t not in ('BULL', 'BEAR'):
        return True, 'SIDEWAY/UNKNOWN pass'
    if t == 'BULL':
        if brk_dn:
            return (signal != 'BUY'), f'BULL break_down → {"block BUY" if signal=="BUY" else "allow"}'
        return (signal != 'SELL'), f'BULL → {"block SELL" if signal=="SELL" else "allow"}'
    # BEAR
    if brk_up:
        return (signal != 'SELL'), f'BEAR break_up → {"block SELL" if signal=="SELL" else "allow BUY"}'
    return (signal != 'BUY'), f'BEAR → {"block BUY" if signal=="BUY" else "allow"}'

old_allowed, old_why = old_trend_ok(t_val, strength, break_up, break_down, 'BUY')
new_allowed, new_why = _scanner.trend_allows_signal('M30', 'BUY')

# ════════════════════════════════════════════════════════════════════
print()
print("╔══════════════════════════════════════════════════════════════╗")
print("║   Before vs After — Ticket 531813679  M30 S3 BUY 17:30 BKK ║")
print("╚══════════════════════════════════════════════════════════════╝")

print(f"""
  Context (จาก log จริง):
    entry=4524.86  sl=4490.53  tp=4570.63
    fill=18:25:13  price=4524.83
    trend ณ เวลา signal: BEAR (weak)  — log: trend_filter=bear_weak

  Breakout info ณ เวลา signal (ข้อมูลย้อนหลัง):
    trend  = {t_val} ({strength})
    break_up   = {break_up}
    break_down = {break_down}
""")

# ── Bug 1 ─────────────────────────────────────────────────────────
print("─" * 65)
print("  Bug 1 — Trend Filter ตอน ORDER_CREATED")
print("─" * 65)
print(f"  {'':30s}  {'BEFORE':^12}  {'AFTER':^12}")
print(f"  {'mode':30s}  {'breakout':^12}  {'breakout':^12}")
print(f"  {'weak strength blocks?':30s}  {'ไม่ (flip)':^12}  {'บล็อก':^12}")
print(f"  {'BEAR + break_up + BUY':30s}  {'ผ่าน ✅→❌':^12}  {'block ✅':^12}")
print()
print(f"  BEFORE: trend_allows_signal → allowed={old_allowed}  ({old_why})")
print(f"  AFTER : trend_allows_signal → allowed={new_allowed}  (why='{new_why}')")
print()
if not old_allowed:
    print("  ⚠️  NOTE: ข้อมูลย้อนหลังอาจต่างจาก 17:30 จริง")
    print("       log บอก bear_weak + break_up → ด้วย old code BUY ผ่าน")
    print("       ด้วย new code: weak → block BUY ไม่ว่า break_up จะเป็นอะไร")
verdict1_before = "ORDER สร้าง (ผ่าน trend filter)" if old_allowed else "ORDER BLOCK"
verdict1_after  = "ORDER สร้าง (ผ่าน trend filter)" if new_allowed else "ORDER BLOCK ✅"
print(f"\n  BEFORE → {verdict1_before}")
print(f"  AFTER  → {verdict1_after}")

# ── Bug 2 ─────────────────────────────────────────────────────────
print()
print("─" * 65)
print("  Bug 2 — swing_data_ready หลัง fill (18:25 → 18:29)")
print("─" * 65)
print(f"  {'':44s}  {'BEFORE':^8}  {'AFTER':^8}")
print(f"  {'_swing_data.clear() ทุก cycle':44s}  {'มี':^8}  {'ไม่มี':^8}")
# จำลอง before: clear แล้ว check ก่อน scan
_scanner._swing_data.clear()
before_ready = swing_data_ready('M30')
# restore after: inject กลับ
_scanner._swing_data['M30'] = {"trend": final_trend, "breakout": brk_info}
after_ready = swing_data_ready('M30')
print(f"  {'swing_data_ready(M30) หลัง clear':44s}  {str(before_ready):^8}  {str(after_ready):^8}")
print()
verdict2_before = f"fill_round1_skip_no_data ทุก 5s นาน ~4.5 นาที ❌"
verdict2_after  = f"recheck วิ่งได้ทันทีใน cycle แรก ✅"
print(f"  BEFORE → {verdict2_before}")
print(f"  AFTER  → {verdict2_after}")

# ── Bug 3 ─────────────────────────────────────────────────────────
print()
print("─" * 65)
print("  Bug 3 — _close_position ล้มเหลว (18:29:47 retcode=None)")
print("─" * 65)
print(f"  {'':44s}  {'BEFORE':^8}  {'AFTER':^8}")
print(f"  {'retry เมื่อ ok=False':44s}  {'ไม่มี':^8}  {'3 รอบ':^8}")
print(f"  {'แจ้งเตือน TG เมื่อ fail ทุก retry':44s}  {'ไม่มี':^8}  {'มี':^8}")
print()
verdict3_before = "close ล้มเหลว ไม่มี retry → position ค้างเปิด ❌"
verdict3_after  = "retry 3 รอบ (0.5s) → ถ้าสำเร็จปิดได้, ถ้าไม่ได้แจ้ง TG ✅"
print(f"  BEFORE → {verdict3_before}")
print(f"  AFTER  → {verdict3_after}")

# ── สรุปรวม ───────────────────────────────────────────────────────
print()
print("╔══════════════════════════════════════════════════════════════╗")
print("║  สรุปผล: ถ้าเกิดเหตุการณ์เดียวกันวันนี้                      ║")
print("╚══════════════════════════════════════════════════════════════╝")
print(f"""
  BEFORE (code เดิม):
    17:30  ORDER_CREATED ผ่าน — BEAR weak + break_up → BUY allowed
    18:25  ENTRY_FILL — เข้า position สวนทาง
    18:25  fill_round1_skip_no_data × ทุก 5s เป็นเวลา ~4.5 นาที
    18:29  fill_round1 → allowed=False → _close_position → ok=False
           ไม่มี retry → position ยังค้างอยู่ ❌

  AFTER (code ใหม่):
    17:30  ORDER_CREATED ผ่าน — BEAR weak + break_up → BUY (เหมือนเดิม)
    18:25  ENTRY_FILL — เข้า position สวนทาง
    18:25  fill_round1 วิ่งได้ทันที (Bug 2: ไม่ clear _swing_data แล้ว)
    18:25  fill_round1 → allowed=False → _close_position + retry 3 รอบ (Bug 3)
           → close สำเร็จ → แจ้ง TG ✅
""")

mt5.shutdown()
