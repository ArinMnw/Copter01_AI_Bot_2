# Telegram UI และเมนู

เอกสารนี้สรุปหลักการแก้ไขเมนู, label และ callback ของฝั่ง Telegram

## ไฟล์หลัก

- `handlers/keyboard.py`: ข้อความเมนู, inline keyboard และข้อความสรุป
- `handlers/callback_handler.py`: action ของ callback ต่าง ๆ

## กติกาเวลาแก้ไข

- ให้มอง `handlers/keyboard.py` เป็นไฟล์ที่ text-sensitive
- อย่าเปลี่ยน callback name ถ้ายังไม่ได้แก้ handler logic ให้รองรับด้วย
- ระวัง encoding ของข้อความไทยและ emoji
- ถ้าเป็นงานแก้ text อย่างเดียว อย่าแตะ logic ส่วนอื่นที่ไม่เกี่ยวข้อง

## การตรวจสอบหลังแก้

- รัน `python check_mojibake.py` หลังแก้ text หนัก ๆ
- รัน `python -m py_compile handlers/keyboard.py handlers/callback_handler.py`

## ความเสี่ยงที่พบบ่อย

- ข้อความไทยหรือ emoji เพี้ยนเพราะ encoding
- เปลี่ยน label แล้วลืมอัปเดต callback ให้สอดคล้อง
- ข้อความเมนูกับ config state แสดงผลไม่ตรงกัน

## Convention เรื่อง Toggle Icon

- ฟังก์ชันที่เปิด/ปิดได้ ให้ใช้ icon `🟢ON` สำหรับเปิด และ `🔴OFF` สำหรับปิด
- ถ้าสถานะเป็น OFF ห้ามต่อ `|` แล้วใส่รายละเอียดต่อท้าย ให้แสดงแค่ `🔴OFF`
- ถ้าเป็น ON และมีรายละเอียดเสริม ใช้รูปแบบ `🟢ON | รายละเอียด`
- ปุ่มในเมนูและ status text ในเมนูเดียวกันต้องใช้ suffix เดียวกัน

## โครงสร้าง Master Toggle

ฟังก์ชันที่มี submenu (Trail SL, Entry Candle Mode, Opposite Order):

- ปุ่ม master toggle อยู่ **ด้านในสุด** ของ submenu ตัวเอง (ไม่ใช่หน้าหลัก)
- Label ใช้รูปแบบ `🟢 เปิดใช้งาน <ชื่อ>` เมื่อ ON, `🔴 ปิดใช้งาน <ชื่อ>` เมื่อ OFF
- callback ของ master toggle ใช้ pattern `toggle_<name>_enabled`
- ฟังก์ชันจริงใน `trailing.py` ใช้ `getattr(config, "<FLAG>", True)` gate เพื่อ early-return ถ้า OFF

ฟังก์ชันที่ toggle ตรง (Entry Candle TP, Limit Sweep, Delay SL):

- toggle ที่หน้าหลักเลย ไม่มี submenu แยก
- Delay SL มี 3 mode: `off` → `🔴OFF`, `time` → `🟢ON | ช่วงท้าย TF`, `price` → `🟢ON | ราคาผ่าน Entry`

## Toggle ของแต่ละท่า

### ท่าที่ 9 — RSI Divergence

- รวมจาก 4 ปุ่ม (Bull/Bear × Regular/Hidden) เหลือ 2 ปุ่ม:
  - **Regular** → toggle ทั้ง `RSI9_PLOT_BULLISH` + `RSI9_PLOT_BEARISH`
  - **Hidden** → toggle ทั้ง `RSI9_PLOT_HIDDEN_BULLISH` + `RSI9_PLOT_HIDDEN_BEARISH`
- callback: `toggle_rsi9_regular`, `toggle_rsi9_hidden`
- default: Regular ON, Hidden OFF

### ท่าที่ 10 — CRT TBS

- 2 sub-toggle:
  - **Bar mode** (`CRT_BAR_MODE`): `2bar` / `3bar`
  - **Entry mode** (`CRT_ENTRY_MODE`): `htf` / `mtf`
- callback: `set_crt_bar_mode_<mode>`, `set_crt_entry_mode_<mode>`
- default: `2bar` + `mtf`
- master toggle ของ S10 อยู่ในหน้า strategy ปกติ

### Trend Filter

- **Mode** (`trend_filter_mode`): `basic` / `breakout`
- callback: `set_trend_filter_mode_<mode>`
- default: `basic`
- มี per-TF toggle และ Trail SL Override toggle แยก

### Sideway HHLL Filter

อยู่ใน Trend Filter menu section `━ Sideway Filter ━`

ปุ่ม: `🟢 Sideway HHLL Filter: ON` / `🔴 Sideway HHLL Filter: OFF`

callback: `toggle_sideway_hhll_filter`

config: `TREND_FILTER_SIDEWAY_HHLL` (default `True`)

logic (ตั้งแต่ 2026-05-22) — เมื่อ trend = SIDEWAY ดู `last_label`:
- `HH` หรือ `HL` → block SELL (bullish momentum ล่าสุด)
- `LH` หรือ `LL` → block BUY (bearish momentum ล่าสุด)

## Profit summary (หน้าหลัก)

- แสดง BUY / SELL breakdown ต่อ strategy
- กดปุ่ม trend filter เพื่อ filter สรุปกำไรตาม trend ตอนเปิดออเดอร์
- callback parsing: ใช้ `"_".join(parts[5:])` สำหรับ key ที่มี underscore เช่น `bull_strong`

