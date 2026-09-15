//+------------------------------------------------------------------+
//|                                               ZigZagPA_Lib.mqh    |
//|  Library ที่ port มาจาก Pine v3 "[STRATEGY][RS]ZigZag PA Strategy   |
//|  V4.1" — ZigZag (bar-color flip), Heikin Ashi transform,          |
//|  Harmonic pattern recognition 17 แบบ (Bat/Butterfly/Gartley/...)   |
//+------------------------------------------------------------------+
#property strict

//+------------------------------------------------------------------+
//| แปลง OHLC ดิบเป็น Heikin Ashi (สูตรมาตรฐาน)                        |
//+------------------------------------------------------------------+
void ZZPA_ComputeHeikinAshi(const double &o[], const double &h[], const double &l[], const double &c[],
                             double &hO[], double &hH[], double &hL[], double &hC[])
  {
   int n = ArraySize(c);
   ArrayResize(hO, n);
   ArrayResize(hH, n);
   ArrayResize(hL, n);
   ArrayResize(hC, n);
   for(int i = 0; i < n; i++)
     {
      hC[i] = (o[i] + h[i] + l[i] + c[i]) / 4.0;
      hO[i] = (i == 0) ? (o[i] + c[i]) / 2.0 : (hO[i-1] + hC[i-1]) / 2.0;
      hH[i] = MathMax(h[i], MathMax(hO[i], hC[i]));
      hL[i] = MathMin(l[i], MathMin(hO[i], hC[i]));
     }
  }

//+------------------------------------------------------------------+
//| ZigZag ตาม logic ของ Pine (bar-color flip, ไม่ใช่ swing high/low   |
//| แบบทั่วไป): เปลี่ยนสีแท่ง (isUp->isDown หรือ isDown->isUp) และ      |
//| ทิศทางก่อนหน้าไม่ตรงกับปลายทางใหม่ → บันทึกจุด pivot = highest(2)   |
//| (ยอด) หรือ lowest(2) (ก้น) ที่ index i (คือแท่งที่กลับสี)           |
//+------------------------------------------------------------------+
void ZZPA_ComputeZigZag(const datetime &t[], const double &o[], const double &h[], const double &l[], const double &c[],
                         bool &isPivot[], double &pivotVal[])
  {
   int n = ArraySize(c);
   ArrayResize(isPivot, n);
   ArrayResize(pivotVal, n);
   for(int i = 0; i < n; i++)
     {
      isPivot[i]  = false;
      pivotVal[i] = 0.0;
     }

   int direction = 0; // 0=ยังไม่กำหนด (เทียบเท่า na/nz(0) ของ Pine)
   long expectedGapSeconds = 0;
   for(int i = 1; i < n; i++)
     {
      long actualGapSeconds = (long)t[i] - (long)t[i-1];
      if(expectedGapSeconds == 0)
         expectedGapSeconds = actualGapSeconds;
      else if(actualGapSeconds > expectedGapSeconds * 3 / 2)
        {
         // แท่งหายไปทั้งแท่งระหว่างกลาง (เช่น broker ไม่มีข้อมูลช่วงนั้นเลย) —
         // i-1 กับ i ไม่ใช่แท่งติดกันจริง ห้ามเทียบกลับสีข้ามช่องว่างนี้แบบผิดๆ
         direction = 0; // ไม่รู้ทิศทางที่แท้จริงอีกต่อไป รอ flip ใหม่หลัง gap
         continue;
        }

      bool prevUp   = c[i-1] >= o[i-1];
      bool prevDown = c[i-1] <= o[i-1];
      bool curUp    = c[i]   >= o[i];
      bool curDown  = c[i]   <= o[i];

      if(prevUp && curDown && direction != -1)
        {
         isPivot[i]  = true;
         pivotVal[i] = MathMax(h[i-1], h[i]); // highest(2)
        }
      else if(prevDown && curUp && direction != 1)
        {
         isPivot[i]  = true;
         pivotVal[i] = MathMin(l[i-1], l[i]); // lowest(2)
        }

      if(prevUp && curDown)
         direction = -1;
      else if(prevDown && curUp)
         direction = 1;
      // else: คงทิศทางเดิม (persist)
     }
  }

//+------------------------------------------------------------------+
//| ดึงจุด pivot ล่าสุด 5 จุด (X,A,B,C,D จากเก่าไปใหม่) นับถอยหลังจาก    |
//| uptoIndex — เทียบเท่า valuewhen(sz,sz,4..0) ของ Pine                |
//+------------------------------------------------------------------+
bool ZZPA_GetLastPivots(const bool &isPivot[], const double &pivotVal[], const int uptoIndex,
                         double &x, double &a, double &b, double &c, double &d)
  {
   double found[5];
   int cnt = 0;
   for(int i = uptoIndex; i >= 0 && cnt < 5; i--)
     {
      if(isPivot[i])
        {
         found[cnt] = pivotVal[i];
         cnt++;
        }
     }
   if(cnt < 5)
      return(false);

   d = found[0];
   c = found[1];
   b = found[2];
   a = found[3];
   x = found[4];
   return(true);
  }

