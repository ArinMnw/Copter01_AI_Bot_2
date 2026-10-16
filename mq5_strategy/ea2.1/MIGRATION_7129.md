# EA2.1 migration — 2026-10-15

EA2.1 has moved from `demo-iux-2101182459` to `demo-exness-434237129`.
The source profile no longer enables EA2_1. The target keeps its existing strategies and
enables EA2_1 alongside INDI1, at 0.1% balance risk per trade. The 15-minute audit monitor
is paused; migration does not resume it. Broker state is initialized locally on the new
symbol and terminal, rather than copying the IUX signal state across accounts.

Exness XAUUSDm has point 0.001 instead of IUX's 0.01. The target profile scales all price
thresholds by ten (including minimum leg, OB preference and spread cap), preserving the
same price distances: SL12, TP50, BE trigger0.75/lock0.25, trail trigger1/distance0.75/step0.05.

At the observed balance of $10,075.34, the 0.1% budget is $10.07534. Minimum lot 0.01 with
SL12 risks approximately $12, so such entries are skipped. Risk is not increased to meet
the broker's minimum lot. This requires roughly $12,000 balance for the minimum lot at
these symbol specifications, excluding fees and slippage.
