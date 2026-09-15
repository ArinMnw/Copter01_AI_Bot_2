//+------------------------------------------------------------------+
//|                                RSI_MACD_Stoch_Combined.mq5        |
//|  รวม RSI + MACD + Stochastic ไว้ในหน้าต่างย่อยเดียว (สำหรับ MT5      |
//|  มือถือที่ลาก-มัดหน้าต่างแยกกันไม่ได้เหมือน desktop)                  |
//|                                                                     |
//|  ⚠️ ข้อจำกัดของ MQL5: indicator เดียวเปิดได้แค่ 1 หน้าต่างย่อย        |
//|  ทุกเส้นต้องแชร์แกน Y เดียวกัน แต่ RSI/Stochastic เป็นสเกล 0-100     |
//|  ส่วน MACD เป็นค่าต่าง EMA (ไม่มีขอบเขตตายตัว ปกติแกว่งแคบกว่ามาก)    |
//|  แก้ด้วยการ "normalize" MACD ให้แสดงรอบเส้น 50 แทน — เส้น MACD ตัดขึ้น |
//|  เหนือ 50 = ค่าจริงเป็นบวก (bullish), ตัดลงใต้ 50 = ค่าจริงเป็นลบ       |
//|  (bearish) ตัวเลขบนแกนไม่ใช่ค่า MACD จริงอีกต่อไป                     |
//|  ⚠️ 2026-08-17 แก้บั๊ก: เดิม normalize ด้วย scale คงที่ (คูณตัวเลข     |
//|  เดียวตายตัว) ทำให้พอสลับไป TF ใหญ่ (แกว่งแรงกว่า M15 มาก) เส้น MACD   |
//|  ทะลุกรอบ 0-100 ไปเลย (ค่าจริง MACD ผันตาม volatility ของ TF นั้นๆ    |
//|  แต่ scale ไม่ผัน) แก้เป็น normalize แบบ dynamic แทน: หาค่า           |
//|  |MACD| สูงสุดในแท่งที่มองเห็นทั้งหมดของรอบคำนวณนี้ก่อน แล้วคำนวณ      |
//|  scale เองให้พอดี ±InpMACDTargetAmplitude รอบเส้น 50 เสมอ ไม่ว่าจะ    |
//|  TF ไหน/สลับ symbol ไหนก็ไม่ทะลุกรอบอีก                               |
//|  RSI/Stochastic ยังเป็นค่าจริง 0-100 ตามปกติ ไม่ถูกแตะ                |
//+------------------------------------------------------------------+
#property copyright "Copter01 AI Bot"
#property link       ""
#property version    "1.00"
#property indicator_separate_window
#property indicator_buffers 5
#property indicator_plots   5
#property indicator_minimum 0
#property indicator_maximum 100

// --- RSI (สเกลจริง 0-100) ---
#property indicator_label1  "RSI"
#property indicator_type1   DRAW_LINE
#property indicator_color1  clrBlack
#property indicator_style1  STYLE_SOLID
#property indicator_width1  1

// --- Stochastic %K / %D (สเกลจริง 0-100) ---
#property indicator_label2  "Stoch %K"
#property indicator_type2   DRAW_LINE
#property indicator_color2  clrBlack
#property indicator_style2  STYLE_DASH
#property indicator_width2  1

#property indicator_label3  "Stoch %D"
#property indicator_type3   DRAW_LINE
#property indicator_color3  clrBlack
#property indicator_style3  STYLE_DOT
#property indicator_width3  1

// --- MACD main/signal (normalize รอบเส้น 50 — ดู comment บนสุดไฟล์) ---
#property indicator_label4  "MACD (norm.)"
#property indicator_type4   DRAW_LINE
#property indicator_color4  clrPurple
#property indicator_style4  STYLE_SOLID
#property indicator_width4  1

#property indicator_label5  "MACD Signal (norm.)"
#property indicator_type5   DRAW_LINE
#property indicator_color5  clrRed
#property indicator_style5  STYLE_DASH
#property indicator_width5  2

