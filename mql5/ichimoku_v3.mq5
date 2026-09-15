//+------------------------------------------------------------------+
//|                                                 ichimoku_v3.mq5   |
//|  Ichimoku Cloud v3 (แปลงจาก Pine Script v6 "Ichimoku Cloud")      |
//|  ⚠️ v3: Entry (เปิด order) ใช้เงื่อนไขเต็ม รวม Lead A/Lead B         |
//|         Exit (ปิด order) ใช้เงื่อนไขแบบย่อ ไม่รวม Lead A/Lead B      |
//|         → ปิด position เดิมได้ก่อนที่สัญญาณเปิดฝั่งใหม่จะ confirm    |
//|           (อาจมีช่วง flat คั่นระหว่างปิดกับเปิดฝั่งใหม่)             |
//|                                                                     |
//|  Conversion Line  = donchian(conversionPeriods)                    |
//|  Base Line        = donchian(basePeriods)                          |
//|  Leading Span A    = avg(Conversion, Base), offset +displacement   |
//|  Leading Span B    = donchian(laggingSpan2Periods), offset +displ. |
//|  Lagging Span       = close, offset -displacement                  |
//|  donchian(len)     = avg(lowest(len), highest(len))                |
//+------------------------------------------------------------------+
#property copyright   "Copter01 AI Bot"
#property link        ""
#property version     "3.00"
#property indicator_chart_window
#property indicator_buffers 7
#property indicator_plots   6

#include "HHLL_Lib.mqh"
#include "Fractals_Lib.mqh"

// สีตรงตาม Pine Script ต้นฉบับ: #2962FF/#B71C1C/#43A047/#A5D6A7/#EF9A9A
#property indicator_label1  "Conversion Line"
#property indicator_type1   DRAW_LINE
#property indicator_color1  C'41,98,255'
#property indicator_width1  1

#property indicator_label2  "Base Line"
#property indicator_type2   DRAW_LINE
#property indicator_color2  C'183,28,28'
#property indicator_width2  1

#property indicator_label3  "Lagging Span"
#property indicator_type3   DRAW_LINE
#property indicator_color3  C'67,160,71'
#property indicator_width3  1

#property indicator_label4  "Leading Span A"
#property indicator_type4   DRAW_LINE
#property indicator_color4  C'165,214,167'
#property indicator_width4  1

#property indicator_label5  "Leading Span B"
#property indicator_type5   DRAW_LINE
#property indicator_color5  C'239,154,154'
#property indicator_width5  1

// Cloud fill: LightGoldenrod (Lead A > Lead B) / LightSalmon (Lead A < Lead B)
#property indicator_label6  "Kumo Cloud"
#property indicator_type6   DRAW_FILLING
#property indicator_color6  clrLightGoldenrod,clrLightSalmon

input int InpConversionPeriods  = 9;   // Conversion Line Length
input int InpBasePeriods        = 26;  // Base Line Length
input int InpLaggingSpan2Periods = 52; // Leading Span B Length
input int InpDisplacement       = 26;  // Lagging Span / Displacement

input bool             InpShowTable   = true;             // แสดงตารางราคาเรียลไทม์
input ENUM_BASE_CORNER InpTableCorner = CORNER_RIGHT_LOWER; // มุมของตาราง
input int              InpTableX      = 10;                // ระยะขอบ X
input int              InpTableY      = 20;                // ระยะขอบ Y
input int              InpTableMarginTop = 20;              // margin top เพิ่ม (ผลักตารางออกจากมุมยึด)
input int              InpTableFontSize = 9;                // ขนาดตัวอักษร

