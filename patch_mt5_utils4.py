import re

with open('mt5_utils.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Original block:
orig = '''        if getattr(config, "ML_SCORING_ENABLED", False):
            import ml_scoring
            from datetime import datetime, timezone, timedelta
            time_bkk = datetime.now(timezone(timedelta(hours=7)))
            features = ml_scoring.extract_features(SYMBOL, tf, signal, current, time_bkk)
            prob = ml_scoring.predict_success_probability(features)
            
            # If probability is too low (e.g. < 45%), reject the trade
            threshold = getattr(config, "ML_PROB_THRESHOLD", 0.45)
            if prob < threshold:
                observable = getattr(config, "OBSERVABLE_MODE", False)
                from bot_log import log_event
                log_event("ML_FILTER", f"ML Score too low ({prob:.2f} < {threshold}) {'[OBSERVABLE]' if observable else ''}", tf=tf, sid=sid, signal=signal)
                
                if observable:
                    print(f"[{time_bkk.strftime('%H:%M:%S')}] 👀 [OBSERVABLE] ML Score too low ({prob:.2f} < {threshold}). Would have blocked {signal}.")
                else:
                    return {"success": False, "skipped": True, "reason": f"ML Score low ({prob:.2f} < {threshold})"}'''

# Replacement block (indented properly):
new_block = '''        if getattr(config, "ML_SCORING_ENABLED", False):
            try:
                sid_num = int(str(sid).replace("S", ""))
            except:
                sid_num = 0
            
            if sid_num >= 80:
                import ml_scoring
                from datetime import datetime, timezone, timedelta
                time_bkk = datetime.now(timezone(timedelta(hours=7)))
                features = ml_scoring.extract_features(SYMBOL, tf, signal, current, time_bkk)
                prob = ml_scoring.predict_success_probability(features)
                
                # If probability is too low (e.g. < 45%), reject the trade
                threshold = getattr(config, "ML_PROB_THRESHOLD", 0.45)
                if prob < threshold:
                    observable = getattr(config, "OBSERVABLE_MODE", False)
                    from bot_log import log_event
                    log_event("ML_FILTER", f"ML Score too low ({prob:.2f} < {threshold}) {'[OBSERVABLE]' if observable else ''}", tf=tf, sid=sid, signal=signal)
                    
                    if observable:
                        print(f"[{time_bkk.strftime('%H:%M:%S')}] 👀 [OBSERVABLE] ML Score too low ({prob:.2f} < {threshold}). Would have blocked {signal}.")
                    else:
                        return {"success": False, "skipped": True, "reason": f"ML Score low ({prob:.2f} < {threshold})"}'''

content = content.replace(orig, new_block)

with open('mt5_utils.py', 'w', encoding='utf-8') as f:
    f.write(content)
print('mt5_utils.py successfully patched!')