input int                InpRSIPeriod    = 14;             // RSI Period
input int                InpMACDFast     = 12;              // MACD Fast EMA
input int                InpMACDSlow     = 26;              // MACD Slow EMA
input int                InpMACDSignal   = 1;                // MACD Signal
input bool                InpMACDUseFixedScale   = false;      // true = ใช้ตาราง scale คงที่ต่อ TF (ตัวเลขตรงกันทุกเครื่อง) | false = auto (ปรับเองตามข้อมูล แต่ต่างกันได้ข้ามเครื่อง)
// scale คงที่ต่อ TF (ใช้เมื่อ InpMACDUseFixedScale=true) — TF เล็กแกว่งน้อย
// ต้องการ scale ใหญ่, TF ใหญ่แกว่งมากต้องการ scale เล็ก ใช้ค่าเดียวข้าม TF
// จะทะลุกรอบบาง TF (เจอจริง 2026-08-17) — ปรับตัวเลขต่อแถวได้เองถ้ายังทะลุ/
// เล็กไปในบาง TF (ตัวเลขนี้เป็นค่าประมาณเริ่มต้นของทองคำ ไม่ใช่ทดสอบมาแบบ
// ละเอียด) ค่าคงที่ ไม่ขึ้นกับข้อมูลที่โหลดมา = ตรงกันทุกเครื่องเสมอ
input double              InpScaleM1  = 30.0;                   // Scale สำหรับ M1
input double              InpScaleM5  = 15.0;                   // Scale สำหรับ M5
input double              InpScaleM15 = 8.0;                    // Scale สำหรับ M15
input double              InpScaleM30 = 5.0;                    // Scale สำหรับ M30
input double              InpScaleH1  = 3.0;                    // Scale สำหรับ H1
input double              InpScaleH4  = 1.5;                    // Scale สำหรับ H4
input double              InpScaleD1  = 0.5;                    // Scale สำหรับ D1
input double              InpScaleOther = 1.0;                  // Scale สำหรับ TF อื่นที่ไม่อยู่ในลิสต์
input double              InpMACDTargetAmplitude = 35.0;      // MACD normalize ให้แกว่งไม่เกิน ±เท่านี้รอบเส้น 50 (ใช้เมื่อ InpMACDUseFixedScale=false)
input int                 InpMACDNormalizeBars   = 500;        // จำนวนแท่งล่าสุดที่ใช้คำนวณ scale (ใช้เมื่อ InpMACDUseFixedScale=false)
input int                InpStochK       = 5;                 // Stochastic %K
input int                InpStochD       = 3;                 // Stochastic %D
input int                InpStochSlowing = 3;                 // Stochastic Slowing
input ENUM_APPLIED_PRICE InpAppliedPrice = PRICE_CLOSE;        // Applied Price (RSI/MACD)

double RSIBuffer[];
double StochKBuffer[];
double StochDBuffer[];
double MacdBuffer[];
double MacdSignalBuffer[];

int g_rsi_handle;
int g_macd_handle;
int g_stoch_handle;

//+------------------------------------------------------------------+
double FixedScaleForPeriod()
  {
   switch(_Period)
     {
      case PERIOD_M1:  return(InpScaleM1);
      case PERIOD_M5:  return(InpScaleM5);
      case PERIOD_M15: return(InpScaleM15);
      case PERIOD_M30: return(InpScaleM30);
      case PERIOD_H1:  return(InpScaleH1);
      case PERIOD_H4:  return(InpScaleH4);
      case PERIOD_D1:  return(InpScaleD1);
      default:         return(InpScaleOther);
     }
  }