input bool InpShowSignals        = true; // แสดงจุด Entry/SL/TP บนกราฟ (ดูคร่าวๆ ไม่ใช่ยิงออเดอร์จริง)
input int  InpSwingLookback      = 20;   // ย้อนหลังกี่แท่งหา swing high/low (สำหรับ SL)
input int  InpSLBufferPoints     = 50;   // buffer เพิ่มจาก swing high/low (points)
input int  InpSignalLookbackBars = 0;    // วาดสัญญาณย้อนหลังกี่แท่งล่าสุด (0 = ไม่จำกัด วาดตามข้อมูลที่โหลด/เลื่อนดู)
input double InpVisualLotSize    = 0.01; // lot ที่ใช้คำนวณกำไร/ขาดทุน (USD) บนกราฟเท่านั้น (ต้องตรงกับ EA)

input bool InpUseHHLL         = true;  // เปิดใช้ HH/LL renew (ปิดแล้วเข้าใหม่ฝั่งเดิมทันที)
input bool InpUseFractals     = false; // เปิดใช้ Fractals renew (ปิดแล้วเข้าใหม่ฝั่งเดิมทันทีเมื่อเจอ fractal ตรงข้าม) — เลือกได้แค่ตัวเดียว

input int  InpHHLLLeft     = 5;    // HH/LL pivot: left bars
input int  InpHHLLRight    = 5;    // HH/LL pivot: right bars
input int  InpHHLLLookback = 500;  // HH/LL pivot: max lookback bars
input int  InpFractalsLookback = 500; // Fractals (Left=2,Right=2 ตายตัว): max lookback bars

// สถานะ position (จำลองตาม logic ของ EA): 0=ไม่มี, 1=BUY, -1=SELL
int      g_OpenDir        = 0;
datetime g_OpenEntryTime  = 0;
double   g_OpenEntryPrice = 0;

double ConversionBuffer[];
double BaseBuffer[];
double LaggingBuffer[];
double LeadSpanABuffer[];
double LeadSpanBBuffer[];
double CloudABuffer[];
double CloudBBuffer[];

#define ICHI_ROWS 5
string  g_TblPrefix;
string  g_RowNames[ICHI_ROWS] = {"Conversion","Base","Lagging","Lead A","Lead B"};
color   g_RowColors[ICHI_ROWS] = {C'41,98,255', C'183,28,28', C'67,160,71', C'165,214,167', C'239,154,154'};

string  g_SigPrefix;

//+------------------------------------------------------------------+
int OnInit()
  {
   SetIndexBuffer(0, ConversionBuffer, INDICATOR_DATA);
   SetIndexBuffer(1, BaseBuffer,       INDICATOR_DATA);
   SetIndexBuffer(2, LaggingBuffer,    INDICATOR_DATA);
   SetIndexBuffer(3, LeadSpanABuffer,  INDICATOR_DATA);
   SetIndexBuffer(4, LeadSpanBBuffer,  INDICATOR_DATA);
   SetIndexBuffer(5, CloudABuffer,     INDICATOR_DATA);
   SetIndexBuffer(6, CloudBBuffer,     INDICATOR_DATA);

   PlotIndexSetInteger(2, PLOT_SHIFT, -InpDisplacement + 1);
   PlotIndexSetInteger(3, PLOT_SHIFT,  InpDisplacement - 1);
   PlotIndexSetInteger(4, PLOT_SHIFT,  InpDisplacement - 1);
   PlotIndexSetInteger(5, PLOT_SHIFT,  InpDisplacement - 1);

   ArraySetAsSeries(ConversionBuffer, false);
   ArraySetAsSeries(BaseBuffer,       false);
   ArraySetAsSeries(LaggingBuffer,    false);
   ArraySetAsSeries(LeadSpanABuffer,  false);
   ArraySetAsSeries(LeadSpanBBuffer,  false);
   ArraySetAsSeries(CloudABuffer,     false);
   ArraySetAsSeries(CloudBBuffer,     false);

   int maxLen = MathMax(InpConversionPeriods, MathMax(InpBasePeriods, InpLaggingSpan2Periods));
   IndicatorSetInteger(INDICATOR_DIGITS, _Digits);
   PlotIndexSetInteger(0, PLOT_DRAW_BEGIN, maxLen - 1);
   PlotIndexSetInteger(1, PLOT_DRAW_BEGIN, maxLen - 1);
   PlotIndexSetInteger(3, PLOT_DRAW_BEGIN, maxLen - 1);
   PlotIndexSetInteger(4, PLOT_DRAW_BEGIN, maxLen - 1);
   PlotIndexSetInteger(5, PLOT_DRAW_BEGIN, maxLen - 1);

   g_TblPrefix = "IchiTbl_" + IntegerToString(ChartID()) + "_";
   ObjectsDeleteAll(0, g_TblPrefix); // ล้าง object ค้างจาก session ก่อนหน้า กันซ้อนทับ/เหลื่อม
   if(InpShowTable)
      CreateTable();

   g_SigPrefix = "IchiSig_" + IntegerToString(ChartID()) + "_";
   ObjectsDeleteAll(0, g_SigPrefix);
   g_OpenDir = 0;
   g_OpenEntryTime = 0;
   g_OpenEntryPrice = 0;

   return(INIT_SUCCEEDED);
  }

