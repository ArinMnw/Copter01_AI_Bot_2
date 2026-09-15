//+------------------------------------------------------------------+
//|                                                ZigZagPA_EA.mq5    |
//|  ZigZag PA Strategy EA — ported จาก Pine v3 "[STRATEGY][RS]ZigZag  |
//|  PA Strategy V4.1"                                                 |
//|                                                                     |
//|  แนวคิด:                                                            |
//|  1) ZigZag แบบ bar-color flip (ไม่ใช่ swing high/low ทั่วไป) บน       |
//|     timeframe ทางเลือก (Alt Timeframe) หรือ TF ปัจจุบันของ EA         |
//|  2) เก็บจุด pivot ล่าสุด 5 จุด (X,A,B,C,D) มาคำนวณอัตราส่วน           |
//|     ฮาร์มอนิก (xab,xad,abc,bcd) แล้วจับคู่กับ 17 harmonic pattern      |
//|     (Bat, AntiBat, AltBat, Butterfly, AntiButterfly, Gartley,        |
//|     AntiGartley, Crab, AntiCrab, Shark, AntiShark, 5-O, Wolf,        |
//|     Head&Shoulders, Contracting/Expanding Triangle, ABCD)            |
//|  3) เจอ pattern ฝั่ง Bull/Bear แล้วรอราคาย่อกลับเข้า Fib Entry        |
//|     Window (จาก C-D leg) ถึงเข้าไม้ ปิดไม้เมื่อแตะ Fib TP หรือ Fib SL  |
//|  4) รองรับ 2 ชุดพารามิเตอร์อิสระ (Target1/Target2) ใช้สัญญาณ          |
//|     pattern เดียวกันแต่คนละ Fib rate/ขนาดไม้ — Target2 ปิดอยู่โดย     |
//|     default (target02_active=false ใน Pine)                          |
//|                                                                     |
//|  ข้อแตกต่างจาก Pine ต้นฉบับ (ตัดสินใจร่วมกับผู้ใช้แล้ว):              |
//|  1) Alt Timeframe ใช้วิธี aggregate จากแท่ง M1 เอง (custom bar,       |
//|     non-repaint ใช้เฉพาะแท่งที่ปิดสนิทแล้ว) เหมือน EA ตัวก่อนหน้า      |
//|  2) ขนาดไม้แปลงจาก trade_size (USD notional ตรงกับ Pine qty) เป็น     |
//|     lot ผ่าน contract size ของ symbol แล้ว floor ตาม volume step      |
//|  3) Target1/Target2 ใช้ magic number แยกกัน จัดการ position อิสระ     |
//|     ต่อกัน แทนการพึ่งพา netting แบบ entry-ID ของ TradingView          |
//|  4) ไม่ตั้ง SL/TP เป็น broker-level order — ปิดไม้ด้วยการเช็ค          |
//|     high/low เทียบ Fib level ทุกแท่งใหม่ เหมือน strategy.close        |
//|     ของ Pine (ของเดิมก็ไม่ได้ตั้ง hard stop เช่นกัน)                   |
//|  5) ตัดฟีเจอร์ pattern label วาดบนกราฟ (showPatterns) ออก เพราะ        |
//|     ไม่กระทบ logic การเทรด                                           |
//+------------------------------------------------------------------+
#property copyright "Copter01 AI Bot"
#property link       ""
#property version    "1.00"

#include <Trade\Trade.mqh>
#include "ZigZagPA_Lib.mqh"

// === ZigZag / Alt Timeframe ===
input bool InpUseHA        = false; // Use Heikken Ashi Candles
input bool InpUseAltTF     = true;  // Use Alt Timeframe
input int  InpAltTFMinutes = 60;    // Alt Timeframe (นาที, ตรงกับ tf="60" ของ Pine)
input int  InpCalcBars     = 300;   // จำนวนแท่ง (บน Alt/Calc TF) ที่ใช้หา zigzag pivot ย้อนหลัง

