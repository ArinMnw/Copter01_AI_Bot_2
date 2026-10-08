# -*- coding: utf-8 -*-
"""scaffold.py — เขียนไฟล์ strategy/s20.<N>/strategy20_<N>.py จาก spec (ใช้โดย batch_*.py)"""
import os
import textwrap

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))

TEMPLATE = '''# -*- coding: utf-8 -*-
"""S20.{n} — {name}

แนวคิด: {concept}
Causal: ทุก indicator ใช้ข้อมูลถึงแท่ง i ที่ปิดแล้วเท่านั้น (ดู strategy/s20_gen/ind.py) engine เข้าไม้ที่ open แท่ง i+1
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen"))
import numpy as np
import pandas as pd
import ind as I

META = {meta}


def generate(df, tf):
{body}
'''


def write(n, name, concept, meta, body, overwrite=False):
    d = os.path.join(ROOT, "strategy", f"s20.{n}")
    os.makedirs(d, exist_ok=True)
    p = os.path.join(d, f"strategy20_{n}.py")
    if os.path.exists(p) and not overwrite:
        return p
    m = {"sid": f"20.{n}", "name": name, "concept": concept}
    m.update(meta)
    src = TEMPLATE.format(n=n, name=name, concept=concept, meta=repr(m),
                          body=textwrap.indent(textwrap.dedent(body).strip("\n"), "    "))
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        f.write(src)
    return p