//+------------------------------------------------------------------+
void OnDeinit(const int reason)
  {
   ObjectsDeleteAll(0, g_TblPrefix);
   ObjectsDeleteAll(0, g_SigPrefix);
  }

//+------------------------------------------------------------------+
void CreateLabel(const string name, const int x, const int y, const string text,
                  const color clr, const int fontSize, const bool bold = false)
  {
   if(ObjectFind(0, name) < 0)
      ObjectCreate(0, name, OBJ_LABEL, 0, 0, 0);
   ObjectSetInteger(0, name, OBJPROP_CORNER, InpTableCorner);
   ObjectSetInteger(0, name, OBJPROP_XDISTANCE, x);
   ObjectSetInteger(0, name, OBJPROP_YDISTANCE, y);
   ObjectSetInteger(0, name, OBJPROP_COLOR, clr);
   ObjectSetInteger(0, name, OBJPROP_FONTSIZE, fontSize);
   ObjectSetString(0, name, OBJPROP_FONT, bold ? "Arial Bold" : "Arial");
   ObjectSetString(0, name, OBJPROP_TEXT, text);
   ObjectSetInteger(0, name, OBJPROP_SELECTABLE, false);
   ObjectSetInteger(0, name, OBJPROP_HIDDEN, true);
   ObjectSetInteger(0, name, OBJPROP_BACK, false);
  }


// ตำแหน่งเริ่ม/ความกว้างของแต่ละคอลัมน์: No | Name | Price (ตัด Color ออก, Price ใช้สีข้อความแทน)
int g_ColStart[3] = {0, 26, 120};
int g_ColWidth[3] = {22, 90, 70};
#define ICHI_TABLE_W 190

//+------------------------------------------------------------------+
// คำนวณระยะจากมุมของอ็อบเจ็กต์ — ถ้ามุมเป็นขวา/ล่าง ต้องกลับด้าน (mirror)
// เพื่อให้ลำดับคอลัมน์/แถวบนหน้าจอยังคงเรียง No→Price และ header→แถวข้อมูลเหมือนเดิม
// หมายเหตุ: label anchor เป็น LEFT_UPPER เสมอ (วาดข้อความจากซ้ายไปขวาเหมือนกันทุกมุม)
// จึงมิเรอร์แค่ตำแหน่งเริ่ม ห้ามลบ "size" ออก มิฉะนั้นช่องที่ความกว้างไม่เท่ากันจะเบียดกัน
int MirrorPos(const int offset, const int total, const bool mirror, const int margin)
  {
   if(!mirror)
      return(margin + offset);
   return(margin + (total - offset));
  }

//+------------------------------------------------------------------+
int TableColX(const int col)
  {
   bool mirror = (InpTableCorner == CORNER_RIGHT_UPPER || InpTableCorner == CORNER_RIGHT_LOWER);
   return(MirrorPos(g_ColStart[col], ICHI_TABLE_W, mirror, InpTableX));
  }

