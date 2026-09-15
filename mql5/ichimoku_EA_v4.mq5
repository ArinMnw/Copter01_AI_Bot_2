//+------------------------------------------------------------------+
//|                                              ichimoku_EA_v4.mq5   |
//|  Ichimoku Trend EA v4 — เงื่อนไขเดียว: Conversion vs Base เท่านั้น  |
//|                                                                     |
//|    Conversion > Base → เปิด/ถือ BUY, ปิด SELL                       |
//|    Conversion < Base → เปิด/ถือ SELL, ปิด BUY                       |
//|                                                                     |
//|  Entry : market order หลังแท่งปิด (ใช้ราคาตลาด ณ แท่งใหม่)          |
//|  SL    : BUY  = lowest(N)  ก่อนหน้า - buffer                       |
//|          SELL = highest(N) ก่อนหน้า + buffer  (mirror ตามทิศ)      |
//|  TP    : ไม่มี                                                      |
//|  Close : ปิดออเดอร์เมื่อเกิดสัญญาณฝั่งตรงข้าม (แล้วเปิดฝั่งใหม่ต่อ)  |
//+------------------------------------------------------------------+
#property copyright "Copter01 AI Bot"
#property link       ""
#property version    "4.00"

#include <Trade\Trade.mqh>
#include "HHLL_Lib.mqh"
#include "Fractals_Lib.mqh"

input int    InpConversionPeriods   = 9;    // Conversion Line Length
input int    InpBasePeriods         = 26;   // Base Line Length
input int    InpLaggingSpan2Periods = 52;   // Leading Span B Length

input int    InpSwingLookback  = 20;    // ย้อนหลังกี่แท่งสำหรับหา swing high/low (SL)
input int    InpSLBufferPoints = 50;    // buffer เพิ่มจาก swing high/low (points)
input double InpFixedLot       = 0.01;  // ขนาด lot คงที่
input ulong  InpMagic          = 20260809; // Magic number
input int    InpSlippage       = 20;    // slippage (points)

input bool   InpUseHHLL        = true;  // เปิดใช้ HH/LL renew (ปิดแล้วเข้าใหม่ฝั่งเดิมทันที)
input bool   InpUseFractals    = false; // เปิดใช้ Fractals renew (ปิดแล้วเข้าใหม่ฝั่งเดิมทันทีเมื่อเจอ fractal ตรงข้าม) — เลือกได้แค่ตัวเดียว

input int    InpHHLLLeft       = 5;     // HH/LL pivot: left bars
input int    InpHHLLRight      = 5;     // HH/LL pivot: right bars
input int    InpHHLLLookback   = 500;   // HH/LL pivot: max lookback bars

CTrade trade;
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
// Donchian avg(highest,lowest) ของ symbol/period ปัจจุบัน เริ่มนับจาก shift ไปอีก len แท่ง
double Donchian(const int shift, const int len)
  {
   int idxHigh = iHighest(_Symbol, _Period, MODE_HIGH, len, shift);
   int idxLow  = iLowest(_Symbol, _Period, MODE_LOW,  len, shift);
   if(idxHigh < 0 || idxLow < 0)
      return(EMPTY_VALUE);

   double hi = iHigh(_Symbol, _Period, idxHigh);
   double lo = iLow(_Symbol, _Period, idxLow);
   return((hi + lo) / 2.0);
  }

