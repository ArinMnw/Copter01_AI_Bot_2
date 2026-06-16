# -*- coding: utf-8 -*-
"""ข้อมูล pattern + candlestick สำหรับ Strategy Docs tab ใน dashboard.py

โครงสร้าง:
    STRATEGY_PATTERNS[sid] = {
        "name": ชื่อท่า,
        "tag":  สถานะสั้น (main-flow/standalone · ON/OFF · ...),
        "doc":  คำอธิบายภาพรวม (รองรับ <b>),
        "cfg":  config/หมายเหตุสั้น,
        "patterns": [ pattern, ... ],
    }
    pattern = {
        "title": ชื่อ pattern,
        "desc":  คำอธิบาย (รองรับ <b>),
        "candles": [ {"o","h","l","c","lab"}, ... ],   # สี เขียว/แดง คำนวณจาก c>=o ใน JS
        "refs":  [ {"p": ราคา, "c": สีเส้น, "t": label} ],  # เส้นแนวนอน entry/SL/TP/zone
        "band":  {"from","to","c"} หรือ None,            # แถบโซน (เช่น FVG)
        "note":  สรุป 1 บรรทัดใต้กราฟ,
    }

สี refs: Entry=#fbbf24 (ทอง) · SL=#fb7185 (แดง) · TP=#34d399 (เขียว) · zone=#a78bfa (ม่วง)

ราคาในตัวอย่างเป็นค่า "เชิงอธิบาย" (illustrative) เพื่อให้เห็นรูปแบบแท่ง ไม่ใช่ราคาจริง
แต่ความสัมพันธ์ของแท่ง (กลืน/gap/ไส้) ยึดตาม logic จริงในแต่ละ strategyN.py
"""

ENTRY = "#fbbf24"
SL = "#fb7185"
TP = "#34d399"
ZONE = "#a78bfa"


def _c(o, h, l, c, lab):
    return {"o": o, "h": h, "l": l, "c": c, "lab": lab}


