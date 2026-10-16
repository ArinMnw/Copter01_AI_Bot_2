"""EA2.1 demo-portfolio bridge, using the same signal engine and dedicated SID."""

import math
import sys
import time
from pathlib import Path
from datetime import datetime, timezone

import config
import mt5_worker as mt5
from bot_log import log_event

_EA_DIR = Path(__file__).resolve().parent / "mq5_strategy" / "ea2.1"
if str(_EA_DIR) not in sys.path:
    sys.path.append(str(_EA_DIR))
from live_ea2_1 import (detect_ea2_1, execution_intent, mark_execution_attempt,
                        acknowledge_execution)

_last_log = 0.0


def reconcile_execution(symbol):
    """Only positive broker evidence resolves a send with an unknown outcome."""
    intent = execution_intent(config, symbol)
    if not intent or intent["status"] not in ("inflight", "unknown"):
        return True
    positions = mt5.positions_get(symbol=symbol)
    start = int(intent.get("broker_time", 0))
    if not start or positions is None:
        return False
    deals = mt5.history_deals_get(datetime.fromtimestamp(start - 5, timezone.utc),
                                 datetime.fromtimestamp(start + 300, timezone.utc))
    if deals is None:
        return False
    side = mt5.ORDER_TYPE_BUY if intent["event"]["signal"] == "BUY" else mt5.ORDER_TYPE_SELL
    matches = set()
    for pos in positions:
        if (pos.magic == config.EA2_1_MAGIC_NUMBER and pos.symbol == symbol
                and pos.type == side and start - 2 <= pos.time <= start + 300):
            matches.add(int(pos.identifier))
    for deal in deals:
        if (deal.magic == config.EA2_1_MAGIC_NUMBER and deal.symbol == symbol
                and deal.type == side and deal.entry == mt5.DEAL_ENTRY_IN
                and start - 2 <= deal.time <= start + 300):
            matches.add(int(deal.position_id))
    if len(matches) != 1:
        return False  # Absence is not proof of rejection; do not send again.
    ticket = matches.pop()
    acknowledge_execution(config, symbol, intent["token"], success=True, ticket=ticket)
    log_event("EA2_1_EXECUTION_RECONCILED", "broker entry confirmed", ticket=ticket,
              sid=config.EA2_1_SID, symbol=symbol)
    return True


def demo_account_allowed(account):
    return bool(account is not None and account.trade_mode == mt5.ACCOUNT_TRADE_MODE_DEMO
                and int(account.login) == int(config.MT5_LOGIN or 0))


def risk_volume(signal, symbol, entry, sl, requested_volume, account, info):
    """Round down; optionally allow only a 0.01-lot floor above the risk budget."""
    risk_pct = float(config.EA2_1_RISK_PERCENT)
    if not 0 < risk_pct <= 100:
        return 0.0
    budget = float(account.balance) * risk_pct / 100.0
    if not math.isfinite(budget) or budget <= 0 or not math.isfinite(float(requested_volume)) or float(requested_volume) <= 0:
        return 0.0
    side = mt5.ORDER_TYPE_BUY if signal == "BUY" else mt5.ORDER_TYPE_SELL
    loss = mt5.order_calc_profit(side, symbol, 1.0, entry, sl)
    if loss is None or not math.isfinite(float(loss)) or float(loss) >= 0:
        return 0.0
    step = float(info.volume_step)
    if not math.isfinite(step) or step <= 0:
        return 0.0
    raw = min(float(requested_volume), budget / abs(float(loss)), float(info.volume_max))
    volume = round(math.floor(raw / step + 1e-10) * step, 8)
    if (volume < 0.01 and getattr(config, "EA2_1_MIN_LOT_FALLBACK", False)
            and float(info.volume_min) <= 0.01 <= float(info.volume_max)
            and math.isclose(0.01 / step, round(0.01 / step), abs_tol=1e-8)):
        return 0.01
    if volume < float(info.volume_min) or volume * abs(float(loss)) > budget + 1e-6:
        return 0.0
    return volume