//+------------------------------------------------------------------+
int TableRowY(const int row, const int rowH, const int totalRows)
  {
   bool mirror = (InpTableCorner == CORNER_LEFT_LOWER || InpTableCorner == CORNER_RIGHT_LOWER);
   int offset  = rowH * row;
   int totalH  = rowH * totalRows;
   return(MirrorPos(offset, totalH, mirror, InpTableY + InpTableMarginTop));
  }

//+------------------------------------------------------------------+
void CreateTable()
  {
   int rowH = InpTableFontSize + 10;
   int totalRows = ICHI_ROWS + 1; // header + data rows
   int y;

   y = TableRowY(0, rowH, totalRows);
   CreateLabel(g_TblPrefix + "hdr_no",    TableColX(0), y, "No",    clrWhite, InpTableFontSize, true);
   CreateLabel(g_TblPrefix + "hdr_name",  TableColX(1), y, "Name",  clrWhite, InpTableFontSize, true);
   CreateLabel(g_TblPrefix + "hdr_price", TableColX(2), y, "Price", clrWhite, InpTableFontSize, true);

   for(int i = 0; i < ICHI_ROWS; i++)
     {
      y = TableRowY(i + 1, rowH, totalRows);
      CreateLabel(g_TblPrefix + "no" + IntegerToString(i), TableColX(0), y,
                  IntegerToString(i + 1), clrWhite, InpTableFontSize);
      CreateLabel(g_TblPrefix + "name" + IntegerToString(i), TableColX(1), y,
                  g_RowNames[i], clrWhite, InpTableFontSize);
      CreateLabel(g_TblPrefix + "price" + IntegerToString(i), TableColX(2), y,
                  "-", g_RowColors[i], InpTableFontSize);
     }
  }

//+------------------------------------------------------------------+
void UpdateTable(const double conv, const double base, const double lag,
                  const double leadA, const double leadB)
  {
   double vals[ICHI_ROWS];
   vals[0] = conv;
   vals[1] = base;
   vals[2] = lag;
   vals[3] = leadA;
   vals[4] = leadB;

   for(int i = 0; i < ICHI_ROWS; i++)
     {
      string txt = (vals[i] == EMPTY_VALUE) ? "-" : DoubleToString(vals[i], _Digits);
      ObjectSetString(0, g_TblPrefix + "price" + IntegerToString(i), OBJPROP_TEXT, txt);
     }
  }

//+------------------------------------------------------------------+
double Donchian(const double &high[], const double &low[], int shift, int len, int rates_total)
  {
   if(shift - len + 1 < 0)
      return(EMPTY_VALUE);

   double hi = high[shift];
   double lo = low[shift];
   for(int i = 1; i < len; i++)
     {
      int idx = shift - i;
      if(high[idx] > hi) hi = high[idx];
      if(low[idx]  < lo) lo = low[idx];
     }
   return((hi + lo) / 2.0);
  }

//+------------------------------------------------------------------+
// v3: เงื่อนไขแยก 2 ชุด
//   Strict*  (มี Lead A/B) — ใช้ตอน "เปิด" position ใหม่เท่านั้น
//   Relaxed* (ไม่มี Lead A/B) — ใช้ตอน "ปิด" position ฝั่งตรงข้ามเท่านั้น
bool RelaxedSellSignalAt(const int i)
  {
   if(ConversionBuffer[i] == EMPTY_VALUE || BaseBuffer[i] == EMPTY_VALUE)
      return(false);
   return(LaggingBuffer[i] < ConversionBuffer[i] && LaggingBuffer[i] < BaseBuffer[i] &&
          ConversionBuffer[i] < BaseBuffer[i]);
  }

bool RelaxedBuySignalAt(const int i)
  {
   if(ConversionBuffer[i] == EMPTY_VALUE || BaseBuffer[i] == EMPTY_VALUE)
      return(false);
   return(LaggingBuffer[i] > ConversionBuffer[i] && LaggingBuffer[i] > BaseBuffer[i] &&
          ConversionBuffer[i] > BaseBuffer[i]);
  }