STRATEGY_PATTERNS = {
    1: {
        "name": "ท่า 1 — กลืนกิน / ตำหนิ / ย้อนโครงสร้าง",
        "tag": "main-flow · ON · code PA/PB/PC/PE/P4",
        "doc": "ใช้แท่ง [2][1][0] เป็นแกน หา pattern กลืนกิน/ตำหนิ. body แท่งสัญญาณ ≥ 35%, "
               "ใช้ <b>engulf_min_price()</b> เป็น gap ขั้นต่ำ. มี Zone Mode + Forward Confirm "
               "(ตั้ง order ก่อน รอ S2/S3 ฝั่งเดียวกันใน 5 แท่ง).",
        "cfg": "S1_ZONE_MODE='zone' · Forward Confirm 5 แท่ง · TP fallback RR 1:1",
        "patterns": [
            {"title": "Pattern A — BUY กลืนกินต่อเนื่อง", "desc": "[2]แดง → [1]เขียวกลืน Close&gt;High[2]+gap → [0]เขียวกลืน Close&gt;High[1]+gap",
             "candles": [_c(104, 104.6, 100.2, 100.6, "[2]"), _c(100.6, 106.2, 100.3, 105.8, "[1]"), _c(105.8, 109, 105.4, 108.5, "[0]")],
             "refs": [{"p": 105.8, "c": ENTRY, "t": "Entry"}, {"p": 100.2, "c": SL, "t": "SL"}, {"p": 112, "c": TP, "t": "TP"}],
             "band": None, "note": "[1] กลืน High[2] · [0] กลืน High[1] → BUY"},
            {"title": "Pattern A — SELL (สลับสี)", "desc": "[2]เขียว → [1]แดงกลืน Close&lt;Low[2]−gap → [0]แดงกลืน Close&lt;Low[1]−gap",
             "candles": [_c(100, 104.8, 99.4, 104.4, "[2]"), _c(104.4, 104.7, 98.8, 99.2, "[1]"), _c(99.2, 99.6, 95.8, 96.2, "[0]")],
             "refs": [{"p": 99.2, "c": ENTRY, "t": "Entry"}, {"p": 104.8, "c": SL, "t": "SL"}, {"p": 93, "c": TP, "t": "TP"}],
             "band": None, "note": "[1] กลืน Low[2] · [0] กลืน Low[1] → SELL"},
            {"title": "Pattern B — ตำหนิ + กลืนกลับ (BUY)", "desc": "[2]แดง → [1]เขียว 'ตำหนิ' (ไส้กินเข้า zone [2]) body≥35% → [0]เขียวกลืน [1]",
             "candles": [_c(104, 104.5, 100.5, 101, "[2]"), _c(101, 103, 100.8, 102.6, "[1]"), _c(102.6, 106.5, 102.2, 106, "[0]")],
             "refs": [{"p": 102.6, "c": ENTRY, "t": "Entry"}, {"p": 100.5, "c": SL, "t": "SL"}, {"p": 110, "c": TP, "t": "TP"}],
             "band": None, "note": "[1] ตำหนิเข้า zone [2] → [0] เขียวกลืน [1]"},
            {"title": "Pattern E — แดง·แดง·เขียวกลืน (BUY)", "desc": "[2]แดง → [1]แดง → [0]เขียว Close&gt;High[1]+gap, body[0]≥35%",
             "candles": [_c(104, 104.4, 101, 101.4, "[2]"), _c(101.4, 101.8, 99, 99.4, "[1]"), _c(99.4, 104, 99.2, 103.6, "[0]")],
             "refs": [{"p": 99.4, "c": ENTRY, "t": "Entry"}, {"p": 99, "c": SL, "t": "SL"}, {"p": 107, "c": TP, "t": "TP"}],
             "band": None, "note": "2 แท่งแดง → [0] เขียวกลืน High[1] (P4/C ใช้ logic เฉพาะใน strategy1.py)"},
        ],
    },
    2: {
        "name": "ท่า 2 — FVG (Fair Value Gap)",
        "tag": "main-flow · ON",
        "doc": "หา Fair Value Gap ระหว่าง [2][1][0]. [1] ต้องกลืน [2] เกิน gap ขั้นต่ำ, [0] ต้องยังไม่ปิด gap. "
               "entry คำนวณจากด้านในของ gap. มีโหมด normal (ต้องเจอ S1/S2/S3 ย้อนหลัง) และ parallel.",
        "cfg": "ENGULF_MIN · S2_NORMAL_CONFIRM_LOOKBACK_BARS · pattern: กลืนกิน / ปฏิเสธราคา",
        "patterns": [
            {"title": "FVG — BUY", "desc": "[1]เขียว Close&gt;High[2]+gap · [0] ยังไม่ปิด gap (Low[0]&gt;High[2]) → entry ในช่อง gap",
             "candles": [_c(102, 102.5, 99.5, 100, "[2]"), _c(100, 106, 99.8, 105.5, "[1]"), _c(105.5, 107, 103.5, 106, "[0]")],
             "refs": [{"p": 103, "c": ENTRY, "t": "Entry"}, {"p": 99.5, "c": SL, "t": "SL"}, {"p": 110, "c": TP, "t": "TP"}],
             "band": {"from": 102.5, "to": 103.5, "c": "rgba(251,191,36,.18)"},
             "note": "แถบทอง = FVG (High[2]→Low[0]) · รอ retrace เข้า gap"},
            {"title": "FVG — SELL", "desc": "[1]แดง Close&lt;Low[2]−gap · [0] ยังไม่ปิด gap (High[0]&lt;Low[2]) → entry ในช่อง gap",
             "candles": [_c(100, 104.5, 99.5, 104, "[2]"), _c(104, 104.2, 98, 98.5, "[1]"), _c(98.5, 100.5, 97, 98, "[0]")],
             "refs": [{"p": 101, "c": ENTRY, "t": "Entry"}, {"p": 104.5, "c": SL, "t": "SL"}, {"p": 94, "c": TP, "t": "TP"}],
             "band": {"from": 100.5, "to": 99.5, "c": "rgba(251,191,36,.18)"},
             "note": "แถบทอง = FVG (Low[2]→High[0]) · รอ retrace เข้า gap"},
            {"title": "ปฏิเสธราคา (BUY) — รับได้ทั้งแท่งเขียว/แดง", "desc": "[0] ไส้ล่างยาวปฏิเสธราคาในช่อง gap (cancel_bars=1 ถ้าไม่ fill ใน 1 แท่ง)",
             "candles": [_c(102, 102.5, 99.5, 100, "[2]"), _c(100, 106, 99.8, 105.5, "[1]"), _c(105.5, 106, 103.2, 105, "[0]")],
             "refs": [{"p": 103.3, "c": ENTRY, "t": "Entry"}, {"p": 99.5, "c": SL, "t": "SL"}, {"p": 109, "c": TP, "t": "TP"}],
             "band": {"from": 102.5, "to": 103.5, "c": "rgba(251,191,36,.18)"},
             "note": "[0] ไส้ล่างยาว (ปฏิเสธ) แต่ไม่ปิด gap → ตั้ง limit ในช่อง"},
        ],
    },
    3: {
        "name": "ท่า 3 — DM / SP / Marubozu",
        "tag": "main-flow · ON",
        "doc": "3 แท่ง: [2] body ชัด → [1] พัก → [0] กลืนกลับ. ใช้ engulf_min_price() เป็น gap. "
               "ย้อนดู S1/S2/S3 ฝั่งเดียวกัน 8 แท่งก่อนเข้า.",
        "cfg": "Marubozu / No-Engulf → WAIT (marubozu_pending) รอแท่งถัดไป confirm",
        "patterns": [
            {"title": "DM/SP — BUY", "desc": "[2]เขียว body≥35% → [1]แดง/doji → [0]เขียว Close&gt;High[1]+gap",
             "candles": [_c(100, 104.5, 99.8, 104, "[2]"), _c(104, 104.3, 101.5, 102, "[1]"), _c(102, 107, 101.8, 106.5, "[0]")],
             "refs": [{"p": 106.5, "c": ENTRY, "t": "Entry"}, {"p": 101.5, "c": SL, "t": "SL"}, {"p": 112, "c": TP, "t": "TP"}],
             "band": None, "note": "[2]แรง → [1]พัก → [0]กลืนกลับ Close&gt;High[1]"},
            {"title": "DM/SP — SELL", "desc": "[2]แดง body≥35% → [1]เขียว/doji → [0]แดง Close&lt;Low[1]−gap",
             "candles": [_c(104, 104.2, 99.5, 100, "[2]"), _c(100, 102.5, 99.7, 102, "[1]"), _c(102, 102.2, 97, 97.5, "[0]")],
             "refs": [{"p": 97.5, "c": ENTRY, "t": "Entry"}, {"p": 102.5, "c": SL, "t": "SL"}, {"p": 92, "c": TP, "t": "TP"}],
             "band": None, "note": "[2]แรง → [1]พัก → [0]กลืนกลับ Close&lt;Low[1]"},
            {"title": "Marubozu Pending (BUY)", "desc": "[0] เป็น marubozu (ไม่มีไส้) → WAIT เก็บ marubozu_pending → รอแท่งถัดไป confirm เขียว",
             "candles": [_c(100, 104.5, 99.8, 104, "[2]"), _c(104, 104.3, 101.5, 102, "[1]"), _c(102, 106.5, 101.9, 106.4, "[0]")],
             "refs": [{"p": 106.5, "c": ENTRY, "t": "Entry (รอ)"}, {"p": 101.5, "c": SL, "t": "SL"}],
             "band": None, "note": "[0] marubozu → ยังไม่เข้า รอแท่งถัดไปยืนยันทิศ"},
        ],
    },
    4: {
        "name": "ท่า 4 — นัยยะสำคัญ FVG",
        "tag": "main-flow · ON",
        "doc": "FVG ที่ <b>กลืน swing สำคัญจริง</b> ไม่ใช่ gap ธรรมดา. Close[1] ต้องปิดทะลุ swing เดิม "
               "และห่าง ≥ engulf_min_price(), swing ที่กลืนต้องอยู่ 'ใน gap'.",
        "cfg": "swing high/low ใช้ต่อเป็นฐานของท่า 8",
        "patterns": [
            {"title": "นัยยะ FVG — BUY", "desc": "[1]เขียว High[1]&gt;High[2] · Close[1] ปิดเหนือ Swing High เดิม · [0]ยังไม่ปิด gap",
             "candles": [_c(101, 101.8, 99, 99.3, "[2]"), _c(99.3, 106.5, 99.2, 106, "[1]"), _c(106, 107.5, 104, 106.8, "[0]")],
             "refs": [{"p": 103.5, "c": ENTRY, "t": "Entry"}, {"p": 99, "c": SL, "t": "SL"}, {"p": 112, "c": TP, "t": "TP"}, {"p": 102.5, "c": ZONE, "t": "Swing"}],
             "band": {"from": 101.8, "to": 104, "c": "rgba(251,191,36,.16)"},
             "note": "Close[1] ทะลุ Swing (ม่วง) ที่อยู่ในช่อง FVG → BUY"},
            {"title": "นัยยะ FVG — SELL", "desc": "[1]แดง Low[1]&lt;Low[2] · Close[1] ปิดใต้ Swing Low เดิม · [0]ยังไม่ปิด gap",
             "candles": [_c(99, 101, 98.2, 100.7, "[2]"), _c(100.7, 100.8, 93.5, 94, "[1]"), _c(94, 96, 92.5, 93.2, "[0]")],
             "refs": [{"p": 96.8, "c": ENTRY, "t": "Entry"}, {"p": 101, "c": SL, "t": "SL"}, {"p": 88, "c": TP, "t": "TP"}, {"p": 97, "c": ZONE, "t": "Swing"}],
             "band": {"from": 98.2, "to": 96, "c": "rgba(251,191,36,.16)"},
             "note": "Close[1] ทะลุ Swing Low (ม่วง) ในช่อง FVG → SELL"},
        ],
    },
    5: {
        "name": "ท่า 5 — Scalping (Momentum + Reversal)",
        "tag": "main-flow · OFF · M1/M5/M15",
        "doc": "Scalping 3 แท่ง 2 รูปแบบ (Momentum/Reversal) กรอง 4 ชั้น: <b>Time / ATR / EMA20 / Zone</b>.",
        "cfg": "S5_ATR_MAX_MULT 2.5 · S5_ZONE_BUFFER 1.5 · S5_TREND_BARS 20 · no-trade 00-03",
        "patterns": [
            {"title": "Momentum — BUY", "desc": "[1]เขียว body≥60% → [0]เขียว Open≥Close[1]−atr×0.1",
             "candles": [_c(100.5, 101, 100.2, 100.6, "[2]"), _c(100.6, 103.2, 100.4, 103, "[1]"), _c(103, 104.5, 102.9, 104.2, "[0]")],
             "refs": [{"p": 103, "c": ENTRY, "t": "Entry"}, {"p": 102.4, "c": SL, "t": "SL"}, {"p": 105, "c": TP, "t": "TP"}],
             "band": None, "note": "[1] โมเมนตัมแรง → [0] ต่อทิศ → entry = Open[0]"},
            {"title": "Reversal — BUY", "desc": "[2]แดง≥35% → [1]Doji/ตำหนิ → [0]เขียว≥35% Close&gt;High[1]",
             "candles": [_c(105, 105.3, 101, 101.3, "[2]"), _c(101.3, 101.8, 100.6, 101.1, "[1]"), _c(101.1, 104.5, 100.9, 104, "[0]")],
             "refs": [{"p": 101.4, "c": ENTRY, "t": "Entry"}, {"p": 100.4, "c": SL, "t": "SL"}, {"p": 106, "c": TP, "t": "TP"}],
             "band": None, "note": "[1] Doji เล็ก → [0] เขียวยืนยัน Close&gt;High[1]"},
            {"title": "Reversal — SELL", "desc": "[2]เขียว≥35% → [1]Doji/ตำหนิ → [0]แดง≥35% Close&lt;Low[1]",
             "candles": [_c(99, 103, 98.7, 102.7, "[2]"), _c(102.7, 103.4, 102.2, 102.9, "[1]"), _c(102.9, 103.1, 99.5, 100, "[0]")],
             "refs": [{"p": 102.6, "c": ENTRY, "t": "Entry"}, {"p": 103.6, "c": SL, "t": "SL"}, {"p": 98, "c": TP, "t": "TP"}],
             "band": None, "note": "[1] Doji → [0] แดงยืนยัน Close&lt;Low[1]"},
        ],
    },
    6: {"name": "ท่า 6 / 7 — S6 trail + S6i swing", "tag": "management (ไม่ใช่ pattern เข้า)",
        "doc": "State machine จัดการ position ที่ถือไว้: ดูสัญญาณท่า 1 ฝั่งตรงข้ามเพื่อปรับ TP / ปิด / ตั้งไม้สวน. "
               "S6i เป็น swing logic อิสระ.", "cfg": "อยู่ใน trailing.py · ดู docs/strategies/s6.md", "patterns": []},
    8: {
        "name": "ท่า 8 — กินไส้ Swing",
        "tag": "main-flow · OFF (เปิดรายตัว)",
        "doc": "ตั้ง limit 2 ฝั่งที่ขอบ swing. SELL: Entry=High+17%, SL=High+31%, TP=Swing Low. BUY สลับ.",
        "cfg": "swing จาก strategy4.py · ระวัง LL/HH จาก Limit Sweep",
        "patterns": [
            {"title": "กินไส้ Swing — BUY (ที่ Swing Low)", "desc": "Entry=Low−17%·range · SL=Low−31%·range · TP=Swing High",
             "candles": [_c(105, 105.5, 101, 101.5, "[2]"), _c(101.5, 102, 99.5, 100, "[1]"), _c(100, 101, 99.2, 100.8, "[0]")],
             "refs": [{"p": 99.4, "c": ENTRY, "t": "Entry"}, {"p": 98.5, "c": SL, "t": "SL"}, {"p": 105, "c": TP, "t": "TP (Swing H)"}, {"p": 99.5, "c": ZONE, "t": "Swing L"}],
             "band": None, "note": "limit ใต้ Swing Low เผื่อราคามากินไส้แล้วเด้ง"},
            {"title": "กินไส้ Swing — SELL (ที่ Swing High)", "desc": "Entry=High+17%·range · SL=High+31%·range · TP=Swing Low",
             "candles": [_c(101, 104.5, 100.5, 104, "[2]"), _c(104, 105.5, 103.2, 104.6, "[1]"), _c(104.6, 105.2, 103.8, 104.3, "[0]")],
             "refs": [{"p": 106, "c": ENTRY, "t": "Entry"}, {"p": 106.8, "c": SL, "t": "SL"}, {"p": 100, "c": TP, "t": "TP (Swing L)"}, {"p": 105.5, "c": ZONE, "t": "Swing H"}],
             "band": None, "note": "limit เหนือ Swing High เผื่อราคามากินไส้แล้วเด้งลง"},
        ],
    },
    9: {
        "name": "ท่า 9 — RSI Divergence",
        "tag": "standalone · ON · sync RSIDivergencePane.mq5",
        "doc": "pivot RSI (immediate previous). <b>Regular Bullish</b>: price LL + RSI HL → BUY. "
               "เจอแล้วตั้ง LIMIT @ midpoint ของแท่ง pivot ปัจจุบัน.",
        "cfg": "RSI9_PERIOD/LEFT/RIGHT/RANGE_MIN/MAX · 4 types (Regular/Hidden)",
        "patterns": [
            {"title": "Regular Bullish Divergence — BUY", "desc": "ราคาทำ Lower Low แต่ RSI ทำ Higher Low → LIMIT @ midpoint แท่ง pivot",
             "candles": [_c(102, 102.5, 98, 98.5, "p1"), _c(98.5, 100, 98.2, 99.5, "·"), _c(99.5, 100.2, 96.5, 97, "p2")],
             "refs": [{"p": 98.35, "c": ENTRY, "t": "Entry mid"}, {"p": 96.5, "c": SL, "t": "SL"}, {"p": 103, "c": TP, "t": "TP"}],
             "band": None, "note": "price LL (p2&lt;p1) + RSI HL = bullish divergence → BUY LIMIT"},
            {"title": "Regular Bearish — SELL", "desc": "ราคาทำ Higher High แต่ RSI ทำ Lower High → SELL LIMIT @ midpoint",
             "candles": [_c(98, 102, 97.5, 101.5, "p1"), _c(101.5, 101.8, 100, 100.5, "·"), _c(100.5, 103.5, 100.3, 103, "p2")],
             "refs": [{"p": 101.9, "c": ENTRY, "t": "Entry mid"}, {"p": 103.5, "c": SL, "t": "SL"}, {"p": 96, "c": TP, "t": "TP"}],
             "band": None, "note": "price HH (p2&gt;p1) + RSI LH → SELL LIMIT"},
            {"title": "Hidden Bullish — BUY (default OFF)", "desc": "ราคาทำ Higher Low แต่ RSI ทำ Lower Low (ตามเทรนด์ขึ้น) → BUY",
             "candles": [_c(99, 102, 98.5, 99.2, "p1"), _c(99.2, 101, 99, 100.5, "·"), _c(100.5, 101.5, 99.6, 100, "p2")],
             "refs": [{"p": 100.55, "c": ENTRY, "t": "Entry mid"}, {"p": 99.6, "c": SL, "t": "SL"}, {"p": 104, "c": TP, "t": "TP"}],
             "band": None, "note": "price HL (p2&gt;p1) + RSI LL = hidden bullish"},
        ],
    },
    10: {"name": "ท่า 10 — CRT TBS", "tag": "standalone · ON",
         "doc": "liquidity sweep + 3-bar. HTF mode = market ทันที, MTF mode = LTF confirmation (Phase1 failed-push → Phase2 engulf → Model OB/FVG).",
         "cfg": "CRT_BAR_MODE 2bar/3bar · CRT_ENTRY_MODE htf/mtf · ดู docs/strategies/s10.md",
         "patterns": [
            {"title": "HTF Sweep — BUY (Model 2, market)", "desc": "[1] ไส้ sweep ใต้ parent low แล้วปิดกลับ → [0] ยืนยัน → market BUY ทันที",
             "candles": [_c(100, 104, 99, 103, "[2]"), _c(103, 103.5, 97, 102.5, "[1]"), _c(102.5, 105, 102, 104.5, "[0]")],
             "refs": [{"p": 99, "c": ZONE, "t": "parent low"}, {"p": 104.5, "c": ENTRY, "t": "Entry"}, {"p": 97, "c": SL, "t": "SL"}, {"p": 108, "c": TP, "t": "TP"}],
             "band": None, "note": "[1] sweep parent low (97&lt;99) ปิดกลับ → market BUY"},
            {"title": "MTF Model 1 — Order Block (BUY limit)", "desc": "Phase1 failed-push (close&lt;parent.low) → engulf → LIMIT ที่ Order Block",
             "candles": [_c(101, 101.5, 98, 98.3, "[2]"), _c(98.3, 101.5, 98, 101.2, "[1]"), _c(101.2, 101.5, 100.8, 101, "[0]")],
             "refs": [{"p": 99.2, "c": ENTRY, "t": "Entry OB"}, {"p": 97, "c": SL, "t": "SL"}, {"p": 105, "c": TP, "t": "TP"}],
             "band": None, "note": "failed-push → engulf → LIMIT ที่ OB.open"}
         ]},
    11: {"name": "ท่า 11 — Fibo S1", "tag": "hook S1 · OFF",
         "doc": "Hook ติด S1: เมื่อ S1 fire → ลง anchor → ตี Fibo → รอ wick แตะ KRH1/KRH2/KRH3 → ตั้ง LIMIT @ 50%.",
         "cfg": "TP=7.044 · SL=−0.31 · ดู docs/strategies/s11.md",
         "patterns": [
            {"title": "Pattern 1 — แตะ KRH1 → LIMIT @ 50% (BUY)", "desc": "S1 fire → ลง anchor → ตี Fibo → wick แตะ KRH1 (1.617) → ตั้ง LIMIT ที่ Fibo 50%",
             "candles": [_c(100, 101, 99.5, 100.8, "[2]"), _c(100.8, 103, 100.5, 102.5, "[1]"), _c(102.5, 106.2, 102, 104, "[0]")],
             "refs": [{"p": 106, "c": ZONE, "t": "KRH1"}, {"p": 103, "c": ENTRY, "t": "Entry 50%"}, {"p": 99, "c": SL, "t": "SL −0.31"}, {"p": 110, "c": TP, "t": "TP 7.044"}],
             "band": None, "note": "wick [0] แตะ KRH1 (106) → LIMIT ที่ Fibo 50% (103)"}
         ]},
    12: {"name": "ท่า 12 — Range Trading", "tag": "standalone · ON",
         "doc": "หา range จาก pivot swing M5 → buy zone (ใกล้ low) / sell zone (ใกล้ high) → limit หลายชั้น. cooldown 30 นาทีหลัง SL.",
         "cfg": "S12_ORDER_COUNT · S12_COOLDOWN_SECS · ดู docs/strategies/s12.md",
         "patterns": [
            {"title": "Range — BUY zone (ใกล้ range low)", "desc": "ราคาในกรอบ range → ตั้ง limit หลายชั้นใน buy zone (ใกล้ swing low), TP ที่ range high",
             "candles": [_c(102, 103, 101, 101.5, "[3]"), _c(101.5, 102, 100.2, 100.5, "[2]"), _c(100.5, 101, 100, 100.8, "[1]"), _c(100.8, 101.5, 100.3, 101.2, "[0]")],
             "refs": [{"p": 103, "c": ZONE, "t": "range high"}, {"p": 100, "c": ZONE, "t": "range low"}, {"p": 100.3, "c": ENTRY, "t": "Entry"}, {"p": 99, "c": SL, "t": "SL"}, {"p": 103, "c": TP, "t": "TP"}],
             "band": None, "note": "limit ใน buy zone (ใกล้ range low) · TP ที่ range high"}
         ]},
    13: {"name": "ท่า 13 — EzAlgo V5", "tag": "standalone · OFF",
         "doc": "supertrend crossover → mix market/limit ตาม current price vs entry. TP1/2/3 = 0.7R/1.2R/1.5R. TSO 4 orders แยก.",
         "cfg": "S13_SUPERTREND_ATR · S13_STOP_ATR_MULT · ดู docs/strategies/s13.md",
         "patterns": [
            {"title": "Supertrend Cross — BUY", "desc": "close ตัดขึ้นเหนือเส้น supertrend → BUY (TP1/2/3 = 0.7R/1.2R/1.5R)",
             "candles": [_c(101, 101.5, 99, 99.5, "[2]"), _c(99.5, 101, 99, 100.8, "[1]"), _c(100.8, 103, 100.5, 102.5, "[0]")],
             "refs": [{"p": 100.5, "c": ZONE, "t": "Supertrend"}, {"p": 102.5, "c": ENTRY, "t": "Entry"}, {"p": 98.5, "c": SL, "t": "SL"}, {"p": 108.5, "c": TP, "t": "TP3"}],
             "band": None, "note": "[0] close ตัดขึ้นเหนือ supertrend → BUY"},
            {"title": "Supertrend Cross — SELL", "desc": "close ตัดลงใต้เส้น supertrend → SELL",
             "candles": [_c(99, 101, 98.5, 100.5, "[2]"), _c(100.5, 101, 99, 99.2, "[1]"), _c(99.2, 99.5, 97, 97.5, "[0]")],
             "refs": [{"p": 99.5, "c": ZONE, "t": "Supertrend"}, {"p": 97.5, "c": ENTRY, "t": "Entry"}, {"p": 101.5, "c": SL, "t": "SL"}, {"p": 91.5, "c": TP, "t": "TP3"}],
             "band": None, "note": "[0] close ตัดลงใต้ supertrend → SELL"}
         ]},
    14: {
        "name": "ท่า 14 — Sweep RSI",
        "tag": "standalone · OFF · market",
        "doc": "หา LL/HH zone จาก RSI ย้อนหลัง. <b>Sweep (BUY)</b>: ไส้ทะลุ LL zone แต่ปิดกลับเหนือ → market ทันที.",
        "cfg": "S14_REVERSAL_LOOKBACK 50 · Flip ปิดฝั่งตรงข้ามก่อน",
        "patterns": [
            {"title": "Sweep — BUY (rejection wick)", "desc": "ไส้ [0] ทะลุ LL zone แต่ปิดกลับเหนือ zone (rejection)",
             "candles": [_c(101.2, 101.6, 100.4, 100.7, "[2]"), _c(100.7, 101, 99.3, 99.6, "[1]"), _c(99.6, 101.9, 98.2, 101.6, "[0]")],
             "refs": [{"p": 100, "c": ZONE, "t": "LL zone"}, {"p": 101.6, "c": ENTRY, "t": "Entry"}, {"p": 98.2, "c": SL, "t": "SL"}, {"p": 105, "c": TP, "t": "TP"}],
             "band": None, "note": "[0] ไส้ทะลุ LL (98.2) แต่ปิดกลับเหนือ → Sweep BUY"},
            {"title": "Engulf — BUY", "desc": "[0] close ทะลุ LL zone ลงไป (engulf)",
             "candles": [_c(101.2, 101.5, 100.4, 100.7, "[2]"), _c(100.7, 101, 99.8, 99.9, "[1]"), _c(99.9, 100.1, 98.5, 98.7, "[0]")],
             "refs": [{"p": 100, "c": ZONE, "t": "LL zone"}, {"p": 98.7, "c": ENTRY, "t": "Entry"}, {"p": 97.8, "c": SL, "t": "SL"}, {"p": 102, "c": TP, "t": "TP"}],
             "band": None, "note": "[0] close ทะลุ LL zone → Engulf BUY"},
        ],
    },
    15: {
        "name": "ท่า 15 — Volume Profile POC + Absorption",
        "tag": "standalone · OFF",
        "doc": "คำนวณ VP จาก tick_volume → POC/VAH/VAL. ตรวจ Absorption ที่โซน → LIMIT ที่ POC/VAL (BUY) หรือ POC/VAH (SELL).",
        "cfg": "S15_LOOKBACK · S15_VAL_VAH_PCT 70% · รองรับ MULTI",
        "patterns": [
            {"title": "Absorption ที่ VAL — BUY", "desc": "ราคาลงทดสอบ VAL แล้วถูกดูดซับ (long wick/2-bar reversal) → LIMIT ที่ VAL",
             "candles": [_c(103, 103.4, 101.5, 101.8, "[2]"), _c(101.8, 102, 99.8, 100.2, "[1]"), _c(100.2, 102.5, 99.9, 102.2, "[0]")],
             "refs": [{"p": 100, "c": ZONE, "t": "VAL"}, {"p": 103, "c": ZONE, "t": "POC"}, {"p": 100.1, "c": ENTRY, "t": "Entry"}, {"p": 99, "c": SL, "t": "SL"}, {"p": 103, "c": TP, "t": "TP→POC"}],
             "band": None, "note": "ทดสอบ VAL แล้วเด้ง (absorption) → BUY ที่ VAL, TP ที่ POC"},
            {"title": "Absorption ที่ VAH — SELL", "desc": "ราคาขึ้นทดสอบ VAH แล้วถูกดูดซับ (long wick/2-bar reversal) → LIMIT ที่ VAH",
             "candles": [_c(98, 100.2, 97.5, 100, "[2]"), _c(100, 102.2, 99.8, 101.8, "[1]"), _c(101.8, 102, 99.5, 99.8, "[0]")],
             "refs": [{"p": 102, "c": ZONE, "t": "VAH"}, {"p": 99, "c": ZONE, "t": "POC"}, {"p": 101.9, "c": ENTRY, "t": "Entry"}, {"p": 103, "c": SL, "t": "SL"}, {"p": 99, "c": TP, "t": "TP→POC"}],
             "band": None, "note": "ทดสอบ VAH แล้วถูกดูดซับ → SELL ที่ VAH, TP ที่ POC"},
        ],
    },
    16: {"name": "ท่า 16 — AMD x iFVG", "tag": "standalone · OFF · M1",
         "doc": "Asian Range (08-12 BKK) → killzone sweep Asian high/low → Inversion FVG เป็น entry zone. (default OFF — order จริงติดลบ)",
         "cfg": "S16_KILLZONES · S16_KZ_ONE_SHOT · ดู docs/strategies/s16.md",
         "patterns": [
            {"title": "AMD x iFVG — BUY", "desc": "killzone sweep Asian Low → ปิดกลับผ่าน FVG → iFVG (inversion) เป็น entry zone",
             "candles": [_c(100, 100.5, 98, 98.3, "[2]"), _c(98.3, 101.5, 98.2, 101.2, "[1]"), _c(101.2, 101.5, 100, 100.5, "[0]")],
             "refs": [{"p": 99, "c": ZONE, "t": "Asian Low"}, {"p": 100.3, "c": ENTRY, "t": "Entry iFVG"}, {"p": 98, "c": SL, "t": "SL"}, {"p": 103, "c": TP, "t": "TP"}],
             "band": None, "note": "sweep Asian Low → ปิดผ่าน FVG → iFVG = entry (BUY)"}
         ]},
    17: {
        "name": "ท่า 17 — Sweep Sniper",
        "tag": "standalone · OFF · M1",
        "doc": "4 ชั้น: liquidity sweep (เปิดในกรอบ+ปิดกลับ) + wick≥30% + RSI≤32 + PD Discount. "
               "Entry LIMIT retrace 61.8% · TP สั้น 0.3×ATR (WR สูงแต่ RR ต่ำ).",
        "cfg": "S17_LOOKBACK 60 · S17_TP_ATR_MULT 0.3 · M1 เท่านั้น",
        "patterns": [
            {"title": "Sweep Sniper — BUY", "desc": "ไส้ sweep ลึกทะลุ low กรอบ แต่ปิดกลับ → LIMIT รอ retrace 61.8% ของแท่ง sweep",
             "candles": [_c(101, 101.2, 100.6, 100.8, "[2]"), _c(100.8, 101, 99, 100.6, "[1]"), _c(100.6, 100.9, 97.8, 100.5, "[0]")],
             "refs": [{"p": 98.9, "c": ENTRY, "t": "Entry 61.8%"}, {"p": 97.3, "c": SL, "t": "SL"}, {"p": 99.4, "c": TP, "t": "TP (สั้น)"}],
             "band": None, "note": "ไส้ sweep ลึก (97.8) ปิดกลับ → LIMIT retrace 61.8%"},
        ],
    },
    18: {"name": "ท่า 18 — TJR / ICT Full-Confluence", "tag": "standalone · OFF",
         "doc": "7 ชั้น: Killzone → HTF Bias → Liquidity Sweep → MSS → Entry ใน FVG/OB ใน OTE 62-79% → RSI → RR. Entry LIMIT.",
         "cfg": "S18_SESSIONS · S18_OTE_LO/HI · ดู docs/strategies/s18.md",
         "patterns": [
            {"title": "TJR Confluence — BUY", "desc": "sweep swing low → MSS (close ทะลุ structure) → retrace เข้า FVG/OB ใน OTE 62-79%",
             "candles": [_c(101, 101.5, 97.8, 100.5, "[3]"), _c(100.5, 103.5, 100.2, 103.2, "[2]"), _c(103.2, 103.5, 101, 101.3, "[1]"), _c(101.3, 102, 100.8, 101.8, "[0]")],
             "refs": [{"p": 103, "c": ZONE, "t": "MSS"}, {"p": 101.5, "c": ENTRY, "t": "Entry"}, {"p": 97.8, "c": SL, "t": "SL"}, {"p": 107, "c": TP, "t": "TP"}],
             "band": {"from": 101, "to": 102.2, "c": "rgba(251,191,36,.16)"},
             "note": "sweep → MSS → entry ในแถบ OTE 62-79% (ทอง)"}
         ]},
    19: {"name": "ท่า 19 — ICT Advanced (Silver Bullet + Breaker + BPR)", "tag": "standalone · OFF",
         "doc": "ต่อยอด S18: Silver Bullet window แคบ + Power of 3 + Breaker/BPR/FVG ใน OTE + NDOG เป็น TP.",
         "cfg": "S19_SILVER_BULLET_SESSIONS · S19_ZONE_PREFER · ดู docs/strategies/s19.md",
         "patterns": [
            {"title": "Silver Bullet — BUY", "desc": "ใน Silver Bullet window: sweep (Power of 3) → MSS → entry ที่ Breaker/BPR/FVG ใน OTE, TP=NDOG",
             "candles": [_c(101, 101.3, 98, 100.6, "[3]"), _c(100.6, 103.2, 100.3, 103, "[2]"), _c(103, 103.2, 101.2, 101.5, "[1]"), _c(101.5, 102, 101, 101.7, "[0]")],
             "refs": [{"p": 103, "c": ZONE, "t": "MSS"}, {"p": 101.4, "c": ENTRY, "t": "Entry Breaker"}, {"p": 98, "c": SL, "t": "SL"}, {"p": 106, "c": TP, "t": "TP NDOG"}],
             "band": {"from": 101, "to": 102.2, "c": "rgba(251,191,36,.16)"},
             "note": "Silver Bullet + P3 → Breaker/BPR ใน OTE → TP ที่ NDOG"}
         ]},
}
