import numpy as np
from sklearn.ensemble import RandomForestClassifier

def main():
    P_full = np.load('lts_P_matrix.npy')
    num_days, num_legs = P_full.shape
    
    lookback = 14
    train_window = 120 
    test_window = 7    
    
    balance = 1000.0
    start_day = lookback + train_window
    
    R = 0.87 
    
    max_days = num_days - test_window
    total_trades = 0
    winning_trades = 0
    
    for day in range(start_day, max_days, test_window):
        train_start = day - train_window
        train_end = day
        
        X_train = []
        Y_train = []
        
        for t in range(train_start, train_end):
            features = P_full[t-lookback:t, :]
            for leg in range(num_legs):
                X_train.append(features[:, leg])
                Y_train.append(1 if P_full[t, leg] > 0 else 0)
                
        clf = RandomForestClassifier(n_estimators=50, max_depth=3, random_state=42)
        clf.fit(X_train, Y_train)
        
        for t in range(day, day + test_window):
            if t >= num_days:
                break
                
            daily_profit = 0
            features_t = P_full[t-lookback:t, :]
            X_test = features_t.T
            
            p_proba = clf.predict_proba(X_test)
            if p_proba.shape[1] == 1:
                if clf.classes_[0] == 1:
                    probs = p_proba[:, 0]
                else:
                    probs = np.zeros(X_test.shape[0])
            else:
                probs = p_proba[:, 1]
                
            confident_legs = np.where(probs > 0.55)[0] # LOWERED THRESHOLD
            
            if len(confident_legs) > 0:
                for leg in confident_legs:
                    W = probs[leg] 
                    # Fixed compounding for testing
                    multiplier = (balance / 1000.0) * 0.1 
                    
                    raw_pnl = P_full[t, leg]
                    actual_pnl = raw_pnl * multiplier
                    daily_profit += actual_pnl
                    
                    total_trades += 1
                    if raw_pnl > 0:
                        winning_trades += 1
                            
            balance += daily_profit
            
            if balance <= 0:
                print(f"Day {t}: BLOWN UP!")
                return
                
            if balance >= 100000 and balance - daily_profit < 100000:
                print(f"Day {t}: Reached \,000 threshold! Balance = {balance:,.2f}")

    print(f"--- WFO Simulation Complete ---")
    print(f"Final Balance: {balance:,.2f}")
    if total_trades > 0:
        print(f"Out-of-sample Win Rate (ML Filtered): {winning_trades/total_trades*100:.2f}%")
        print(f"Total ML Signals Executed: {total_trades}")

if __name__ == '__main__':
    main()