## Toggle จุดกลับตัว -> Trail SL

- `↩️ จุดกลับตัว -> Trail SL`
- เป็น toggle แยกที่อยู่หน้า settings ชั้นนอกสุด ไม่รวมอยู่ใน submenu อื่น
- callback: `toggle_trail_reversal_override`
- ใช้ config `TRAIL_SL_REVERSAL_OVERRIDE_ENABLED`

## Toggle Scale-Out 3X (Triple Scale-Out)

- ปุ่ม: `📈 Scale-Out 3X: 🟢ON` / `🔴OFF`
- อยู่หน้า settings ชั้นนอกสุด ใต้ปุ่ม `📦 Lot Size Auto`
- callback: `toggle_scale_out`
- ใช้ config `SCALE_OUT_ENABLED` (default `True`)
- Always-4-steps formula (ตั้งแต่ 2026-05-22):
  - **volume รวมเสมอ = base × 4** (XAU 0.04, BTC 0.16)
  - General: `[min(200,TP), min(300,TP), min(600,TP), TP]`
  - S10: `[min(200,TP), min(300,TP), TP/2, TP]`
  - S13: สร้าง 4 orders แยก ใช้ general formula
- เมื่อกดปิด (ON→OFF) จะเรียก `scale_out_cleanup_on_disable()` ใน `trailing.py` ทันที:
  - position TSO ที่ fill แล้ว → ปิดทั้งหมด
  - pending TSO → cancel + สร้างใหม่ด้วย lot เดิม
  - callback notification แสดงสรุป `closed: N` / `reset_pending: M`
  - **S13 orders ไม่ถูกแตะ** (ไม่ได้ register ใน `scale_out_state`)

## SL Guard Toggle

อยู่ใน Trend Filter menu ต่อท้าย section "Premium/Discount Zone"

section header: `━ SL Guard ━`

ปุ่ม:
- toggle ON/OFF: `🟢 SL Guard: ON (Nx SL → block, Ypt)` / `🔴 SL Guard: OFF`
- count options: `1x SL`, `2x SL`, `3x SL`
- near points: `100pt`, `200pt`, `300pt`, `500pt`

callback: `toggle_sl_guard`, `set_sl_guard_count_N`, `set_sl_guard_pts_N`

config:
- `SL_GUARD_ENABLED` (default `True`)
- `SL_GUARD_COUNT` (default `2`)
- `SL_GUARD_NEAR_POINTS` (default `200`)

## Loss Guard Toggle (SL Guard Loss)

อยู่ใน Trend Filter menu ต่อท้าย SL Guard (ไม่มี section header แยก)

ปุ่ม:
- toggle ON/OFF: `🟢 Loss Guard: ON (>$N)` / `🔴 Loss Guard: OFF`
- threshold options: `$3`, `$5`, `$10`, `$20`

callback: `toggle_sl_guard_loss`, `set_sl_guard_loss_thr_N`

config:
- `SL_GUARD_LOSS_ENABLED` (default `True`)
- `SL_GUARD_LOSS_THRESHOLD` (default `5.0`)

พฤติกรรม: ถ้า position ปิดด้วยขาดทุน > threshold → นับเป็น SL hit ใน guard count ของ TF นั้น (ทำงานร่วมกับ `SL_GUARD_ENABLED`)

## PD Zone Recheck Toggle

อยู่ใน Trend Filter menu ต่อท้าย section "Pending RSI Recheck"

section header: `━ Premium/Discount Zone ━`

ปุ่ม toggle:
- ON: `🟢 PD Zone Recheck: ON`
- OFF: `🔴 PD Zone Recheck: OFF`

- callback: `toggle_pd_zone_check`
- config: `PD_ZONE_CHECK_ENABLED` (persist ใน `bot_state.json` key `pd_zone_check_enabled`)
- handler: ใน `handlers/callback_handler.py` → toggle `config.PD_ZONE_CHECK_ENABLED`, save, refresh menu

**พฤติกรรมเมื่อ ON:**
- เปิด `_pd_zone_process()` ใน `trailing.py`
- ตรวจ 3 รอบ 2/3 ว่า entry อยู่ใน Premium หรือ Discount zone
- ส่ง Telegram แจ้งทุกรอบ

## Triple Recheck

ไม่มีปุ่ม toggle แยกสำหรับ Triple Recheck — เปิดอัตโนมัติเมื่อ:

- `PD_ZONE_CHECK_ENABLED = True`
- `LIMIT_TREND_RECHECK = True`
- `PENDING_RSI_RECHECK_ENABLED = True`

ทั้งสามเปิดพร้อมกัน

**พฤติกรรม:**
- แต่ละ recheck จะไม่ตัดสินทันที แต่ record ผลใน `_triple_check_state`
- เมื่อได้ผลครบ 2/3: fails ≥ 2 → cancel/close, passes ≥ 2 → keep
- Telegram แจ้งสรุป `RSI ✅/❌ | Trend ✅/❌ | PD ✅/❌` เมื่อตัดสินแล้ว

## Markdown Safety ใน ticket lookup

- helper `_md_escape(s)` ใน `handlers/text_handler.py` — escape `\`, `` ` ``, `*`, `_`, `[`, `]`
- `_safe_reply_md(message, text, **kwargs)` — ลอง `parse_mode="Markdown"` ก่อน
  - ถ้า `BadRequest` (`can't parse entities`) → **fallback เป็น plain text**
- ใช้ใน `_handle_ticket_lookup` เพื่อกัน silent fail เมื่อ comment/pattern มีตัวอักษรพิเศษ
