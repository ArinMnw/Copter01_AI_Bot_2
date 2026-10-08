# -*- coding: utf-8 -*-
"""Backtest wrapper S20.691 — ส่งต่อ argument ทั้งหมดให้ strategy/s20_gen/engine.py
    python strategy/s20.691/backtest_s20_691.py --days 365
    python strategy/s20.691/backtest_s20_691.py --start 2026-01-01 --end 2026-06-30 --tfs H1,H4
    python strategy/s20.691/backtest_s20_691.py --days 90 --compare --compare-profile demo-exness-434237129
"""
import os, sys, runpy
sys.argv = [sys.argv[0], "--strategy", "S20.691"] + sys.argv[1:]
runpy.run_path(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s20_gen", "engine.py"), run_name="__main__")
