# ผล closed-candle / grid causal replay

วันที่8ตุลาคม2026 ต่อจาก Vantage export27,473,009 ticks เป้าหมายยังเป็น35,462 orders ตรงครบหนึ่งต่อหนึ่ง100% **ยังไม่ผ่าน** รอบนี้ทดสอบ38 candidates และ2 independent portfolio prototypes ไม่ส่งtrade/แก้production/เปลี่ยนบัญชี

## ขอบเขตและสิ่งที่เปลี่ยน

- เพิ่ม `ClosedBar`, `ClosedCandleConfig`, `ClosedCandleStrategy` ใน `strategy_scalping456.py`; รับเฉพาะ OHLCที่ปิดแล้วเท่านั้น ปฏิเสธ future/wrong-TF/duplicate bars ก่อน consume batch
- Entry body/engulf/breakout ใช้ broker M1/M5/M15/M30/H1 จริงที่ exportใหม่ ไม่จำลองtick pathจากOHLC ไม่เติมticksที่หาย
- Stops/trailing ยังจัดการทุกtickและstopก่อนmodify ใช้ SL100/trail40/30/lot10 เป็น fixed benchmark ไม่อ้างว่าเป็น source inputs
- FixedVol20 แยก quote fill จาก pending-level grid fill; pendingระดับ last filled entry±step คำนวณก่อนtrigger ไม่copyราคาledger เพิ่ม target roundingแบบhalf-up3digits แยกจากค่าเดิมhalf-even
- Defaultsของtick/gridเดิมคงอยู่; testsเก่า20ยังผ่าน Candidateใหม่ยังไม่มีsource hedge/emergency/session/lot-switch rulesที่ยืนยัน
- Parameters และการแบ่งช่วงกำหนดก่อนรันใน `EXPERIMENT_CANDLE_GRID_PLAN.md` ไม่จูนใหม่จาก scores

## Closed-candle: 20 candidates

ตัวเลขด้านล่างเป็นจำนวน source orders ที่ตรงทุก observable field ด้วยเวลา tolerance0 ทั้ง35,462 rowsอยู่ใน denominator รวมFixedVol20ที่candle engineยังไม่สร้าง ไม่ใช่ matched-only percentage

| TF | Body/level | Engulf/level | Breakout/level | Breakout/quote |
|---|---:|---:|---:|---:|
| M1 | 0 | 0 | 6 | 0 |
| M5 | 0 | 0 | 4 | 1 |
| M15 | 1 | 0 | 0 | 1 |
| M30 | 1 | 0 | 0 | 1 |
| H1 | 1 | 0 | 1 | 1 |

ดีที่สุดรอบนี้ฝั่งXAU M1 breakout/level มี79,099 predictionsในsource window, exact6, missing35,456, extra79,093 ไม่ดีกว่าold fixed-close benchmark17อย่างเพียงพอและยังไม่ผ่านทั้งคู่ ผลนี้ปฏิเสธกฎที่ทดลอง ไม่ได้พิสูจน์ว่าoriginal EAไม่ใช้candle featuresเลย

## FixedVol20: 16 grid +2 trial candidates

Grid step/target3หรือ15 × progressive/fixed .1 × fixed-close/rolling-extrema entry × quote/pending-level fill รวม16 Presetsคงที่ตลอดช่วง ไม่ใส่วันที่เปลี่ยนparametersจากledger Entryราคา3, ratio1.68, volume step.1, cap174, weighted TP half-up3digits

ดีที่สุดคือ grid3/progressive/rolling/quote: predictions18,740 / exact14 / missing35,448 / extra18,726 ทั้ง14อยู่ในdevelopmentและchronological validationได้0 ไม่ถือ14ไม้เป็นEA engineที่ถอดสำเร็จ อีก15 grid candidates exact0

Trial2แบบใช้ SLราคา10, entryราคา3, activation0/distanceราคา10, lot.1: levelมี3,146 predictions / quote3,135 ทั้งสองexact0 ไม่มีtrial orderถูกตัดจากscoring และไม่อ้างว่าค่าเหล่านี้เป็นrecovered settings

## Portfolio prototypes ที่ตั้งไว้ล่วงหน้า

เป็นการรวม independent generators ตามsymbol/engine ไม่ใช่original portfolio-equity/margin/hedge couplingที่ยืนยัน

| Prototype | Predictions | Exact | Missing | Extra |
|---|---:|---:|---:|---:|
| M1 breakout level + grid3 progressive fixed-close level + trial level | 100,533 | 6 | 35,456 | 100,527 |
| M5 breakout quote + grid15 progressive rolling quote + trial quote | 64,752 | 1 | 35,461 | 64,751 |

ไม่มีการเลือกcomponentsใหม่ตามvalidationเพื่ออ้างว่าportfolioผ่าน ทุกกลุ่มXAU31,210/Fixed4,252และmanual-unknown/close-byยังอยู่ในscope

## Entry แยกจาก exit: diagnostic ไม่ใช่success

`data/vantage_candle_grid_entry_diagnostics_20261008/` เก็บผลentry-onlyของทุกsource row/40models สองgrid3 progressive quote candidatesตรงsymbol/side/lot/open second/open price130 rowsจาก35,462 แต่full-orderตรง0และ14ตามลำดับ; M1 breakoutมีentry-only34 แต่full-order6หรือ0ตามfillmode