// === Target 1 ===
input double InpT1_TradeSize = 10000.0; // Target1 - Trade size (USD notional)
input double InpT1_EWRate    = 0.236;   // Target1 - Fib rate สำหรับ Entry Window
input double InpT1_TPRate    = 0.618;   // Target1 - Fib rate สำหรับ TP
input double InpT1_SLRate    = -0.236;  // Target1 - Fib rate สำหรับ SL
input ulong  InpMagicT1      = 20260811; // Magic number Target1

// === Target 2 ===
input bool   InpT2_Active    = false;   // Target2 - Active?
input double InpT2_TradeSize = 10000.0; // Target2 - Trade size (USD notional)
input double InpT2_EWRate    = 0.236;   // Target2 - Fib rate สำหรับ Entry Window
input double InpT2_TPRate    = 1.618;   // Target2 - Fib rate สำหรับ TP
input double InpT2_SLRate    = -0.236;  // Target2 - Fib rate สำหรับ SL
input ulong  InpMagicT2      = 20260812; // Magic number Target2

input int InpSlippage = 20; // Max Slippage Guard (points) — ถ้าราคาตลาดขยับเกินนี้จากราคาที่ขอ
                             // ตอนส่งคำสั่ง Buy/Sell จะ "ยกเลิกไม้" แทนที่จะ fill ราคาที่แย่กว่าที่ยอมรับได้

CTrade   trade;
datetime g_LastBarTime = 0;

//+------------------------------------------------------------------+
int OnInit()
  {
   trade.SetDeviationInPoints(InpSlippage);
   trade.SetTypeFillingBySymbol(_Symbol);
   return(INIT_SUCCEEDED);
  }

//+------------------------------------------------------------------+
bool HasOpenPositionForMagic(const ulong magic, ENUM_POSITION_TYPE &type)
  {
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0)
         continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol)
         continue;
      if((ulong)PositionGetInteger(POSITION_MAGIC) != magic)
         continue;

      type = (ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE);
      return(true);
     }
   return(false);
  }

//+------------------------------------------------------------------+
void ClosePositionsForMagic(const ulong magic)
  {
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0)
         continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol)
         continue;
      if((ulong)PositionGetInteger(POSITION_MAGIC) != magic)
         continue;
      trade.PositionClose(ticket);
     }
  }

//+------------------------------------------------------------------+
// เปิดไม้ผ่าน market order พร้อม slippage guard (InpSlippage) — ถ้าราคา
// ตลาดขยับเกินจำนวน point ที่ยอมรับได้ระหว่างตัดสินใจกับตอนส่งคำสั่งจริง
// broker/CTrade จะปฏิเสธคำสั่งแทนที่จะ fill ราคาที่แย่กว่าที่ต้องการ —
// คืนค่า true/false ให้ผู้เรียกรู้ว่าไม้เข้าจริงหรือถูกยกเลิก
//+------------------------------------------------------------------+
bool OpenPosition(const ulong magic, const bool isBuy, const double lot)
  {
   trade.SetExpertMagicNumber(magic);
   bool ok = isBuy ? trade.Buy(lot, _Symbol, 0.0, 0.0, 0.0)
                   : trade.Sell(lot, _Symbol, 0.0, 0.0, 0.0);
   if(!ok)
     {
      PrintFormat("[ZZPA magic=%I64u] ORDER REJECTED (%s lot=%.2f) — ราคาตลาดขยับเกิน InpSlippage=%d "
                  "points หรือ broker ปฏิเสธ retcode=%d comment=%s",
                  magic, isBuy ? "BUY" : "SELL", lot, InpSlippage,
                  trade.ResultRetcode(), trade.ResultComment());
     }
   return(ok);
  }

