# Pending-stop experiment — frozen before predictions/scoring

8 ตุลาคม 2026 พี่ให้ทำต่อจาก public orders/ticks และยืนยันว่าไม่มี EA ต้นทาง รอบนี้ไม่รอ/ขอไฟล์ EA จากพี่ซ้ำ ไม่เปลี่ยน original 35,462-order objective

## Evidence / purpose

Public open observations มี `PipScalperEA V2 BUY STOP` / `SELL STOP` comments แต่ไม่ยืนยัน EA/version ของ closed history ส่วน source predecessor diagnostics เดิมสนับสนุน bracket distanceราคา1ในหลายไม้ ยังไม่เป็น causal proof รอบนี้ทดสอบ pending ที่มีอยู่ก่อน fill ต่างจาก market entry ที่ใช้quoteตอนthresholdhit

Previous continuation ที่ทำ path/public metadata/trial2.8 เป็น progressจริง: full-source datasets+new evidence+completed failedreplays ผู้ใช้ยืนยันให้ทำต่อหลังคุยเรื่องข้อจำกัด ไม่ถือ missing EA เป็น blockerที่ต้องรอเอกสารจากพี่ ยังมี bounded causal experiment นี้ให้ทำ

## Frozen factorial — 32 candidates only

- Entry anchor: `fixed_close` simulated last exit (startup first midpoint) / `rolling_extrema` running lowAsk/highBid while flat.
- Opposite policy: `oco` cancels remaining pending on first fill / `retain` keeps opposite and re-arms freed side after its simulated close. Retain allows one position per side, max2, not proven actual max3 or close-by/recovery trigger.
- Pending entry distanceราคา1, initial SLราคา1, point.01, lot10 throughout, no session/clock-based lot/engine switches.
- Entry fill: pre-existing pending `level` / current executable `quote`. Exit fill independently `level` / `quote` (4 execution combinations).
- Trailing: old rejected benchmark activation40/distance30 points; diagnostic-motivated activation16/distance16 points (price.16/.16). Development mode of impliedpeak-to-close was.16 and observed small/zero outcomes support testing activation=distance rather than old minimumprofit10. Neither is recovered EA input.
- 2 anchors × 2 policies × 2 entryfills × 2 exitfills × 2 trails =32. No post-score extra parameters/candidate selection. Both trail benchmarks retain all counterexamples in missing scope.

## Causal lifecycle / event ordering

Pending prices are normalized to .01 with half-up rounding and must be strictly beyond current Ask for BUY / below Bid for SELL at placement. Invalid levels are not silently filled; placement can retry from same simulated reference later. Quotes can jump through existing pending: compare AskBUY/BidSELL with pendinglevel BEFORE ratcheting/replacing pending. Pending created/replaced using currentquote cannot fill until a later quote event, including a later event with equal milliseconds.

Perquote ordering: pre-existing positionSLs first (BUY thenSELL deterministic if simultaneous), pre-existing pendings next (largest breach, BUY tie priority), then trailing of surviving pre-existing positions, then missing/replacement pending placements. Newly opened positions cannot SL/trail on openingquote. OCO waits until flat before new pair. Retain never doubles same-sideposition; pending prices move only while flat. Rolling pending can ratchet toward quotes, never away. After flat transition low/high reinitialize from currentquote, not sourceledger; remaining retained pending is preserved then eligible for flat ratchet.

No brokerAPI/order_send, no future ledger, no original tickets/times/outcomes in signal module. Event search may vectorize first quote threshold crossing and independent SL trajectories, but may not use a future result to choose parameters or mutate state before that quote. Reference/vector full-field parity and changed-future prefix tests required.

## Replay/scoring scope

Same Vantage XAU cache/hashes from firstwarm-upquote Aug18 21:00 UTC to END exclusive Oct8 01:17:56 UTC; no day/split/source-entry resets. Guard SHA-256/source population; archive pre-edit strategy revision for old replay reproduction.

Generate all32prediction trajectories BEFORE parsing sourceoutcomes for scoring. Strict allobservablefields/seconds tolerance0/full35,462denominator, save every source result and extra. This experiment's signal module covers XAU only; all4,252Fixed rows remain missing rather than disappearing. Previous Fixed continuous outputs remain evidence, not assumed verified companionEA/portfolio coupling.

Entry-only one-to-one comparison on symbol/side/lot/open-second/open-price is a named diagnostic, NOT goal success. Save allsource rows/extras for this diagnostic too. It must not certify full trades or sourcefeed identity.

Also report explicitly lot-omitted entry diagnostic (symbol/side/open-second/open-price) to distinguish fixedlot10 mismatch from entry mechanics. All35,462source rows/extras remain represented; this omits a required goalfield and is NEVER exact-order success. No diagnostic is used to reset the replay.

Split remains Sep21 00:00 UTC, development24,350 / crossboundary4 / chronologicalvalidation11,108. Already-inspected ledger is NOT unseenholdout. No model promoted from validation scores. Passing unit/parity/QA is not 100%clone.

## Next decision

Use complete outcomes to reject/preserve mechanisms; no indefinite blind proxy tuning. Pending place/modify history, actual quote/execution differences, manual5 IDs and lot/engine transitions remain unknown. If meaningful evidence-based alternatives are exhausted, report identifiability limits under Goal blocked audit without asking the user for unavailable EA files again.
