#property strict
#property indicator_chart_window
#property indicator_buffers 4
#property indicator_plots 4

#property indicator_label1 "S13 Buy"
#property indicator_type1 DRAW_ARROW
#property indicator_color1 clrDeepSkyBlue
#property indicator_width1 2

#property indicator_label2 "S13 Sell"
#property indicator_type2 DRAW_ARROW
#property indicator_color2 clrCrimson
#property indicator_width2 2

#property indicator_label3 "S13 ST Up"
#property indicator_type3 DRAW_LINE
#property indicator_color3 clrDeepSkyBlue
#property indicator_width3 1

#property indicator_label4 "S13 ST Down"
#property indicator_type4 DRAW_LINE
#property indicator_color4 clrCrimson
#property indicator_width4 1

input double InpSensitivity   = 2.0;
input int    InpSupertrendAtr = 11;
input double InpArrowAtrMult  = 0.8;
input bool   InpDebugLog      = false;

double BuyBuffer[];
double SellBuffer[];
double UpTrendBuffer[];
double DownTrendBuffer[];
datetime g_lastDebugBarTime = 0;

double TrueRange(const double high_cur, const double low_cur, const double prev_close)
{
   double a = high_cur - low_cur;
   double b = MathAbs(high_cur - prev_close);
   double c = MathAbs(low_cur - prev_close);
   return MathMax(a, MathMax(b, c));
}