async def scan_ea2_1(app):
    global _last_log
    if not config.DEMO_PORTFOLIO_ACTIVE.get("EA2_1", False) or not config.auto_active:
        return
    from demo_portfolio import _demo_symbol, _demo_market_open, _place_market_order, _load_state, _save_state
    from trailing import position_sid, position_tf, position_pattern

    account = mt5.account_info()
    if not demo_account_allowed(account):
        raise RuntimeError("EA2.1 requires the configured demo account")
    if config.active_strategies.get(config.EA2_1_SID, False):
        raise RuntimeError("EA2.1 scanner and demo-portfolio routes cannot run together")
    symbol = _demo_symbol()
    if not reconcile_execution(symbol):
        if time.monotonic() - _last_log >= 30:
            log_event("EA2_1_EXECUTION_UNRESOLVED", "send outcome unknown; automatic resend blocked",
                      sid=config.EA2_1_SID, symbol=symbol)
            _last_log = time.monotonic()
        return
    market_open, reason = _demo_market_open(symbol)
    if not market_open:
        return
    bars = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M5, 1, 720)
    htf = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M15, 1, 200)
    signal = detect_ea2_1(bars, tf="M5", mt5=mt5, cfg=config, symbol=symbol,
                          htf_rates=htf, defer_execution=True)
    if time.monotonic() - _last_log >= 30:
        log_event("EA2_1_DEMO_SCAN", signal.get("reason", ""), symbol=symbol,
                  sid=config.EA2_1_SID, signal=signal.get("signal"),
                  risk_percent=config.EA2_1_RISK_PERCENT, login=account.login)
        _last_log = time.monotonic()
    if signal.get("signal") not in ("BUY", "SELL"):
        return
    info = mt5.symbol_info(symbol)
    tick = mt5.symbol_info_tick(symbol)
    if info is None or tick is None:
        return
    entry = float(tick.ask if signal["signal"] == "BUY" else tick.bid)
    # Account for the broker's minimum stop distance before calculating risk.
    minimum = (float(info.trade_stops_level) + 2) * float(info.point)
    distance = max(float(config.EA2_1_SL_POINTS) * float(info.point), minimum)
    sl = entry - distance if signal["signal"] == "BUY" else entry + distance
    tp_distance = float(config.EA2_1_TP_POINTS) * float(info.point)
    tp = entry + tp_distance if signal["signal"] == "BUY" else entry - tp_distance
    volume = risk_volume(signal["signal"], symbol, entry, sl, signal["volume"], account, info)
    if volume <= 0:
        log_event("EA2_1_DEMO_SKIP", "broker lot or risk data cannot satisfy risk budget",
                  sid=config.EA2_1_SID, symbol=symbol)
        return
    nominal_loss = mt5.order_calc_profit(
        mt5.ORDER_TYPE_BUY if signal["signal"] == "BUY" else mt5.ORDER_TYPE_SELL,
        symbol, volume, entry, sl,
    )
    if nominal_loss is not None and abs(float(nominal_loss)) > float(account.balance) * float(config.EA2_1_RISK_PERCENT) / 100.0 + 1e-6:
        log_event("EA2_1_MIN_LOT_FALLBACK", "authorized 0.01 lot exceeds percentage budget",
                  sid=config.EA2_1_SID, symbol=symbol, volume=volume,
                  nominal_sl_loss=abs(float(nominal_loss)), balance=account.balance,
                  actual_risk_percent=abs(float(nominal_loss)) / float(account.balance) * 100.0)
    token = signal["execution_token"]
    mark_execution_attempt(config, symbol, token, volume=volume, broker_time=tick.time)
    try:
        result = _place_market_order(
            signal["signal"], round(sl, info.digits), round(tp, info.digits),
            "M5_EA2.1", config.EA2_1_MAGIC_NUMBER, volume=volume, original_entry=entry,
            max_spread_points=config.EA2_1_MAX_SPREAD_POINTS,
        )
    except Exception:
        acknowledge_execution(config, symbol, token, success=False, uncertain=True)
        raise
    acknowledge_execution(config, symbol, token, success=bool(result.get("success")),
                          uncertain=bool(result.get("uncertain")), ticket=result.get("ticket"))
    if result.get("success"):
        ticket = int(result["ticket"])
        position_sid[ticket] = config.EA2_1_SID
        position_tf[ticket] = "M5"
        position_pattern[ticket] = "EA2_1_M5_M15"
        config.save_runtime_state()
    state = _load_state()
    state["trades"].append({
        "leg": "EA2_1-M5_M15", "ts": config.now_bkk().isoformat(),
        "signal": signal["signal"], "volume": volume, **result,
    })
    _save_state(state)
    log_event("EA2_1_DEMO_ORDER", str(result), sid=config.EA2_1_SID, symbol=symbol,
              volume=volume, risk_percent=config.EA2_1_RISK_PERCENT)
