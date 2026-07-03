# Commands & Tips Guide (คู่มือคำสั่งและคำแนะนำการใช้งานบอท)

เอกสารรวบรวมคำสั่งสคริปต์การรัน Backtest, คิวรี่ราคา, และเคล็ดลับการใช้งานระบบสำหรับผู้ดูแลระบบค่ะ

## Backtest Skill / Checklist

- Checklist งาน backtest ราย strategy และ compare auto trade อยู่ที่ `docs/backtest_strategy_skill.md`
- แนวทางปัจจุบัน: ทำ backtest ราย strategy ใน scope **S1-S14** ให้ครบก่อน แล้วค่อยกลับมา compare auto trade รวมทั้งระบบ เพื่อลดเวลาไล่ gap และทำให้รู้ว่า mismatch มาจาก strategy ไหนแน่ชัด
- S15-S20 พับไว้ก่อน เป็น future work หลังจาก S1-S14 จบ/known gap ชัดเจนแล้ว
- เมื่อทำ step ใดเสร็จ ให้ติ๊ก `[x]` ใน `docs/backtest_strategy_skill.md` และจด command/evidence ล่าสุดไว้ในไฟล์นั้น

---

## 1. คำสั่งการรัน Backtest ตามช่วงเวลา (Time Window Backtest)

สคริปต์สำหรับการจำลองผลการเทรดย้อนหลังแยกตามช่วงเวลาที่ต้องการ (อ้างอิงเขตเวลา Bangkok UTC+7)

### การรันจำลองกลยุทธ์ S10 (CRT TBS)
*   **ไฟล์สคริปต์:** `backtest_s10_timewindow.py`
*   **รูปแบบการรัน (ระบุ TF):**
    ```bash
    python backtest_s10_timewindow.py --start "2026-06-05 00:00" --end "2026-06-06 00:00" --tf M5
    ```
*   **รูปแบบการรัน (ทุก TF):**
    ```bash
    python backtest_s10_timewindow.py --start "2026-06-05 00:00" --end "2026-06-06 00:00"
    ```

### การรันจำลองกลยุทธ์ S14 (Sweep RSI)
*   **ไฟล์สคริปต์:** `backtest_s14_timewindow.py`
*   **รูปแบบการรัน (ระบุ TF):**
    ```bash
    python backtest_s14_timewindow.py --start "2026-06-05 00:00" --end "2026-06-06 00:00" --tf M5
    ```
*   **รูปแบบการรัน (ทุก TF):**
    ```bash
    python backtest_s14_timewindow.py --start "2026-06-05 00:00" --end "2026-06-06 00:00"
    ```
*   **Parameters:**
    *   `--start` (required): เวลาเริ่มต้นของช่วงที่ต้องการดูผล backtest ในรูปแบบเวลา Bangkok UTC+7 เช่น `"2026-06-05 08:00"` หรือ `"2026-06-05T08:00"`
    *   `--end` (required): เวลาสิ้นสุดของช่วงที่ต้องการดูผล backtest ในรูปแบบเวลา Bangkok UTC+7 เช่น `"2026-06-05 10:00"` หรือ `"2026-06-05T10:00"`
    *   `--tf` (optional): ระบุ timeframe ที่ต้องการทดสอบ เช่น `M1`, `M5`, `M15`, `M30`, `H1` ตามที่ `sim_s14_backtest.TF_MAP` รองรับ ถ้าไม่ใส่ จะรันทุก TF ที่สคริปต์รองรับ
*   **หมายเหตุ:** สคริปต์นี้กรองผลจาก `entry_time` ที่อยู่ในช่วง `--start` ถึง `--end` แล้วแสดงรายละเอียด S14 เช่น sub-pattern, swing reference, RSI, PD result และ P&L

### การรัน Auto Trade Backtest + เทียบ Order จริง
*   **ไฟล์สคริปต์:** `backtest_auto_trade.py`
*   **ใช้ทำอะไร:** backtest ระบบ auto trade ตาม `bot_state.json`/config จริงเท่าที่ engine รองรับ และสามารถเทียบผลกับ order จริงจาก log หรือ MT5 history ได้
*   **Strategy หลักใน scope ตอนนี้:** S1, S2, S3, S4, S5, S8, S9, S10, S11, S12, S13 และ S14
*   **Strategy ที่ engine กลางมี baseline/future support:** S15, S16, S17, S18 และ S19 พับไว้ก่อน ไม่ใช้เป็น blocker ของรอบ S1-S14
*   **หมายเหตุ S6/S6i:** S6 (`6`) และ S6i (`7`) ไม่ใช่ standalone order strategy ใน runtime ปัจจุบัน แต่เป็น lifecycle/trailing state ผ่าน `check_s6_trail()` จึงยังไม่มีคำสั่ง `--strategies 6` หรือ `--strategies 7` แยก ต้องรวมเป็น overlay ของ S2/S3/position lifecycle ใน step ถัดไป
*   **ตัวอย่างรัน S1 พร้อมเทียบ MT5 history และสร้าง CSV/XLSX อัตโนมัติ:**
    ```bash
    python backtest_auto_trade.py --start "2026-05-28 08:00" --end "2026-06-08 10:00" --since "2026-05-28 00:00" --tf M15 --strategies 1 --exclude-cancelled --symbol XAUUSD.iux --compare-mt5-history --compare-csv --compare-xlsx --match-minutes 180 --match-entry-points 5
    ```
*   **ตัวอย่างรัน S2 พร้อมเทียบ MT5 history และสร้าง CSV/XLSX อัตโนมัติ:**
    ```bash
    python backtest_auto_trade.py --start "2026-05-28 08:00" --end "2026-06-08 10:00" --since "2026-05-28 00:00" --tf M15 --strategies 2 --exclude-cancelled --symbol XAUUSD.iux --compare-mt5-history --compare-csv --compare-xlsx --match-minutes 180 --match-entry-points 5
    ```
*   **ตัวอย่างรัน S3 พร้อมเทียบ MT5 history และสร้าง CSV/XLSX อัตโนมัติ:**
    ```bash
    python backtest_auto_trade.py --start "2026-05-28 08:00" --end "2026-06-08 10:00" --since "2026-05-28 00:00" --tf M15 --strategies 3 --exclude-cancelled --symbol XAUUSD.iux --compare-mt5-history --compare-csv --compare-xlsx --match-minutes 180 --match-entry-points 5
    ```
*   **ตัวอย่างรัน S3 all-TF เพื่อเช็กว่าก gap เป็นเฉพาะ TF หรือทั้ง strategy:**
    ```bash
    python backtest_auto_trade.py --start "2026-05-28 08:00" --end "2026-06-08 10:00" --since "2026-05-28 00:00" --strategies 3 --exclude-cancelled --symbol XAUUSD.iux --compare-mt5-history --compare-csv --compare-xlsx --match-minutes 180 --match-entry-points 5
    ```
*   **ตัวอย่างรัน S4 พร้อมเทียบ MT5 history และสร้าง CSV/XLSX อัตโนมัติ:**
    ```bash
    python backtest_auto_trade.py --start "2026-05-28 08:00" --end "2026-06-08 10:00" --since "2026-05-28 00:00" --tf M15 --strategies 4 --exclude-cancelled --symbol XAUUSD.iux --compare-mt5-history --compare-csv --compare-xlsx --match-minutes 180 --match-entry-points 5
    ```
*   **ตัวอย่างรัน S5 พร้อมเทียบ MT5 history และสร้าง CSV/XLSX อัตโนมัติ:**
    ```bash
    python backtest_auto_trade.py --start "2026-05-28 08:00" --end "2026-06-08 10:00" --since "2026-05-28 00:00" --tf M15 --strategies 5 --exclude-cancelled --symbol XAUUSD.iux --compare-mt5-history --compare-csv --compare-xlsx --match-minutes 180 --match-entry-points 5
    ```
*   **ตัวอย่างรัน S8 พร้อมเทียบ MT5 history และสร้าง CSV/XLSX อัตโนมัติ:**
    ```bash
    python backtest_auto_trade.py --start "2026-05-28 08:00" --end "2026-06-08 10:00" --since "2026-05-28 00:00" --tf M15 --strategies 8 --exclude-cancelled --symbol XAUUSD.iux --compare-mt5-history --compare-csv --compare-xlsx --match-minutes 180 --match-entry-points 5
    ```
*   **ตัวอย่างรัน S9 พร้อมเทียบ MT5 history และสร้าง CSV/XLSX อัตโนมัติ:**
    ```bash
    python backtest_auto_trade.py --start "2026-05-28 08:00" --end "2026-06-08 10:00" --since "2026-05-28 00:00" --tf M15 --strategies 9 --exclude-cancelled --symbol XAUUSD.iux --compare-mt5-history --compare-csv --compare-xlsx --match-minutes 180 --match-entry-points 5
    ```
*   **ตัวอย่างรัน S11 พร้อมเทียบ MT5 history และสร้าง CSV/XLSX อัตโนมัติ:**
    ```bash
    python backtest_auto_trade.py --start "2026-05-28 08:00" --end "2026-06-08 10:00" --since "2026-05-28 00:00" --tf M15 --strategies 11 --exclude-cancelled --symbol XAUUSD.iux --compare-mt5-history --compare-csv --compare-xlsx --match-minutes 180 --match-entry-points 5
    ```
*   **ตัวอย่างรัน S12 พร้อมเทียบ MT5 history และสร้าง CSV/XLSX อัตโนมัติ:**
    ```bash
    python backtest_auto_trade.py --start "2026-05-28 08:00" --end "2026-06-08 10:00" --since "2026-05-28 00:00" --tf M5 --strategies 12 --exclude-cancelled --symbol XAUUSD.iux --compare-mt5-history --compare-csv --compare-xlsx --match-minutes 180 --match-entry-points 5
    ```
*   **ตัวอย่างรัน S10 พร้อมเทียบ MT5 history และสร้าง CSV/XLSX อัตโนมัติ:**
    ```bash
    python backtest_auto_trade.py --start "2026-06-05 08:00" --end "2026-06-05 10:00" --since "2026-06-05 00:00" --tf H1 --strategies 10 --exclude-cancelled --symbol XAUUSD.iux --compare-mt5-history --compare-csv --compare-xlsx --match-minutes 180 --match-entry-points 5
    ```
*   **ตัวอย่างรัน S14 พร้อมเทียบ MT5 history และสร้าง CSV/XLSX อัตโนมัติ:**
    ```bash
    python backtest_auto_trade.py --start "2026-06-05 08:00" --end "2026-06-05 10:00" --since "2026-06-05 00:00" --tf M15 --strategies 14 --exclude-cancelled --symbol XAUUSD.iux --compare-mt5-history --compare-csv --compare-xlsx --match-minutes 180 --match-entry-points 5
    ```

