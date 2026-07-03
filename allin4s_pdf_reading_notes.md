# All-in-4S PDF Reading Notes

Source folder: `C:\Users\Copter\Downloads\อออิน4s`

## Coverage

- Audited PDF files: 120
- Counted pages: 11,220
- Exact duplicate PDFs found: 31
- Text-extracted PDFs: 36 primary + 24 duplicate text files
- Image-only / mostly-image PDFs: 53 primary + 7 duplicate image files
- Contact sheets generated for all 30 primary image/mostly-image targets after skipping duplicates and split parts covered by full PDFs.

Artifacts:

- `tmp/allin4s_pdf_audit/allin4s_pdf_manifest.csv`
- `tmp/allin4s_pdf_audit/allin4s_pdf_audit.md`
- `tmp/allin4s_pdf_audit/contact_sheets/contact_sheet_index.md`

## Read Concepts Collected

### Force Model

- "รับแรง" comes from zones/causes such as FVG, DM, SP, OB, and candle defects.
- "ส่งแรง" is not the same thing as receiving force. Sending force requires clearing or breaking an H/L reference.
- If the force source is not FVG, the setup should wait until price clears H or L before treating it as directional force.
- A true move should close-cover the relevant wick/body. If it cannot close-cover, it is a defect and price often revisits that wick or a prior wick.
- A strong reversal or continuation candle should close beyond the prior wick, not merely close opposite color.

### 2L / 2H

- A real reversal often creates 2L/2H or M/W style structure.
- After 2L, if price cannot break the prior H, the structure can become a sell reversal / butterfly trap.
- After 2H, if price cannot break the prior L, the structure can become a buy reversal / butterfly trap.
- For automated testing, 2L/2H should not be treated as a standalone entry. It needs the next H/L break or fail-to-break confirmation.

### Fake Reversal Structure

- Fake reversal often forms in the middle of an existing H-L structure while price is still moving in one direction.
- Example sell-side read: there is an H-L and price is moving up. Several red candles fail to close-cover their upper wick, but one red candle can close-cover. That candle can force price upward first, creating a fake buy reversal before later dropping.
- The follow-through candle after the fake move is important. If it immediately violates the fake structure, bias flips back to the main H-L direction.

### Clear Candle

- A clear candle is created when price is pushed hard one way, then pulled back to close the opposite color.
- Type 1: long visible wick from the rejected side.
- Type 2: strong push and pullback where the returning wick becomes longer than the original wick.
- Once a clear condition forms, other candles in that set should not easily pierce the clear area. If they do, the set loses strength.
- The projected destination after a clear candle can be around the wick/clear-origin area, often described as 1000-2500 points in the source material.

### FVG / DM / SP

- First FVG in a trend base is special and often stronger than later FVGs.
- If price takes the latest FVG but cannot make a new H/L, it signals deeper pullback and may seek the second or lower FVG.
- If price receives an FVG and closes covering prior wicks, continuation is favored.
- If price only reaches an FVG but cannot close-cover the wick/body context, it is a warning to exit or flip bias.
- If multiple DM zones exist inside an FVG, the first DM is often tested first.

### Fibo / RUN

- Fibo tests around 50-60 are repeatedly used as a decision area before RUN.
- If price tests 50 and does not break, it can run to RUN.
- If price breaks the 50 structure, it can return to the old low/high instead of continuing.
- KRH and RUN levels are better treated as structured targets/validation, not blind entries.

### Significant Levels / Future Read

- Key levels come from old H/L breaks, first rejection wick, old support/resistance, doji/significant candle, and psychological numbers.
- Daily future reading can use H12 behavior: if D1 closes red but H12 closes red then green, the next day may rise even though D1 color implies downside.
- Psychological numbers such as 3, 7, and 8 appear as context markers, but should be secondary to structure and current order flow.

## Strategy Candidates

### S65 Candidate - Fake Reversal Trap

Core idea:

1. Detect a recent H-L directional leg.
2. Detect a mid-structure fake reversal candle group:
   - 2-3 candles fail to close-cover their rejection wick.
   - Then one candle closes-cover the wick and forces a short counter-move.
3. Wait for the counter-move to fail:
   - For sell setup, fake buy fails to make/hold new H, then closes back below the fake candle origin.
   - For buy setup, fake sell fails to make/hold new L, then closes back above the fake candle origin.
4. Enter in original H-L direction, using the fake structure as SL reference.

Why this is new vs S62-S64:

- S62 was generic close-cover reversal.
- S63 is DM/SP breakout continuation.
- S64 is KRH fib expansion.
- S65 focuses on failed reversal structure after a forced fake move.

### S66 Candidate - FVG Ladder Follow Trend

Core idea:

1. Detect a trend leg with at least 2-3 stacked FVGs.
2. Track whether latest FVG is accepted and makes a new H/L.
3. If latest FVG is accepted but no new H/L appears, avoid trend entry and expect deeper pullback toward lower FVG.
4. If lower/base FVG holds with close-cover force, rejoin trend.

Possible use:

- Standalone follow-trend strategy.
- Or filter for S63/S64 to avoid late entries after latest FVG fails.

## Current Champion Status

- S63 remains the strongest All-in-4S champion candidate so far.
- S64 is viable as secondary candidate.
- S65/S66 are the next research directions from the newly read image-only PDFs.
