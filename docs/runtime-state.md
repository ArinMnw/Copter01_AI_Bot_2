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
- `_entry_state`: state ของ entry candle แยกตาม ticket
- `_s6_state`: state ของท่า 6
- `_s6i_state`: state ของ S6i
- `_armed_states` (`strategy10.py`): per-HTF armed state ของท่า 10 MTF mode — เก็บ `direction, sl_target, tp_target, armed_at, htf_tf, ltf_tf, candles, pattern_base`
- `_s11_state` (`strategy11.py`): per-TF anchor + phase ของท่า 11 (ไม่ persist)

## การบันทึก state

- runtime state จะถูกบันทึกลง `bot_state.json`
- helper สำหรับ save/restore อยู่ใน `config.py`
- ถ้ามีการเปลี่ยนโครงสร้าง state ต้องเช็กเสมอว่า save และ restore ยังสอดคล้องกัน

## หลักการใช้งาน

- ถ้าบั๊กเกี่ยวกับ TF ผิด, strategy id ผิด, pattern ผิด, หรืออาการหลัง restart ให้ไล่ดู map พวกนี้ก่อนเป็นลำดับแรก

## Master Toggle Flags ที่ persist

เก็บใน `bot_state.json` ผ่าน `save_runtime_state()` / `restore_runtime_state()`:

- `TRAIL_SL_ENABLED`: gate `check_engulf_trail_sl()`
- `ENTRY_CANDLE_ENABLED`: gate `check_entry_candle_quality()`
- `OPPOSITE_ORDER_ENABLED`: gate `check_opposite_order_tp()`
- `ENTRY_CANDLE_UPDATE_TP`: toggle ตรงจากหน้าหลัก
- `LIMIT_SWEEP`: toggle ตรงจากหน้าหลัก
- `DELAY_SL_MODE`: `off` / `time` / `price`

State อื่น ๆ ที่ persist:

- `s10_armed_states`: snapshot ของ `_armed_states` ใน `strategy10.py` (in-place restore)

## BTC Lot / Points Scaling

- helper `points_scale()` ใน `config.py` คืน `4.0` สำหรับ `BTCUSD.iux` ส่วน symbol อื่น = `1.0`
- ใช้ scale lot (`get_volume()`) และระยะ point ทุกจุด (engulf min, CRT min/buffer, trailing offsets)
- Telegram UI ยังเห็นค่า config ของ XAUUSD เป็น base — scaling ทำหลังบ้านเท่านั้น