*   **ตัวอย่างรัน S13 พร้อมเทียบ MT5 history และสร้าง CSV/XLSX อัตโนมัติ:**
    ```bash
    python backtest_auto_trade.py --start "2026-05-28 08:00" --end "2026-06-08 10:00" --since "2026-05-28 00:00" --tf M15 --strategies 13 --exclude-cancelled --symbol XAUUSD.iux --compare-mt5-history --compare-csv --compare-xlsx --match-minutes 180 --match-entry-points 5
    ```

*   **Future work: ตัวอย่างรัน S15 พร้อมเทียบ MT5 history และสร้าง CSV/XLSX อัตโนมัติ:**
    ```bash
    python backtest_auto_trade.py --start "2026-05-28 08:00" --end "2026-06-08 10:00" --since "2026-05-28 00:00" --tf M15 --strategies 15 --exclude-cancelled --symbol XAUUSD.iux --compare-mt5-history --compare-csv --compare-xlsx --match-minutes 180 --match-entry-points 5
    ```

*   **Future work: ตัวอย่างรัน S16 พร้อมเทียบ MT5 history และสร้าง CSV/XLSX อัตโนมัติ:**
    ```bash
    python backtest_auto_trade.py --start "2026-05-28 08:00" --end "2026-06-08 10:00" --since "2026-05-28 00:00" --tf M1 --strategies 16 --exclude-cancelled --symbol XAUUSD.iux --compare-mt5-history --compare-csv --compare-xlsx --match-minutes 180 --match-entry-points 5
    ```
*   **Future work: ตัวอย่างรัน S17 พร้อมเทียบ MT5 history และสร้าง CSV/XLSX อัตโนมัติ:**
    ```bash
    python backtest_auto_trade.py --start "2026-05-28 08:00" --end "2026-06-08 10:00" --since "2026-05-28 00:00" --tf M1 --strategies 17 --exclude-cancelled --symbol XAUUSD.iux --compare-mt5-history --compare-csv --compare-xlsx --match-minutes 180 --match-entry-points 5
    ```
*   **ตัวอย่างรัน S17 Sweep Sniper standalone sim สำหรับจูนพารามิเตอร์ — เรียก `detect_s17()` ตรง:**
    ```bash
    python sim_s17_backtest.py --days 60 --tf M1,M30,H1 --symbol XAUUSD.iux --csv
    python sim_s17_backtest.py --days 30 --tf M1,M5 --sweep4   # จูน entry mode/TP/SLbuf/RSI
    # Compounding แบบ S20.12 runner (risk % ต่อไม้ + ระบุช่วงเวลาแบบ --start/--end)
    python sim_s17_backtest.py --days 60 --tf M1,M30,H1 --symbol XAUUSD.iux --compound 2 --start-balance 1000
    python sim_s17_backtest.py --start "01-06-2026 00:00" --end "01-07-2026 00:00" --tf M1 --symbol XAUUSD.iux --compound 2
    ```
    *   `--mode/--tp/--slb/--rsib/--rsis/--wick` override config รายตัวได้, `--spread` ปรับ spread ต่อไม้ (default $0.20)
    *   `--compound N` = risk N% ต่อไม้ (0 = ปิด), `--start-balance` (default 1000), `--max-lot` (default `S17_MAX_LOT`)
    *   CSV ออกที่ `excel_reports/backtest_compare/s17/`
*   **Future work: ตัวอย่างรัน S18 พร้อมเทียบ MT5 history และสร้าง CSV/XLSX อัตโนมัติ:**
    ```bash
    python backtest_auto_trade.py --start "2026-05-28 08:00" --end "2026-06-08 10:00" --since "2026-05-28 00:00" --tf M1 --strategies 18 --exclude-cancelled --symbol XAUUSD.iux --compare-mt5-history --compare-csv --compare-xlsx --match-minutes 180 --match-entry-points 5
    python backtest_auto_trade.py --start "2026-05-28 08:00" --end "2026-06-08 10:00" --since "2026-05-28 00:00" --tf M5 --strategies 18 --exclude-cancelled --symbol XAUUSD.iux --compare-mt5-history --compare-csv --compare-xlsx --match-minutes 180 --match-entry-points 5
    ```
*   **Future work: ตัวอย่างรัน S19 พร้อมเทียบ MT5 history และสร้าง CSV/XLSX อัตโนมัติ:**
    ```bash
    python backtest_auto_trade.py --start "2026-05-28 08:00" --end "2026-06-08 10:00" --since "2026-05-28 00:00" --tf M1 --strategies 19 --exclude-cancelled --symbol XAUUSD.iux --compare-mt5-history --compare-csv --compare-xlsx --match-minutes 180 --match-entry-points 5
    python backtest_auto_trade.py --start "2026-05-28 08:00" --end "2026-06-08 10:00" --since "2026-05-28 00:00" --tf M5 --strategies 19 --exclude-cancelled --symbol XAUUSD.iux --compare-mt5-history --compare-csv --compare-xlsx --match-minutes 180 --match-entry-points 5
    ```
*   **ตัวอย่างรัน S10 และ S14 พร้อมกัน:**
    ```bash
    python backtest_auto_trade.py --start "2026-06-05 08:00" --end "2026-06-05 10:00" --since "2026-06-05 00:00" --strategies 10,14 --exclude-cancelled --symbol XAUUSD.iux --compare-csv --compare-xlsx
    ```
*   **Output folder:** ถ้าใช้ `--compare-csv` หรือ `--compare-xlsx` โดยไม่ระบุ path สคริปต์จะสร้างไฟล์แยก folder ตาม strategy ใน `excel_reports/backtest_compare/` อัตโนมัติ เช่น:
    *   `excel_reports/backtest_compare/s10/compare_s10_H1_20260605_0800_20260605_1000.csv`
    *   `excel_reports/backtest_compare/s10/compare_s10_H1_20260605_0800_20260605_1000_summary.csv`
    *   `excel_reports/backtest_compare/s14/compare_s14_M15_20260605_0800_20260605_1000.xlsx`
    *   `excel_reports/backtest_compare/s10-14/compare_s10-14_ALL_20260605_0800_20260605_1000.csv`
*   **Parameters หลัก:**
    *   `--start` (required): เวลาเริ่มต้นของช่วง backtest ในรูปแบบ Bangkok UTC+7 เช่น `"2026-06-05 08:00"`
    *   `--end` (required): เวลาสิ้นสุดของช่วง backtest ในรูปแบบ Bangkok UTC+7 เช่น `"2026-06-05 10:00"`
    *   `--tf` (optional): timeframe ที่ต้องการทดสอบ เช่น `H1`; สำหรับ S10 ถ้าใส่ HTF เช่น `H1` ระบบจะ map ไป replay LTF ที่เกี่ยวข้อง เช่น `H1 -> M1`; สำหรับ S14 ต้องเป็น TF ที่ `sim_s14_backtest.TF_MAP` รองรับ เช่น `M1`, `M5`, `M15`, `M30`, `H1`, `H4`, `D1`
    *   `--strategies` (optional): strategy ที่ต้องการทดสอบ เช่น `10`, `14`, `10,14`, `17`, `18`, `19`, `all`, หรือ `active` ค่า default คือ `active`; ถ้าเลือก strategy ที่ยังไม่ได้ต่อเข้า engine กลางจะแจ้ง `Not implemented in this replay engine yet`
    *   `--symbol` (optional): symbol ที่ต้องการทดสอบ เช่น `XAUUSD.iux`; ถ้าไม่ใส่ จะใช้ symbol จาก `bot_state.json` แล้ว fallback เป็น `config.SYMBOL`
    *   `--since` (optional): เวลาเริ่มโหลด/จำลองข้อมูลย้อนหลังในรูปแบบ Bangkok UTC+7 ใช้เมื่ออยากให้ engine เริ่ม replay ก่อน `--start` นานขึ้น
    *   `--exclude-cancelled` / `--only-filled` (optional): ซ่อน event ที่ยังไม่ fill หรือถูก cancel ก่อน fill เช่น `CANCEL`, `OPEN_PENDING`, `BLOCK`
*   **Parameters สำหรับเทียบ order จริง:**
    *   `--compare-live` (optional): เทียบ backtest กับ live order จาก log (`ENTRY_FILL` / `POSITION_CLOSED`)
    *   `--compare-mt5-history` (optional): เทียบ backtest กับ order/deal จริงจาก MT5 history โดยตรง
    *   `--compare-source log|mt5|both` (optional): ใช้ร่วมกับ `--compare-live` เพื่อเลือก source; default คือ `log`
    *   `--log-files` (optional): ระบุ log file เองหลายไฟล์ได้ แต่ backtest ห้ามใช้ live logs (`bot.log`, `system.log`, `error.log`, `bot-*.log`, `system-*.log`, `error-*.log`) และจะ reject ทันทีถ้าส่งเข้ามา; ถ้าไม่ใส่จะใช้ `logs/backtest_bot.log` และ archive `logs/old_logs/backtest_bot-*.log` เท่าที่มีอยู่
    *   Backtest log isolation: เวลา run backtest/log จาก helper จะใช้ `logs/backtest_bot.log`, `logs/backtest_system.log`, `logs/backtest_error.log` เท่านั้น ถ้าไฟล์ยังไม่มีสคริปต์จะสร้างใหม่ ถ้ามีแล้วใช้ต่อได้เลย
    *   `--match-minutes` (optional): tolerance เวลาสำหรับ match live/backtest หน่วยนาที default `180`
    *   `--match-entry-points` (optional): tolerance ราคา entry สำหรับ match live/backtest default `1.0`
    *   `--max-match-quality exact|near|loose` (optional): จำกัดคุณภาพการจับคู่; default `loose` คือใช้ tolerance ตามที่ระบุทั้งหมด, `near` จะไม่จับคู่ row ที่ห่างเวลา/entry มากจนเป็น `LOOSE`, `exact` จะจับเฉพาะคู่ใกล้มาก
    *   `--hybrid-live-guard-context` (optional): ใช้ log `SL_GUARD_GROUP_ACTIVATE` / `POSITION_CLOSE_REQUEST` เป็น compare-time overlay สำหรับ replay trade เพื่อช่วยจำลอง close-on-activate จาก strategy context ที่ engine ยัง replay ไม่ครบ; เหมาะกับการไล่ gap `SL_GUARD_CONTEXT_MISSING_BT`
    *   `--pnl-tolerance` (optional): tolerance P&L สำหรับจัดว่า mismatch default `1.0`
    *   `--mt5-close-search-days` (optional): จำนวนวันหลัง `--end` ที่ใช้ค้นหา deal ปิด position จาก MT5 history default `14`