จึงมีทั้งentry timing/stateและexit/accounting/parameterข้อขัดแย้ง ไม่ใช่เพียงแก้ trailingแล้วจะผ่านทั้งหมด Metricentry-onlyไม่แทนเกณฑ์full order และmissing/extraยังบันทึกครบ

## Causality / split / verification

- เริ่ม warm-up inferred UTC18ส.ค.21:00ถึงก่อน8ต.ค.01:17:56; stateต่อเนื่องทุกวัน Generate38candidate predictionsก่อนparse source outcomes
- Barพร้อมใช้งานเมื่อ `open+duration <= current tick`; lookupใช้close times ไม่ใช้open times/future OHLC
- ทดสอบactual-feed reference/vector parityก่อนfull run:20candle casesใช้7ก.ย.00–01UTC,16grid casesใช้7ก.ย.ทั้งวัน ทุกprediction fieldตรงกัน รวม36 checks
- Unit tests43ผ่าน รวมfuture-prefix/changed-future-OHLC, future-batch rejection,5TF×3modes,grid16configs,trial2fill modes,matcherและaccountingเดิม
- Development closedก่อน21ก.ย.00UTCมี24,350source rows; carryข้ามsplit4 rowsไม่ใช้เลือกparameters; chronological validation11,108rows ไม่resetstateและ**ไม่ใช่unseen holdout** เพราะledgerเคยอ่านแล้ว
- Unknown closing behavior108rowsยังไม่ให้ผ่านเอง ไม่หมายถึงmanual108 (เว็บmanual5ยังไม่ทราบtickets)
- Artifact QAตรวจsourceครบ35,462 unique ticketsต่อmodel,one-to-one indexไม่reuse,missing/extraทุกrow,phasepartitionและhashesของทั้ง40modelsผ่าน ไม่ใช่completionของ100%goal

Strategy SHA-256 ของรอบนี้: `7c9ce8cf652d9a493d637fe8609ed656b76b6cf29e07714081d3987ecfcc6f1d`

## หลักฐานและทำซ้ำ

`data/vantage_broker_bars_20261008/` เก็บraw/inferred OHLC/specs/hashes10symbol-TFชุด `data/vantage_candle_grid_replay_20261008/` เป็นผลรันแรก พร้อมreport,38prediction files,40all-source files,40extra files และQA

เพิ่ม CLI tagsแล้วรันซ้ำที่ `data/vantage_candle_grid_replay_20261008_r2/` ด้วยparameters/dataเดิมเสร็จแล้ว QAทั้ง40modelsผ่าน และ SHA-256 ของ118data filesตรงรอบแรกทั้งหมด (38predictions+40source results+40extras) รวมconfigs/scores/phases/parityเหมือนกัน เก็บproofที่ `reproduction_audit.json` ไม่ลบหรือเขียนทับรอบแรก ความสามารถทำซ้ำไม่ใช่100%clone รอบ`_r2`เป็นผลจากCLIversionปัจจุบัน; metadata/code hashesของรอบแรกคงตามversionที่รันจริง

Python compileของ10scriptsที่เพิ่ม/แก้ผ่าน Research-scope `check_mojibake.py` ผ่าน และตรวจUTF-8/LFของไฟล์ที่เปลี่ยนโดยตรง ไม่มีการอ้างว่าglobal encodingทั้งrepoผ่าน (มีปัญหาเดิมนอกscopeในรอบก่อน)

รันจากresearch folder ใช้Pythonที่มีnumpy (exporterต้องมีMetaTrader5ด้วย):

```powershell
python -m unittest test_reconstruction test_vantage_readonly test_strict_source_matcher test_candle_grid_replay test_broker_bars_trial -v
python replay_vantage_candle_grid.py --tag vantage_candle_grid_repeat_NEW
python verify_candle_grid_experiment.py --tag vantage_candle_grid_repeat_NEW
python verify_candle_grid_reproduction.py --first vantage_candle_grid_replay_20261008_r2 --second vantage_candle_grid_repeat_NEW
python diagnose_candle_grid_entries.py --replay-tag vantage_candle_grid_repeat_NEW --tag vantage_entry_repeat_NEW
```

เปลี่ยน `NEW` เป็นชื่อใหม่ที่ยังไม่มี output dirs ป้องกันoverwrite snapshots; verifierเขียนQAแบบexclusive หากมีแล้วให้อ่านผลเดิม ไม่ลบเพื่อrerun หากต้องexport brokerbarsใหม่ใช้ `python export_vantage_bars.py --tag vantage_broker_bars_NEW` และระบุ `--bars-tag` ตอนreplay แต่dataใหม่อาจต่างจากsnapshotเดิม

## ขั้นต่อไปตามหลักฐาน

ไม่วนจูนpresetเดียวให้proxyคล้ายกัน จะตรวจ trailing/SL execution constraintsจากintratrade quote path, lot/parameter/session changes และhedge/close-by triggers แยกจากscorefullcausal โดยtagconditional diagnosticsตามจริง ข้อมูลsource EA inputs/magic/Journal/initial state/manual actionsยังจำเป็นต่อการลดambiguity; ขอพี่เพิ่มถ้ามี แต่ยังมีงานตรวจpathที่เพิ่มหลักฐานได้ Goalจึงยังactive