//+------------------------------------------------------------------+
//| อัตราส่วนฮาร์มอนิก (xab, xad, abc, bcd)                            |
//+------------------------------------------------------------------+
bool ZZPA_CalcRatios(const double x, const double a, const double b, const double c, const double d,
                     double &xab, double &xad, double &abc, double &bcd)
  {
   double denomXA = MathAbs(x - a);
   double denomAB = MathAbs(a - b);
   double denomBC = MathAbs(b - c);
   if(denomXA == 0.0 || denomAB == 0.0 || denomBC == 0.0)
      return(false);

   xab = MathAbs(b - a) / denomXA;
   xad = MathAbs(a - d) / denomXA;
   abc = MathAbs(b - c) / denomAB;
   bcd = MathAbs(c - d) / denomBC;
   return(true);
  }

//+------------------------------------------------------------------+
//| 17 harmonic pattern — mode: 1=bull (d<c), -1=bear (d>c)            |
//| port มาจาก Pine ตรงตัวทุกช่วงตัวเลข (รวมเงื่อนไขซ้ำซ้อนบางจุด        |
//| เพื่อความเป๊ะตรงต้นฉบับ)                                            |
//+------------------------------------------------------------------+
bool ZZPA_IsABCD(const int mode, const double abc, const double bcd, const double d, const double c)
  {
   bool ok = (abc >= 0.382 && abc <= 0.886) && (bcd >= 1.13 && bcd <= 2.618);
   return(ok && (mode == 1 ? d < c : d > c));
  }

bool ZZPA_IsBat(const int mode, const double xab, const double xad, const double abc, const double bcd,
                const double d, const double c)
  {
   bool ok = (xab >= 0.382 && xab <= 0.5) &&
             (abc >= 0.382 && abc <= 0.886) &&
             (bcd >= 1.618 && bcd <= 2.618) &&
             (xad <= 0.618 && xad <= 1.000);
   return(ok && (mode == 1 ? d < c : d > c));
  }

bool ZZPA_IsAntiBat(const int mode, const double xab, const double xad, const double abc, const double bcd,
                    const double d, const double c)
  {
   bool ok = (xab >= 0.500 && xab <= 0.886) &&
             (abc >= 1.000 && abc <= 2.618) &&
             (bcd >= 1.618 && bcd <= 2.618) &&
             (xad >= 0.886 && xad <= 1.000);
   return(ok && (mode == 1 ? d < c : d > c));
  }

bool ZZPA_IsAltBat(const int mode, const double xab, const double xad, const double abc, const double bcd,
                   const double d, const double c)
  {
   bool ok = (xab <= 0.382) &&
             (abc >= 0.382 && abc <= 0.886) &&
             (bcd >= 2.0 && bcd <= 3.618) &&
             (xad <= 1.13);
   return(ok && (mode == 1 ? d < c : d > c));
  }

bool ZZPA_IsButterfly(const int mode, const double xab, const double xad, const double abc, const double bcd,
                      const double d, const double c)
  {
   bool ok = (xab <= 0.786) &&
             (abc >= 0.382 && abc <= 0.886) &&
             (bcd >= 1.618 && bcd <= 2.618) &&
             (xad >= 1.27 && xad <= 1.618);
   return(ok && (mode == 1 ? d < c : d > c));
  }

bool ZZPA_IsAntiButterfly(const int mode, const double xab, const double xad, const double abc, const double bcd,
                          const double d, const double c)
  {
   bool ok = (xab >= 0.236 && xab <= 0.886) &&
             (abc >= 1.130 && abc <= 2.618) &&
             (bcd >= 1.000 && bcd <= 1.382) &&
             (xad >= 0.500 && xad <= 0.886);
   return(ok && (mode == 1 ? d < c : d > c));
  }

bool ZZPA_IsGartley(const int mode, const double xab, const double xad, const double abc, const double bcd,
                    const double d, const double c)
  {
   bool ok = (xab >= 0.5 && xab <= 0.618) &&
             (abc >= 0.382 && abc <= 0.886) &&
             (bcd >= 1.13 && bcd <= 2.618) &&
             (xad >= 0.75 && xad <= 0.875);
   return(ok && (mode == 1 ? d < c : d > c));
  }

bool ZZPA_IsAntiGartley(const int mode, const double xab, const double xad, const double abc, const double bcd,
                        const double d, const double c)
  {
   bool ok = (xab >= 0.500 && xab <= 0.886) &&
             (abc >= 1.000 && abc <= 2.618) &&
             (bcd >= 1.500 && bcd <= 5.000) &&
             (xad >= 1.000 && xad <= 5.000);
   return(ok && (mode == 1 ? d < c : d > c));
  }