*   **TF filter ตอน compare:** ถ้าระบุ `--tf` สคริปต์จะกรอง live rows จาก log/MT5 history ให้ตรง TF ก่อนเทียบ เช่น `--tf M15 --strategies 14` จะไม่นำ `M1_S14` หรือ `M5_S14` มาเป็น live-only; สำหรับ S10 ถ้าระบุ HTF เช่น `H1` จะใช้ comment/meta ที่เป็น `H1 -> M1`
    *   S10 exact HTF filter: `--tf H1 --strategies 10` จะรับเฉพาะ live comment/meta ที่เป็น `[H1_M1]_S10...` ไม่รวม `[M15_M1]_S10...` หรือ `[M30_M1]_S10...` แม้ LTF จะเป็น `M1` เหมือนกัน
*   **S1-S5/S8 range-based replay:** S1, S2, S3, S4, S5, S8 เดี่ยว และ runner กลาง S1-S5/S8 ใช้ range-based MT5 fetch เพื่อดึงข้อมูลย้อนหลังให้ถึง window จริง; ถ้าเลือกหลาย strategy ในกลุ่ม `1,2,3,4,5,8` เช่น `--tf M15 --strategies 1,2,3,4,5` หรือ `--strategies 4,5,8` สคริปต์จะใช้ runner กลางที่ process pending/open state ร่วมกันทีละแท่งแล้ว filter report กลับมาเฉพาะ TF ที่ระบุ; S8/unified ที่มี S8 จะดึง TF ต่ำอย่าง `M1/M5` เพื่อ apply SL Guard Group context ด้วย ถ้า context TF ไม่มี history overlap จะ skip พร้อม log เช่น `Skipping unified S4/S5/S8 context TF M1...`
*   **S1/S2/S3 single-strategy routing:** ถ้ารัน `--strategies 1`, `--strategies 2`, หรือ `--strategies 3` เดี่ยว สคริปต์จะใช้ unified S1-S5/S8 runner เช่นกัน เพื่อให้ shared lifecycle baseline (Limit Guard, Opposite, Trail SL, SL Guard/Group, S1 forward/zone/swing) ตรงกับตอนรันรวมมากขึ้น
*   **S14 context replay:** ถ้า `SL_GUARD_GROUP_ENABLED=True` และรัน S14 แบบระบุ `--tf` สคริปต์จะ replay TF ใน SL Guard Group เดียวกันเป็น context ด้วย เช่น `--tf M15` จะ include `M1`, `M5`, `M15`, `M30`, `H1` เพื่อให้ lifecycle ข้าม TF ใกล้ auto trade จริงขึ้น แต่ report/compare output จะยัง filter กลับมาเฉพาะ TF ที่ระบุ
*   **S14 de-duplicate:** `strategy14.py` จะตัด order ซ้ำใน scan เดียวกันเมื่อ `signal + order_mode + entry + tp` เหมือนกัน เพื่อกัน S14 market order ซ้ำจาก engulf/ref หลายชุดที่ให้ entry/TP เดียวกัน
*   **Nearest columns:** สำหรับ row ที่เป็น `LIVE_ONLY` จะมี `nearest_bt_*` เพื่อดู backtest order ฝั่งเดียวกันที่ใกล้ที่สุด; สำหรับ `BACKTEST_ONLY` จะมี `nearest_live_*` เพื่อดู live order ฝั่งเดียวกันที่ใกล้ที่สุด ช่วยไล่ว่า gap เกิดจากเวลาเกิน tolerance หรือ entry ต่างกันมาก
*   **Gap reason:** row ที่เป็น `LIVE_ONLY` / `BACKTEST_ONLY` จะมี `gap_reason` เช่น `TIME_TOO_FAR`, `ENTRY_TOO_FAR`, `TIME_TOO_FAR+ENTRY_TOO_FAR`, `NO_SAME_SIDE_CANDIDATE`, หรือ `NEAREST_ALREADY_MATCHED_OR_GREEDY`; S14 จะเติม prefix เช่น `LIVE_SIGNAL_NOT_REPLAYED`, `LIVE_SIGNAL_PD_CLOSED_NO_REPLAY`, `BT_SIGNAL_NO_LIVE_FILL`; row ที่เป็น `MISMATCH` จะใช้ note เช่น `TRAIL_SL_DIFF_SOURCE`, `TRAIL_SL_DIFF_MISSING_BT`, `TRAIL_SL_DIFF_PRICE`, `SL_GUARD_CONTEXT_MISSING_BT`, `CLOSE_LIFECYCLE_SL_GUARD`, `LOOSE_MATCH_SL_GUARD`, `LIVE_CLOSE_TREND_RECHECK`, `CLOSE_LIFECYCLE_PD`, `CLOSE_BUCKET_DIFF`, `PNL_DIFF_SAME_BUCKET`
*   **Match quality:** compare detail มี `match_quality` (`EXACT`, `NEAR`, `LOOSE`) และ `match_score` เพื่อช่วยแยกว่า order ที่จับคู่กันอยู่ใกล้จริงหรือเป็นการจับคู่หลวมจาก tolerance เช่น `--match-minutes 180`; ถ้าต้องการ strict ให้เติม `--max-match-quality near` เพื่อให้คู่ `LOOSE` กลายเป็น `LIVE_ONLY` / `BACKTEST_ONLY` แทน
*   **Close timestamp/price columns:** compare report มี `live_close_ts`, `live_close_price`, `bt_close_ts`, `bt_close_price`, `close_price_diff` เพื่อดูว่า order เปิดตรงกันแต่ปิดคนละเวลา/คนละราคา/คนละ lifecycle หรือไม่
*   **Trail diagnostics columns:** report จะอ่าน `SL_CHANGED` จาก log แล้วเติม `live_trail_count`, `live_last_trail_ts`, `live_last_trail_sl`, `live_last_trail_source`, `live_trail_path`, `live_close_vs_trail_sl_diff`; ฝั่ง replay มี `bt_trail_count`, `bt_last_trail_ts`, `bt_last_trail_sl`, `bt_last_trail_source`, `bt_trail_path` เพื่อเทียบว่า P/L ต่างเพราะ trail SL ตาม live ไม่ทันหรือไม่ โดย `*_trail_path` จะแสดงลำดับ trail ล่าสุด เช่น `05-29 13:35 M1 4520.30 -> ...`
*   **SL Guard diagnostics columns:** report จะอ่าน `SL_GUARD_GROUP_ACTIVATE`, `POSITION_CLOSE_REQUEST`, `SL_GUARD_CLOSE` จาก log แล้วเติม `live_sl_guard_*` เช่น activation time, group, trigger TF, trigger candidates, request price/spread; `live_sl_guard_trigger_candidates` คือ SL-hit tickets ใกล้ activation ที่อยู่ใน group เดียวกัน ช่วยชี้ว่า BT ขาด context strategy ไหน; ฝั่ง replay มี `bt_sl_guard_group`, `bt_sl_guard_trigger_tf` เมื่อ order ถูก overlay ปิดด้วย SL Guard Group จริง
*   **System SL Guard Group overlay:** ถ้ารันหลาย strategy พร้อมกัน เช่น `--strategies 4,5,8` หรือ `--strategies all` สคริปต์จะ apply SL Guard Group close-on-activate หลังรวบ trade ทุกท่าที่เลือก เพื่อจำลองการปิด position ข้าม strategy ในระบบจริง; ถ้ารัน strategy เดี่ยว overlay นี้จะไม่เปลี่ยนผล
*   **System Opposite Order overlay:** ถ้ารันหลาย strategy พร้อมกันและเปิด `OPPOSITE_ORDER_ENABLED` สคริปต์จะ apply Opposite Order หลัง merge ทุก strategy; mode `sl_protect` จะปรับ SL protect baseline ของ position ที่เปิดซ้อนข้าม strategy/TF เดียวกัน ส่วน mode `tp_close` จะปิดตัวเก่าที่โดน order ฝั่งตรงข้ามตาม baseline
*   **System Limit Guard overlay:** ถ้ารันหลาย strategy พร้อมกันและเปิด `LIMIT_GUARD` สคริปต์จะ apply Limit Guard หลัง merge ก่อน Opposite/SL Guard overlays; ถ้า filled row ใดควรถูก pending guard จาก position ของ strategy อื่นบล็อกก่อน fill จะถูก mark เป็น cancel และถูกตัดออกเมื่อใช้ `--exclude-cancelled`
*   **PD close type ใน replay:** `PD_FAIL` หมายถึง pending/pre-create cancel และจะถูกตัดออกเมื่อใช้ `--exclude-cancelled`; `PD_FILL_FAIL` หมายถึง position fill แล้วโดน PD Fibo Plus ปิด จึงถือเป็น filled trade มี PnL และยังอยู่ใน compare เหมือน order จริงใน MT5 history
*   **Historical PD drift:** PD pre-create/pending/fill skip list ปัจจุบันอ่านจาก `config.PDFIBOPLUS_SKIP_SIDS` และข้าม `S1/S9/S10/S11/S13/S14/S15/S16/S17/S18/S19` ให้ตรงกันทุกจุด; S2/S3 ไม่อยู่ใน skip list ปัจจุบัน จึงต้องเข้า PD Fibo Plus ตาม config จริง. ถ้าเทียบ MT5 history เก่าก่อน skip-list/config change อาจยังเห็น live close reason `PD Zone...` เป็น expected drift จาก runtime คนละเวอร์ชัน
    *   Current-config note: S2/S3 replay ต้องไม่ hardcode เป็น PD skip; ถ้าต้องวัด history เก่าให้ใช้ diagnostic flag แยก เช่น `--s3-disable-pd-fibo-plus` เท่านั้น
