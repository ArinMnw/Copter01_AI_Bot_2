//+------------------------------------------------------------------+
//|                                                  OCC_MA_Lib.mqh   |
//|  MA-variant library ที่ port มาจากฟังก์ชัน variant() ของ Pine       |
//|  script "Open Close Cross Strategy R5.1" (12 ชนิด MA)             |
//+------------------------------------------------------------------+
#property strict

enum ENUM_OCC_MA_TYPE
  {
   OCC_MA_SMA,     // Simple
   OCC_MA_EMA,     // Exponential
   OCC_MA_DEMA,    // Double Exponential
   OCC_MA_TEMA,    // Triple Exponential
   OCC_MA_WMA,     // Weighted
   OCC_MA_VWMA,    // Volume Weighted (ใช้ tick volume)
   OCC_MA_SMMA,    // Smoothed (RMA)
   OCC_MA_HULLMA,  // Hull
   OCC_MA_LSMA,    // Least Squares (linreg)
   OCC_MA_ALMA,    // Arnaud Legoux
   OCC_MA_SSMA,    // SuperSmoother (Ehlers)
   OCC_MA_TMA      // Triangular (extreme smooth)
  };

//+------------------------------------------------------------------+
//| SMA ที่ index i (หน้าต่าง [i-len+1, i])                            |
//+------------------------------------------------------------------+
double OCC_SMAAt(const double &src[], const int len, const int i)
  {
   if(i - len + 1 < 0)
      return(src[i]);
   double sum = 0.0;
   for(int k = i - len + 1; k <= i; k++)
      sum += src[k];
   return(sum / len);
  }

//+------------------------------------------------------------------+
//| WMA ที่ index i (แท่งล่าสุดในหน้าต่างมี weight สูงสุด)               |
//+------------------------------------------------------------------+
double OCC_WMAAt(const double &src[], const int len, const int i)
  {
   if(i - len + 1 < 0)
      return(src[i]);
   double sum = 0.0, norm = 0.0;
   int w = 1;
   for(int k = i - len + 1; k <= i; k++)
     {
      sum  += src[k] * w;
      norm += w;
      w++;
     }
   return(sum / norm);
  }

//+------------------------------------------------------------------+
//| VWMA ที่ index i                                                   |
//+------------------------------------------------------------------+
double OCC_VWMAAt(const double &src[], const double &vol[], const int len, const int i)
  {
   if(i - len + 1 < 0)
      return(src[i]);
   double sum = 0.0, norm = 0.0;
   for(int k = i - len + 1; k <= i; k++)
     {
      sum  += src[k] * vol[k];
      norm += vol[k];
     }
   if(norm == 0.0)
      return(OCC_SMAAt(src, len, i));
   return(sum / norm);
  }

//+------------------------------------------------------------------+
//| Linear Regression (LSMA) ที่ index i พร้อม offset                  |
//+------------------------------------------------------------------+
double OCC_LinRegAt(const double &src[], const int len, const double offset, const int i)
  {
   if(i - len + 1 < 0)
      return(src[i]);
   double sumX = 0.0, sumY = 0.0, sumXY = 0.0, sumX2 = 0.0;
   for(int j = 0; j < len; j++)
     {
      double x = j;
      double y = src[i - len + 1 + j];
      sumX  += x;
      sumY  += y;
      sumXY += x * y;
      sumX2 += x * x;
     }
   double denom = (len * sumX2 - sumX * sumX);
   if(denom == 0.0)
      return(OCC_SMAAt(src, len, i));
   double slope     = (len * sumXY - sumX * sumY) / denom;
   double intercept = (sumY - slope * sumX) / len;
   return(intercept + slope * (len - 1 - offset));
  }

//+------------------------------------------------------------------+
//| ALMA ที่ index i                                                   |
//+------------------------------------------------------------------+
double OCC_ALMAAt(const double &src[], const int len, const double offset, const double sigma, const int i)
  {
   if(i - len + 1 < 0)
      return(src[i]);
   double m = offset * (len - 1);
   double s = len / sigma;
   double sum = 0.0, norm = 0.0;
   for(int j = 0; j < len; j++)
     {
      double w = MathExp(-1.0 * MathPow(j - m, 2) / (2.0 * s * s));
      sum  += src[i - len + 1 + j] * w;
      norm += w;
     }
   if(norm == 0.0)
      return(OCC_SMAAt(src, len, i));
   return(sum / norm);
  }

//+------------------------------------------------------------------+
//| SMA แบบเต็มซีรีส์                                                  |
//+------------------------------------------------------------------+
void OCC_CalcSMASeries(const double &src[], const int len, double &out[])
  {
   int n = ArraySize(src);
   ArrayResize(out, n);
   for(int i = 0; i < n; i++)
      out[i] = OCC_SMAAt(src, len, i);
  }

//+------------------------------------------------------------------+
//| WMA แบบเต็มซีรีส์                                                  |
//+------------------------------------------------------------------+
void OCC_CalcWMASeries(const double &src[], const int len, double &out[])
  {
   int n = ArraySize(src);
   ArrayResize(out, n);
   for(int i = 0; i < n; i++)
      out[i] = OCC_WMAAt(src, len, i);
  }

