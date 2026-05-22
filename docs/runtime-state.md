# สถานะระหว่างรัน

เอกสารนี้สรุป state ที่ระบบใช้บ่อยระหว่างการทำงานของบอท

## ไฟล์หลักที่เก็บ state

- `config.py`: เก็บค่าตั้งต้น, helper สำหรับ save/restore และ state ที่ต้อง persist
- `trailing.py`: เก็บ state ที่เกี่ยวกับ position, pending, trail และ flow หลังบ้านเป็นหลัก

## ตัวแปร map ที่ใช้บ่อย

- `pending_order_tf`: metadata ของ pending order แยกตาม ticket
- `position_tf`: timeframe ของ position แยกตาม ticket
- `position_sid`: strategy id ของ position แยกตาม ticket
- `position_pattern`: ชื่อ pattern ของ position แยกตาม ticket
- `position_zone_meta`: metadata ของ zone ที่ติดมากับ position (ใช้กับ `S1 zone`)
- `_entry_state`: state ของ entry candle แยกตาม ticket
- `_s6_state`: state ของท่า 6
- `_s6i_state`: state ของ S6i
- `_armed_states` (`strategy10.py`): per-HTF armed state ของท่า 10 MTF mode — เก็บ `direction, sl_target, tp_target, armed_at, htf_tf, ltf_tf, candles, pattern_base`
- `_s11_state` (`strategy11.py`): per-TF anchor + phase ของท่า 11 (ไม่ persist)
- `scale_out_state` (`config.py`): per-ticket state ของ Triple Scale-Out — เก็บ `direction, entry, original_volume, base_volume, per_tp_volume, tp_distances (always 4 steps), step, is_pending, sid, tp_original`
  - `tp_distances` คำนวณ runtime ผ่าน `compute_tso_effective_steps(tp_orig_dist, sid)` — เสมอ 4 steps
  - General formula: `[min(200pt,TP), min(300pt,TP), min(600pt,TP), TP]`
  - S10 formula: `[min(200pt,TP), min(300pt,TP), TP/2, TP]`
  - `step` ขึ้นถึง `3` (4 steps ทุกกรณี)
- `_pd_zone_state` (`trailing.py`): per-ticket state ของ PD Zone Recheck — เก็บรอบการเช็ค (round 1-3), ผลแต่ละรอบ, TF, signal; ไม่ persist ข้าม restart
- `_triple_check_state` (`trailing.py`): per-ticket state ของ Triple Recheck — เก็บ `{rsi: None|True|False, trend: None|True|False, pd: None|True|False, tf, signal}`; ไม่ persist ข้าม restart

## S12 State

### `_s12_state` (`strategy12.py`)

state หลักของท่า 12:

- `last_sl_time: float` — timestamp ที่ SL hit ล่าสุด (ตั้งโดย `s12_cleanup_tickets()`)
- เมื่อ `last_sl_time > 0` และเวลาผ่านไปน้อยกว่า 1800 วินาที → S12 อยู่ใน cooldown
- cooldown ป้องกันไม่ให้ S12 เข้า order ใหม่ทันทีหลัง SL

### `_s12_scan_status` (`scanner.py`)

dict ที่สรุปสถานะ S12 รอบปัจจุบัน — อัปเดตโดย `scan_s12()` ทุก cycle:

**ปกติ (มี zone):**
```python
{
    "side": "BUY" | "SELL" | "—",
    "count": int,
    "zone": "BUY zone" | "SELL zone" | "—",
    "buy_zone_top": float,
    "sell_zone_bot": float,
    "swing_low": float,
    "swing_high": float,
}
```

**ระหว่าง cooldown:**
```python
{"cooldown": "⏳ S12 cooldown N นาที (หลัง SL)"}
```

**พฤติกรรมใน SCAN_SUMMARY:**
- ปกติ: แสดง zone และ side
- cooldown: **ไม่แสดง** S12 block เลย (ป้องกัน body ค้างจากค่า 0.00)
- condition: `if _s12_scan_status and active_strategies.get(12) and not _s12_scan_status.get("cooldown")`

**หมายเหตุ timing:** `scan_s12()` รันหลัง SCAN_SUMMARY ใน `auto_scan` → `_s12_scan_status` ที่แสดงใน SCAN_SUMMARY เป็นของ cycle ก่อนหน้า 1 cycle เสมอ

## การบันทึก state

- runtime state จะถูกบันทึกลง `bot_state.json`
- helper สำหรับ save/restore อยู่ใน `config.py`
- ถ้ามีการเปลี่ยนโครงสร้าง state ต้องเช็กเสมอว่า save และ restore ยังสอดคล้องกัน
- `position_zone_meta` ถูก persist ผ่าน `save_runtime_state()` / `restore_runtime_state()` แล้ว

## หลักการใช้งาน

- ถ้าบั๊กเกี่ยวกับ TF ผิด, strategy id ผิด, pattern ผิด, หรืออาการหลัง restart ให้ไล่ดู map พวกนี้ก่อนเป็นลำดับแรก

## Master Toggle Flags ที่ persist

เก็บใน `bot_state.json` ผ่าน `save_runtime_state()` / `restore_runtime_state()`:

- `TRAIL_SL_ENABLED`: gate `check_engulf_trail_sl()`
- `ENTRY_CANDLE_ENABLED`: gate `check_entry_candle_quality()`
- `TRAIL_SL_REVERSAL_OVERRIDE_ENABLED`: toggle สำหรับยอมให้ Trail SL bypass `Focus Opposite` เมื่อเจอ reversal candle ฝั่งตรงข้าม
- `OPPOSITE_ORDER_ENABLED`: gate `check_opposite_order_tp()`
- `ENTRY_CANDLE_UPDATE_TP`: toggle ตรงจากหน้าหลัก
- `LIMIT_SWEEP`: toggle ตรงจากหน้าหลัก
- `DELAY_SL_MODE`: `off` / `time` / `price`
- `SCALE_OUT_ENABLED`: gate ของ Triple Scale-Out (default `True`)
- `PD_ZONE_CHECK_ENABLED`: gate ของ PD Zone Recheck (default `True`), persist ด้วย key `pd_zone_check_enabled`
- `SL_GUARD_LOSS_ENABLED`: gate ของ SL Guard Loss (default `True`), persist ด้วย key `sl_guard_loss_enabled`
- `SL_GUARD_LOSS_THRESHOLD`: threshold ขาดทุนที่นับเป็น SL hit (default `5.0`), persist ด้วย key `sl_guard_loss_threshold`

State อื่น ๆ ที่ persist:

- `s10_armed_states`: snapshot ของ `_armed_states` ใน `strategy10.py` (in-place restore)
  - field ใหม่ (2026-05-18): `pre_arm`, `fired_tickets`, `awaiting_choch`, `fire_count`
  - ใช้สำหรับ continuous re-trigger flow + CHoCH gate
- `scale_out_state`: snapshot ของ TSO state - restore เฉพาะ ticket ที่ยังมีจริงใน MT5

## BTC Lot / Points Scaling

- helper `points_scale()` ใน `config.py` คืน `4.0` สำหรับ `BTCUSD.iux` ส่วน symbol อื่น = `1.0`
- ใช้ scale lot (`get_volume()`) และระยะ point ทุกจุด (engulf min, CRT min/buffer, trailing offsets)
- Telegram UI ยังเห็นค่า config ของ XAUUSD เป็น base — scaling ทำหลังบ้านเท่านั้น