*   **Historical drift labels ใน compare:** `*_summary.csv` จะแยก old live close ที่ runtime ปัจจุบัน skip แล้วเป็น `LIVE_HISTORICAL_PD_SKIP_DRIFT` หรือ `LIVE_HISTORICAL_TREND_SKIP_DRIFT` ใน `gap_reason`/`mismatch_gap`; เวลาไล่บัค replay ให้ตัดกลุ่มนี้ออกก่อน แล้วโฟกัส rows ที่ยังเป็น `TIME_TOO_FAR`, `ENTRY_TOO_FAR`, `PNL_DIFF_SAME_BUCKET`, `CLOSE_BUCKET_DIFF`, `SL_GUARD...`, หรือ trail/source gap; ถ้าเห็น `REPLAY_PD_PRECREATE_REJECTED:` แปลว่า live-only row นั้นมี nearest raw replay candidate แต่ replay ปัจจุบันยกเลิกด้วย `PD FIBO PLUS` ก่อนวาง pending order; ถ้าเห็น `REPLAY_PD_REJECTED:` เป็น label เก่าของกลุ่มเดียวกันใน report รุ่นก่อน; ถ้าเห็น `BT_AFTER_LAST_FILTERED_LIVE_FILL:` แปลว่า replay order อยู่หลัง live fill สุดท้ายของชุดที่ถูก filter มาเทียบ เช่น `--tf M15` เกิน `--match-minutes` ควรเช็ก TF-specific state/timing ก่อนแก้ signal math
*   **MT5 history empty retry:** ตอน compare ถ้า `history_deals_get()` และ `history_orders_get()` คืนว่างทั้งคู่ สคริปต์จะ `shutdown()/initialize()` MT5 และ retry หนึ่งครั้ง พร้อม log `last_error`; ใช้กันเคส replay ยาวแล้ว MT5 API คืน history ว่างผิดปกติ ไม่ใช่เปลี่ยน logic เทรด
*   **MT5 rates empty retry:** unified S1-S5/S8 replay จะ retry/reinitialize MT5 หนึ่งครั้งถ้า TF ใดคืน rates ว่างหรือน้อยผิดปกติหลัง replay ยาว ๆ; ถ้าเห็น log `[rates retry] M5...` คือกำลังกู้ข้อมูล TF นั้นเพื่อกัน report all-TF เสียแบบ M5/M15/... เป็น 0
*   **Restore guard:** `backtest_auto_trade.py` จะหยุดทันทีถ้า `config.restore_runtime_state()` fail เพราะ baseline ต้องใช้ `bot_state.json` / config จริงเหมือน bot; ใช้ `--allow-restore-fail` ได้เฉพาะ diagnostic ที่พี่รับทราบว่าไม่ใช่ baseline. 2026-06-24 เคยเจอ restore fail จาก `config.py` ที่อ้าง `getattr(config, "S20_7_ENABLED", False)` ภายในไฟล์ `config.py` เอง; แก้แล้วโดยเพิ่ม `S20_7_ENABLED` ใน restore globals และใช้ `S20_7_ENABLED` เป็น default. Smoke S10 หลังแก้ restore ผ่านและเขียน `excel_reports/backtest_compare/s10/smoke_restore_guard.csv` / `_summary.csv` ได้
*   **BT PD diagnostic columns:** compare report มี `bt_pd_h/l`, `bt_pd_fib_382/618`, `bt_pd_fill_h/l`, `bt_pd_round2_*`, `bt_pd_fallback_used`, `bt_pd_outside_range` สำหรับ matched/backtest-only rows; ใช้ไล่ `CLOSE_LIFECYCLE_PD` ว่า BT ใช้ zone/swing snapshot ไหน ตอน live ปิดด้วย `PD Zone fill...`
*   **MT5 history time:** เวลา deal/order จาก MT5 history แปลงด้วย `config.mt5_ts_to_bkk()` ให้ตรงกับ bot log และ replay engine ห้ามใช้ `datetime.fromtimestamp(..., tz=BKK)` ตรง ๆ เพราะจะคลาดกับ server offset ได้
*   **Parameters สำหรับไฟล์รายงาน:**
    *   `--compare-csv` (optional): สร้าง CSV report ถ้าไม่ใส่ path จะใช้ชื่อ auto ใน folder strategy เช่น `excel_reports/backtest_compare/s14/`; ถ้าใส่แค่ชื่อไฟล์ เช่น `my_compare.csv` ก็จะไปอยู่ใน folder strategy เช่นกัน; ถ้าใส่ path เต็ม สคริปต์จะใช้ path นั้น และจะสร้างไฟล์ `*_summary.csv` คู่กันเพื่อสรุป `gap_reason` / reason / PnL ตามกลุ่ม รวมถึง `mismatch_gap` เช่น `TRAIL_SL_DIFF_SOURCE`, `CLOSE_LIFECYCLE_SL_GUARD`, `LIVE_HISTORICAL_PD_SKIP_DRIFT`, `LIVE_HISTORICAL_TREND_SKIP_DRIFT` และ `trail_source_gap` เช่น `M1 -> M5`
    *   `--compare-xlsx` (optional): สร้าง Excel report แบบมี sheet `Summary`, `All Compare`, `Mismatches`, `Live Only`, `Backtest Only`, `Matches`; กติกา path เหมือน `--compare-csv`
    *   `--dump-trades-csv` (optional): สร้าง CSV raw replay events ทั้งหมด รวม `CANCEL`, `OPEN_PENDING`, `BLOCK`, filled rows และ diagnostic fields เช่น `cancel_reason`, `parallel_tfs`, `lifecycle_tf`, `final_gap_bot/top`; ใช้ไล่ว่าทำไม live order หายไปก่อนเป็น filled trade
    *   `nearest_raw_replay_*` columns: ใน compare CSV/XLSX แถว `LIVE_ONLY` จะมี raw replay candidate ที่ใกล้ที่สุด เช่น entry time/entry/close_type/cancel_reason แม้รันด้วย `--exclude-cancelled`; ใช้ดูได้ทันทีว่า replay เคยสร้าง setup แต่ถูก `cancel_bars`, Sweep Filter, PD Fibo Plus, SL Guard, parallel replacement, adjacent-sid block หรือยังเป็น `OPEN_PENDING` หรือไม่. คอลัมน์นี้รวม sid/side/source (`nearest_raw_replay_sid`, `nearest_raw_replay_side`, `nearest_raw_replay_s3_pattern_code`, `nearest_raw_replay_marubozu_source`, `nearest_raw_replay_source_candle_ts`), raw gap/intersection (`nearest_raw_replay_gap_bot/top`, `nearest_raw_replay_final_gap_bot/top`, `nearest_raw_replay_detect_time_raw`), PD context (`nearest_raw_replay_pd_h/l`, `nearest_raw_replay_pd_fib_382/618`, `nearest_raw_replay_pd_fallback_used`, `nearest_raw_replay_pd_outside_range`), cancel timing (`nearest_raw_replay_cancel_age_bars`, `nearest_raw_replay_cancel_bar_touched_entry`) และ block metadata เช่น `nearest_raw_replay_sweep_scan_state/tf`, `nearest_raw_replay_sl_guard_scope/key/count/since/swing_ref`
*   **Scale out columns:** ถ้า `SCALE_OUT_ENABLED=True` และเทียบจาก MT5 history report จะเพิ่ม `live_scale_out_1_pnl` ถึง `live_scale_out_4_pnl` เพื่อแยก P/L ของการปิด partial แต่ละช่อง; XAUUSD ใช้ 0.01 lot ต่อช่อง, BTCUSD ใช้ 0.04 lot ต่อช่อง
*   **Live close reason:** MT5 close deal บางรายการ เช่น `[sl ...]`, `PD Zone fill check`, `SL Guard Group ...` ไม่มี strategy id ใน comment; report จะรวม close deal ด้วย `position_id` หลังจากเจอ entry deal แล้ว และเพิ่ม `live_entry_comment` เพื่อดู comment ตอนเปิด order แยกจาก `live_reason`
*   **S14 Trail SL replay:** S14 replay จำลอง Trail SL แบบ engulf combined ตาม `TRAIL_GROUPS` และใช้ TF ย่อยเป็น price path ระหว่างแท่งหลัก (เช่น M15 -> เดินด้วย M1/M5 ถ้ามีข้อมูล) เพื่อให้ SL/TP/trail/scale-out ใกล้ bot จริงขึ้น
*   **S14 Market fill replay:** S14 เป็น market order ใน bot จริง ดังนั้น baseline replay จะใช้ราคา entry reference ของ strategy บนแท่ง detect (`s_close`) และเวลาแท่ง detect; ราคาจริงใน MT5 history ยังต่างได้ตาม bid/ask tick และ slippage. ถ้าต้องการ probe timing แบบ scanner closed-bar แล้ว market fill ตอนแท่งใหม่เปิด ให้ใช้ diagnostic `--s14-fill-next-bar`
*   **S14 range + HHLL replay:** S14 replay ใช้ range-based MT5 fetch สำหรับ TF/HTF/trail context และ inject historical HHLL เป็น default ให้ `strategy14.py` ใช้ swing refs ได้ตรง runtime; ถ้า HHLL ไม่ถูก inject จะเกิดอาการ raw events เป็น 0 ได้แม้มี live S14 orders
*   **S14 Strong Trend Block replay:** ถ้า `STRONG_TREND_BLOCK_ENABLED=True` และ S14 อยู่ใน `STRONG_TREND_BLOCK_SIDS` replay จะ block S14 signal ที่สวน HHLL strong trend เหมือน runtime; config ปัจจุบันใน baseline เป็น OFF จึงไม่มีผลกับ report เดิม
*   **S14 historical gate drift:** ถ้า S14 live-only เยอะหลัง range+HHLL ถูกแล้ว ให้เช็ค config/version ของ `S14_RSI_DIV_ENABLED` และ `S14_SWEEP_RETURN` ก่อน เพราะ sensitivity test ช่วง 28/05-08/06 ทำให้ M15 kept จาก 3 -> 13/15 และถ้าเปิดทั้งคู่จะ overshoot เป็น 60; baseline summary ล่าสุดยังแยก old PD/Trend closes เป็น `LIVE_HISTORICAL_PD_SKIP_DRIFT` / `LIVE_HISTORICAL_TREND_SKIP_DRIFT` แล้ว เหลือ live-not-replayed หลักจาก signal/gate drift
*   **S14 gate diagnostic CLI:** ใช้ `--s14-disable-rsi-div`, `--s14-enable-sweep-return` และ/หรือ `--s14-fill-next-bar` เพื่อรัน diagnostic replay แบบ override ชั่วคราวหลัง restore `bot_state` โดยไม่เปลี่ยน baseline config จริง; report auto suffix เป็น `_s14_no_rsi_div`, `_s14_sweep_return`, `_s14_next_bar` หรือรวมกัน เช่น `_s14_sweep_return_s14_next_bar`
    ```bash
    python backtest_auto_trade.py --start "2026-05-28 08:00" --end "2026-06-08 10:00" --since "2026-05-28 00:00" --tf M15 --strategies 14 --exclude-cancelled --symbol XAUUSD.iux --compare-mt5-history --compare-csv --compare-xlsx --match-minutes 180 --match-entry-points 5 --s14-disable-rsi-div
    ```
    ```bash
    python backtest_auto_trade.py --start "2026-05-28 08:00" --end "2026-06-08 10:00" --since "2026-05-28 00:00" --tf M15 --strategies 14 --exclude-cancelled --symbol XAUUSD.iux --compare-mt5-history --compare-csv --compare-xlsx --match-minutes 180 --match-entry-points 5 --s14-enable-sweep-return --s14-fill-next-bar
    ```
    *   ผล diagnostic ช่วง 28/05-08/06: `--s14-disable-rsi-div` kept 15 แต่ paired live แค่ 1; `--s14-enable-sweep-return` kept 16 และ paired live 9; `--s14-fill-next-bar` อย่างเดียว kept 3 และ paired live 1; `--s14-enable-sweep-return --s14-fill-next-bar` kept 16, paired live 9, live-only 23, backtest-only 7 และ mismatch ลดจาก 9 เหลือ 8; เปิด RSI-div off + sweep-return พร้อมกัน kept 63 และ overshoot เป็น backtest-only 53 ดังนั้นถ้าจะไล่ S14 live เก่าต่อให้เริ่มจาก sweep-return drift ก่อน
    *   Probe note: live SELL cluster วันที่ 2026-05-29 14:00-16:00 ไม่เกิดจาก current `strategy14.py` แม้เปิด `S14_SWEEP_RETURN=True` และปิด `S14_RSI_DIV_ENABLED`; current code ยังคืน `WAIT` หรือให้ BUY คนละฝั่ง จึงน่าจะเป็น historical strategy/config-version drift
    *   `strategy14.py` รองรับ no-RSI-div path แล้วด้วย `_fmt_rsi()` / `_round_rsi()` กัน crash ตอน `ref_rsi=None`
