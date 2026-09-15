# -*- coding: utf-8 -*-
"""S20.14 merge — รวมสัญญาณของหลาย sub-group (S20.14 Group 1/2/5/9/12/13/14/
16/18/19/21/22/24) ที่ entry/sl/tp ตรงกัน (ในช่วง tolerance) เป็น order เดียว
เพิ่ม lot ตามจำนวน group ที่รวมกัน (base 0.01 ต่อ group) แทนที่จะวางซ้อนกัน
หลาย order ที่ระดับราคาเดียวกัน — กันไม่ให้ S20.14 กิน quota pending order ของ
บัญชี (broker cap เช่น limit_orders=50) จนท่าอื่น (S1-S19) วางไม่ได้

สองกรณีที่ต้องรองรับ (ตามที่พี่ระบุไว้):
  1) เจอพร้อมกันในสแกนรอบเดียวกัน (หลาย group คืน entry/sl/tp ตรงกันในลูป
     signal_results ของ scan_one_tf() รอบเดียว) → รวมเป็น order เดียวตรงๆ
     ก่อน placement เลย ไม่ต้องแตะ MT5 เพิ่ม
  2) เจอไม่พร้อมกัน (group A วาง pending ไปแล้วก่อนหน้า แล้ว group B มาเจอ
     entry/sl/tp เดียวกันในสแกนรอบหลัง) → ยกเลิก pending เดิมของ group A แล้ว
     วางใหม่เป็น order รวม (group ใหม่ขึ้นก่อน ตามด้วย group เดิม) พร้อม lot
     ที่เพิ่มขึ้น

Comment format: "{tf}_s20.14-{group1}-{group2}-..." (เช่น "M30_s20.14-2-14")
— เลขคือหมายเลข Group ตามชื่อฟังก์ชัน strategy_20_14_N ไม่ใช่ sid ทศนิยมเต็ม
(sid=20.142 → group "2", sid=20.1414 → group "14") เพื่อให้ comment สั้นพอ
สำหรับ MT5 (broker comment limit ~31 ตัวอักษร, เผื่อ margin ไว้ที่ ~28)
"""

from __future__ import annotations

MERGE_PREFIX = "s20.14-"
COMMENT_MAX_LEN = 28

# sid (ทศนิยม) ของแต่ละ Group ที่รองรับการรวม — ต้องตรงกับ tuple ใน scanner.py's
# signal_results loop เป๊ะ (Group 3/6/etc ไม่มีอยู่จริงในโค้ด ไม่ต้องใส่)
S20_14_GROUP_SID = {
    "1": 20.141, "2": 20.142, "5": 20.145, "9": 20.149, "12": 20.1412,
    "13": 20.1413, "14": 20.1414, "16": 20.1416, "18": 20.1418, "19": 20.1419,
    "21": 20.1421, "22": 20.1422, "23": 20.1423, "24": 20.1424,
}
S20_14_SID_GROUP = {v: k for k, v in S20_14_GROUP_SID.items()}


def same_price(a, b, tol=0.05):
    try:
        return abs(float(a) - float(b)) <= tol
    except (TypeError, ValueError):
        return False


def is_s20_14_sid(sid) -> bool:
    return sid in S20_14_SID_GROUP


def build_merge_comment(tf_name: str, labels: list) -> str:
    """คืน comment string — ถ้ายาวเกิน COMMENT_MAX_LEN จะตัด label ท้ายๆ ทิ้ง
    (เก็บ label ที่มาก่อนไว้ก่อน) กัน order_send ถูก broker reject เพราะ comment
    ยาวเกิน"""
    labels = list(labels)
    while labels:
        comment = f"{tf_name}_{MERGE_PREFIX}{'-'.join(labels)}"
        if len(comment) <= COMMENT_MAX_LEN:
            return comment
        labels.pop()
    return f"{tf_name}_{MERGE_PREFIX}x"[:COMMENT_MAX_LEN]


def parse_merge_comment(comment: str):
    """แยก comment ที่ build_merge_comment() สร้างไว้ กลับเป็น (tf_name, [labels])
    คืน (None, []) ถ้า comment นี้ไม่ใช่รูปแบบ merge ของเรา"""
    if not comment or MERGE_PREFIX not in comment:
        return None, []
    try:
        tf_part, rest = comment.split(f"_{MERGE_PREFIX}", 1)
    except ValueError:
        return None, []
    labels = [x for x in rest.split("-") if x]
    return tf_part, labels


