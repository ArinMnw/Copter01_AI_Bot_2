import math
import logging
from typing import Dict, Any, Tuple
import numpy as np
import config
from ml_scoring import extract_features, predict_success_probability

logger = logging.getLogger("quant_engine")

def calculate_atr(rates, period=14):
    """คำนวณ ATR (Average True Range) ล่าสุด"""
    if len(rates) < period + 1:
        return 0.0
    
    tr_list = []
    for i in range(1, len(rates)):
        high = rates[i]['high']
        low = rates[i]['low']
        prev_close = rates[i-1]['close']
        
        tr1 = high - low
        tr2 = abs(high - prev_close)
        tr3 = abs(low - prev_close)
        
        tr = max(tr1, tr2, tr3)
        tr_list.append(tr)
        
    # Simple Moving Average of TR
    atr = sum(tr_list[-period:]) / period
    return atr

def evaluate_signal(tf_name: str, sid: int, result: Dict[str, Any], rates, current_price: float, time_bkk) -> Dict[str, Any]:
    """
    Central Quant Engine Gatekeeper
    คืนค่า dict ที่มี 'status': 'APPROVED' หรือ 'REJECTED'
    และค่า 'adjusted_sl', 'adjusted_tp', 'adjusted_lot_multiplier' (ถ้ามี)
    """
    if not config.QUANT_ENGINE_ENABLED:
        return {"status": "APPROVED", "reason": "Quant Engine Disabled"}
        
    if sid not in getattr(config, "QUANT_ENGINE_ACTIVE_SIDS", []):
        return {"status": "APPROVED", "reason": f"Quant Engine bypassed for S{sid}"}
        
    signal = result.get("signal")
    if not signal:
        return {"status": "REJECTED", "reason": "No Signal"}
        
    # --- 1. Volatility Gate (กรองความผันผวน) ---
    atr_14 = calculate_atr(rates, period=14)
    if atr_14 > 0:
        # เช็กความผันผวนแท่งล่าสุดเทียบกับ ATR
        current_candle = rates[-1]
        candle_range = current_candle['high'] - current_candle['low']
        
        if candle_range > atr_14 * config.QUANT_VOLATILITY_BLOCK_MULT:
            reason = f"Volatility Spike Detected: Range={candle_range:.2f} > ATR_Threshold={atr_14 * config.QUANT_VOLATILITY_BLOCK_MULT:.2f}"
            logger.info(f"[QUANT REJECT] {tf_name} S{sid} - {reason}")
            return {"status": "REJECTED", "reason": reason}
            
    # --- 2. AI Scoring Gate (ตรวจคะแนน ML) ---
    # เรียกใช้ระบบสกัดฟีเจอร์และทำนายผล
    try:
        features = extract_features(config.SYMBOL, tf_name, signal, current_price, time_bkk)
        ml_score = predict_success_probability(features) * 100.0  # แปลงเป็น %
        
        if ml_score < config.QUANT_MIN_ML_SCORE:
            reason = f"ML Score Too Low: {ml_score:.1f}% < {config.QUANT_MIN_ML_SCORE}%"
            logger.info(f"[QUANT REJECT] {tf_name} S{sid} - {reason}")
            return {"status": "REJECTED", "reason": reason}
            
        logger.info(f"[QUANT INFO] {tf_name} S{sid} - ML Score: {ml_score:.1f}% (Pass)")
        
    except Exception as e:
        logger.error(f"[QUANT ERROR] ML Scoring failed: {e}")
        # กรณี ML พัง ยอมให้ผ่านไปก่อน (Fail-Open)
        ml_score = 50.0 

    # --- 3. Dynamic SL/TP Modification ---
    adjusted_sl = result.get("sl")
    adjusted_tp = result.get("tp")
    adjusted_lot_multiplier = 1.0
    
    if atr_14 > 0 and adjusted_sl is not None and result.get("entry") is not None:
        entry = result.get("entry")
        # คำนวณระยะ SL เดิม
        original_sl_distance = abs(entry - adjusted_sl)
        
        # ถ้าระยะ SL เดิมแคบกว่า ATR * MULT ให้ขยาย SL
        min_sl_distance = atr_14 * config.QUANT_ATR_SL_MULTIPLIER
        
        if original_sl_distance < min_sl_distance:
            if signal == "BUY":
                adjusted_sl = entry - min_sl_distance
            else:
                adjusted_sl = entry + min_sl_distance
                
            logger.info(f"[QUANT MODIFY] {tf_name} S{sid} - Expanded SL from {result.get('sl')} to {adjusted_sl:.5f} (ATR={atr_14:.5f})")
            
            # ขยับ TP ตาม RR เดิม
            if adjusted_tp is not None:
                original_tp_distance = abs(adjusted_tp - entry)
                if original_sl_distance > 0:
                    rr_ratio = original_tp_distance / original_sl_distance
                    if signal == "BUY":
                        adjusted_tp = entry + (min_sl_distance * rr_ratio)
                    else:
                        adjusted_tp = entry - (min_sl_distance * rr_ratio)

    # --- 4. Position Sizing (Lot Multiplier) ---
    # ถ้าคะแนน AI สูงลิ่ว (เช่น > 85%) ให้เบิ้ล Lot 1.5 เท่า
    if ml_score >= 85.0:
        adjusted_lot_multiplier = 1.5
        logger.info(f"[QUANT MODIFY] {tf_name} S{sid} - Aggressive Sizing! ML Score = {ml_score:.1f}% -> Lot x1.5")
    elif ml_score < 60.0:
        # ถ้าคะแนนผ่านเกณฑ์ขั้นต่ำมาแบบเฉียดฉิว (เช่น 50-60%) ลด Lot เหลือ 0.5 เท่า
        adjusted_lot_multiplier = 0.5
        logger.info(f"[QUANT MODIFY] {tf_name} S{sid} - Defensive Sizing. ML Score = {ml_score:.1f}% -> Lot x0.5")

    return {
        "status": "APPROVED",
        "adjusted_sl": adjusted_sl,
        "adjusted_tp": adjusted_tp,
        "adjusted_lot_multiplier": adjusted_lot_multiplier
    }