bool ZZPA_IsCrab(const int mode, const double xab, const double xad, const double abc, const double bcd,
                 const double d, const double c)
  {
   bool ok = (xab >= 0.500 && xab <= 0.875) &&
             (abc >= 0.382 && abc <= 0.886) &&
             (bcd >= 2.000 && bcd <= 5.000) &&
             (xad >= 1.382 && xad <= 5.000);
   return(ok && (mode == 1 ? d < c : d > c));
  }

bool ZZPA_IsAntiCrab(const int mode, const double xab, const double xad, const double abc, const double bcd,
                     const double d, const double c)
  {
   bool ok = (xab >= 0.250 && xab <= 0.500) &&
             (abc >= 1.130 && abc <= 2.618) &&
             (bcd >= 1.618 && bcd <= 2.618) &&
             (xad >= 0.500 && xad <= 0.750);
   return(ok && (mode == 1 ? d < c : d > c));
  }

bool ZZPA_IsShark(const int mode, const double xab, const double xad, const double abc, const double bcd,
                  const double d, const double c)
  {
   bool ok = (xab >= 0.500 && xab <= 0.875) &&
             (abc >= 1.130 && abc <= 1.618) &&
             (bcd >= 1.270 && bcd <= 2.240) &&
             (xad >= 0.886 && xad <= 1.130);
   return(ok && (mode == 1 ? d < c : d > c));
  }

bool ZZPA_IsAntiShark(const int mode, const double xab, const double xad, const double abc, const double bcd,
                      const double d, const double c)
  {
   bool ok = (xab >= 0.382 && xab <= 0.875) &&
             (abc >= 0.500 && abc <= 1.000) &&
             (bcd >= 1.250 && bcd <= 2.618) &&
             (xad >= 0.500 && xad <= 1.250);
   return(ok && (mode == 1 ? d < c : d > c));
  }

bool ZZPA_Is5o(const int mode, const double xab, const double xad, const double abc, const double bcd,
               const double d, const double c)
  {
   bool ok = (xab >= 1.13 && xab <= 1.618) &&
             (abc >= 1.618 && abc <= 2.24) &&
             (bcd >= 0.5 && bcd <= 0.625) &&
             (xad >= 0.0 && xad <= 0.236);
   return(ok && (mode == 1 ? d < c : d > c));
  }

bool ZZPA_IsWolf(const int mode, const double xab, const double xad, const double abc, const double bcd,
                 const double d, const double c)
  {
   bool ok = (xab >= 1.27 && xab <= 1.618) &&
             (abc >= 0 && abc <= 5) &&
             (bcd >= 1.27 && bcd <= 1.618) &&
             (xad >= 0.0 && xad <= 5);
   return(ok && (mode == 1 ? d < c : d > c));
  }

bool ZZPA_IsHnS(const int mode, const double xab, const double xad, const double abc, const double bcd,
                const double d, const double c)
  {
   bool ok = (xab >= 2.0 && xab <= 10) &&
             (abc >= 0.90 && abc <= 1.1) &&
             (bcd >= 0.236 && bcd <= 0.88) &&
             (xad >= 0.90 && xad <= 1.1);
   return(ok && (mode == 1 ? d < c : d > c));
  }

bool ZZPA_IsConTria(const int mode, const double xab, const double xad, const double abc, const double bcd,
                    const double d, const double c)
  {
   bool ok = (xab >= 0.382 && xab <= 0.618) &&
             (abc >= 0.382 && abc <= 0.618) &&
             (bcd >= 0.382 && bcd <= 0.618) &&
             (xad >= 0.236 && xad <= 0.764);
   return(ok && (mode == 1 ? d < c : d > c));
  }

bool ZZPA_IsExpTria(const int mode, const double xab, const double xad, const double abc, const double bcd,
                    const double d, const double c)
  {
   bool ok = (xab >= 1.236 && xab <= 1.618) &&
             (abc >= 1.000 && abc <= 1.618) &&
             (bcd >= 1.236 && bcd <= 2.000) &&
             (xad >= 2.000 && xad <= 2.236);
   return(ok && (mode == 1 ? d < c : d > c));
  }

