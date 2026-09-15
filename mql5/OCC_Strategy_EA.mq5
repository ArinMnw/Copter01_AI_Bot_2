//+------------------------------------------------------------------+
//|                                            OCC_Strategy_EA.mq5    |
//|  Open-Close Cross Strategy EA — ported จาก Pine v3 "OCC Strategy   |
//|  R5.1" (@JayRogers, revised by JustUncleL)                        |
//|                                                                     |
//|  แนวคิด: คำนวณ MA ของราคา Close และ MA ของราคา Open (เลือกชนิด MA   |
//|  ได้ 12 แบบ) บน timeframe ทางเลือก (Alternate Resolution = TF       |
//|  ปัจจุบัน x multiplier) แล้วดูจุดตัด (cross) ระหว่างสองเส้นนี้        |
//|    closeSeries ตัดขึ้นเหนือ openSeries → xlong  (สัญญาณ BUY)        |
//|    closeSeries ตัดลงใต้ openSeries    → xshort (สัญญาณ SELL)        |
//|                                                                     |
//|  ข้อแตกต่างจาก Pine ต้นฉบับ (ตัดสินใจร่วมกับผู้ใช้แล้ว):              |
//|  1) Alternate Resolution ใช้วิธี aggregate จากแท่ง M1 เอง (custom    |
//|     bar) ให้ตรงกับ multiplier ทุกค่า ไม่ snap ไปที่ TF มาตรฐานของ    |
//|     MT5 (Pine ใช้ security() ซึ่งรองรับ resolution ใดก็ได้)          |
//|  2) ไม่ repaint — ใช้เฉพาะแท่ง (สังเคราะห์) ที่ปิดสนิทแล้วเท่านั้น    |
//|     ต่างจาก Pine default ที่ repaint ค่า Alt TF ที่ยังไม่ปิด          |
//|     (lookahead_on) เว้นแต่ตั้ง Delay Open/Close MA >=1               |
//|  3) ขนาด lot คำนวณจาก % ของ Equity ตรงกับ default ของ Pine           |
//|     (percent_of_equity 10%) โดยแปลง notional = equity*pct/100        |
//|     เป็น lot ผ่าน contract size ของ symbol แล้ว floor ตาม volume      |
//|     step/min/max ของโบรกเกอร์ — ปิดได้ด้วย InpUseEquityPercent=false  |
//|     (กลับไปใช้ InpFixedLot คงที่แบบ EA ตัวอื่นในโปรเจกต์)             |
//|  4) ตัดฟีเจอร์ bar-color และ bar-count-limit (ebar) ออก เพราะ        |
//|     ไม่มีความหมายสำหรับ EA เทรดจริง/Strategy Tester ของ MT5          |
//+------------------------------------------------------------------+
#property copyright "Copter01 AI Bot"
#property link       ""
#property version    "1.00"

#include <Trade\Trade.mqh>
#include "OCC_MA_Lib.mqh"

// === Alternate Resolution ===
input bool   InpUseAltRes   = true;   // Use Alternate Resolution?
input int    InpAltResMult  = 3;      // Multiplier for Alternate Resolution (TF ปัจจุบัน x เท่านี้)

// === MA ===
input ENUM_OCC_MA_TYPE InpMAType = OCC_MA_SMMA; // MA Type
input int    InpMALen       = 8;      // MA Period
input double InpOffsetSigma = 6.0;    // Offset for LSMA / Sigma for ALMA
input double InpOffsetALMA  = 0.85;   // Offset for ALMA
input int    InpDelayOffset = 0;      // Delay Open/Close MA (bars, 0=repaint ตาม Pine, ที่นี่ไม่ repaint อยู่แล้ว)
input int    InpCalcBars    = 300;    // จำนวนแท่ง (บน Alt TF) ที่ใช้คำนวณ MA ย้อนหลัง (warm-up ของ EMA/SMMA/ฯลฯ)

// === Trade type ===
enum ENUM_OCC_TRADE_TYPE
  {
   OCC_TRADE_LONG,  // LONG only
   OCC_TRADE_SHORT, // SHORT only
   OCC_TRADE_BOTH,  // BOTH
   OCC_TRADE_NONE   // NONE (ไม่เทรด)
  };
input ENUM_OCC_TRADE_TYPE InpTradeType = OCC_TRADE_BOTH; // What trades should be taken

// === SL/TP ===
input int    InpSLPoints = 0; // Initial Stop Loss Points (0=disable)
input int    InpTPPoints = 0; // Initial Target Profit Points (0=disable)