*   **S14 trail-source diagnostic:** ถ้าเห็น `TRAIL_SL_DIFF_SOURCE` แต่ `live_last_trail_source` ว่าง ให้เช็กก่อนว่า `logs/bot.log` มีช่วงเวลาของ live ticket นั้นจริงไหม; baseline 28/05-08/06 มี ticket `534295319` วันที่ 2026-05-29 แต่ log ที่มีเริ่ม 2026-06-18 จึง reconstruct live trail source ไม่ได้
*   **S10 pending cancel arm-state replay:** S10 replay ทำตาม runtime ปัจจุบันคือ pending/sibling cancel ไม่เรียก `strategy10.handle_ticket_closed()` เพื่อเคลียร์ arm state; จะเคลียร์ผ่าน position close จริงเท่านั้น ทำให้ลด backtest-only จากการ retry parent เดิมซ้ำเกินจริง
*   **S10 historical model-selection drift:** ถ้า S10 live history เก่า entry ต่างจาก replay แต่ parent/SL/TP เดียวกัน ให้ดู `strategy10` Phase1/Model selection ก่อน เช่น 2026-06-05 live ตั้ง `4452.22/4453.00` แต่ current replay เลือก latest failed-push แล้วได้ `4464.44/4464.58`; กรณีนี้เป็น logic-version drift มากกว่า SL/TP lifecycle
*   **S16 duplicate-storm diagnostic:** ช่วง `2026-06-09 00:00` ถึง `2026-06-10 23:59` บน M1 มี live S16 duplicate storm จริง; ใช้คำสั่ง `python backtest_auto_trade.py --start "2026-06-09 00:00" --end "2026-06-10 23:59" --since "2026-06-09 00:00" --tf M1 --strategies 16 --exclude-cancelled --symbol XAUUSD.iux --compare-mt5-history --compare-csv --compare-xlsx --match-minutes 180 --match-entry-points 5` เพื่อเทียบ current replay กับ history ช่วงนั้น
*   **S14 SL Guard Group overlay:** S14 replay มี overlay สำหรับ close-on-activate ของ `SL_GUARD_GROUP`; ถ้า context TF ไม่สร้าง loss/SL trigger เหมือน live report จะยังแสดงเป็น mismatch ซึ่งมักชี้ไปที่ signal/config/trail drift ของ TF context มากกว่าแค่ lifecycle overlay
*   **Hybrid live guard context:** ถ้าเปิด `--hybrid-live-guard-context` สคริปต์จะใช้ activation จาก log มาปิด replay trade ที่ยังเปิดอยู่ใน group เดียวกันด้วยราคา request จาก live ก่อน แล้ว mark ฝั่ง replay เป็น `SL_GUARD_GROUP_LIVECTX`; ใช้เพื่อวัดว่า gap มาจาก guard context ที่ engine ยัง replay ไม่ครบหรือไม่ โดยถ้าใช้ชื่อไฟล์อัตโนมัติ report จะลงท้าย `_hybrid_guard` เพื่อไม่ให้ทับ baseline report
    *   หมายเหตุ: hybrid guard ช่วยเฉพาะกรณีมี replay trade อยู่ให้ปิด ถ้า live-only เป็น signal ที่ replay ไม่สร้างเลย เช่น S15 2026-06-03, ผล compare จะไม่เปลี่ยนและควรไล่ signal/config drift ก่อน
*   **S14 family diagnostic:** `--prefer-same-s14-family` จะให้ matcher prefer S14 family เดียวกันก่อน (`BUY_SWEEP`, `BUY_ENGULF`, `SELL_SWEEP`, `SELL_ENGULF`) ใช้สำหรับไล่ subtype drift เท่านั้น; ถ้าใช้ชื่อไฟล์อัตโนมัติ report จะลงท้าย `_s14_family`; baseline ปกติไม่ควรเปิดทันที เพราะข้อมูลเก่าบางช่วง label family กับ replay drift แต่เวลา/entry ยังเป็นคู่เทียบที่มีประโยชน์
*   **Compare summary เพิ่มเติม:** ไฟล์ `*_summary.csv` จะสรุปทั้ง `gap_reason`, `trail_source_gap`, `live_entry_comment` / `mismatch_entry_comment`; สำหรับ report ที่มี S14 family จริงจะเพิ่ม `live_s14_family` / `bt_s14_family` / `mismatch_s14_family` และ `s14_family_mismatch` เพื่อช่วยดูว่ากลุ่ม gap กระจุกอยู่ที่ S14 family ไหน เช่น `BUY_SWEEP`, `BUY_ENGULF`, `SELL_SWEEP`, `SELL_ENGULF` แม้ comment คนละยุค (`M15_S14_BE`, `M15_S14_BS`, `M15_S14_BSSH4`)
*   **Progress log:** ระหว่างรันสคริปต์จะพิมพ์เวลา elapsed เช่น `[00:47] Running S10 replay on M1...` หรือ `[00:12] Running S14 replay on M15...` เพื่อให้รู้ว่ายังทำงานอยู่ ไม่ได้ค้าง
*   **S1 baseline replay:** S1 replay ใช้ range-based fetch + `strategy1.strategy_1()` จริง, จำลอง pending limit fill, `cancel_bars`, fixed SL/TP, เก็บ `s1_zone_meta`, replay S1 forward confirm และ zone/swing post-check ตาม `S1_ZONE_MODE`; runtime ปัจจุบัน skip PD/Trend/RSI recheck สำหรับ S1 แล้ว และ replay มี Limit Guard, Opposite Order, Trail SL, SL Guard baseline ผ่าน unified S1-S5/S8 runner แล้ว gap ที่ยังเหลือคือ exact trail/guard/live-state timing
    *   S1 note: `S1_ZONE_MODE=swing` ใน config/bot_state ปัจจุบันทำให้ replay ปิดหลายไม้ด้วย `S1_SWING_EXIT`; ถ้าเทียบ history เก่าที่ยังมี `PD Zone...`, `Fill Trend Recheck`, หรือ `SL Guard Group...` ให้ถือเป็น historical lifecycle drift ก่อน
*   **S2 baseline replay:** S2 replay ใช้ range-based fetch + `strategy2.strategy_2()` จริง, จำลอง normal confirm lookback, swing fallback, pending limit fill, `cancel_bars`, fixed SL/TP และ PD Fibo Plus ตาม `config.PDFIBOPLUS_SKIP_SIDS` ปัจจุบัน; runtime ปัจจุบันยัง skip Trend recheck สำหรับ S2 และ replay มี Limit Guard, Opposite Order, Trail SL, SL Guard baseline, RSI Fill Recheck, current-TF Trend Filter scan block และ Limit TP/SL Break Cancel baseline เมื่อ config เปิดแล้ว gap ที่ยังเหลือคือ exact FVG parallel cancel/re-place ข้าม TF, Sweep Filter timing, higher-TF/exported trend scan state และ timing/shared-state drift
    *   S2 compare update: PD Fibo Plus ต้องตาม `config.PDFIBOPLUS_SKIP_SIDS` ปัจจุบัน และไม่ hardcode S2 เป็น skip ใน fallback ฝั่ง sim; งานที่เหลือคือ FVG parallel timing/re-place, Sweep Filter timing, SL Guard/Trail timing และ shared state
    *   S2 update: S2-only unified replay มี first-pass multi-TF `FVG_PARALLEL` context แล้ว เช่น `--tf M15 --strategies 2` จะ include `M5/M15/M30/H1` เพื่อให้ pending overlap ถูกแทนด้วย intersection entry ใกล้ bot จริงขึ้น
    *   S2 connected-FVG diagnostic: ใช้ `--s2-include-connected-fvg-context` เพื่อ include one-hop group ที่โยงกัน เช่น live comment `[M1_M5_M15]_S2`; flag นี้ยังเป็น diagnostic และปิดใน baseline เพราะผลเทียบช่วง 28/05-08/06 ยัง mixed: ลด backtest-only จาก 7 เหลือ 3 แต่ matched ลดจาก 5 เหลือ 3
        ```bash
        python backtest_auto_trade.py --start "2026-05-28 08:00" --end "2026-06-08 10:00" --since "2026-05-28 00:00" --tf M15 --strategies 2 --exclude-cancelled --symbol XAUUSD.iux --compare-mt5-history --compare-csv --compare-xlsx --match-minutes 180 --match-entry-points 5 --s2-include-connected-fvg-context
        ```
    *   S2 lifecycle-TF diagnostic: ใช้ `--s2-parallel-lifecycle-tf` เพื่อทดสอบให้ S2 parallel fill/SL/TP เดินบน TF เล็กสุดในกลุ่ม เหมือน runtime ที่ตั้ง `position_tf=check_tf`; ปิดใน baseline เพราะช่วง 28/05-08/06 matched ยังเท่าเดิม 5 แต่ backtest-only เพิ่ม 7 -> 8 แม้ P&L ดีขึ้นเล็กน้อย
        ```bash
        python backtest_auto_trade.py --start "2026-05-28 08:00" --end "2026-06-08 10:00" --since "2026-05-28 00:00" --tf M15 --strategies 2 --exclude-cancelled --symbol XAUUSD.iux --compare-mt5-history --compare-csv --compare-xlsx --match-minutes 180 --match-entry-points 5 --s2-parallel-lifecycle-tf
        ```
    *   S2 fill-before-cancel diagnostic: ใช้ `--s2-fill-before-cancel-bars` เพื่อทดสอบกรณีแท่งที่ order หมดอายุด้วย `cancel_bars` แตะ entry พร้อมกัน ว่า broker/live น่าจะ fill ก่อน cancel หรือไม่; flag นี้ยังเป็น diagnostic เพราะช่วง 28/05-08/06 matched เพิ่ม 3 -> 5 และ live-only ลด 29 -> 27 แต่ mismatches เพิ่ม 3 -> 5 และ P&L ยังแย่ (`-93.33`)
        ```bash
        python backtest_auto_trade.py --start "2026-05-28 08:00" --end "2026-06-08 10:00" --since "2026-05-28 00:00" --tf M15 --strategies 2 --exclude-cancelled --symbol XAUUSD.iux --compare-mt5-history --compare-csv --compare-xlsx --match-minutes 180 --match-entry-points 5 --s2-fill-before-cancel-bars
        ```
    *   S2 no-sweep diagnostic: ใช้ `--s2-disable-sweep-filter` เพื่อวัดว่า historical live orders เกิดจาก Sweep Filter ที่ปิด/looser ใน runtime เก่าหรือไม่; ปิดใน baseline เพราะช่วง 28/05-08/06 matched ดีขึ้น 5 -> 9 แต่ backtest-only เพิ่ม 7 -> 11 และ P&L overshoot เป็น `+106.14`
        ```bash
        python backtest_auto_trade.py --start "2026-05-28 08:00" --end "2026-06-08 10:00" --since "2026-05-28 00:00" --tf M15 --strategies 2 --exclude-cancelled --symbol XAUUSD.iux --compare-mt5-history --compare-csv --compare-xlsx --match-minutes 180 --match-entry-points 5 --s2-disable-sweep-filter
        ```
    *   S2 raw-events diagnostic: ใช้ `--dump-trades-csv` และไม่ใส่ `--exclude-cancelled` เพื่อเก็บ replay event ทุกสถานะไว้ตรวจ เช่นไฟล์ล่าสุด `excel_reports/backtest_compare/s2/s2_raw_events_include_cancelled.csv` มี 103 events: Sweep Filter 53, `cancel_bars` 13, parallel replacement 10, SL Guard 7, adjacent same-sid 6, OPEN_PENDING 2. ถ้ารัน compare ปกติด้วย `--exclude-cancelled` ให้เริ่มดูคอลัมน์ `nearest_raw_replay_*` ในไฟล์ compare ก่อน เพราะระบบเติม candidate ใกล้ที่สุดให้แล้ว
        ```bash
        python backtest_auto_trade.py --start "2026-05-28 08:00" --end "2026-06-08 10:00" --since "2026-05-28 00:00" --tf M15 --strategies 2 --symbol XAUUSD.iux --dump-trades-csv s2_raw_events_include_cancelled.csv --compare-mt5-history --compare-csv s2_include_cancelled_diagnostic.csv --match-minutes 180 --match-entry-points 5
        ```
    *   S2 performance update: unified multi-TF replay มี progress ภายใน loop เช่น `S2 multi-TF replay progress 1537/30759 event(s) (4%)`; หลัง `--end` จะไม่ scan สร้าง signal ใหม่แล้ว แต่ยังเดิน lifecycle ต่อถึง `--mt5-close-search-days` เพื่อหา close ของ order ที่เปิดใน window
    *   S2 composite TF update: compare parser/report filter รองรับ comment หลาย TF เช่น `[M5_M15_M30]_S2` และ replay row ที่มี `parallel_tfs` รวม TF ที่ขอแล้ว ดังนั้น `--tf M15` จะนับ order composite ที่มี M15 เป็นสมาชิกด้วย
    *   S2 sweep update: S2-only multi-TF replay ใช้ optimized historical sweep scan block แล้ว โดยจำกัด sweep window ตาม runtime 150 แท่งและ cache HTF rates เพื่อลด timeout; sweep timestamp/expiry metadata สำหรับ report อยู่ในฝั่ง `sim_s458_backtest.py` เพื่อไม่ต้องแก้ runtime `sweep_filter.py` และ replay จะ expire sweep ด้วย historical bar time แทน wall-clock ปัจจุบัน
