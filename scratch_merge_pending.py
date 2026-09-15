# -*- coding: utf-8 -*-
"""ใช้ mt5.order_send() ตรงๆ (raw connection เดียวกับที่ query orders) แทนการ
เรียก mt5_utils.open_order() เพราะ open_order() พึ่ง mt5_worker.py (subprocess
worker ของบอทตัวจริง) ซึ่งใช้ multiprocessing.spawn — เรียกจากสคริปต์เดี่ยวๆ
แบบนี้ชนปัญหา "bootstrapping phase" (ต้องมี if __name__=='__main__' guard และ
ยังเสี่ยงชนกับ connection ของบอทจริงที่รันอยู่คู่กันด้วย) เลยเลี่ยงไปส่ง
order_send() เองตรงๆ แทน (payload เดียวกับที่ open_order() ส่งจริง)"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "strategy", "s20.14"))

import config
import MetaTrader5 as mt5
import s20_14_merge as m


def parse_tf(comment):
    return comment.split("_S", 1)[0] if "_S" in comment else comment


def parse_group_label(comment):
    if "_S20." not in comment:
        return None
    after = comment.split("_S20.", 1)[1]
    digits = after.split("_", 1)[0]
    try:
        sid_val = float(f"20.{digits}")
    except ValueError:
        return None
    return m.S20_14_SID_GROUP.get(sid_val)


def main():
    ok = config.mt5_initialize(mt5)
    assert ok, "mt5 init failed"
    SYMBOL = config.resolve_mt5_symbol(mt5, "XAUUSD", set_runtime=False)

    orders = mt5.orders_get(symbol=SYMBOL)
    print(f"pending ก่อนแก้: {len(orders)}")

    items = []
    for o in orders:
        label = parse_group_label(o.comment)
        if label is None:
            continue
        sig = "BUY" if o.type in (mt5.ORDER_TYPE_BUY_LIMIT, mt5.ORDER_TYPE_BUY_STOP) else "SELL"
        items.append({
            "ticket": o.ticket, "comment": o.comment, "tf": parse_tf(o.comment),
            "signal": sig, "entry": o.price_open, "sl": o.sl, "tp": o.tp,
            "volume": o.volume_initial, "label": label,
        })

    used = [False] * len(items)
    clusters = []
    for i in range(len(items)):
        if used[i]:
            continue
        cluster = [i]
        for j in range(i + 1, len(items)):
            if used[j]:
                continue
            a, b = items[i], items[j]
            if a["tf"] != b["tf"] or a["signal"] != b["signal"]:
                continue
            if not (m.same_price(a["entry"], b["entry"]) and m.same_price(a["sl"], b["sl"]) and m.same_price(a["tp"], b["tp"])):
                continue
            cluster.append(j)
        for idx in cluster:
            used[idx] = True
        if len(cluster) > 1:
            clusters.append(cluster)

    print(f"เจอ {len(clusters)} กลุ่มที่ควรรวม (รวม {sum(len(c) for c in clusters)} ไม้ -> เหลือ {len(clusters)} ไม้)")

    tick = mt5.symbol_info_tick(SYMBOL)
    bid, ask = float(tick.bid), float(tick.ask)
    info = mt5.symbol_info(SYMBOL)
    point = float(info.point) if info and getattr(info, "point", 0) else 0.01
    tol = max(point * 2.0, 0.01)
    magic = int(getattr(config, "MAGIC_NUMBER", 234001) or 234001)

    total_placed = total_cancelled = total_failed = 0
    for c in clusters:
        rows = [items[i] for i in c]
        labels = sorted((r["label"] for r in rows), key=int)
        total_vol = round(sum(r["volume"] for r in rows), 2)
        ref = rows[0]
        tf_name, signal, entry, sl, tp = ref["tf"], ref["signal"], ref["entry"], ref["sl"], ref["tp"]
        comment = m.build_merge_comment(tf_name, labels)

        print(f"\n[{tf_name}] {signal} entry={entry} sl={sl} tp={tp} รวม group {labels} lot={total_vol} comment={comment}")

        current = ask if signal == "BUY" else bid
        if signal == "BUY" and entry >= current - tol:
            print(f"  ⏭️ ข้าม: entry ผ่านราคาปัจจุบันไปแล้ว (ask={current})")
            total_failed += 1
            continue
        if signal == "SELL" and entry <= current + tol:
            print(f"  ⏭️ ข้าม: entry ผ่านราคาปัจจุบันไปแล้ว (bid={current})")
            total_failed += 1
            continue

        # บัญชีติด limit_orders cap (50/50 เต็มพอดี) — วางใหม่ก่อนไม่ได้เพราะ
        # ไม่มีที่ว่าง ต้องยกเลิกของเดิมส่วนเกินก่อน (เหลือไว้ 1 ตัวกันไม่ให้
        # setup นี้หายไปเลยถ้าวางใหม่พลาด) แล้วค่อยวางตัวรวม สุดท้ายค่อยยกเลิก
        # ตัวที่เหลือทีหลังเมื่อวางใหม่สำเร็จแล้วเท่านั้น
        keep_ticket_row = rows[0]
        extra_rows = rows[1:]
        for row in extra_rows:
            rc = mt5.order_send({"action": mt5.TRADE_ACTION_REMOVE, "order": row["ticket"]})
            ok_cancel = rc is not None and rc.retcode == mt5.TRADE_RETCODE_DONE
            print(f"    {'✅' if ok_cancel else '❌'} ยกเลิกส่วนเกินก่อน ticket={row['ticket']} ({row['comment']})")
            if ok_cancel:
                total_cancelled += 1

        ot = mt5.ORDER_TYPE_BUY_LIMIT if signal == "BUY" else mt5.ORDER_TYPE_SELL_LIMIT
        r = mt5.order_send({
            "action": mt5.TRADE_ACTION_PENDING,
            "symbol": SYMBOL,
            "volume": total_vol,
            "type": ot,
            "price": entry,
            "sl": sl,
            "tp": tp,
            "deviation": 20,
            "magic": magic,
            "comment": comment,
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_RETURN,
        })
        if r is None or r.retcode != mt5.TRADE_RETCODE_DONE:
            print(f"  ❌ วาง order รวมไม่สำเร็จ: retcode={getattr(r, 'retcode', None)} comment={getattr(r, 'comment', None)}"
                  f" — เก็บ ticket={keep_ticket_row['ticket']} ({keep_ticket_row['comment']}) ไว้ไม่รวม")
            total_failed += 1
            continue
        print(f"  ✅ วาง order รวมสำเร็จ ticket={r.order}")
        total_placed += 1
        rc = mt5.order_send({"action": mt5.TRADE_ACTION_REMOVE, "order": keep_ticket_row["ticket"]})
        ok_cancel = rc is not None and rc.retcode == mt5.TRADE_RETCODE_DONE
        print(f"    {'✅' if ok_cancel else '❌'} ยกเลิกตัวสุดท้าย ticket={keep_ticket_row['ticket']} ({keep_ticket_row['comment']})")
        if ok_cancel:
            total_cancelled += 1

    remaining = mt5.orders_get(symbol=SYMBOL)
    print(f"\n=== สรุป: วางใหม่สำเร็จ {total_placed} | ยกเลิกของเดิม {total_cancelled} | ล้มเหลว/ข้าม {total_failed} ===")
    print(f"pending หลังแก้: {len(remaining)}")
    mt5.shutdown()


if __name__ == "__main__":
    main()
