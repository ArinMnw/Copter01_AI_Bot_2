import numpy as np

def main():
    P_full = np.load('lts_P_matrix.npy')
    num_days, num_legs = P_full.shape
    
    lookback = 3
    balance = 1000.0
    
    for day in range(lookback, num_days):
        recent_pnl = P_full[day-lookback:day, :]
        win_rate = (recent_pnl > 0).sum(axis=0) / lookback
        
        active_legs = win_rate >= 0.66
        if active_legs.sum() == 0:
            continue
            
        daily_raw_pnl = P_full[day, active_legs].sum()
        
        # multiplier = base leverage factor
        # If we just scale position size linearly with balance, we get compounding.
        multiplier = (balance / 1000.0) * 0.1 # Very aggressive
        
        actual_pnl = daily_raw_pnl * multiplier
        balance += actual_pnl
        
        if balance <= 100:
            print(f"Day {day}: BLOWN UP! Balance = {balance:.2f}")
            break
            
        if balance >= 100000:
            print(f"Day {day}: REACHED TARGET! Balance = {balance:,.2f}")
            break

    print(f"Final Balance after {day} days: {balance:,.2f}")

if __name__ == '__main__':
    main()