bool StrictSellSignalAt(const int i)
  {
   if(LeadSpanBBuffer[i] == EMPTY_VALUE)
      return(false);
   return(RelaxedSellSignalAt(i) && LeadSpanABuffer[i] < LeadSpanBBuffer[i]);
  }

bool StrictBuySignalAt(const int i)
  {
   if(LeadSpanBBuffer[i] == EMPTY_VALUE)
      return(false);
   return(RelaxedBuySignalAt(i) && LeadSpanABuffer[i] > LeadSpanBBuffer[i]);
  }

//+------------------------------------------------------------------+
double SwingHighAt(const double &high[], const int i, const int lookback)
  {
   int from = MathMax(0, i - lookback + 1);
   double hi = high[from];
   for(int k = from; k <= i; k++)
      if(high[k] > hi) hi = high[k];
   return(hi);
  }

double SwingLowAt(const double &low[], const int i, const int lookback)
  {
   int from = MathMax(0, i - lookback + 1);
   double lo = low[from];
   for(int k = from; k <= i; k++)
      if(low[k] < lo) lo = low[k];
   return(lo);
  }

//+------------------------------------------------------------------+
// วาดจุด Entry (ลูกศร) + เส้น SL แบบคร่าวๆ ให้ดูตำแหน่งบนกราฟ (ไม่ใช่ order จริง)
void DrawSignal(const datetime t, const double entryPrice, const double slPrice, const bool isBuy)
  {
   string tag  = isBuy ? "buy" : "sell";
   string base = g_SigPrefix + tag + "_" + IntegerToString((long)t);

   string arrowName = base + "_entry";
   if(ObjectFind(0, arrowName) < 0)
      ObjectCreate(0, arrowName, isBuy ? OBJ_ARROW_BUY : OBJ_ARROW_SELL, 0, t, entryPrice);
   ObjectSetInteger(0, arrowName, OBJPROP_COLOR, isBuy ? clrLime : clrRed);
   ObjectSetInteger(0, arrowName, OBJPROP_WIDTH, 2);
   ObjectSetInteger(0, arrowName, OBJPROP_SELECTABLE, false);
   ObjectSetInteger(0, arrowName, OBJPROP_HIDDEN, true);
   ObjectSetString(0, arrowName, OBJPROP_TOOLTIP,
                    (isBuy ? "BUY entry ~ " : "SELL entry ~ ") + DoubleToString(entryPrice, _Digits));

   datetime tEnd = t + PeriodSeconds(_Period) * 10;
   string slName = base + "_sl";
   if(ObjectFind(0, slName) < 0)
      ObjectCreate(0, slName, OBJ_TREND, 0, t, slPrice, tEnd, slPrice);
   else
     {
      ObjectMove(0, slName, 0, t, slPrice);
      ObjectMove(0, slName, 1, tEnd, slPrice);
     }
   ObjectSetInteger(0, slName, OBJPROP_COLOR, clrRed);
   ObjectSetInteger(0, slName, OBJPROP_STYLE, STYLE_DASH);
   ObjectSetInteger(0, slName, OBJPROP_WIDTH, 1);
   ObjectSetInteger(0, slName, OBJPROP_RAY_RIGHT, false);
   ObjectSetInteger(0, slName, OBJPROP_SELECTABLE, false);
   ObjectSetInteger(0, slName, OBJPROP_HIDDEN, true);
   ObjectSetString(0, slName, OBJPROP_TOOLTIP, "SL ~ " + DoubleToString(slPrice, _Digits));
  }

//+------------------------------------------------------------------+
// กำไร/ขาดทุนโดยประมาณเป็น USD (ใช้ InpVisualLotSize) — สำหรับแสดงผลบนกราฟเท่านั้น
double CalcPnLUSD(const double entryPrice, const double exitPrice, const bool isBuy)
  {
   double tickSize  = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   double tickValue = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   if(tickSize <= 0.0)
      return(0.0);

   double priceDiff = isBuy ? (exitPrice - entryPrice) : (entryPrice - exitPrice);
   return(priceDiff / tickSize * tickValue * InpVisualLotSize);
  }

