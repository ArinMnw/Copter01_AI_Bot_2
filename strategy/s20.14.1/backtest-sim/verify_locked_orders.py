import pandas as pd
import sys

def verify_locked_orders():
    print('=============================================')
    print('[SEARCH] VERIFYING LOCKED ORDERS (Regression Test)')
    print('=============================================')
    
    # 1. Load Master CSV (Truth)
    try:
        master_df = pd.read_csv('../../../docs/allin4s/Full Trading/master_36_orders_v32.csv')
    except Exception as e:
        print(f'Error reading master CSV: {e}')
        return
        
    # 2. Filter only Done/Locked orders
    done_orders = master_df[master_df["Reviewed"].astype(str).str.strip() == 'Done']
    if len(done_orders) == 0:
        print('No locked orders found to verify.')
        return
        
    print(f'Found {len(done_orders)} locked orders to verify: {done_orders["Order"].tolist()}\n')
    
    # 3. Load latest Simulation output (trades.csv)
    try:
        trades_df = pd.read_csv('../excel/trades.csv')
    except Exception as e:
        print(f'Error reading trades.csv. Did you run v38?: {e}')
        return

    errors = 0
    # 4. Verify each locked order
    for idx, row in done_orders.iterrows():
        order_num = row['Order']
        expected_entry = round(float(row['Bot_Entry']), 2)
        expected_sl = round(float(row['Bot_SL']), 2)
        expected_tp = round(float(row['Bot_TP']), 2)
        expected_time = str(row['Bot_Time']).strip()
        expected_pat = str(row['Bot_Pattern']).strip()
        
        # Find matching order in trades.csv by Entry price (since time might be fill time vs pattern time)
        match = trades_df[
            (round(trades_df['Entry'], 2) == expected_entry)
        ]
        
        if len(match) == 0:
            print(f'[FAIL] ORDER {order_num} BROKEN! Could not find trade at {expected_time} with Entry {expected_entry}')
            errors += 1
            continue
            
        trade = match.iloc[0]
        actual_sl = round(float(trade['SL']), 2)
        actual_tp = round(float(trade['TP']), 2)
        
        broken = False
        if actual_sl != expected_sl:
            print(f'[FAIL] ORDER {order_num} BROKEN! SL changed from {expected_sl} to {actual_sl}')
            broken = True
        if actual_tp != expected_tp:
            print(f'[FAIL] ORDER {order_num} BROKEN! TP changed from {expected_tp} to {actual_tp}')
            broken = True
        
        if broken:
            errors += 1
        else:
            print(f'[PASS] Order {order_num} ({expected_pat}): OK')

    print('\n=============================================')
    if errors == 0:
        print(f'[SUCCESS] ALL {len(done_orders)} LOCKED ORDERS PASSED!')
    else:
        print(f'[WARNING] {errors} LOCKED ORDERS FAILED REGRESSION TEST!')
    print('=============================================')

if __name__ == "__main__":
    verify_locked_orders()
