import sys
import os
from datetime import datetime, timedelta, timezone
import csv

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
STRATEGY_DIR = os.path.dirname(SCRIPT_DIR)
EXCEL_DIR = os.path.join(STRATEGY_DIR, "excel")

# ต้องขึ้นไป 3 ชั้นถึง project root เพื่อ import config ได้ (pattern เดียวกับ s20.6/s20.12)
sys.path.append(os.path.abspath(os.path.join(SCRIPT_DIR, "..", "..", "..")))
import MetaTrader5 as mt5
import config

BKK = timezone(timedelta(hours=7))


def export_history():
    if not config.mt5_initialize(mt5):
        print("MT5 Init failed:", mt5.last_error())
        return

    resolved_symbol = config.SYMBOL

    # From midnight BKK today — บวก padding กว้างๆ กันเคส MT5 server tz ดันช่วงเวลาออกนอกขอบ
    now_bkk = datetime.now(BKK)
    start_dt = now_bkk.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(hours=6)
    end_dt = now_bkk + timedelta(days=1) + timedelta(hours=6)

    print(f"Fetching history from {start_dt.strftime('%Y-%m-%d %H:%M:%S')} to {end_dt.strftime('%Y-%m-%d %H:%M:%S')} BKK")

    deals = mt5.history_deals_get(start_dt, end_dt)
    if deals is None:
        print("No deals found or error:", mt5.last_error())
        mt5.shutdown()
        return

    os.makedirs(EXCEL_DIR, exist_ok=True)
    csv_file = os.path.join(EXCEL_DIR, "mt5_actual_history_s20_8.csv")

    rows = []
    for deal in deals:
        # กรองเฉพาะ S20.8 + symbol ของ profile ปัจจุบัน
        if deal.symbol != resolved_symbol:
            continue
        if "S20.8" not in str(deal.comment):
            continue

        dt_bkk = config.mt5_ts_to_bkk(deal.time)
        type_str = "Buy" if deal.type == 0 else "Sell" if deal.type == 1 else "Balance" if deal.type == 2 else str(deal.type)
        entry_str = "In" if deal.entry == 0 else "Out" if deal.entry == 1 else str(deal.entry)

        rows.append({
            "Ticket": deal.ticket,
            "Order": deal.order,
            "Time (BKK)": dt_bkk,
            "Type": type_str,
            "Entry": entry_str,
            "Volume": deal.volume,
            "Price": deal.price,
            "Commission": deal.commission,
            "Swap": deal.swap,
            "Profit": deal.profit,
            "Symbol": deal.symbol,
            "Comment": deal.comment,
        })

    rows.sort(key=lambda r: r["Time (BKK)"])

    with open(csv_file, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["Ticket", "Order", "Time (BKK)", "Type", "Entry", "Volume", "Price", "Commission", "Swap", "Profit", "Symbol", "Comment"])
        for r in rows:
            writer.writerow([
                r["Ticket"], r["Order"], r["Time (BKK)"].strftime("%Y-%m-%d %H:%M:%S"),
                r["Type"], r["Entry"], r["Volume"], r["Price"], r["Commission"],
                r["Swap"], r["Profit"], r["Symbol"], r["Comment"],
            ])

    print(f"Exported {len(rows)} deals (Filtered for S20.8) to {csv_file}")
    mt5.shutdown()


if __name__ == "__main__":
    export_history()