//+------------------------------------------------------------------+
// แปลง trade_size (USD notional เทียบเท่า qty ของ Pine) เป็น lot ผ่าน   |
// contract size ของ symbol แล้ว floor ตาม volume step/min/max            |
//+------------------------------------------------------------------+
double CalcLotFromNotional(const double notionalUSD, const double price)
  {
   double contractSize = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_CONTRACT_SIZE);
   if(contractSize <= 0.0 || price <= 0.0)
      return(0.0);

   double lot = notionalUSD / (price * contractSize);

   double lotStep = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   double lotMin  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double lotMax  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   if(lotStep > 0.0)
      lot = MathFloor(lot / lotStep) * lotStep;
   lot = MathMax(lotMin, MathMin(lotMax, lot));
   return(lot);
  }

//+------------------------------------------------------------------+
// รวมแท่ง M1 ให้เป็นแท่งสังเคราะห์ขนาด barMinutes นาที ตัดแท่งสุดท้าย     |
// ทิ้งถ้ายังฟอร์มไม่เสร็จ (non-repaint, เหมือน EA ตัวก่อนหน้า)            |
//+------------------------------------------------------------------+
bool BuildSyntheticBars(const int barMinutes, const int barsNeeded, MqlRates &out[])
  {
   if(barMinutes <= 0)
      return(false);

   int bucketSeconds = barMinutes * 60;
   int m1Needed = barMinutes * (barsNeeded + 3);

   MqlRates m1[];
   ArraySetAsSeries(m1, false);
   int copied = CopyRates(_Symbol, PERIOD_M1, 1, m1Needed, m1); // shift=1 ข้ามแท่ง M1 ที่กำลังฟอร์ม
   if(copied <= 1)
      return(false);

   // เตือน (ไม่ได้แก้ข้อมูล) ถ้าเจอ gap ใน M1 history ของ broker — pivot ที่คำนวณจาก
   // ช่วงที่ข้อมูลขาดหายอาจไม่แม่น ไม่ใช่บั๊กโค้ด แต่ควรรู้ตัวไว้ (ยืนยันจากการสืบสวนจริง
   // ที่เจอ gap 28/60 แท่งช่วง 03:30-04:30 น. วันที่ 6 ส.ค. 2026 ของ broker IUX)
   static datetime lastWarnedGapEnd = 0;
   for(int gi = 1; gi < copied; gi++)
     {
      long gapSeconds = (long)(m1[gi].time - m1[gi-1].time);
      if(gapSeconds > 120 && m1[gi].time > lastWarnedGapEnd)
        {
         PrintFormat("ZigZagPA WARNING: M1 data gap %s -> %s (~%d นาทีหาย) — pivot ช่วงนี้อาจไม่แม่น "
                     "(ข้อมูล broker ขาดหาย ไม่ใช่บั๊กโค้ด ดู CheckM1DataGaps.mq5 เพื่อตรวจสอบละเอียด)",
                     TimeToString(m1[gi-1].time, TIME_DATE | TIME_MINUTES | TIME_SECONDS),
                     TimeToString(m1[gi].time, TIME_DATE | TIME_MINUTES | TIME_SECONDS),
                     (int)(gapSeconds / 60));
         lastWarnedGapEnd = m1[gi].time;
        }
     }

   ArrayResize(out, 0);
   ArraySetAsSeries(out, false);

   for(int i = 0; i < copied; i++)
     {
      long bucketStartLong = (((long)m1[i].time) / bucketSeconds) * bucketSeconds;
      datetime bucketStart = (datetime)bucketStartLong;
      int n = ArraySize(out);
      if(n == 0 || out[n-1].time != bucketStart)
        {
         ArrayResize(out, n + 1);
         out[n].time  = bucketStart;
         out[n].open  = m1[i].open;
         out[n].high  = m1[i].high;
         out[n].low   = m1[i].low;
         out[n].close = m1[i].close;
        }
      else
        {
         out[n-1].high  = MathMax(out[n-1].high, m1[i].high);
         out[n-1].low   = MathMin(out[n-1].low, m1[i].low);
         out[n-1].close = m1[i].close;
        }
     }

   int total = ArraySize(out);
   if(total == 0)
      return(false);

   long nowBucket = ((long)TimeCurrent() / bucketSeconds) * bucketSeconds;
   if((long)out[total-1].time == nowBucket)
     {
      ArrayResize(out, total - 1);
      total--;
     }
   return(total > 0);
  }

