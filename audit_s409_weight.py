# -*- coding: utf-8 -*-
"""Cached allocation curve for the finalized S409 configuration."""

from datetime import datetime
import json
from pathlib import Path


BASE_CACHE = Path("scratch/portfolio_s408_events.json")
S409_CACHE = Path("scratch/portfolio_s409_events.json")
WEIGHTS = (0.25, 0.50, 0.75, 1.00, 1.25, 1.50, 2.00, 2.50, 2.75,
           3.00, 3.25, 3.50, 3.75, 4.00, 5.00, 7.50, 10.00)


def _events(path, key):
    data = json.loads(path.read_text(encoding="utf-8"))
    return [(datetime.fromisoformat(stamp), float(profit))
            for stamp, profit in data[key]]


def _stats(events):
    equity = peak = drawdown = 0.0
    for _, profit in sorted(events):
        equity += profit
        peak = max(peak, equity)
        drawdown = max(drawdown, peak - equity)
    return {"net": equity, "max_drawdown": drawdown,
            "return_dd": equity / drawdown if drawdown else float("inf")}


def main():
    baseline = _events(BASE_CACHE, "baseline")
    candidate = _events(S409_CACHE, "s409")
    print("baseline", _stats(baseline))
    for weight in WEIGHTS:
        weighted = baseline + [(stamp, profit * weight)
                               for stamp, profit in candidate]
        print(f"weight_{weight:.2f}", _stats(weighted))


if __name__ == "__main__":
    main()
