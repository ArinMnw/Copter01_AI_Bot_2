import re

with open('mt5_utils.py', 'r', encoding='utf-8') as f:
    content = f.read()

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
                
                # Dynamic Lot Sizing based on ML Prob and ATR
                atr_val = features[1] if isinstance(features, (list, tuple)) and len(features) > 1 else 20.0
                if isinstance(features, dict):
                    atr_val = features.get('atr', 20.0)
                
                # If high prob (>0.75), increase lot. If high ATR (> 35, high risk), reduce lot.
                if getattr(config, "ML_LOT_SCALING_ENABLED", True):
                    mult = 1.0
                    if prob >= 0.75:
                        mult *= 1.5
                    elif prob < 0.50:
                        mult *= 0.5
                    
                    if atr_val > 35:
                        mult *= 0.7
                    elif atr_val < 15:
                        mult *= 1.2
                        
                    if mult != 1.0:
                        volume = volume * mult
                        info = mt5.symbol_info(SYMBOL)
                        if info:
                            v_step = info.volume_step
                            volume = round(volume / v_step) * v_step
                            volume = max(info.volume_min, min(volume, info.volume_max))
                        print(f"[{time_bkk.strftime('%H:%M:%S')}] ⚖️ [Dynamic Lot] Adjusted volume to {volume} (Prob: {prob:.2f}, ATR: {atr_val:.1f}, Mult: {mult:.2f})")
                
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
print('mt5_utils.py patched with ML filter AND Dynamic Lot Sizing!')