//+------------------------------------------------------------------+
// วาดจุด TP/ปิดออเดอร์ = ราคาปิดของแท่งที่เกิดสัญญาณฝั่งตรงข้าม + เส้นเชื่อมจาก entry
// เขียว = กำไร, แดง = ขาดทุน (เหมือนเส้น SL ที่แดงอยู่แล้ว) พร้อม label บอกจำนวน USD
void DrawExit(const datetime entryTime, const double entryPrice,
               const datetime exitTime, const double exitPrice, const bool wasBuy)
  {
   string tag  = wasBuy ? "buy" : "sell";
   string name = g_SigPrefix + tag + "_tp_" + IntegerToString((long)exitTime);

   bool  profit = wasBuy ? (exitPrice > entryPrice) : (exitPrice < entryPrice);
   color clr    = profit ? clrLime : clrRed;

   if(ObjectFind(0, name) < 0)
      ObjectCreate(0, name, OBJ_ARROW_CHECK, 0, exitTime, exitPrice);
   ObjectSetInteger(0, name, OBJPROP_COLOR, clr);
   ObjectSetInteger(0, name, OBJPROP_WIDTH, 2);
   ObjectSetInteger(0, name, OBJPROP_SELECTABLE, false);
   ObjectSetInteger(0, name, OBJPROP_HIDDEN, true);
   ObjectSetString(0, name, OBJPROP_TOOLTIP,
                    "TP (" + (wasBuy ? "Buy" : "Sell") + " ปิดด้วยสัญญาณกลับด้าน) ~ " +
                    DoubleToString(exitPrice, _Digits));

   string lineName = g_SigPrefix + tag + "_tpline_" + IntegerToString((long)exitTime);
   if(ObjectFind(0, lineName) < 0)
      ObjectCreate(0, lineName, OBJ_TREND, 0, entryTime, entryPrice, exitTime, exitPrice);
   else
     {
      ObjectMove(0, lineName, 0, entryTime, entryPrice);
      ObjectMove(0, lineName, 1, exitTime, exitPrice);
     }
   ObjectSetInteger(0, lineName, OBJPROP_COLOR, clr);
   ObjectSetInteger(0, lineName, OBJPROP_STYLE, STYLE_DOT);
   ObjectSetInteger(0, lineName, OBJPROP_WIDTH, 1);
   ObjectSetInteger(0, lineName, OBJPROP_RAY_RIGHT, false);
   ObjectSetInteger(0, lineName, OBJPROP_SELECTABLE, false);
   ObjectSetInteger(0, lineName, OBJPROP_HIDDEN, true);

   double pnl = CalcPnLUSD(entryPrice, exitPrice, wasBuy);
   string pnlText = (pnl >= 0 ? "+" : "") + DoubleToString(pnl, 2) + " USD";

   string txtName = g_SigPrefix + tag + "_tptxt_" + IntegerToString((long)exitTime);
   if(ObjectFind(0, txtName) < 0)
      ObjectCreate(0, txtName, OBJ_TEXT, 0, exitTime, exitPrice);
   else
      ObjectMove(0, txtName, 0, exitTime, exitPrice);
   ObjectSetString(0, txtName, OBJPROP_TEXT, pnlText);
   ObjectSetInteger(0, txtName, OBJPROP_COLOR, clr);
   ObjectSetInteger(0, txtName, OBJPROP_FONTSIZE, 8);
   ObjectSetInteger(0, txtName, OBJPROP_ANCHOR, ANCHOR_LOWER);
   ObjectSetInteger(0, txtName, OBJPROP_SELECTABLE, false);
   ObjectSetInteger(0, txtName, OBJPROP_HIDDEN, true);
  }