int OnInit()
{
   SetIndexBuffer(0, BuyBuffer, INDICATOR_DATA);
   SetIndexBuffer(1, SellBuffer, INDICATOR_DATA);
   SetIndexBuffer(2, UpTrendBuffer, INDICATOR_DATA);
   SetIndexBuffer(3, DownTrendBuffer, INDICATOR_DATA);

   ArraySetAsSeries(BuyBuffer, true);
   ArraySetAsSeries(SellBuffer, true);
   ArraySetAsSeries(UpTrendBuffer, true);
   ArraySetAsSeries(DownTrendBuffer, true);

   PlotIndexSetInteger(0, PLOT_ARROW, 233);
   PlotIndexSetInteger(1, PLOT_ARROW, 234);
   PlotIndexSetDouble(0, PLOT_EMPTY_VALUE, EMPTY_VALUE);
   PlotIndexSetDouble(1, PLOT_EMPTY_VALUE, EMPTY_VALUE);
   PlotIndexSetDouble(2, PLOT_EMPTY_VALUE, EMPTY_VALUE);
   PlotIndexSetDouble(3, PLOT_EMPTY_VALUE, EMPTY_VALUE);

   IndicatorSetString(INDICATOR_SHORTNAME, "S13 EzAlgo");
   if(InpDebugLog)
      Print("S13_EzAlgo init ok | symbol=", _Symbol, " tf=", EnumToString((ENUM_TIMEFRAMES)_Period), " atr=", InpSupertrendAtr, " sens=", DoubleToString(InpSensitivity, 2));
   return INIT_SUCCEEDED;
}

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
   ArraySetAsSeries(time, true);
   ArraySetAsSeries(open, true);
   ArraySetAsSeries(high, true);
   ArraySetAsSeries(low, true);
   ArraySetAsSeries(close, true);

   int period = MathMax(1, InpSupertrendAtr);
   if(rates_total < period + 5)
   {
      if(InpDebugLog)
         Print("S13_EzAlgo skip: rates_total=", rates_total, " need=", period + 5);
      return 0;
   }

   for(int s = 0; s < rates_total; s++)
   {
      BuyBuffer[s] = EMPTY_VALUE;
      SellBuffer[s] = EMPTY_VALUE;
      UpTrendBuffer[s] = EMPTY_VALUE;
      DownTrendBuffer[s] = EMPTY_VALUE;
   }

   int n = rates_total;
   double atrCalc[];
   double upperBand[];
   double lowerBand[];
   double superTrend[];
   int direction[];
   ArrayResize(atrCalc, n);
   ArrayResize(upperBand, n);
   ArrayResize(lowerBand, n);
   ArrayResize(superTrend, n);
   ArrayResize(direction, n);
   ArraySetAsSeries(atrCalc, true);
   ArraySetAsSeries(upperBand, true);
   ArraySetAsSeries(lowerBand, true);
   ArraySetAsSeries(superTrend, true);
   ArraySetAsSeries(direction, true);

   for(int i = 0; i < n; i++)
   {
      atrCalc[i] = 0.0;
      upperBand[i] = EMPTY_VALUE;
      lowerBand[i] = EMPTY_VALUE;
      superTrend[i] = EMPTY_VALUE;
      direction[i] = 0;
   }

   double trSum = 0.0;
   int seedCount = 0;
   for(int i = n - 2; i >= 0; i--)
   {
      double tr = TrueRange(high[i], low[i], close[i + 1]);
      if(seedCount < period)
      {
         trSum += tr;
         seedCount++;
         if(seedCount == period)
            atrCalc[i] = trSum / period;
      }
      else
      {
         atrCalc[i] = ((atrCalc[i + 1] * (period - 1)) + tr) / period;
      }
   }

   for(int i = n - 1; i >= 0; i--)
   {
      if(atrCalc[i] <= 0.0)
         continue;

      double upper = close[i] + (InpSensitivity * atrCalc[i]);
      double lower = close[i] - (InpSensitivity * atrCalc[i]);

      if(i < n - 1 && lowerBand[i + 1] != EMPTY_VALUE)
      {
         double prevLower = lowerBand[i + 1];
         double prevUpper = upperBand[i + 1];
         double prevClose = close[i + 1];
         if(!(lower > prevLower || prevClose < prevLower))
            lower = prevLower;
         if(!(upper < prevUpper || prevClose > prevUpper))
            upper = prevUpper;
      }

      lowerBand[i] = lower;
      upperBand[i] = upper;

      if(i == n - 1 || atrCalc[i + 1] <= 0.0 || superTrend[i + 1] == EMPTY_VALUE)
      {
         direction[i] = 1;
      }
      else if(superTrend[i + 1] == upperBand[i + 1])
      {
         direction[i] = (close[i] > upper) ? -1 : 1;
      }
      else
      {
         direction[i] = (close[i] < lower) ? 1 : -1;
      }

      superTrend[i] = (direction[i] == -1) ? lower : upper;
      if(direction[i] == -1)
         UpTrendBuffer[i] = superTrend[i];
      else
         DownTrendBuffer[i] = superTrend[i];
   }

   for(int i = n - 2; i >= 1; i--)
   {
      if(superTrend[i] == EMPTY_VALUE || superTrend[i + 1] == EMPTY_VALUE)
         continue;

      bool bull = (close[i + 1] <= superTrend[i + 1] && close[i] > superTrend[i]);
      bool bear = (close[i + 1] >= superTrend[i + 1] && close[i] < superTrend[i]);
      double pad = atrCalc[i] * InpArrowAtrMult;

      if(bull)
         BuyBuffer[i] = low[i] - pad;
      else if(bear)
         SellBuffer[i] = high[i] + pad;
   }

   BuyBuffer[0] = EMPTY_VALUE;
   SellBuffer[0] = EMPTY_VALUE;

   if(InpDebugLog && time[0] != g_lastDebugBarTime)
   {
      g_lastDebugBarTime = time[0];
      int trendCount = 0;
      int buyCount = 0;
      int sellCount = 0;
      for(int s = 1; s < MathMin(n, 300); s++)
      {
         if(UpTrendBuffer[s] != EMPTY_VALUE || DownTrendBuffer[s] != EMPTY_VALUE)
            trendCount++;
         if(BuyBuffer[s] != EMPTY_VALUE)
            buyCount++;
         if(SellBuffer[s] != EMPTY_VALUE)
            sellCount++;
      }
      Print("S13_EzAlgo calc | tf=", EnumToString((ENUM_TIMEFRAMES)_Period),
            " bars=", rates_total,
            " trendPoints=", trendCount,
            " buySignals=", buyCount,
            " sellSignals=", sellCount,
            " lastClose=", DoubleToString(close[1], _Digits),
            " stUp=", (UpTrendBuffer[1] == EMPTY_VALUE ? "EMPTY" : DoubleToString(UpTrendBuffer[1], _Digits)),
            " stDn=", (DownTrendBuffer[1] == EMPTY_VALUE ? "EMPTY" : DoubleToString(DownTrendBuffer[1], _Digits)));
   }
   return rates_total;
}