// === Order size ===
input bool   InpUseEquityPercent = true;  // Use % of Equity (ตรงกับ Pine default_qty_type=percent_of_equity)
input double InpEquityPercent    = 10.0;  // % ของ Equity ต่อไม้ (Pine default_qty_value=10)
input double InpFixedLot = 0.01;      // ขนาด lot คงที่ (ใช้เมื่อ InpUseEquityPercent=false)
input ulong  InpMagic    = 20260810;  // Magic number
input int    InpSlippage = 20;        // slippage (points)

CTrade   trade;
datetime g_LastBarTime = 0;

//+------------------------------------------------------------------+
int OnInit()
  {
   trade.SetExpertMagicNumber(InpMagic);
   trade.SetDeviationInPoints(InpSlippage);
   trade.SetTypeFillingBySymbol(_Symbol);
   return(INIT_SUCCEEDED);
  }

//+------------------------------------------------------------------+
bool HasOpenPosition(ENUM_POSITION_TYPE &type)
  {
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0)
         continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol)
         continue;
      if((ulong)PositionGetInteger(POSITION_MAGIC) != InpMagic)
         continue;

      type = (ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE);
      return(true);
     }
   return(false);
  }

//+------------------------------------------------------------------+
void ClosePositions()
  {
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0)
         continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol)
         continue;
      if((ulong)PositionGetInteger(POSITION_MAGIC) != InpMagic)
         continue;
      trade.PositionClose(ticket);
     }
  }

//+------------------------------------------------------------------+
// คำนวณ lot จาก % ของ Equity (เทียบเท่า Pine strategy.percent_of_equity) |
// notional = equity * pct/100, lot = notional / (price * contractSize)  |
// แล้ว floor ตาม volume step/min/max ของโบรกเกอร์                       |
//+------------------------------------------------------------------+
double CalcOrderLot(const double price)
  {
   if(!InpUseEquityPercent)
      return(InpFixedLot);

   double contractSize = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_CONTRACT_SIZE);
   if(contractSize <= 0.0 || price <= 0.0)
      return(InpFixedLot);

   double equity   = AccountInfoDouble(ACCOUNT_EQUITY);
   double notional = equity * InpEquityPercent / 100.0;
   double lot      = notional / (price * contractSize);

   double lotStep = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   double lotMin  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double lotMax  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   double lotRaw  = lot;
   if(lotStep > 0.0)
      lot = MathFloor(lot / lotStep) * lotStep;
   lot = MathMax(lotMin, MathMin(lotMax, lot));

   PrintFormat("CalcOrderLot: equity=%.2f pct=%.2f%% price=%.2f contractSize=%.2f notional=%.2f lotRaw=%.5f lotStep=%.2f -> lot=%.2f",
               equity, InpEquityPercent, price, contractSize, notional, lotRaw, lotStep, lot);
   return(lot);
  }

//+------------------------------------------------------------------+
// รวมแท่ง M1 ให้เป็นแท่งสังเคราะห์ขนาด barMinutes นาที (aligned กับ       |
// epoch เหมือนวิธี resample มาตรฐาน) ตัดแท่งสุดท้ายทิ้งถ้ายังฟอร์มไม่เสร็จ |
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
         out[n].time         = bucketStart;
         out[n].open         = m1[i].open;
         out[n].high         = m1[i].high;
         out[n].low          = m1[i].low;
         out[n].close        = m1[i].close;
         out[n].tick_volume  = m1[i].tick_volume;
        }
      else
        {
         out[n-1].high         = MathMax(out[n-1].high, m1[i].high);
         out[n-1].low          = MathMin(out[n-1].low, m1[i].low);
         out[n-1].close        = m1[i].close;
         out[n-1].tick_volume += m1[i].tick_volume;
        }
     }

   int total = ArraySize(out);
   if(total == 0)
      return(false);

   // ถ้าแท่งสุดท้ายยังอยู่ใน bucket ที่กำลังฟอร์มอยู่ตอนนี้ (เทียบกับเวลาจริง) ให้ตัดทิ้ง
   long nowBucket = ((long)TimeCurrent() / bucketSeconds) * bucketSeconds;
   if((long)out[total-1].time == nowBucket)
     {
      ArrayResize(out, total - 1);
      total--;
     }
   return(total > 0);
  }

