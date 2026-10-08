//+------------------------------------------------------------------+
//|                                                          MFI.mq5 |
//|                                  Copyright 2026, Antigravity AI  |
//|                                             https://www.mql5.com |
//+------------------------------------------------------------------+
#property copyright "Copyright 2026, Antigravity AI"
#property link      "https://www.mql5.com"
#property version   "1.00"
#property indicator_separate_window
#property indicator_minimum 0
#property indicator_maximum 100
#property indicator_buffers 3
#property indicator_plots   2

//--- plot 1: Background Fill
#property indicator_label1  "Background"
#property indicator_type1   DRAW_FILLING
#property indicator_color1  clrNONE // Set in OnInit via ARGB for transparency

//--- plot 2: MF Line
#property indicator_label2  "MF"
#property indicator_type2   DRAW_LINE
#property indicator_color2  C'126,87,194' // #7E57C2
#property indicator_style2  STYLE_SOLID
#property indicator_width2  2

//--- levels
#property indicator_level1  20
#property indicator_level2  50
#property indicator_level3  80
#property indicator_levelcolor C'120,123,134' // #787B86
#property indicator_levelstyle STYLE_DOT

//--- input parameters
input int InpLength = 14;      // Length (min=1, max=2000)

//--- indicator buffers
double         FillTopBuffer[];
double         FillBottomBuffer[];
double         MFIBuffer[];

int            handle_mfi;

//+------------------------------------------------------------------+
//| Custom indicator initialization function                         |
//+------------------------------------------------------------------+
int OnInit()
  {
//--- check input
   if(InpLength < 1 || InpLength > 2000)
     {
      Print("Length must be between 1 and 2000");
      return(INIT_PARAMETERS_INCORRECT);
     }
     
//--- indicator buffers mapping
   SetIndexBuffer(0, FillTopBuffer, INDICATOR_DATA);
   SetIndexBuffer(1, FillBottomBuffer, INDICATOR_DATA);
   SetIndexBuffer(2, MFIBuffer, INDICATOR_DATA);
   
//--- set background fill color with alpha (Pine Script alpha 90 means 90% transparent, so 10% opaque)
// ColorToARGB(color, alpha) - Alpha is 0-255, where 25 is approx 10% opacity
   PlotIndexSetInteger(0, PLOT_LINE_COLOR, 0, ColorToARGB(C'126,87,194', 25));
   
//--- set short name
   IndicatorSetString(INDICATOR_SHORTNAME, "MFI(" + IntegerToString(InpLength) + ")");
   IndicatorSetInteger(INDICATOR_DIGITS, 2);
   
//--- get handle for standard MFI (Uses Typical Price HLC/3 by default)
   handle_mfi = iMFI(Symbol(), Period(), InpLength, VOLUME_TICK);
   if(handle_mfi == INVALID_HANDLE)
     {
      Print("Failed to get handle for iMFI");
      return(INIT_FAILED);
     }

   return(INIT_SUCCEEDED);
  }
  
//+------------------------------------------------------------------+
//| Custom indicator deinitialization function                       |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
  {
   ObjectDelete(0, "MFI_Label_Value_Right");
   if(handle_mfi != INVALID_HANDLE)
      IndicatorRelease(handle_mfi);
  }

//+------------------------------------------------------------------+
//| Custom indicator iteration function                              |
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
//--- check for data
   if(rates_total < InpLength)
      return(0);

//--- calculate how many values to copy
   int to_copy = rates_total - prev_calculated;
   if(prev_calculated > 0)
      to_copy++;
      
   if(to_copy > rates_total)
      to_copy = rates_total;

//--- copy data from standard MFI
   if(CopyBuffer(handle_mfi, 0, 0, to_copy, MFIBuffer) <= 0)
     {
      Print("Failed to copy data from iMFI");
      return(0);
     }

//--- set fill buffers (static 80 and 20)
   int start = prev_calculated;
   if(start > 0) start--;
   for(int i = start; i < rates_total; i++)
     {
      FillTopBuffer[i] = 80.0;
      FillBottomBuffer[i] = 20.0;
     }

   //--- Highlight current value on the top right
   if(rates_total > 0)
     {
      double current_val = MFIBuffer[rates_total - 1];
      
      string short_name = "MFI(" + IntegerToString(InpLength) + ")";
      int current_subwindow = ChartWindowFind(0, short_name);
      
      if(current_subwindow >= 0)
        {
         string obj_name = "MFI_Label_Value_Right";
         if(ObjectFind(0, obj_name) != current_subwindow)
           {
            ObjectDelete(0, obj_name);
            ObjectCreate(0, obj_name, OBJ_LABEL, current_subwindow, 0, 0);
            ObjectSetInteger(0, obj_name, OBJPROP_CORNER, CORNER_RIGHT_UPPER);
            ObjectSetInteger(0, obj_name, OBJPROP_ANCHOR, ANCHOR_RIGHT_UPPER);
            ObjectSetInteger(0, obj_name, OBJPROP_XDISTANCE, 15);
            ObjectSetInteger(0, obj_name, OBJPROP_YDISTANCE, 15);
            ObjectSetInteger(0, obj_name, OBJPROP_SELECTABLE, false);
            ObjectSetInteger(0, obj_name, OBJPROP_HIDDEN, true);
            ObjectSetString(0, obj_name, OBJPROP_FONT, "Arial");
            ObjectSetInteger(0, obj_name, OBJPROP_FONTSIZE, 12);
            ObjectSetInteger(0, obj_name, OBJPROP_BACK, false);
           }
         
         string text_val = "MFI: " + DoubleToString(current_val, 2);
         ObjectSetString(0, obj_name, OBJPROP_TEXT, text_val);
         color tag_color = C'126,87,194'; // MediumPurple
         ObjectSetInteger(0, obj_name, OBJPROP_COLOR, tag_color);
         ChartRedraw(0);
        }
     }

//--- return value of prev_calculated for next call
   return(rates_total);
  }
//+------------------------------------------------------------------+
