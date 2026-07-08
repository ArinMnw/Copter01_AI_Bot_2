import numpy as np
from scipy.optimize import linprog

def main():
    P_full = np.load('lts_P_matrix.npy')
    num_days, num_legs = P_full.shape
    
    train_window = 60
    test_window = 7
    start_day = 0
    
    for step in range(10):
        train_start = start_day
        train_end = train_start + train_window
        test_start = train_end
        test_end = test_start + test_window
        
        P_train = P_full[train_start:train_end, :]
        P_test = P_full[test_start:test_end, :]
        
        c = -np.sum(P_train, axis=0) / train_window
        A_ub = -P_train
        b_ub = np.ones(train_window) * 500
        bounds = [(0, 100.0) for _ in range(num_legs)]
        
        res = linprog(c, A_ub=A_ub, b_ub=b_ub, bounds=bounds, method='highs')
        if not res.success:
            start_day += test_window
            continue
            
        w_opt = res.x
        test_pnl = P_test @ w_opt
        profit = test_pnl.sum()
        worst = test_pnl.min()
        print(f"Window {step+1}: Profit = {profit:.2f}, Worst = {worst:.2f}")
        start_day += test_window

if __name__ == '__main__':
    main()