//+------------------------------------------------------------------+
// ดึงค่า closeSeries/openSeries ล่าสุด 2 ค่า (แท่งปัจจุบัน+แท่งก่อนหน้า) |
// บน Alt/Calc TF สำหรับเช็ค crossover/crossunder                        |
//+------------------------------------------------------------------+
bool GetOCCSeries(double &curClose, double &curOpen, double &prevClose, double &prevOpen)
  {
   int baseMinutes = (int)(PeriodSeconds(_Period) / 60);
   if(baseMinutes <= 0)
      baseMinutes = 1;
   int barMinutes = InpUseAltRes ? baseMinutes * InpAltResMult : baseMinutes;

   MqlRates bars[];
   int need = InpCalcBars + InpDelayOffset + 5;
   if(!BuildSyntheticBars(barMinutes, need, bars))
      return(false);

   int total = ArraySize(bars);
   int usable = total - InpDelayOffset; // ตัดแท่งล่าสุดออก InpDelayOffset แท่ง (เทียบเท่า close[delayOffset] ของ Pine)
   if(usable < InpMALen + 2)
      return(false);

   double closeArr[], openArr[], volArr[];
   ArrayResize(closeArr, usable);
   ArrayResize(openArr,  usable);
   ArrayResize(volArr,   usable);
   for(int i = 0; i < usable; i++)
     {
      closeArr[i] = bars[i].close;
      openArr[i]  = bars[i].open;
      volArr[i]   = (double)bars[i].tick_volume;
     }

   double closeSeries[], openSeries[];
   OCC_CalcSeries(InpMAType, closeArr, volArr, InpMALen, InpOffsetSigma, InpOffsetALMA, closeSeries);
   OCC_CalcSeries(InpMAType, openArr,  volArr, InpMALen, InpOffsetSigma, InpOffsetALMA, openSeries);

   int n = usable;
   curClose  = closeSeries[n-1];
   curOpen   = openSeries[n-1];
   prevClose = closeSeries[n-2];
   prevOpen  = openSeries[n-2];
   return(true);
  }

//+------------------------------------------------------------------+
void OnTick()
  {
   datetime barTime = iTime(_Symbol, _Period, 0);
   if(barTime == g_LastBarTime)
      return; // รอแท่งใหม่ (chart TF) — เทียบเท่า calc_on_every_tick=false ของ Pine
   g_LastBarTime = barTime;

   if(InpTradeType == OCC_TRADE_NONE)
      return;

   double curClose, curOpen, prevClose, prevOpen;
   if(!GetOCCSeries(curClose, curOpen, prevClose, prevOpen))
      return;

   bool xlong  = (curClose > curOpen) && (prevClose <= prevOpen); // crossover
   bool xshort = (curClose < curOpen) && (prevClose >= prevOpen); // crossunder
   if(!xlong && !xshort)
      return;

   double point  = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   double slDist = InpSLPoints * point;
   double tpDist = InpTPPoints * point;

   ENUM_POSITION_TYPE posType;
   bool hasPos = HasOpenPosition(posType);

   if(xlong)
     {
      if(InpTradeType == OCC_TRADE_SHORT) // strategy.close("short", when=longCond and tradeType=="SHORT")
        {
         if(hasPos && posType == POSITION_TYPE_SELL)
            ClosePositions();
        }
      else // LONG หรือ BOTH → strategy.entry("long", when=longCond and tradeType!="SHORT")
        {
         if(hasPos && posType == POSITION_TYPE_SELL)
            ClosePositions(); // reversal: ปิดฝั่งตรงข้ามก่อน (เทียบเท่า auto-flip ของ Pine)
         hasPos = HasOpenPosition(posType);
         if(!(hasPos && posType == POSITION_TYPE_BUY)) // pyramiding=0: ห้ามซ้อนไม้ฝั่งเดียวกัน
           {
            double price = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
            double sl = (InpSLPoints > 0) ? price - slDist : 0.0;
            double tp = (InpTPPoints > 0) ? price + tpDist : 0.0;
            trade.Buy(CalcOrderLot(price), _Symbol, 0.0, sl, tp);
           }
        }
     }
   else if(xshort)
     {
      if(InpTradeType == OCC_TRADE_LONG) // strategy.close("long", when=shortCond and tradeType=="LONG")
        {
         if(hasPos && posType == POSITION_TYPE_BUY)
            ClosePositions();
        }
      else // SHORT หรือ BOTH → strategy.entry("short", when=shortCond and tradeType!="LONG")
        {
         if(hasPos && posType == POSITION_TYPE_BUY)
            ClosePositions();
         hasPos = HasOpenPosition(posType);
         if(!(hasPos && posType == POSITION_TYPE_SELL))
           {
            double price = SymbolInfoDouble(_Symbol, SYMBOL_BID);
            double sl = (InpSLPoints > 0) ? price + slDist : 0.0;
            double tp = (InpTPPoints > 0) ? price - tpDist : 0.0;
            trade.Sell(CalcOrderLot(price), _Symbol, 0.0, sl, tp);
           }
        }
     }
  }
//+------------------------------------------------------------------+