//+------------------------------------------------------------------+
bool GetIchimokuValues(const int shift, double &conv, double &base, double &lag,
                        double &leadA, double &leadB)
  {
   conv = Donchian(shift, InpConversionPeriods);
   base = Donchian(shift, InpBasePeriods);
   leadB = Donchian(shift, InpLaggingSpan2Periods);
   lag  = iClose(_Symbol, _Period, shift);

   if(conv == EMPTY_VALUE || base == EMPTY_VALUE || leadB == EMPTY_VALUE)
      return(false);

   leadA = (conv + base) / 2.0;
   return(true);
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
double SwingHigh(const int lookback)
  {
   int idx = iHighest(_Symbol, _Period, MODE_HIGH, lookback, 1);
   if(idx < 0)
      return(EMPTY_VALUE);
   return(iHigh(_Symbol, _Period, idx));
  }

//+------------------------------------------------------------------+
double SwingLow(const int lookback)
  {
   int idx = iLowest(_Symbol, _Period, MODE_LOW, lookback, 1);
   if(idx < 0)
      return(EMPTY_VALUE);
   return(iLow(_Symbol, _Period, idx));
  }

//+------------------------------------------------------------------+
void OnTick()
  {
   datetime barTime = iTime(_Symbol, _Period, 0);
   if(barTime == g_LastBarTime)
      return; // รอแท่งใหม่
   g_LastBarTime = barTime;

   double conv, base, lag, leadA, leadB;
   if(!GetIchimokuValues(1, conv, base, lag, leadA, leadB))
      return; // ข้อมูลย้อนหลังไม่พอ

   // v4: เงื่อนไขเดียว — Conversion vs Base เท่านั้น (ใช้ทั้งเปิดและปิด, mirror กัน)
   bool sellSignal = (conv < base);
   bool buySignal  = (conv > base);

   double point  = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   double buffer = InpSLBufferPoints * point;

   ENUM_POSITION_TYPE posType;
   bool hasPos = HasOpenPosition(posType);

   if(hasPos)
     {
      if((posType == POSITION_TYPE_SELL && buySignal) ||
         (posType == POSITION_TYPE_BUY  && sellSignal))
        {
         ClosePositions();
         hasPos = false;
        }
     }

   if(hasPos)
     {
      if(InpUseHHLL)
        {
         // ยังถือฝั่งเดิมอยู่ → เช็ค HH/LL renew (ปิดแล้วเข้าใหม่ฝั่งเดิมทันที ไม่รอ entry signal)
         string pivotLabel;
         if(HHLL_CheckNewPivot(_Symbol, _Period, InpHHLLLeft, InpHHLLRight, InpHHLLLookback, pivotLabel))
           {
            if(posType == POSITION_TYPE_BUY && (pivotLabel == "HH" || pivotLabel == "LH"))
              {
               ClosePositions();
               double sl = SwingLow(InpSwingLookback);
               if(sl != EMPTY_VALUE)
                 {
                  sl -= buffer;
                  trade.Buy(InpFixedLot, _Symbol, 0.0, sl, 0.0);
                 }
              }
            else if(posType == POSITION_TYPE_SELL && (pivotLabel == "LL" || pivotLabel == "HL"))
              {
               ClosePositions();
               double sl = SwingHigh(InpSwingLookback);
               if(sl != EMPTY_VALUE)
                 {
                  sl += buffer;
                  trade.Sell(InpFixedLot, _Symbol, 0.0, sl, 0.0);
                 }
              }
           }
        }
      else if(InpUseFractals)
        {
         // ยังถือฝั่งเดิมอยู่ → เช็ค Fractals renew (ปิดแล้วเข้าใหม่ฝั่งเดิมทันที ไม่รอ entry signal)
         bool fracUp, fracDown;
         Fractals_CheckNew(_Symbol, _Period, fracUp, fracDown);
         if(posType == POSITION_TYPE_BUY && fracUp)
           {
            ClosePositions();
            double sl = SwingLow(InpSwingLookback);
            if(sl != EMPTY_VALUE)
              {
               sl -= buffer;
               trade.Buy(InpFixedLot, _Symbol, 0.0, sl, 0.0);
              }
           }
         else if(posType == POSITION_TYPE_SELL && fracDown)
           {
            ClosePositions();
            double sl = SwingHigh(InpSwingLookback);
            if(sl != EMPTY_VALUE)
              {
               sl += buffer;
               trade.Sell(InpFixedLot, _Symbol, 0.0, sl, 0.0);
              }
           }
        }
      return; // ไม่ว่า renew หรือไม่ ก็มี position ฝั่งเดิมอยู่แล้ว ไม่ต้องเช็ค entry ใหม่
     }

   if(buySignal)
     {
      double sl = SwingLow(InpSwingLookback);
      if(sl != EMPTY_VALUE)
        {
         sl -= buffer;
         trade.Buy(InpFixedLot, _Symbol, 0.0, sl, 0.0);
        }
     }
   else if(sellSignal)
     {
      double sl = SwingHigh(InpSwingLookback);
      if(sl != EMPTY_VALUE)
        {
         sl += buffer;
         trade.Sell(InpFixedLot, _Symbol, 0.0, sl, 0.0);
        }
     }
  }
//+------------------------------------------------------------------+