//+------------------------------------------------------------------+
int OnCalculate(const int rates_total,
                 const int prev_calculated,
                 const datetime &time[],
                 const double &open[],
                 const double &high[],
                 const double &low[],
                 const double &close[],
                 const long &tick_volume[],
                 const long &volume[],
                 const int &spread[])
  {
   int start = prev_calculated > 0 ? prev_calculated - 1 : 0;

   for(int i = start; i < rates_total; i++)
     {
      double conv = Donchian(high, low, i, InpConversionPeriods, rates_total);
      double base = Donchian(high, low, i, InpBasePeriods, rates_total);
      double leadB = Donchian(high, low, i, InpLaggingSpan2Periods, rates_total);

      ConversionBuffer[i] = conv;
      BaseBuffer[i]       = base;
      LaggingBuffer[i]    = close[i];

      if(conv != EMPTY_VALUE && base != EMPTY_VALUE)
         LeadSpanABuffer[i] = (conv + base) / 2.0;
      else
         LeadSpanABuffer[i] = EMPTY_VALUE;

      LeadSpanBBuffer[i] = leadB;

      CloudABuffer[i] = LeadSpanABuffer[i];
      CloudBBuffer[i] = leadB;
     }

   if(InpShowTable && rates_total > 0)
     {
      int last = rates_total - 1;
      UpdateTable(ConversionBuffer[last], BaseBuffer[last], LaggingBuffer[last],
                  LeadSpanABuffer[last], LeadSpanBBuffer[last]);
     }

   if(InpShowSignals)
     {
      int sigStart = MathMax(start, 1);
      if(start == 0) // คำนวณใหม่ทั้งประวัติ ต้องรีเซ็ตสถานะ position จำลอง
        {
         g_OpenDir = 0;
         g_OpenEntryTime = 0;
         g_OpenEntryPrice = 0;
        }
      double buffer = InpSLBufferPoints * _Point;

      // สร้าง pivot HH/HL/LH/LL (สำหรับ HHLL mode) และ Fractals (สำหรับ Fractals mode)
      // ครั้งเดียวต่อรอบคำนวณ (เฉพาะแท่งที่ปิดแล้ว, ไม่รวมแท่งกำลังฟอร์ม)
      bool isHH[], isHL[], isLH[], isLL[];
      bool isFracUp[], isFracDown[];
      int pivotN = MathMax(rates_total - 1, 0);
      if(InpUseHHLL && !InpUseFractals)
         HHLL_MarkPivots(high, low, time, pivotN, InpHHLLLeft, InpHHLLRight, InpHHLLLookback, isHH, isHL, isLH, isLL);
      if(InpUseFractals)
         Fractals_MarkAll(high, low, pivotN, InpFractalsLookback, isFracUp, isFracDown);

      // v3: ปิด position ด้วยเงื่อนไขแบบย่อ (relaxed, ไม่มี Lead A/B)
      //     เปิด position ใหม่ด้วยเงื่อนไขเต็ม (strict, มี Lead A/B) เท่านั้น
      //     → อาจมีช่วง flat คั่นระหว่างปิดฝั่งเดิมกับเปิดฝั่งใหม่
      // HHLL renew: ถือ BUY แล้วเจอ HH/LH หรือถือ SELL แล้วเจอ LL/HL → ปิดแล้วเข้าใหม่ฝั่งเดิมทันที
      // Fractals renew: ถือ BUY แล้วเจอ fractal บน / ถือ SELL แล้วเจอ fractal ล่าง → ปิดแล้วเข้าใหม่ฝั่งเดิมทันที
      for(int i = sigStart; i < rates_total; i++)
        {
         bool relaxSell = RelaxedSellSignalAt(i);
         bool relaxBuy  = RelaxedBuySignalAt(i);
         bool strictSell = StrictSellSignalAt(i);
         bool strictBuy  = StrictBuySignalAt(i);
         bool pivotHH = (InpUseHHLL && !InpUseFractals && i < pivotN) && (isHH[i] || isLH[i]);
         bool pivotLL = (InpUseHHLL && !InpUseFractals && i < pivotN) && (isLL[i] || isHL[i]);
         bool fracUp   = (InpUseFractals && i < pivotN) && isFracUp[i];
         bool fracDown = (InpUseFractals && i < pivotN) && isFracDown[i];
         bool draw    = (InpSignalLookbackBars <= 0) || (rates_total - 1 - i <= InpSignalLookbackBars);

         if(g_OpenDir == 1 && relaxSell) // ปิด BUY ด้วย TP = close ของแท่งสัญญาณ Sell (แบบย่อ, เปลี่ยนฝั่งจริง)
           {
            if(draw)
               DrawExit(g_OpenEntryTime, g_OpenEntryPrice, time[i], close[i], true);
            g_OpenDir = 0;
           }
         else if(g_OpenDir == -1 && relaxBuy) // ปิด SELL ด้วย TP = close ของแท่งสัญญาณ Buy (แบบย่อ, เปลี่ยนฝั่งจริง)
           {
            if(draw)
               DrawExit(g_OpenEntryTime, g_OpenEntryPrice, time[i], close[i], false);
            g_OpenDir = 0;
           }
         else if(g_OpenDir == 1 && pivotHH) // HHLL renew BUY (ไม่เปลี่ยนฝั่ง)
           {
            if(draw)
               DrawExit(g_OpenEntryTime, g_OpenEntryPrice, time[i], close[i], true);
            double sl = SwingLowAt(low, i, InpSwingLookback) - buffer;
            if(draw)
               DrawSignal(time[i], close[i], sl, true);
            g_OpenEntryTime  = time[i];
            g_OpenEntryPrice = close[i];
           }
         else if(g_OpenDir == -1 && pivotLL) // HHLL renew SELL (ไม่เปลี่ยนฝั่ง)
           {
            if(draw)
               DrawExit(g_OpenEntryTime, g_OpenEntryPrice, time[i], close[i], false);
            double sl = SwingHighAt(high, i, InpSwingLookback) + buffer;
            if(draw)
               DrawSignal(time[i], close[i], sl, false);
            g_OpenEntryTime  = time[i];
            g_OpenEntryPrice = close[i];
           }
         else if(g_OpenDir == 1 && fracUp) // Fractals renew BUY (ไม่เปลี่ยนฝั่ง)
           {
            if(draw)
               DrawExit(g_OpenEntryTime, g_OpenEntryPrice, time[i], close[i], true);
            double sl = SwingLowAt(low, i, InpSwingLookback) - buffer;
            if(draw)
               DrawSignal(time[i], close[i], sl, true);
            g_OpenEntryTime  = time[i];
            g_OpenEntryPrice = close[i];
           }
         else if(g_OpenDir == -1 && fracDown) // Fractals renew SELL (ไม่เปลี่ยนฝั่ง)
           {
            if(draw)
               DrawExit(g_OpenEntryTime, g_OpenEntryPrice, time[i], close[i], false);
            double sl = SwingHighAt(high, i, InpSwingLookback) + buffer;
            if(draw)
               DrawSignal(time[i], close[i], sl, false);
            g_OpenEntryTime  = time[i];
            g_OpenEntryPrice = close[i];
           }

         if(g_OpenDir == 0)
           {
            if(strictSell)
              {
               double sl = SwingHighAt(high, i, InpSwingLookback) + buffer;
               if(draw)
                  DrawSignal(time[i], close[i], sl, false);
               g_OpenDir = -1;
               g_OpenEntryTime  = time[i];
               g_OpenEntryPrice = close[i];
              }
            else if(strictBuy)
              {
               double sl = SwingLowAt(low, i, InpSwingLookback) - buffer;
               if(draw)
                  DrawSignal(time[i], close[i], sl, true);
               g_OpenDir = 1;
               g_OpenEntryTime  = time[i];
               g_OpenEntryPrice = close[i];
              }
           }
        }
     }

   return(rates_total);
  }
//+------------------------------------------------------------------+