def cluster_same_scan(signal_results):
    """รวมรายการใน signal_results (list ของ (sid, result_dict)) ที่เป็น S20.14
    group และมี signal/entry/sl/tp ตรงกัน (tol=0.05) ให้เหลือ 1 รายการต่อกลุ่ม
    — ไม่แตะรายการอื่น (sid ที่ไม่ใช่ S20.14) เลย

    ผลลัพธ์ที่ merge แล้วจะมี key เพิ่ม:
      "_s20_14_labels": ["2", "14"]   (เรียงจากเลข group น้อยไปมาก)
      "_s20_14_count":  2
    ใน result dict (ใช้คูณ lot และสร้าง comment ตอน placement)"""
    s20_items = [(sid, r) for sid, r in signal_results if is_s20_14_sid(sid)]
    other_items = [(sid, r) for sid, r in signal_results if not is_s20_14_sid(sid)]
    if len(s20_items) < 2:
        return signal_results

    n = len(s20_items)
    used = [False] * n
    merged = []
    for i in range(n):
        if used[i]:
            continue
        sid_i, r_i = s20_items[i]
        cluster = [i]
        for j in range(i + 1, n):
            if used[j]:
                continue
            sid_j, r_j = s20_items[j]
            if r_j.get("signal") != r_i.get("signal"):
                continue
            if not (same_price(r_i.get("entry"), r_j.get("entry"))
                    and same_price(r_i.get("sl"), r_j.get("sl"))
                    and same_price(r_i.get("tp"), r_j.get("tp"))):
                continue
            cluster.append(j)
        for idx in cluster:
            used[idx] = True

        if len(cluster) == 1:
            merged.append((sid_i, r_i))
            continue

        labels = sorted((S20_14_SID_GROUP[s20_items[k][0]] for k in cluster), key=int)
        base_sid, base_r = s20_items[cluster[0]]
        merged_r = dict(base_r)
        merged_r["_s20_14_labels"] = labels
        merged_r["_s20_14_count"] = len(labels)
        merged.append((base_sid, merged_r))

    return other_items + merged


def find_cross_cycle_match(mt5_mod, symbol, tf_name, signal, entry, sl, tp, exclude_ticket=None):
    """หา pending order เดิมที่วางไว้จากสแกนรอบก่อน (comment แบบ merge ของเรา)
    ที่ tf/signal ตรงกัน และ entry/tp ตรงกัน (tol=0.05) — คืน
    (ticket, tf_name, existing_labels) หรือ (None, None, []) ถ้าไม่เจอ

    ไม่เช็ก SL: กลุ่ม S20.14 คำนวณ SL จาก ATR ของแท่งที่ยังไม่ปิด ซึ่งขยับทุก
    สแกน (5s) เกิน tol=0.05 ได้ง่าย ถ้าเช็ก SL ด้วยจะทำให้ merge เดิมหาไม่เจอ
    ทุกรอบ กลายเป็นสร้าง merged order ใหม่ซ้ำๆ แทนที่จะอัปเดตตัวเดิม (เจอจริง
    2026-09-04 — ticket M15_s20.14-5-13-19-24 สามตัวค้างพร้อมกัน SL ต่างกัน
    0.16-0.20 เพราะ SL drift เกิน tolerance ทุกครั้งที่ลองจับคู่)"""
    want_types = (
        {mt5_mod.ORDER_TYPE_BUY_LIMIT, mt5_mod.ORDER_TYPE_BUY_STOP}
        if signal == "BUY"
        else {mt5_mod.ORDER_TYPE_SELL_LIMIT, mt5_mod.ORDER_TYPE_SELL_STOP}
    )
    orders = mt5_mod.orders_get(symbol=symbol) or []
    for order in orders:
        if exclude_ticket is not None and int(order.ticket) == int(exclude_ticket):
            continue
        if order.type not in want_types:
            continue
        comment = getattr(order, "comment", "") or ""
        order_tf, labels = parse_merge_comment(comment)
        if not order_tf or not labels:
            continue
        if order_tf != tf_name:
            continue
        if not same_price(getattr(order, "price_open", 0.0), entry):
            continue
        if not same_price(getattr(order, "tp", 0.0), tp):
            continue
        return order.ticket, order_tf, labels
    return None, None, []
