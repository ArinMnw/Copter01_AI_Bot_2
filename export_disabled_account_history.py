"""
Export ประวัติเทรดทั้งหมด (all-time) ของบัญชีที่ (Disabled) ออกมาเก็บเป็นไฟล์ local
เผื่อโดนปิดบัญชีจริงจาก broker ในอนาคต — ตอนนั้นจะ login ผ่าน MT5 API ไม่ได้อีกเลย
มีแต่ไฟล์ archive นี้เท่านั้นที่เหลือให้ดูข้อมูลย้อนหลัง

รันตรงๆ: python export_disabled_account_history.py
ผลลัพธ์: history_archive/<account_key>.json (deals/orders/open positions/pending orders ทั้งหมด)
"""
import os
import sys
import json
import time
from datetime import datetime, timedelta

import MetaTrader5 as mt5

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
ARCHIVE_DIR = os.path.join(ROOT_DIR, "history_archive")

# บัญชีที่ (Disabled) ตอนนี้ — ดู ACCOUNT_LABELS ใน dashboard.py
DISABLED_ACCOUNTS = {
    "demo-iux-2101183586": os.path.join(ROOT_DIR, "profiles", "demo", "demo-iux-2101183586", "mt5", "terminal64.exe"),
    "demo-vantage-26253671": os.path.join(ROOT_DIR, "profiles", "demo", "demo-vantage-26253671", "mt5", "terminal64.exe"),
}


def _row_to_dict(row):
    d = row._asdict()
    return d


def export_account(acc_key, mt5_path, connect_retries=5, sync_wait_rounds=6):
    print(f"\n===== {acc_key} =====")
    if not os.path.exists(mt5_path):
        print(f"  mt5 path ไม่พบ: {mt5_path}")
        return False

    ok = False
    for attempt in range(1, connect_retries + 1):
        ok = mt5.initialize(path=mt5_path, timeout=120000)
        if ok:
            break
        print(f"  เชื่อมต่อครั้งที่ {attempt} ไม่สำเร็จ: {mt5.last_error()} — รออีกสักครู่แล้วลองใหม่")
        time.sleep(5)
    if not ok:
        print(f"  เชื่อมต่อ MT5 ไม่สำเร็จหลังลอง {connect_retries} ครั้ง: {mt5.last_error()}")
        return False

    ai = mt5.account_info()
    account_info = _row_to_dict(ai) if ai else {}
    print(f"  connected login={account_info.get('login')} balance={account_info.get('balance')} server={account_info.get('server')}")

    end = datetime.now()
    start = end - timedelta(days=3650)

    # MT5 terminal ที่เพิ่งเชื่อมต่อ/เปิดใหม่ อาจยัง sync ประวัติจากฝั่ง broker ไม่ครบ —
    # ดึงซ้ำจนกว่าจำนวน deals จะนิ่ง (เท่ากัน 2 รอบติดกัน) ก่อนค่อยเชื่อว่าครบจริง
    deals, orders_hist = [], []
    prev_counts = (None, None)
    for round_i in range(1, sync_wait_rounds + 1):
        deals = mt5.history_deals_get(start, end) or []
        orders_hist = mt5.history_orders_get(start, end) or []
        counts = (len(deals), len(orders_hist))
        print(f"  sync round {round_i}: deals={counts[0]} history_orders={counts[1]}")
        if counts == prev_counts:
            break
        prev_counts = counts
        time.sleep(8)

    open_positions = mt5.positions_get() or []
    pending_orders = mt5.orders_get() or []

    payload = {
        "account_key": acc_key,
        "exported_at": datetime.now().isoformat(),
        "export_range_days": 3650,
        "account_info": account_info,
        "deals": [_row_to_dict(d) for d in deals],
        "history_orders": [_row_to_dict(o) for o in orders_hist],
        "open_positions": [_row_to_dict(p) for p in open_positions],
        "pending_orders": [_row_to_dict(o) for o in pending_orders],
    }

    os.makedirs(ARCHIVE_DIR, exist_ok=True)
    out_path = os.path.join(ARCHIVE_DIR, f"{acc_key}.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2, default=str)

    print(f"  deals={len(deals)} history_orders={len(orders_hist)} open_positions={len(open_positions)} pending_orders={len(pending_orders)}")
    print(f"  บันทึกแล้ว: {out_path}")

    mt5.shutdown()
    return True


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    results = {}
    for acc_key, mt5_path in DISABLED_ACCOUNTS.items():
        results[acc_key] = export_account(acc_key, mt5_path)

    print("\n===== สรุป =====")
    for acc_key, ok in results.items():
        print(f"  {acc_key}: {'สำเร็จ' if ok else 'ล้มเหลว'}")
