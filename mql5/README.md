# TrendFilterLines — MT5 Indicator

วาด **trend channel เฉียง 2 เส้น** (resistance + support) ผ่าน swing 2 จุด
ต่อ TF ที่เปิด Per-TF ใน Trend Filter ของบอท
พร้อม **panel สรุป trend ของทุก TF** ที่มุมล่างขวาของ chart

## ไฟล์ที่เกี่ยวข้อง

- `TrendFilterLines.mq5` — source code ของ indicator
- `RSIDivergencePane.mq5` — RSI แยกหน้าต่างล่างสำหรับท่าที่ 9
- `SwingHLLevels.mq5` — วาดเส้น Swing High / Swing Low ล่าสุดของแต่ละ TF ไปทางขวาประมาณ 5 แท่ง
- `trend_state.txt` / `trend_state_<symbol>.txt` — ไฟล์ที่ Python bot เขียน แล้ว indicator อ่าน
  (Location: `<MT5 Common>\Files\trend_state*.txt`)

## วิธีติดตั้ง

1. เปิด MT5 → ไปที่ `File > Open Data Folder`
2. ไปเส้นทาง `MQL5\Indicators\` (ของ terminal ตัวที่ใช้)
3. copy `TrendFilterLines.mq5` จากโฟลเดอร์ `mql5/` ของ bot ลงไปวางที่นี่
4. copy `RSIDivergencePane.mq5` ลงไปวางที่โฟลเดอร์เดียวกัน ถ้าต้องการ RSI pane
5. เปิด MetaEditor (F4 จาก MT5) → เปิดไฟล์ที่ต้องการ → กด `Compile` (F7)
6. กลับ MT5 → ใน Navigator panel → Refresh → หา indicator ใต้ `Indicators`
7. ลาก indicator ไปวางบน chart ที่ต้องการ

## RSIDivergencePane

ใช้สำหรับท่าที่ 9 โดยเฉพาะ:

- แสดง RSI ในหน้าต่างแยกด้านล่าง
- มี input แบบแนวเดียวกับ indicator divergence ในรูป
- ใช้ pivot RSI เพื่อหา Regular / Hidden Bullish และ Bearish
- มีเส้นระดับ `30 / 50 / 70`

Input หลัก:

| Parameter | Default | คำอธิบาย |
|---|---|---|
| `InpRsiPeriod` | `14` | ค่า period ของ RSI |
| `InpRsiSource` | `PRICE_CLOSE` | ราคาที่ใช้คำนวณ RSI |
| `InpPivotLookbackRight` | `5` | จำนวนแท่งฝั่งขวาของ pivot |
| `InpPivotLookbackLeft` | `5` | จำนวนแท่งฝั่งซ้ายของ pivot |
| `InpLookbackRangeMax` | `60` | ระยะห่าง pivot สูงสุด |
| `InpLookbackRangeMin` | `5` | ระยะห่าง pivot ต่ำสุด |
| `InpPlotBullish` | `true` | แสดง Regular Bullish |
| `InpPlotHiddenBullish` | `false` | แสดง Hidden Bullish |
| `InpPlotBearish` | `true` | แสดง Regular Bearish |
| `InpPlotHiddenBearish` | `false` | แสดง Hidden Bearish |
| `InpRsiColor` | `DeepSkyBlue` | สีเส้น RSI |
| `InpRsiWidth` | `2` | ความหนาเส้น RSI |

ข้อสำคัญ:

- ถ้าต้องการให้สัญญาณท่า 9 ตรงกับ pane นี้ ให้ค่าใน `config.py` ตรงกับ input ของ indicator
- ค่า default ที่ตั้งไว้ตอนนี้ตรงกับรูป:
  - `RSI 14`
  - `close`
  - `pivot 5 / 5`
  - `range 5-60`
- เปิดเฉพาะ `Regular Bullish` และ `Regular Bearish`

## SwingHLLevels

ใช้สำหรับดูเส้น `H/L` ที่หาเจอในแต่ละ TF แบบเร็วบน chart:

- คำนวณใน MT5 เอง ไม่ต้องอ่านไฟล์จาก Python bot
- ใช้ logic หา swing แบบเดียวกับ `strategy4.py`
- วาดเส้น `Swing High` และ `Swing Low` ล่าสุดของแต่ละ TF
- ลากเส้นไปทางขวาประมาณ `5` แท่งของ TF นั้น (ปรับได้ด้วย `InpExtendBars`)

input หลัก:

| Parameter | Default | คำอธิบาย |
|---|---|---|
| `InpLookback` | `100` | จำนวน bars ที่ใช้หา swing |
| `InpExtendBars` | `5` | ลากเส้นไปทางขวากี่แท่ง |
| `InpRefreshSec` | `5` | refresh ทุกกี่วินาที |
| `InpOnlyPerTfOn` | `true` | ถ้าเปิด จะแสดงเฉพาะ TF ที่ bot ติ๊กเปิดไว้ใน `trend_state_<symbol>.txt` |
| `InpShowLabels` | `true` | แสดง label ที่ปลายเส้น |
| `InpShowM1` ... `InpShowD1` | `true` | เปิด/ปิดการวาดแต่ละ TF |

หมายเหตุ:
- indicator นี้ล็อกให้แสดงเฉพาะ TF ของ chart ปัจจุบันเสมอ
- ตัวอย่าง: ถ้าเปิด chart `M1` จะเห็นแค่เส้น `H/L` ของ `M1`

## วิธีใช้

- ต้องรัน bot Python ไว้ก่อน (จะเขียนทั้ง `trend_state.txt` และ `trend_state_<symbol>.txt` ทุกรอบ scan)
- ใน bot ให้เปิด Trend Filter → Per-TF → ติ๊ก TF ที่อยาก plot เส้น
- กลับมาที่ MT5 — จะเห็นเส้นอัตโนมัติภายใน 5 วินาที (default refresh)
- Default: indicator จะแสดงเฉพาะเส้นของ TF ที่ตรงกับ chart ปัจจุบัน
  (เปลี่ยน timeframe → refresh อัตโนมัติผ่าน `CHARTEVENT_CHART_CHANGE`)
- File resolver: ถ้า `InpFileName` เป็นค่า default `trend_state.txt` indicator จะมองหา `trend_state_<symbol>.txt` ก่อน (เช่น `trend_state_XAUUSD.iux.txt`) ถ้าไม่มีค่อย fallback กลับไปอ่าน `trend_state.txt` รวม

## Input parameters (ปรับตอน attach indicator)

| Parameter | Default | คำอธิบาย |
|---|---|---|
| `InpFileName` | `trend_state.txt` | ถ้าใช้ค่า default indicator จะเลือก `trend_state_<symbol>.txt` อัตโนมัติถ้ามี ไม่งั้นค่อย fallback ไป `trend_state.txt` |
| `InpRefreshSec` | `5` | อัปเดตทุกกี่วินาที |
| `InpOnlyPerTfOn` | `true` | วาดเฉพาะ TF ที่ per_tf_on=1 (ติ๊กใน Telegram) |
| `InpOnlyChartTf` | `true` | วาดเฉพาะ TF ที่ตรงกับ period ของ chart |
| `InpBullColor` | Lime | สีเส้นฝั่ง Bull |
| `InpBearColor` | Red | สีเส้นฝั่ง Bear |
| `InpSidewayColor` | Gray | สีเส้นฝั่ง Sideway |
| `InpStrongWidth` | `2` | ความหนาเส้น strong trend |
| `InpWeakWidth` | `1` | ความหนาเส้น weak trend |
| `InpShowLabels` | `true` | แสดง label ที่ปลายขวาของเส้น |
| `InpLabelFontSize` | `9` | ขนาดฟอนต์ label |
| `InpShowPanel` | `true` | แสดง panel สรุป trend ของทุก TF ที่มุมล่างขวา |
| `InpPanelXOffset` | `10` | ระยะ X จากขอบขวาของ chart (px) |
| `InpPanelYOffset` | `20` | ระยะ Y จากขอบล่างของ chart (px) |
| `InpPanelFontSize` | `10` | ขนาดฟอนต์ panel |
| `InpPanelFont` | `Consolas` | ฟอนต์ panel (แนะนำ monospace) |
| `InpPanelHeaderColor` | White | สี header ของ panel |

## Summary Panel (มุมล่างขวา)

แสดง trend ของทุก TF ที่เปิด Per-TF ไว้ เรียงจาก TF เล็ก → TF ใหญ่ (M1 อยู่บน D1 อยู่ล่าง)
จัดเป็น table 2 column: **TF ชิดซ้าย**, **Icon ชิดขวา**

```
TREND FILTER
M1         🟢🟢↑
M5           🔴
M15           ⚪
M30           ⚫
H1         🟢🟢
H4         🔴🔴↓
```

ความหมาย icon:

| Icon | ความหมาย |
|---|---|
| 🟢🟢 | Bull strong |
| 🟢 | Bull weak |
| 🔴🔴 | Bear strong |
| 🔴 | Bear weak |
| ⚪ | Sideway (มี swing แต่ตี trend ไม่ออก) |
| ⚫ | Unknown (หา swing ไม่ครบ) |

ความหมาย break marker (ต่อท้าย icon):

| Marker | ความหมาย |
|---|---|
| ↑ | break_up — close แท่งล่าสุด > SH ปัจจุบัน |
| ↓ | break_down — close แท่งล่าสุด < SL ปัจจุบัน |
| (ไม่มี) | ราคายังอยู่ในกรอบ SH/SL |

- **ไม่ filter ตาม TF ของ chart** — panel แสดงทุก TF ที่ `per_tf_on=1` (ต่างจากเส้น trend ที่ filter ด้วย `InpOnlyChartTf`)
- Respect `InpOnlyPerTfOn` — ถ้าเปิดจะแสดงเฉพาะ TF ที่ติ๊กใน Telegram
- TF ที่ trend = UNKNOWN จะแสดงใน panel ด้วย icon ⚪ (สี gray) — ไม่กรองออกเหมือนการลากเส้น เพื่อยืนยันว่า bot กำลังเขียนไฟล์อยู่จริง
- สีแต่ละบรรทัด: BULL = lime, BEAR = red, SIDEWAY/UNKNOWN = gray (ตาม `InpBullColor`/`InpBearColor`/`InpSidewayColor`)
- ถ้าไม่มี TF ที่ active จะแสดง `No Active TF`

## การคำนวณ trend (strong / weak / sideway)

logic อยู่ที่ `scanner.py` → `_compute_trend_info()` ใช้ swing 3 จุดล่าสุดของทั้ง SH (high) และ SL (low):

**ตัวนับ streak** ทำงานแยกฝั่ง H กับฝั่ง L:
- ถ้า `cur <= prev` → 0 (ไม่ขึ้น)
- ถ้า `cur > prev` **และ** `prev > prev_prev` → 2 (ขึ้น 2 คู่ติดกัน)
- ถ้า `cur > prev` แต่ `prev <= prev_prev` → 1 (ขึ้นคู่เดียว)

**เงื่อนไขผลลัพธ์:**

| เงื่อนไข | trend | strength |
|---|---|---|
| HH ≥ 2 และ HL ≥ 2 | BULL | strong |
| LH ≥ 2 และ LL ≥ 2 | BEAR | strong |
| HH ≥ 1 และ HL ≥ 1 | BULL | weak |
| LH ≥ 1 และ LL ≥ 1 | BEAR | weak |
| ฝั่ง H กับ L สวนทาง | SIDEWAY | - |
| หา sh / sl ไม่เจอ | UNKNOWN | - |

**สรุป:**
- **strong** = swing 3 จุดล่าสุดของทั้ง 2 ฝั่งเรียงเป็นขั้นบันได (HH×2 + HL×2 หรือ LH×2 + LL×2)
- **weak** = swing 2 จุดล่าสุดไปทางเดียวกัน แต่ 3 จุดยังไม่ติด
- **SIDEWAY** = high ทำต่ำลงแต่ low ทำสูงขึ้น (หรือกลับกัน) = inside structure / compression

ตัวอย่าง:

```
Bull strong:
  SH: 2680 > 2670 > 2650   (HH 2 คู่)
  SL: 2660 > 2640 > 2620   (HL 2 คู่)