*   **S3 baseline replay:** S3 replay ใช้ range-based fetch + `strategy3.strategy_3()` จริง, จำลอง normal confirm lookback, swing fallback, Marubozu/No Engulf pending ยืนยันแท่งถัดไป, pending limit fill, fixed SL/TP, PD Fibo Plus ตาม `config.PDFIBOPLUS_SKIP_SIDS` ปัจจุบัน, adjacent same-sid block, first-pass sweep scan block และ current-TF Trend Filter scan block เมื่อ config เปิด; runtime ปัจจุบันยัง skip Trend recheck สำหรับ S3 และ replay มี Limit Guard, Opposite Order, Trail SL, RSI modes, SL Guard baseline แล้ว gap ที่ยังเหลือคือ global runtime state, higher-TF/exported trend scan state, exact sweep expiry/state และ timing/shared-state drift
    *   S3 compare update: baseline ล่าสุดหลังใช้ current config มี raw events 112, kept 23, P&L `-41.41`, matched 7, live-only 8, backtest-only 16; report รุ่นใหม่ใช้ `REPLAY_PD_PRECREATE_REJECTED:` เพื่อบอก live-only rows ที่ replay สร้าง candidate แล้วแต่ถูก `PD FIBO PLUS` reject ก่อนวาง pending order. งานที่เหลือคือ high backtest-only count, adjacent/sweep/global-state timing และ Trail/Guard shared state
    *   S3 backtest-only update: report ล่าสุดแยก `BT_AFTER_LAST_FILTERED_LIVE_FILL:` แล้ว โดย 12/16 backtest-only rows อยู่หลัง live M15 S3 fill สุดท้ายเกิน match window (`--match-minutes 180`). Cross-check all MT5 history หลัง `2026-06-02 17:48` ยังมี live 533 rows และ S3 อีก 58 rows ใน TF อื่น จึงเป็น M15-filter-specific gap ไม่ใช่หลักฐานว่า S3 ปิดทั้งท่า
    *   S3 all-TF compare update: report `excel_reports/backtest_compare/s3/compare_s3_ALL_20260528_0800_20260608_1000.csv` โหลด MT5 history ได้จริง (`deals=10014`, `orders=12669`), live rows 264, backtest rows 299, matched total 146 (`MATCH=3`, `MISMATCH=143`), live-only 118, backtest-only 153. Gap หลักหลังแยก bucket คือ `LOOSE_MATCH_PNL_DIFF`, `LIVE_CLOSE_PD_BT_NON_PD`, `BT_CLOSE_PD_LIVE_NON_PD`, `ENTRY_TOO_FAR`, และ current-config PD reject (`REPLAY_PD_PRECREATE_REJECTED` ใน report รุ่นใหม่ / `REPLAY_PD_REJECTED` ใน report รุ่นเก่า); ใช้ all-TF report ก่อนสรุปว่า S3 ปิดหรือเพี้ยนทั้งท่า
    *   S3 PD-fill timing sync: replay now checks PD fill round1 against prior closed bars and uses entry price as the immediate-close proxy on round1 fail, matching runtime timing better than using the completed fill bar. Result is mixed, not final parity, so next S3 pass still needs deeper PD lifecycle/tick timing work.
    *   S3 diagnostics update: all-TF report now carries `bt_pd_*` columns and compare buckets separate PD/PnL direction: `LIVE_CLOSE_PD_BT_NON_PD=31`, `BT_CLOSE_PD_LIVE_NON_PD=19`, true `CLOSE_LIFECYCLE_PD=10`, `LOOSE_MATCH_PNL_DIFF=38`, `CLOSE_PRICE_DIFF_SAME_BUCKET=7`, and residual `PNL_DIFF_SAME_BUCKET=1`. This prevents the old `CLOSE_LIFECYCLE_PD=60` / `PNL_DIFF_SAME_BUCKET=46` buckets from hiding whether the issue is PD lifecycle, loose matching, or close-price drift.
    *   S3 near-match diagnostic: ใช้ `--max-match-quality near` และ output suffix `_near` เพื่อแยก loose match ออกโดยไม่ทับ baseline. Latest result: matched `146 -> 43`, live-only `118 -> 221`, backtest-only `153 -> 256`, mismatch `143 -> 41`; สรุปว่า loose gap ส่วนใหญ่คือ signal timing/entry drift ไม่ใช่ P&L math เพี้ยนล้วน ๆ
        ```bash
        python backtest_auto_trade.py --start "2026-05-28 08:00" --end "2026-06-08 10:00" --since "2026-05-28 00:00" --strategies 3 --exclude-cancelled --symbol XAUUSD.iux --compare-mt5-history --compare-csv excel_reports/backtest_compare/s3/compare_s3_ALL_20260528_0800_20260608_1000_near.csv --compare-xlsx excel_reports/backtest_compare/s3/compare_s3_ALL_20260528_0800_20260608_1000_near.xlsx --match-minutes 180 --match-entry-points 5 --max-match-quality near
        ```
    *   S3 near report diagnostics: report `_near` now includes `live_s3_pattern_code`, `bt_s3_pattern_code`, `bt_detect_ts`, `bt_source_candle_ts`, and `bt_marubozu_source`. Latest rerun wrote CSV/XLSX successfully and shows backtest-only `NOENGULF=133` (mostly detect one bar after source candle) versus live-only `G=113`, `R=77`, `G_DOJI=16`, `R_DOJI=15`; next S3 pass should inspect Marubozu/NoEngulf pending confirm and shared dedup/active-state timing.
    *   S3 context-strategy diagnostic: ใช้ `--context-strategies` เพื่อให้ replay รัน strategy อื่นเป็น shared-state context แต่ report/compare ยัง filter เฉพาะ `--strategies`; context extras จะเคารพ restored `active_strategies` จาก config/state จริง เช่น requested `1,2,4,5,8` แต่ถ้า S5/S8 OFF จะใช้ context จริงเป็น `[1,2,4]` และ skip `[5,8]`
        ```bash
        python backtest_auto_trade.py --start "2026-05-28 08:00" --end "2026-06-08 10:00" --since "2026-05-28 00:00" --strategies 3 --context-strategies 1,2,4,5,8 --exclude-cancelled --symbol XAUUSD.iux --compare-mt5-history --compare-csv excel_reports/backtest_compare/s3/compare_s3_ALL_20260528_0800_20260608_1000_near_ctx.csv --compare-xlsx excel_reports/backtest_compare/s3/compare_s3_ALL_20260528_0800_20260608_1000_near_ctx.xlsx --match-minutes 180 --match-entry-points 5 --max-match-quality near
        ```
        Valid rerun after restore fix (2026-06-24): ใช้เวลา `09:50`, restore ผ่านจริง, live rows `264`, backtest rows `236`, matched `36` (`MATCH=1`, `MISMATCH=35`), live-only `228`, backtest-only `200`, matched P&L diff `+12.86`, match quality `EXACT=2 | NEAR=34 | LOOSE=0`. ใช้เป็น diagnostic เท่านั้น เพราะ backtest-only ลดลงแต่ matched count ลดและ live-only เพิ่มเมื่อเทียบกับ S3-only `_near`. Report now separates `bt_s3_pattern_code` (`G/R/G_DOJI/R_DOJI`) from `bt_marubozu_source` (`noengulf/marubozu`).
        Latest report-only diagnostic update: `nearest_bt_*` / `nearest_live_*` now include close time/price, side, TF, pattern, S3 C1 code, Marubozu source, entry, PnL, reason, time diff, and entry diff. Rerun result stayed unchanged (`MATCH=1`, `MISMATCH=35`, `LIVE_ONLY=228`, `BACKTEST_ONLY=200`).
        Latest raw-replay diagnostic update: live-only rows now include `nearest_raw_replay_sid/side/s3_pattern_code/marubozu_source/source_candle_ts`; valid report shows nearest raw replay sid distribution S1=`135`, S2=`49`, S3=`38`, S4=`6`, so inspect `nearest_raw_replay_sid` before treating a live-only nearest candidate as an S3 setup failure.
        Latest S3 placement-context update: report also includes `bt_s3_prev_sid_*`, `bt_s3_last_traded_*`, `bt_s3_pending_same_sid_tf`, `bt_s3_open_same_sid_tf`, and `bt_s3_active_same_sid_tf`. Rerun result stayed unchanged; BACKTEST_ONLY active same-S3 TF is `True=72`, `False=124`, blank `4`, while adjacent previous SID is `True=1`.
    *   S3 no-PD diagnostic: ใช้ `--s3-disable-pd-fibo-plus` เพื่อวัด historical-bound ว่าถ้า S3 ไม่ผ่าน PD gate จะเทียบ MT5 history เก่าดีขึ้นไหม; flag นี้ปิดเฉพาะ replay process และสร้าง suffix `_s3_no_pd`. ปิดใน baseline เพราะช่วง 28/05-08/06 matched ดีขึ้นเล็กน้อย 7 -> 8 แต่ backtest-only เพิ่ม 16 -> 41 และ P&L overshoot เป็น `+405.83`
        ```bash
        python backtest_auto_trade.py --start "2026-05-28 08:00" --end "2026-06-08 10:00" --since "2026-05-28 00:00" --tf M15 --strategies 3 --exclude-cancelled --symbol XAUUSD.iux --compare-mt5-history --compare-csv --compare-xlsx --match-minutes 180 --match-entry-points 5 --s3-disable-pd-fibo-plus
        ```