//+------------------------------------------------------------------+
// สร้าง synthetic bars → (Heikin Ashi ถ้าเปิด) → ZigZag → ดึงจุด        |
// X,A,B,C,D ล่าสุด                                                     |
//+------------------------------------------------------------------+
bool GetZigZagXABCD(double &x, double &a, double &b, double &c, double &d)
  {
   int baseMinutes = (int)(PeriodSeconds(_Period) / 60);
   if(baseMinutes <= 0)
      baseMinutes = 1;
   int barMinutes = InpUseAltTF ? InpAltTFMinutes : baseMinutes;

   MqlRates bars[];
   int need = InpCalcBars + 10;
   if(!BuildSyntheticBars(barMinutes, need, bars))
      return(false);

   int n = ArraySize(bars);
   if(n < 10)
      return(false);

   datetime tm[];
   double o[], h[], l[], cl[];
   ArrayResize(tm, n);
   ArrayResize(o, n);
   ArrayResize(h, n);
   ArrayResize(l, n);
   ArrayResize(cl, n);
   for(int i = 0; i < n; i++)
     {
      tm[i] = bars[i].time;
      o[i]  = bars[i].open;
      h[i]  = bars[i].high;
      l[i]  = bars[i].low;
      cl[i] = bars[i].close;
     }

   double uo[], uh[], ul[], uc[];
   if(InpUseHA)
     {
      ZZPA_ComputeHeikinAshi(o, h, l, cl, uo, uh, ul, uc);
     }
   else
     {
      ArrayCopy(uo, o);
      ArrayCopy(uh, h);
      ArrayCopy(ul, l);
      ArrayCopy(uc, cl);
     }

   bool isPivot[];
   double pivotVal[];
   ZZPA_ComputeZigZag(tm, uo, uh, ul, uc, isPivot, pivotVal);

   return(ZZPA_GetLastPivots(isPivot, pivotVal, n - 1, x, a, b, c, d));
  }

