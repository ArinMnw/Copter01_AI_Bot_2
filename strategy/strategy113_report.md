# S113 — Wyckoff VSA Fractal Reversal

## EDGE

S113 จับเหตุการณ์กลับตัวแบบสองจังหวะ ซึ่งต่างจาก S95/S112 ที่เข้าใกล้จังหวะ
liquidity sweep โดยตรง:

1. สร้าง trading range จาก quantile 10%/90% ของ High/Low ย้อนหลัง 48 แท่ง
2. กรองให้ range อยู่ในภาวะบีบตัว และมีความกว้าง 2.5–9.0 ATR
3. รอ Wyckoff Spring/Upthrust กวาดขอบ range แล้วปิดกลับเข้ากรอบ
4. บังคับ VSA tick-volume spike อย่างน้อย 1.35 เท่าของ median 30 แท่ง
5. รอแท่งถัดไปยืนยัน micro-CHoCH และตรวจตำแหน่งบน synthetic HTF 3 เท่า
6. เข้าแบบ market ที่ close ของแท่งยืนยัน; backtest fill ที่ open แท่งถัดไป

แนวคิดเชิงคณิตศาสตร์หลัก:

- `ATR = mean(max(H-L, |H-Cprev|, |L-Cprev|), 14)`
- `volume_ratio = sweep_tick_volume / median(tick_volume, 30)`
- BUY SL = `spring_low - 0.20 × ATR`; SELL กลับด้าน
- TP อยู่ระหว่าง 1.5R–2.0R โดยเล็ง liquidity ฝั่งตรงข้ามของ range

ระบบนี้เสริมพอร์ตเดิมด้วยสัญญาณที่หายากและต้องมี volume absorption + confirmation
ก่อนเข้า จึงลดการชนกับ sweep ที่เข้าเร็วกว่า แต่แลกกับจำนวนออเดอร์ที่ต่ำมาก

หลักฐาน overlap เบื้องต้น: ในช่วงที่ `s112_trades.csv` และ S113 มีข้อมูลร่วมกัน
(2026-03-06 ถึง 2026-07-14) S112 มี 43 ไม้ ส่วน S113 มี 2 ไม้ และไม่มี S113
ไม้ใดชน S112 ภายใน ±60 นาทีหรือวันเดียวกันเลย อย่างไรก็ตาม n=2 เล็กเกินไปสำหรับ
การสรุป correlation/diversification ของพอร์ต จึงถือเป็นเพียงหลักฐานสนับสนุนขั้นต้น

## Recommended cfg

ค่าตั้งต้นอยู่ใน `strategy113.DEFAULT_CFG` และส่ง `{}` เข้า `detect_s113` ได้โดยตรง
ค่าหลักที่ผ่านการตรวจปัจจุบัน:

```python
{
    "RANGE_BARS": 48,
    "RANGE_Q": 0.10,
    "SQUEEZE_RATIO_MAX": 0.90,
    "VOLUME_SPIKE_MULT": 1.35,
    "MICRO_BREAK_BARS": 3,
    "HTF_FACTOR": 3,
    "SL_BUFFER_ATR": 0.20,
    "TP_RR": 1.50,
    "TP_MAX_RR": 2.00,
    "TRADE_HOURS": (14, 20),
    "ML_FILTER_ENABLED": False,
    "ML_SCORE_THRESHOLD": 0.55,
}
```

ML ปิดเป็นค่าเริ่มต้น เพราะยังไม่มีหลักฐาน OOS ว่าโมเดลปัจจุบันช่วย S113 จริง หากเปิด
ระบบจะ fail closed เมื่อเรียก scorer ไม่สำเร็จ และจะไม่ปล่อยสัญญาณโดยข้าม filter เงียบ ๆ

## Backtest evidence

ทดสอบ XAUUSD.iux, M5, ขอข้อมูล 730 nominal days (MT5 คืน 210,510 แท่ง
ช่วง 2023-06-28 11:35 ถึง 2026-07-16 19:15 BKK), spread 0.20:

- ใช้เฉพาะแท่งปิดแล้ว
- synthetic HTF จัดแนวด้วย timestamp และตัด bucket ที่ยังไม่ครบ
- fill ที่ open ของแท่งถัดไป
- ถ้า SL/TP ถูกแตะในแท่งเดียวกัน ตัดสิน SL ก่อน
- ถือ S113 ได้ครั้งละหนึ่ง position

ผลชุดที่ใช้เลือก session: `n=12`, Win Rate `83.3%`, Net `+70.53`, PF `10.51`,
Max DD `4.85`

| ปี | n | Win Rate | Net |
|---|---:|---:|---:|
| 2023 | 2 | 100% | +9.75 |
| 2024 | 4 | 50% | +3.88 |
| 2025 | 4 | 100% | +35.07 |
| 2026 | 2 | 100% | +21.83 |

### Frozen-parameter holdout

หลัง freeze ทุก parameter รวม `TRADE_HOURS=(14, 20)` แล้วดึงข้อมูลเพิ่มย้อนหลังถึง
2020-04-27 ได้ช่วง untouched ก่อน 2023-06-28 จำนวน 5 ไม้: Win Rate `60.0%`,
Net `+5.80`, PF `1.75` (2022: +0.83, 2023 ก่อน cutoff: +4.97)

ผลรวม 2020-04-27 ถึง 2026-07-16 คือ `n=17`, Win Rate `76.5%`, Net `+76.33`,
PF `6.03`, Max DD `7.75` แต่ห้ามใช้ตัวเลขรวมนี้แทน OOS เพราะมี in-sample 12 ไม้ปนอยู่

ข้อสรุปตามหลักฐาน: backward holdout ยังมีกำไร แต่ WR 60% และ sample เพียง 5 ไม้
จึง **ไม่ยืนยัน** เป้าหมาย WR 70–85% นอกชุดจูน และยังไม่ใช่หลักฐาน Holy Grail
ต้องทำ frozen-parameter forward test ต่อก่อนพิจารณาเชื่อมเข้าบอทจริง

คำสั่งรัน holdout ซ้ำ:

```powershell
python sim_s113_backtest.py --days 1500 --tf M5 `
  --signal-end 2023-06-28T11:35:00 --out-prefix scratch/s113_m5_holdout
```