*   **S4 baseline replay:** S4 replay ใช้ range-based fetch + `strategy4.strategy_4(..., tf=tf_name)` จริงพร้อม inject historical HHLL cache ต่อแท่งให้ detect swing เหมือน live scanner, จำลอง pending limit fill, fixed SL/TP, PD Fibo Plus pending/fill round1+round2 gate, Pending Trend Check/Fill Trend Recheck round1+round2, RSI Fill Recheck mode1/mode2/mode3 เมื่อเปิด config, Limit Guard, Opposite Order, engulf/reversal/Focus/trend-override Trail SL baseline, SL Guard/Group retry/unblock baseline, Limit Sweep follow-up S8 เมื่อเปิด config และ system-level Limit Guard/same-bar duplicate/Opposite/SL Guard Group overlays เมื่อรันหลาย strategy; gap ที่ยังเหลือคือ full shared pending/open state และ TF ที่มี live S4 rows
*   **S5 baseline replay:** S5 replay ใช้ range-based fetch + `strategy5.strategy_5()` จริงพร้อมส่ง historical signal time และ inject historical HHLL cache สำหรับ no-trade-hour/zone filters, จำลอง pending limit fill, fixed SL/TP, PD Fibo Plus pending/fill round1+round2 gate, Pending Trend Check/Fill Trend Recheck round1+round2, RSI Fill Recheck mode1/mode2/mode3 เมื่อเปิด config, Limit Guard, Opposite Order, engulf/reversal/Focus/trend-override Trail SL baseline, SL Guard/Group retry/unblock baseline, Limit Sweep follow-up S8 เมื่อเปิด config และ system-level Limit Guard/same-bar duplicate/Opposite/SL Guard Group overlays เมื่อรันหลาย strategy; gap ที่ยังเหลือคือ full shared pending/open state และ TF ที่มี live S5 rows
*   **S8 baseline replay:** S8 replay ใช้ `strategy8.strategy_8(..., tf=tf_name)` จริงพร้อม inject historical HHLL cache, จำลอง dual-side pending, delayed SL baseline, swing-change cancel, PD Fibo Plus pending/fill round1+round2 gate, Pending Trend Check/Fill Trend Recheck round1+round2, RSI Fill Recheck mode1/mode2/mode3 เมื่อเปิด config, Limit Guard, Opposite Order, same-bar duplicate setup overlay, engulf/reversal/Focus/trend-override Trail SL baseline, SL Guard/Group retry/unblock baseline, Limit Sweep follow-up S8 เมื่อเปิด config, S8 runner-level group context overlay และ system-level Limit Guard/same-bar duplicate/Opposite/SL Guard Group overlays เมื่อรันหลาย strategy; gap ที่ยังเหลือคือ full shared cross-TF/cross-strategy pending/open state
*   **S9 baseline replay:** S9 replay ใช้ range-based fetch เมื่อรันผ่าน central date window แล้วเรียก `strategy9.strategy_9()` จริง, จำลอง RSI divergence setup, pivot `setup_sig` dedup, passed-entry invalidation, pending limit fill และ fixed SL/TP; runtime skip PD/Trend/RSI recheck สำหรับ S9 แล้ว และมี Limit Guard, Opposite Order, Trail SL และ SL Guard Group close-on-activate overlay baseline; gap หลักที่เหลือคือ bar/tick timing, shared runtime state และ TF ที่มี live S9 rows
*   **S11 baseline replay:** S11 replay ใช้ range-based MT5 fetch สำหรับ main/trail TF, ใช้ `strategy1.strategy_1()` เพื่อ hook S1 anchor แล้วเรียก `strategy11.strategy_11()` จริง, ใช้ rolling `TF_LOOKBACK + 6` เหมือน scanner แทน full-history slice เพื่อกัน timeout, จำลอง pending limit fill, fixed SL/TP, skip PD ตาม `PDFIBOPLUS_SKIP_SIDS`, มี duplicate/adjacent guard baseline, shadow S1 linked cleanup baseline, Limit Guard pending-cancel baseline, Opposite Order baseline, Trail SL baseline และมี SL Guard Group close-on-activate overlay baseline; gap หลักที่เหลือคือ bar/tick timing, shared runtime state และ historical runtime drift
*   **S12 baseline replay:** S12 replay ใช้ `strategy12` zone helper จริงบน M5, จำลอง market entry ด้วยราคา close ของ M5, order count/side state, momentum block, TP จาก M15, breakout/flip close-all และ SL cooldown หลังโดน SL ตาม `S12_COOLDOWN_SECONDS`; gap ที่ยังเหลือคือ bid/ask tick fidelity
*   **S13 baseline replay:** S13 replay ใช้ `strategy13.strategy_13()` จริง, จำลอง split TP เป็น market rows, close ฝั่งตรงข้ามเมื่อมี opposite signal, skip PD/Trail/Opposite Order ตาม runtime, มี Fill Trend Recheck round1 baseline และมี SL Guard Group close-on-activate overlay baseline; gap ที่ยังเหลือคือ trend round2/scan timing และ market-vs-limit split จาก tick จริง
*   **S15 baseline replay:** S15 replay ใช้ `strategy15.strategy_15()` จริง, ปิด global cooldown แบบ wall-time เฉพาะใน replay แล้วใช้ level cooldown ตาม bar time, จำลอง pending limit fill + fixed SL/TP, skip PD/Trend/RSI/Trail/Opposite/Limit Guard ตาม runtime และมี SL Guard Group close-on-activate overlay baseline
*   **S16 baseline replay:** S16 replay จำลองเวลา BKK และ Asian range จากข้อมูลย้อนหลังเอง ไม่ใช้ `config.now_bkk()` ของ runtime, จำลอง AMD x iFVG pending limit fill + fixed SL/TP, skip PD/Trend/Trail/Opposite ตาม runtime และมี SL Guard Group close-on-activate overlay baseline
*   **S17 baseline replay:** S17 replay ใช้ `strategy17.detect_s17()` จริงพร้อมเวลา BKK ย้อนหลัง, จำลอง Sweep Sniper limit fill/cancel, fixed SL/TP, optional time stop และ skip PD/Trend/RSI/Trail/Opposite/Limit Guard ตาม runtime standalone พร้อม SL Guard Group close-on-activate overlay baseline
*   **S18 baseline replay:** S18 replay ใช้ `strategy18.detect_s18()` จริงพร้อม HTF bias slice ย้อนหลัง, จำลอง TJR/ICT limit fill/cancel และ fixed SL/TP; runtime/replay skip PD/Trend/RSI/Entry Candle/Trail/Opposite/Limit Guard ตาม standalone flow และมี SL Guard Group close-on-activate overlay baseline
*   **S19 baseline replay:** S19 replay ใช้ `strategy19.detect_s19()` จริงพร้อมเวลา BKK ย้อนหลัง, จำลอง Silver Bullet/PO3/Breaker-BPR-FVG/NDOG limit fill/cancel และ fixed SL/TP; runtime/replay skip PD/Trend/RSI/Entry Candle/Trail/Opposite/Limit Guard ตาม standalone flow และมี SL Guard Group close-on-activate overlay baseline
*   **หมายเหตุ:** ตอนนี้ engine กลางรองรับ replay จริงเฉพาะ S1/S2/S3/S4/S5/S8/S9/S10/S11/S12/S13/S14/S15/S16/S17/S18/S19 ก่อน ถ้าเลือก strategy อื่น สคริปต์จะแจ้งว่า `Not implemented in this replay engine yet`

---

## 2. การค้นหาแท่งเทียนราคา OHLC ผ่าน Telegram

พี่สามารถพิมพ์ส่งข้อความแชทเพื่อตรวจสอบแท่งราคา ณ เวลาใด ๆ ได้โดยตรงใน Telegram บอทจะทำการดึงข้อมูลจาก MT5 และจัดรูปแบบแสดงผลให้ทันทีค่ะ

*   **รูปแบบคำสั่ง (Format):**
    ```text
    [Timeframe] [วัน-เดือน-ปี ค.ศ.] [เวลา ชั่วโมง:นาที]
    ```
*   **ตัวอย่างการส่งแชท:**
    *   `M5 05-06-2026 11:15`
    *   `M15 05-06-2026 13:15`
    *   `H1 06-06-2026 18:00`
*   **หมายเหตุ:** เวลาที่พี่ป้อนจะเป็นเวลา Bangkok (UTC+7) เสมอ โดยบอทจะคำนวณและแปลงค่าชิฟต์ไปเป็นเวลาของ Server MT5 อัตโนมัติตามค่าคอนฟิกค่ะ

---

## 3. การดู HHLL Trend ณ เวลาย้อนหลัง ผ่าน Telegram

พี่สามารถสอบถาม Trend ของ HHLL ณ ช่วงเวลาใด ๆ ย้อนหลังได้ทันที บอทจะดึงข้อมูลจาก MT5 แล้วคำนวณ HH/HL/LH/LL + Trend จริงตามโครงสร้างตลาด พร้อมบอกเวลาแท่ง, confirm และเวลาที่บอทตรวจจับเจอจริงจาก log ค่ะ