//+------------------------------------------------------------------+
//| รวมแพทเทิร์นทั้งหมดของฝั่ง mode ที่กำหนด (bull=1/bear=-1)           |
//| เทียบเท่า buy_patterns_00/01 หรือ sel_patterns_00/01 ของ Pine       |
//+------------------------------------------------------------------+
bool ZZPA_AnyPattern(const int mode, const double xab, const double xad, const double abc, const double bcd,
                     const double d, const double c)
  {
   if(ZZPA_IsABCD(mode, abc, bcd, d, c))               return(true);
   if(ZZPA_IsBat(mode, xab, xad, abc, bcd, d, c))       return(true);
   if(ZZPA_IsAltBat(mode, xab, xad, abc, bcd, d, c))    return(true);
   if(ZZPA_IsButterfly(mode, xab, xad, abc, bcd, d, c)) return(true);
   if(ZZPA_IsGartley(mode, xab, xad, abc, bcd, d, c))   return(true);
   if(ZZPA_IsCrab(mode, xab, xad, abc, bcd, d, c))      return(true);
   if(ZZPA_IsShark(mode, xab, xad, abc, bcd, d, c))     return(true);
   if(ZZPA_Is5o(mode, xab, xad, abc, bcd, d, c))        return(true);
   if(ZZPA_IsWolf(mode, xab, xad, abc, bcd, d, c))      return(true);
   if(ZZPA_IsHnS(mode, xab, xad, abc, bcd, d, c))       return(true);
   if(ZZPA_IsConTria(mode, xab, xad, abc, bcd, d, c))   return(true);
   if(ZZPA_IsExpTria(mode, xab, xad, abc, bcd, d, c))   return(true);
   // กลุ่ม "Anti" (buy_patterns_01 / sel_patterns_01)
   if(ZZPA_IsAntiBat(mode, xab, xad, abc, bcd, d, c))       return(true);
   if(ZZPA_IsAntiButterfly(mode, xab, xad, abc, bcd, d, c)) return(true);
   if(ZZPA_IsAntiGartley(mode, xab, xad, abc, bcd, d, c))   return(true);
   if(ZZPA_IsAntiCrab(mode, xab, xad, abc, bcd, d, c))      return(true);
   if(ZZPA_IsAntiShark(mode, xab, xad, abc, bcd, d, c))     return(true);
   return(false);
  }

//+------------------------------------------------------------------+
//| เหมือน ZZPA_AnyPattern แต่คืนชื่อ pattern ที่ match ตัวแรกด้วย        |
//| (ใช้สำหรับ debug log เทียบกับ label บนกราฟ Pine)                    |
//+------------------------------------------------------------------+
string ZZPA_MatchedPatternName(const int mode, const double xab, const double xad, const double abc,
                                const double bcd, const double d, const double c)
  {
   if(ZZPA_IsABCD(mode, abc, bcd, d, c))               return("ABCD");
   if(ZZPA_IsBat(mode, xab, xad, abc, bcd, d, c))       return("Bat");
   if(ZZPA_IsAltBat(mode, xab, xad, abc, bcd, d, c))    return("AltBat");
   if(ZZPA_IsButterfly(mode, xab, xad, abc, bcd, d, c)) return("Butterfly");
   if(ZZPA_IsGartley(mode, xab, xad, abc, bcd, d, c))   return("Gartley");
   if(ZZPA_IsCrab(mode, xab, xad, abc, bcd, d, c))      return("Crab");
   if(ZZPA_IsShark(mode, xab, xad, abc, bcd, d, c))     return("Shark");
   if(ZZPA_Is5o(mode, xab, xad, abc, bcd, d, c))        return("5-O");
   if(ZZPA_IsWolf(mode, xab, xad, abc, bcd, d, c))      return("Wolf Wave");
   if(ZZPA_IsHnS(mode, xab, xad, abc, bcd, d, c))       return("Head and Shoulders");
   if(ZZPA_IsConTria(mode, xab, xad, abc, bcd, d, c))   return("Contracting Triangle");
   if(ZZPA_IsExpTria(mode, xab, xad, abc, bcd, d, c))   return("Expanding Triangle");
   if(ZZPA_IsAntiBat(mode, xab, xad, abc, bcd, d, c))       return("Anti Bat");
   if(ZZPA_IsAntiButterfly(mode, xab, xad, abc, bcd, d, c)) return("Anti Butterfly");
   if(ZZPA_IsAntiGartley(mode, xab, xad, abc, bcd, d, c))   return("Anti Gartley");
   if(ZZPA_IsAntiCrab(mode, xab, xad, abc, bcd, d, c))      return("Anti Crab");
   if(ZZPA_IsAntiShark(mode, xab, xad, abc, bcd, d, c))     return("Anti Shark");
   return("");
  }

//+------------------------------------------------------------------+
//| f_last_fib(rate): Fib level ที่ยืดจากจุด d ตามทิศทางขาสุดท้าย (c->d) |
//+------------------------------------------------------------------+
double ZZPA_LastFib(const double rate, const double d, const double c)
  {
   double fibRange = MathAbs(d - c);
   return((d > c) ? (d - fibRange * rate) : (d + fibRange * rate));
  }
//+------------------------------------------------------------------+