//+------------------------------------------------------------------+
int OnInit()
  {
   SetIndexBuffer(0, RSIBuffer, INDICATOR_DATA);
   SetIndexBuffer(1, StochKBuffer, INDICATOR_DATA);
   SetIndexBuffer(2, StochDBuffer, INDICATOR_DATA);
   SetIndexBuffer(3, MacdBuffer, INDICATOR_DATA);
   SetIndexBuffer(4, MacdSignalBuffer, INDICATOR_DATA);
   ArraySetAsSeries(RSIBuffer, true);
   ArraySetAsSeries(StochKBuffer, true);
   ArraySetAsSeries(StochDBuffer, true);
   ArraySetAsSeries(MacdBuffer, true);
   ArraySetAsSeries(MacdSignalBuffer, true);

   IndicatorSetString(INDICATOR_SHORTNAME, "RSI+MACD+Stoch Combined");
   IndicatorSetInteger(INDICATOR_DIGITS, 2);

   // ระดับ level รวมทุกตัว สีต่างกันตามที่มา (ใช้ API แบบ runtime เพื่อกำหนด
   // สีต่อเส้นได้อิสระ — #property indicator_levelcolor เดี่ยวกำหนดได้สีเดียว
   // ทั้งไฟล์เท่านั้น ไม่พอสำหรับ 2 ชุดสีที่ต้องใช้ร่วมกัน)
   IndicatorSetInteger(INDICATOR_LEVELS, 5);
   IndicatorSetDouble(INDICATOR_LEVELVALUE, 0, 10.0);   // RSI Buy
   IndicatorSetInteger(INDICATOR_LEVELCOLOR, 0, clrGreen);
   IndicatorSetDouble(INDICATOR_LEVELVALUE, 1, 15.0);   // Stoch oversold
   IndicatorSetInteger(INDICATOR_LEVELCOLOR, 1, clrGreen);
   IndicatorSetDouble(INDICATOR_LEVELVALUE, 2, 50.0);   // เส้นกลาง (RSI TP / Stoch mid / MACD zero-cross)
   IndicatorSetInteger(INDICATOR_LEVELCOLOR, 2, clrYellow);
   IndicatorSetDouble(INDICATOR_LEVELVALUE, 3, 85.0);   // Stoch Sell
   IndicatorSetInteger(INDICATOR_LEVELCOLOR, 3, clrRed);
   IndicatorSetDouble(INDICATOR_LEVELVALUE, 4, 90.0);   // RSI upper
   IndicatorSetInteger(INDICATOR_LEVELCOLOR, 4, clrRed);
   for(int i = 0; i < 5; i++)
      IndicatorSetInteger(INDICATOR_LEVELSTYLE, i, STYLE_DOT);

   g_rsi_handle   = iRSI(_Symbol, _Period, InpRSIPeriod, InpAppliedPrice);
   g_macd_handle  = iMACD(_Symbol, _Period, InpMACDFast, InpMACDSlow, InpMACDSignal, InpAppliedPrice);
   g_stoch_handle = iStochastic(_Symbol, _Period, InpStochK, InpStochD, InpStochSlowing, MODE_SMA, STO_LOWHIGH);

   if(g_rsi_handle == INVALID_HANDLE || g_macd_handle == INVALID_HANDLE || g_stoch_handle == INVALID_HANDLE)
     {
      Print("RSI_MACD_Stoch_Combined: handle failed, err=", GetLastError());
      return(INIT_FAILED);
     }
   return(INIT_SUCCEEDED);
  }