//+------------------------------------------------------------------+
// จัดการไม้ของ target หนึ่งชุด (Target1 หรือ Target2) — เช็คปิดก่อน        |
// (แตะ Fib TP/SL) แล้วค่อยเช็คเปิด (pattern + เข้า Fib Entry Window)      |
//+------------------------------------------------------------------+
void ManageTarget(const ulong magic, const double tradeSize, const double ewRate,
                   const double tpRate, const double slRate,
                   const bool bullPattern, const bool bearPattern,
                   const string bullName, const string bearName,
                   const double x, const double a, const double b, const double c, const double d,
                   const double curClose, const double curHigh, const double curLow)
  {
   double fibEW = ZZPA_LastFib(ewRate, d, c);
   double fibTP = ZZPA_LastFib(tpRate, d, c);
   double fibSL = ZZPA_LastFib(slRate, d, c);

   ENUM_POSITION_TYPE posType;
   bool hasPos = HasOpenPositionForMagic(magic, posType);

   if(hasPos && posType == POSITION_TYPE_BUY)
     {
      if((curHigh >= fibTP) || (curLow <= fibSL))
        {
         PrintFormat("[ZZPA magic=%I64u] CLOSE BUY: high=%.2f low=%.2f fibTP=%.2f fibSL=%.2f (X=%.2f A=%.2f B=%.2f C=%.2f D=%.2f)",
                     magic, curHigh, curLow, fibTP, fibSL, x, a, b, c, d);
         ClosePositionsForMagic(magic);
         hasPos = false;
        }
     }
   else if(hasPos && posType == POSITION_TYPE_SELL)
     {
      if((curLow <= fibTP) || (curHigh >= fibSL))
        {
         PrintFormat("[ZZPA magic=%I64u] CLOSE SELL: high=%.2f low=%.2f fibTP=%.2f fibSL=%.2f (X=%.2f A=%.2f B=%.2f C=%.2f D=%.2f)",
                     magic, curHigh, curLow, fibTP, fibSL, x, a, b, c, d);
         ClosePositionsForMagic(magic);
         hasPos = false;
        }
     }

   if(hasPos)
      return; // pyramiding=0: มี position อยู่แล้วไม่เปิดซ้ำ

   bool buyEntry  = bullPattern && (curClose <= fibEW);
   bool sellEntry = bearPattern && (curClose >= fibEW);

   if(buyEntry)
     {
      double price = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
      double lot = CalcLotFromNotional(tradeSize, price);
      PrintFormat("[ZZPA magic=%I64u] ENTRY BUY \"%s\": close=%.2f fibEW=%.2f lot=%.2f (X=%.2f A=%.2f B=%.2f C=%.2f D=%.2f)",
                  magic, bullName, curClose, fibEW, lot, x, a, b, c, d);
      if(lot > 0.0)
         OpenPosition(magic, true, lot);
     }
   else if(sellEntry)
     {
      double price = SymbolInfoDouble(_Symbol, SYMBOL_BID);
      double lot = CalcLotFromNotional(tradeSize, price);
      PrintFormat("[ZZPA magic=%I64u] ENTRY SELL \"%s\": close=%.2f fibEW=%.2f lot=%.2f (X=%.2f A=%.2f B=%.2f C=%.2f D=%.2f)",
                  magic, bearName, curClose, fibEW, lot, x, a, b, c, d);
      if(lot > 0.0)
         OpenPosition(magic, false, lot);
     }
  }

//+------------------------------------------------------------------+
void OnTick()
  {
   datetime barTime = iTime(_Symbol, _Period, 0);
   if(barTime == g_LastBarTime)
      return; // รอแท่งใหม่ (chart TF) — เทียบเท่า calc_on_every_tick=false ของ Pine
   g_LastBarTime = barTime;

   double x, a, b, c, d;
   if(!GetZigZagXABCD(x, a, b, c, d))
      return;

   double xab, xad, abc, bcd;
   if(!ZZPA_CalcRatios(x, a, b, c, d, xab, xad, abc, bcd))
      return;

   bool bullPattern = ZZPA_AnyPattern(1, xab, xad, abc, bcd, d, c);
   bool bearPattern = ZZPA_AnyPattern(-1, xab, xad, abc, bcd, d, c);
   string bullName = bullPattern ? ZZPA_MatchedPatternName(1, xab, xad, abc, bcd, d, c) : "";
   string bearName = bearPattern ? ZZPA_MatchedPatternName(-1, xab, xad, abc, bcd, d, c) : "";
   // หมายเหตุ: ไม่ return ตรงนี้แม้ไม่มี pattern เพราะยังต้องเช็คปิดไม้เดิม (Fib TP/SL) ต่อใน ManageTarget

   double curClose = iClose(_Symbol, _Period, 1);
   double curHigh  = iHigh(_Symbol, _Period, 1);
   double curLow   = iLow(_Symbol, _Period, 1);

   ManageTarget(InpMagicT1, InpT1_TradeSize, InpT1_EWRate, InpT1_TPRate, InpT1_SLRate,
                bullPattern, bearPattern, bullName, bearName, x, a, b, c, d, curClose, curHigh, curLow);

   if(InpT2_Active)
      ManageTarget(InpMagicT2, InpT2_TradeSize, InpT2_EWRate, InpT2_TPRate, InpT2_SLRate,
                   bullPattern, bearPattern, bullName, bearName, x, a, b, c, d, curClose, curHigh, curLow);
  }
//+------------------------------------------------------------------+
