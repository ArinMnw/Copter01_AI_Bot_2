import MetaTrader5 as mt5
from datetime import datetime, timedelta, timezone
import csv

BKK = timezone(timedelta(hours=7))

def export_history():
    if not mt5.initialize():
        print("MT5 Init failed:", mt5.last_error())
        return

    # From midnight BKK today
    now_bkk = datetime.now(BKK)
    start_dt = now_bkk.replace(hour=0, minute=0, second=0, microsecond=0)
    end_dt = now_bkk + timedelta(days=1)
    
    print(f"Fetching history from {start_dt.strftime('%Y-%m-%d %H:%M:%S')} to {end_dt.strftime('%Y-%m-%d %H:%M:%S')} BKK")

    deals = mt5.history_deals_get(start_dt, end_dt)
    if deals is None:
        print("No deals found or error:", mt5.last_error())
        mt5.shutdown()
        return

    csv_file = "mt5_actual_history_s20_8.csv"
    count = 0
    with open(csv_file, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["Ticket", "Order", "Time (BKK)", "Type", "Entry", "Volume", "Price", "Commission", "Swap", "Profit", "Symbol", "Comment"])
        
        for deal in deals:
            # กรองเฉพาะ S20.8
            if "S20.8" not in str(deal.comment):
                continue
                
            count += 1
            # deal.time เป็น timestamp ของเวลาฝั่ง Server (UTC+6)
            # เราแปลงเป็น datetime ก่อน (ถือเป็น UTC ชั่วคราว) แล้วค่อยบวก 1 ชั่วโมงให้เป็น BKK (UTC+7)
            dt_server = datetime.fromtimestamp(deal.time, tz=timezone.utc).replace(tzinfo=None)
            dt_bkk = dt_server + timedelta(hours=1)
            
            type_str = "Buy" if deal.type == 0 else "Sell" if deal.type == 1 else "Balance" if deal.type == 2 else str(deal.type)
            entry_str = "In" if deal.entry == 0 else "Out" if deal.entry == 1 else str(deal.entry)
            
            writer.writerow([
                deal.ticket,
                deal.order,
                dt_bkk.strftime("%Y-%m-%d %H:%M:%S"),
                type_str,
                entry_str,
                deal.volume,
                deal.price,
                deal.commission,
                deal.swap,
                deal.profit,
                deal.symbol,
                deal.comment
            ])
            
    print(f"Exported {count} deals (Filtered for S20.8) to {csv_file}")
    mt5.shutdown()

if __name__ == "__main__":
    export_history()