//+------------------------------------------------------------------+
//| EMA แบบเต็มซีรีส์ (seed = SMA ที่ index len-1)                     |
//+------------------------------------------------------------------+
void OCC_CalcEMASeries(const double &src[], const int len, double &out[])
  {
   int n = ArraySize(src);
   ArrayResize(out, n);
   double alpha = 2.0 / (len + 1.0);
   for(int i = 0; i < n; i++)
     {
      if(i < len - 1)
         out[i] = src[i];
      else if(i == len - 1)
         out[i] = OCC_SMAAt(src, len, i);
      else
         out[i] = out[i-1] + alpha * (src[i] - out[i-1]);
     }
  }

//+------------------------------------------------------------------+
//| SMMA/RMA แบบเต็มซีรีส์ (seed = SMA ที่ index len-1)                |
//+------------------------------------------------------------------+
void OCC_CalcSMMASeries(const double &src[], const int len, double &out[])
  {
   int n = ArraySize(src);
   ArrayResize(out, n);
   for(int i = 0; i < n; i++)
     {
      if(i < len - 1)
         out[i] = src[i];
      else if(i == len - 1)
         out[i] = OCC_SMAAt(src, len, i);
      else
         out[i] = (out[i-1] * (len - 1) + src[i]) / len;
     }
  }

//+------------------------------------------------------------------+
//| SuperSmoother (Ehlers) แบบเต็มซีรีส์ — สัมประสิทธิ์เหมือน Pine เป๊ะ |
//+------------------------------------------------------------------+
void OCC_CalcSSMASeries(const double &src[], const int len, double &out[])
  {
   int n = ArraySize(src);
   ArrayResize(out, n);
   double a1 = MathExp(-1.414 * 3.14159 / len);
   double b1 = 2.0 * a1 * MathCos(1.414 * 3.14159 / len);
   double c2 = b1;
   double c3 = -a1 * a1;
   double c1 = 1.0 - c2 - c3;
   for(int i = 0; i < n; i++)
     {
      double prevSrc = (i >= 1) ? src[i-1] : src[i];
      double v1 = (i >= 1) ? out[i-1] : src[i];
      double v2 = (i >= 2) ? out[i-2] : src[i];
      out[i] = c1 * (src[i] + prevSrc) / 2.0 + c2 * v1 + c3 * v2;
     }
  }

//+------------------------------------------------------------------+
//| จุดเข้าหลัก — port ฟังก์ชัน variant() ของ Pine ทั้ง 12 ชนิด MA      |
//| src[]/vol[] ต้องเป็น array ลำดับเก่า→ใหม่ (index 0 = แท่งเก่าสุด)    |
//+------------------------------------------------------------------+
void OCC_CalcSeries(const ENUM_OCC_MA_TYPE type, const double &src[], const double &vol[],
                     const int len, const double offsetSigma, const double offsetALMA, double &out[])
  {
   int n = ArraySize(src);
   ArrayResize(out, n);

   switch(type)
     {
      case OCC_MA_EMA:
        {
         OCC_CalcEMASeries(src, len, out);
         break;
        }
      case OCC_MA_DEMA:
        {
         double e1[], e2[];
         OCC_CalcEMASeries(src, len, e1);
         OCC_CalcEMASeries(e1, len, e2);
         for(int i = 0; i < n; i++)
            out[i] = 2.0 * e1[i] - e2[i];
         break;
        }
      case OCC_MA_TEMA:
        {
         double e1[], e2[], e3[];
         OCC_CalcEMASeries(src, len, e1);
         OCC_CalcEMASeries(e1, len, e2);
         OCC_CalcEMASeries(e2, len, e3);
         for(int i = 0; i < n; i++)
            out[i] = 3.0 * (e1[i] - e2[i]) + e3[i];
         break;
        }
      case OCC_MA_WMA:
        {
         OCC_CalcWMASeries(src, len, out);
         break;
        }
      case OCC_MA_VWMA:
        {
         for(int i = 0; i < n; i++)
            out[i] = OCC_VWMAAt(src, vol, len, i);
         break;
        }
      case OCC_MA_SMMA:
        {
         OCC_CalcSMMASeries(src, len, out);
         break;
        }
      case OCC_MA_HULLMA:
        {
         int halfLen = MathMax(1, len / 2);
         int sqrtLen = MathMax(1, (int)MathRound(MathSqrt(len)));
         double wHalf[], wFull[], raw[];
         OCC_CalcWMASeries(src, halfLen, wHalf);
         OCC_CalcWMASeries(src, len, wFull);
         ArrayResize(raw, n);
         for(int i = 0; i < n; i++)
            raw[i] = 2.0 * wHalf[i] - wFull[i];
         OCC_CalcWMASeries(raw, sqrtLen, out);
         break;
        }
      case OCC_MA_LSMA:
        {
         for(int i = 0; i < n; i++)
            out[i] = OCC_LinRegAt(src, len, offsetSigma, i);
         break;
        }
      case OCC_MA_ALMA:
        {
         for(int i = 0; i < n; i++)
            out[i] = OCC_ALMAAt(src, len, offsetALMA, offsetSigma, i);
         break;
        }
      case OCC_MA_SSMA:
        {
         OCC_CalcSSMASeries(src, len, out);
         break;
        }
      case OCC_MA_TMA:
        {
         double s1[];
         OCC_CalcSMASeries(src, len, s1);
         OCC_CalcSMASeries(s1, len, out);
         break;
        }
      default: // OCC_MA_SMA
        {
         OCC_CalcSMASeries(src, len, out);
         break;
        }
     }
  }
//+------------------------------------------------------------------+