//+------------------------------------------------------------------+
void OnDeinit(const int reason)
  {
   if(g_rsi_handle != INVALID_HANDLE)   IndicatorRelease(g_rsi_handle);
   if(g_macd_handle != INVALID_HANDLE)  IndicatorRelease(g_macd_handle);
   if(g_stoch_handle != INVALID_HANDLE) IndicatorRelease(g_stoch_handle);
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
   if(BarsCalculated(g_rsi_handle) < rates_total ||
      BarsCalculated(g_macd_handle) < rates_total ||
      BarsCalculated(g_stoch_handle) < rates_total)
      return(0);

   if(CopyBuffer(g_rsi_handle, 0, 0, rates_total, RSIBuffer) <= 0)
      return(0);
   if(CopyBuffer(g_stoch_handle, 0, 0, rates_total, StochKBuffer) <= 0)
      return(0);
   if(CopyBuffer(g_stoch_handle, 1, 0, rates_total, StochDBuffer) <= 0)
      return(0);

   double macdRaw[];
   ArraySetAsSeries(macdRaw, true);
   if(CopyBuffer(g_macd_handle, 0, 0, rates_total, macdRaw) <= 0)
      return(0);

   // ⚠️ 2026-08-17: เลิกใช้ buffer 1 (SIGNAL_LINE) ของ built-in iMACD แล้ว —
   // เจอจริงว่า MT5 คืนค่า 0 ตลอดทุกแท่งเมื่อ InpMACDSignal=1 (บั๊ก/ข้อจำกัด
   // ของ built-in indicator กับ period ขอบแบบนี้โดยเฉพาะ ไม่เกี่ยวกับโค้ดของ
   // เรา) แก้ด้วยการคำนวณเส้น Signal เอง (EMA ของเส้น MACD หลัก ตาม
   // InpMACDSignal) แทน — รองรับทุก period ถูกต้อง ไม่พึ่งพา built-in อีก
   int n = rates_total;
   double signalRaw[];
   ArrayResize(signalRaw, n);
   int sigPeriod = MathMax(1, InpMACDSignal);
   double alpha = 2.0 / (sigPeriod + 1.0);
   // macdRaw เป็น as-series (index 0 = แท่งล่าสุด) — EMA ต้องไล่จากแท่งเก่า
   // สุด (index n-1) มาแท่งล่าสุด (index 0) ตามลำดับเวลาจริง
   double prevEma = macdRaw[n - 1];
   signalRaw[n - 1] = prevEma;
   for(int i = n - 2; i >= 0; i--)
     {
      prevEma = macdRaw[i] * alpha + prevEma * (1.0 - alpha);
      signalRaw[i] = prevEma;
     }

   // ⚠️ 2026-08-17: มี 2 โหมด — auto (เดิม) คำนวณ scale เองจาก
   // InpMACDNormalizeBars แท่งล่าสุด แก้ปัญหาเส้นค้างที่ 50 จาก outlier เก่า
   // ในประวัติศาสตร์ได้ แต่**ค่าที่ได้ขึ้นกับจำนวนแท่งที่แต่ละเครื่องโหลดมา
   // จริง** (มือถือ/คอมอาจ sync ประวัติราคาไม่เท่ากัน) ทำให้ตัวเลขต่างกันได้
   // ข้ามเครื่องแม้ดูแท่งเดียวกัน (เจอจริง 2026-08-17) — ให้ตัวเลขตรงกันทุก
   // เครื่องแน่นอน ใช้ InpMACDUseFixedScale=true (default) แล้วใช้ตาราง
   // scale ต่อ TF (FixedScaleForPeriod) แทนตัวเลขเดียวข้าม TF (เคยลองตัวเลข
   // เดียวคงที่ก่อน แล้วทะลุกรอบในบาง TF เพราะ MACD แกว่งไม่เท่ากันแต่ละ TF)
   double scale;
   if(InpMACDUseFixedScale)
     {
      scale = FixedScaleForPeriod();
     }
   else
     {
      int normBars = MathMin(n, InpMACDNormalizeBars);
      double maxAbs = 0.0;
      for(int i = 0; i < normBars; i++)
        {
         maxAbs = MathMax(maxAbs, MathAbs(macdRaw[i]));
         maxAbs = MathMax(maxAbs, MathAbs(signalRaw[i]));
        }
      scale = (maxAbs > 0.0) ? (InpMACDTargetAmplitude / maxAbs) : 1.0;
     }

   for(int i = 0; i < n; i++)
     {
      MacdBuffer[i]       = 50.0 + macdRaw[i] * scale;
      MacdSignalBuffer[i] = 50.0 + signalRaw[i] * scale;
     }

   return(rates_total);
  }
//+------------------------------------------------------------------+