Bull weak:
  SH: 2680 > 2670 > 2675   (ขึ้นคู่เดียว — prev_prev สูงกว่า prev)
  SL: 2660 > 2640 > 2650

Sideway:
  SH: 4772 < 4833           (LH — high ลง)
  SL: 4723 > 4668           (HL — low ขึ้น)
```

## การลากเส้น (channel)

| Trend | เส้นบน (resistance) | เส้นล่าง (support) |
|---|---|---|
| 🟢 **BULL** | `prev_sh → sh` (เอียงขึ้น) | `prev_sl → sl` (เอียงขึ้น) |
| 🔴 **BEAR** | `prev_sh → sh` (เอียงลง) | `prev_sl → sl` (เอียงลง) |
| ⚪ **SIDEWAY** | `prev_sh → sh` | `prev_sl → sl` |
| ❓ **UNKNOWN** | ไม่ลาก | ไม่ลาก |

- **Ray right only** — เส้นยื่นไปขวาเรื่อย ๆ ไม่ยื่นซ้าย
- **สี**: BULL = lime, BEAR = red, SIDEWAY = gray
- **Style**: strong = solid, weak = dashed
- **Width**: strong = 2, weak = 1
- **Label**: `[TF] Bull-strong resistance 🚀` / `[M1] Bear-weak support`
  - 🚀 = break_up (close > SH ปัจจุบัน)
  - 💥 = break_down (close < SL ปัจจุบัน)
  - วางที่ขวาของแท่งปัจจุบัน +3 bar ตามความชันของเส้น

## Breakout detection (🚀 / 💥)

- ใช้ **horizontal level** ของ SH / SL ปัจจุบัน (ไม่ใช่ projected trend line)
- `break_up` ถ้า close แท่งล่าสุด > ราคา SH ปัจจุบัน
- `break_down` ถ้า close แท่งล่าสุด < ราคา SL ปัจจุบัน
- Flag แสดงต่อท้าย label ของทั้ง 2 เส้น

## ทดสอบว่า bot เขียนไฟล์แล้วหรือยัง

เปิด File Explorer ไปที่:

```
%AppData%\MetaQuotes\Terminal\Common\Files\trend_state.txt
%AppData%\MetaQuotes\Terminal\Common\Files\trend_state_<symbol>.txt
```

bot จะเขียนทั้ง 2 ไฟล์ทุกรอบ scan — ถ้ามี + mtime update ตามรอบ scan (ทุก ~5 วินาที) = bot ทำงานปกติ

ถ้าไม่มี:
- bot ยัง connect MT5 ไม่ได้
- หรือ trend filter ยังไม่ได้ scan รอบแรก — รอจน scan cycle แรกจบ

### File format (สำหรับ debug)

```
# generated_at=2026-04-23 14:30:00
# symbol=XAUUSD.iux
# tf,trend,strength,sh_time,sh_price,prev_sh_time,prev_sh_price,sl_time,sl_price,prev_sl_time,prev_sl_price,break_flag,per_tf_on
M1,BULL,strong,1777089000,2680.00,1777088700,2650.00,1777089480,2670.00,1777089120,2640.00,-,1
M5,SIDEWAY,-,0,0,0,0,0,0,0,0,-,0
H1,BEAR,strong,...
```

- `_time` เป็น unix timestamp (int)
- `_price` เป็น float 2 หลัก
- `break_flag` = `-`, `break_up`, หรือ `break_down`
- `per_tf_on` = `1` ถ้าผู้ใช้ติ๊ก TF นี้ใน Telegram, `0` ถ้าไม่

## Uninstall

- ลบ indicator ออกจาก chart (right-click chart → Indicators list → remove)
- indicator `OnDeinit` จะลบ object ที่สร้างไว้อัตโนมัติ (prefix `TFL_`)
- ไฟล์ `trend_state.txt` ปล่อยไว้ได้ bot จะ overwrite เอง

## Troubleshooting

| อาการ | สาเหตุ / วิธีแก้ |
|---|---|
| ไม่มีเส้นโผล่บน chart | ตรวจว่า bot รันอยู่ + เปิด Per-TF ติ๊ก TF ของ chart นั้น + `InpOnlyChartTf` เป็น true หรือ false ตามต้องการ |
| `Comment` โชว์ "cannot open" | ไฟล์ยังไม่ถูกสร้าง — รอ bot scan รอบแรก หรือ `Common\Files` path ผิด |
| เส้นค้างไม่อัปเดต | Restart indicator (detach/attach) หรือเช็กว่า `InpRefreshSec` เท่ากับอะไร |
| เส้นโชว์ TF อื่นที่ไม่ต้องการ | Set `InpOnlyChartTf = true` |
| อยากดูหลาย TF พร้อมกัน | Set `InpOnlyChartTf = false` |
| Panel ที่มุมล่างขวาไม่โชว์ | Set `InpShowPanel = true` |
| Panel emoji สีไม่ขึ้น / เป็นกรอบ ▯ | เปลี่ยน `InpPanelFont` เป็น `Segoe UI Emoji` |
| Panel ข้อความซ้อนกัน | ลดฟอนต์ (`InpPanelFontSize`) หรือเพิ่ม offset |