### รูปแบบคำสั่ง

```text
trend [Timeframe] [วัน-เดือน-ปี ค.ศ.] [เวลา ชั่วโมง:นาที]
```

### ตัวอย่าง

```text
trend M5 05-06-2026 11:15
trend M15 06-06-2026 09:00
trend H1 07-06-2026 14:30
```

### ตัวอย่างผลลัพธ์

```
📊 *HHLL Trend Lookup [M5]*
🕐 ณ BKK: `05-06-2026 11:15`

📈 Trend: 🔴 BEAR (strong)
🏷 Last label: `LL` `4435.25`  แท่ง `05-06 10:20`
🔗 Structure: `LL ▸ LH ▸ LL ▸ LH ▸ LL ▸ LL`

*Swing Points:*
`HH` `4483.34`
  แท่ง: `05-06 02:00` | confirm: `05-06 02:25` | เจอ: `2026-06-05 02:25:04`
`LH` `4455.13`
  แท่ง: `05-06 09:25` | confirm: `05-06 09:50` | เจอ: `2026-06-05 09:50:03`
`HL` `4476.85`
  แท่ง: `05-06 02:45` | confirm: `05-06 03:10` | เจอ: `2026-06-05 03:10:04`
`LL` `4435.25`
  แท่ง: `05-06 10:20` | confirm: `05-06 10:45` | เจอ: `05-06 10:45` *(est)*
```

### รันผ่าน Python CLI (ไม่ต้องเปิด Telegram)

```bash
python trend_lookup.py M5 05-06-2026 11:15
python trend_lookup.py H1 07-06-2026 14:30
```

### หมายเหตุ

- เวลาที่ป้อนเป็น **Bangkok (UTC+7)** เสมอ
- **Trend:** `BULL` / `BEAR` / `SIDEWAY` + `strong` / `weak` คำนวณจาก h0+l0 ของ HHLL structure เหมือนกับที่ MQL5 `SetTrend` ใช้
- **Last label:** label ล่าสุดตาม **timestamp จริง** (ไม่ใช่ ZZ array order)
- **confirm time:** บาร์ที่ `HHLL_RIGHT` บาร์หลังแท่ง swing (เวลาที่ pivot ถูก confirm)
- **detect time:** เวลาที่บอทตรวจจับเจอจริงจาก log (`SCAN` line) ถ้าหาใน log ไม่เจอจะแสดง `(est)` แทน เช่น กรณีบอท restart ช่วงนั้น
- Timeframe รองรับ: `M1`, `M5`, `M15`, `M30`, `H1`, `H4`, `D1`

---

## 4. การค้นหาและตรวจสอบประวัติออเดอร์ (Ticket Lookup)  <!-- เดิม section 3 -->

เมื่อต้องการทราบสถานะหรือประวัติของตั๋ว (Ticket) ใด ๆ ย้อนหลัง

### วิธีการค้นหาบน Telegram
*   **การใช้งาน:** เพียงแค่พี่พิมพ์ส่งเฉพาะ **หมายเลข Ticket** เข้าไปในช่องแชท Telegram โดยตรง (เช่น `538738316`)
*   **ขั้นตอนการทำงานของบอทเบื้องหลัง:**
    1.  บอทจะตรวจสอบหาประวัติข้อความของระบบเทรดดั้งเดิมผ่านทางบันทึกข้อความส่งในแชท (`_grep_tg_sent_near_ts`)
    2.  หากไม่พบประวัติในแชท บอทจะทำการ **Fallback** ไปดึงข้อมูลตั๋วผ่าน MT5 โดยตรงอัตโนมัติ (`_fetch_ticket_metadata_from_mt5`)
    3.  เมื่อได้ข้อมูล (ราคาเปิด, SL, TP, เวลาเปิดตั๋ว) บอทจะทำการวาดและจำลองแผนภาพแท่งราคา ณ ช่วงเวลานั้น (Reconstruct Candle Block) ส่งกลับมาให้พี่ทันทีค่ะ
    4.  หากไม่สามารถเข้าถึงข้อมูลตั๋วได้จริง ๆ พี่สามารถเปิดอ่านค้นหาประวัติตั๋วผ่านไฟล์บันทึกประวัติการสแกนในโฟลเดอร์ `logs/` โดยตรงได้ค่ะ

---

## 5. เคล็ดลับและคำแนะนำเพิ่มเติมสำหรับผู้พัฒนา (Tips & Tricks)

### การแปลค่าความต่างของเวลาชาร์ต (MT5 Server Time vs Bangkok Time)
*   **เวลาบน Chart ของ IUX (UTC+6):** จะช้ากว่าเวลา BKK อยู่ 1 ชั่วโมง
*   **เวลา Bangkok (BKK, UTC+7):** จะเร็วกว่าเวลา Chart อยู่ 1 ชั่วโมง
*   **สูตรการคิด:**
    $$\text{เวลา BKK} = \text{เวลาชาร์ต (Server Time)} + 1\text{ ชั่วโมง}$$
    *ตัวอย่าง: ถ้าชาร์ตแสดงผลเวลา `12:29` เวลา BKK คือ `13:29` (ให้บวกเพิ่ม 1 ชั่วโมงสำหรับการสืบค้นเสมอ)*

### การค้นหาค่า OHLC ของบาร์ราคาผ่าน Python CLI (ด่วน)
หากต้องการคิวรี่ OHLC ของเวลา BKK แบบเร็วบน Command line สามารถรันคำสั่งนี้ได้ค่ะ (แก้เวลา `YYYY-MM-DD HH:MM` ตามต้องการ):
```bash
python -c "import MetaTrader5 as mt5, config; mt5.initialize(); rates = mt5.copy_rates_from_pos(config.SYMBOL, mt5.TIMEFRAME_M5, 0, 5200); import sim_s14_backtest; bkk_rates = [(sim_s14_backtest.to_bkk(r['time']).strftime('%Y-%m-%d %H:%M'), r['open'], r['high'], r['low'], r['close']) for r in rates]; print('\n'.join([str(x) for x in bkk_rates if x[0] == '2026-06-05 13:15'])); mt5.shutdown()"
```

### สถาปัตยกรรม HHLL vs Swing (สำคัญสำหรับ Trend)

ระบบมี pivot 2 ชุดที่ต่างกัน ห้ามสลับกัน:

| ชุด | ตัวแปร | RIGHT | หน้าที่ |
|---|---|---|---|
| Swing | `_swing_data` | 10 | raw pivot สำหรับ display / breakout |
| HHLL | `_hhll_data` | 5 | classify HH/HL/LH/LL → Trend |

- **Trend (BULL/BEAR/SIDEWAY)** อ่านจาก `_hhll_data` เสมอ ผ่าน `get_trend_from_structure(tf)` (`scanner.py`, `trailing.py`)
- ห้ามอ่าน trend จาก `_swing_data` เพราะเป็น cache รอบก่อน
- Logic ตรงกับ MQL5 `SetTrend`: `HH+HL=BULL`, `LH+LL=BEAR`, อื่น=SIDEWAY

### Trend Recheck Rounds (trailing.py)

- `LIMIT_TREND_RECHECK_ROUNDS` ใน config ควบคุมจำนวนรอบ recheck
  - `1` = R1 เท่านั้น (default ปัจจุบัน)
  - `2` = เปิด R2 ด้วย (R2 รอ swing ใหม่แล้วค่อยตัดสิน)
- R2 ต้องเรียก `fetch_hhll(tf)` ก่อน `get_swing_hl_pts(tf)` เสมอ เพราะถ้าไม่ fetch จะอ่าน cache เก่าจาก R1

### Last label ของ HHLL

- `last_label` คือ label ของ swing point ที่มี **timestamp ล่าสุดที่สุด** (เทียบข้าม HH/HL/LH/LL)
- ห้ามใช้ลำดับสุดท้ายของ ZZ array เพราะ ZZ เรียงตาม price path ไม่ใช่เวลา

### คำสั่งตรวจสอบความปลอดภัยของ Repository (ก่อน Deploy หรือ Commit)
*   **ตรวจสอบการเข้ารหัสและสระภาษาไทยล้มเหลว (Mojibake):**
    ```bash
    python check_mojibake.py
    ```
*   **ตรวจสอบการคอมไพล์และ Syntax โค้ดทั้งหมด:**
    ```bash
    python verify_repo.py
    ```

### การรัน Backtest แบบครบทุก Strategy (OLD vs NEW)
ถ้าต้องการรัน Backtest แบบสมบูรณ์เพื่อเปรียบเทียบผลลัพธ์ระหว่าง OLD (อิงจาก Log MT5 ของจริง) กับ NEW (อิงจากโค้ดใหม่) สามารถใช้คำสั่งนี้:

```bash
python backtest_auto_trade.py --start "YYYY-MM-DD HH:MM" --end "YYYY-MM-DD HH:MM" --strategies all --compare-live --compare-xlsx <ชื่อไฟล์>
```
- `--strategies all` : รันตั้งแต่ S1 ถึง S19
- `--compare-live` : เอาผลจากโค้ดใหม่ไปเทียบกับ History Order ที่เทรดจริง
- `--compare-xlsx` : ส่งออกผลลัพธ์เป็นไฟล์ Excel ที่โฟลเดอร์ `excel_reports/backtest_compare/` (แบ่ง Sheet แบบ Summary, All Compare, Matches, Mismatches)

### สร้างไฟล์ Compare ทุก Strategy จาก Log จริง (OLD vs NEW swing dir check)
สร้างไฟล์ Excel เปรียบเทียบผลจริง (OLD) กับผลที่จะเกิดถ้าเพิ่ม swing direction check (NEW)
แยก sheet ตามแต่ละท่า + sheet `All_Compare` รวมทุกท่า + sheet `Summary` สรุปสถิติ
(โครงสร้างเหมือน `s14_compare_old_new` / `compare_all_jun10_12`)

```bash
# วันที่ 15 ถึงปัจจุบัน
python make_strategy_compare.py --start 2026-06-15

# กำหนดช่วงเอง
python make_strategy_compare.py --start 2026-06-10 --end 2026-06-12

# กำหนดชื่อไฟล์ output เอง
python make_strategy_compare.py --start 2026-06-15 --out excel_reports/my_report.xlsx
```
- `--start` (บังคับ) : วันเริ่ม `YYYY-MM-DD`
- `--end`   : วันสิ้นสุด (default = วันนี้)
- `--out`   : path output (default = `excel_reports/compare_all_<start>_<end>.xlsx`)
- `--logs`  : glob pattern ของ log เอง (default = auto-glob `logs/old_logs/bot-*.log*` รวมไฟล์ rotate `.bak`)
- ⚠️ ดึงจาก `logs/` — ข้อมูลย้อนหลังจำกัดตามที่ log ยัง retain อยู่ (log rotate แล้วข้อมูลเก่าจะหาย)
