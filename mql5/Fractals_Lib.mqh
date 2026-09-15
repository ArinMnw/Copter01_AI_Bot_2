//+------------------------------------------------------------------+
//|                                                Fractals_Lib.mqh   |
//|  พอร์ต Bill Williams Fractals (Left=2, Right=2 ตายตัว ตาม            |
//|  MQL5\Indicators\Examples\Fractals.mq5 ต้นฉบับ) มาเป็น library      |
//|  ใช้ร่วมกันใน EA/indicator หลายตัว (#include "Fractals_Lib.mqh")     |
//+------------------------------------------------------------------+
#ifndef __FRACTALS_LIB_MQH__
#define __FRACTALS_LIB_MQH__

//+------------------------------------------------------------------+
// สำหรับ EA: เช็คว่าแท่งที่เพิ่งปิดล่าสุด (shift=1) ทำให้ fractal ที่บาร์
// shift=3 (Left=2,Right=2) เพิ่ง confirm หรือไม่ (shift=1,2 คือ 2 แท่งขวาของ pivot)
bool Fractals_CheckNew(const string symbol, const ENUM_TIMEFRAMES period,
                        bool &isUp, bool &isDown)
  {
   isUp = false;
   isDown = false;

   double h1 = iHigh(symbol, period, 1), h2 = iHigh(symbol, period, 2), h3 = iHigh(symbol, period, 3);
   double h4 = iHigh(symbol, period, 4), h5 = iHigh(symbol, period, 5);
   double l1 = iLow(symbol, period, 1),  l2 = iLow(symbol, period, 2),  l3 = iLow(symbol, period, 3);
   double l4 = iLow(symbol, period, 4),  l5 = iLow(symbol, period, 5);

   if(h5 == 0.0 || l5 == 0.0) // ข้อมูลย้อนหลังไม่พอ
      return(false);

   if(h3 > h2 && h3 > h1 && h3 >= h4 && h3 >= h5)
      isUp = true;
   if(l3 < l2 && l3 < l1 && l3 <= l4 && l3 <= l5)
      isDown = true;

   return(isUp || isDown);
  }

//+------------------------------------------------------------------+
// สำหรับ indicator: mark isUp[]/isDown[] จาก array ของ OnCalculate ครั้งเดียว
// (index ตรงกับ high[]/low[] — flag วางที่บาร์ยืนยัน idx+2 ไม่ใช่บาร์ยอด/ก้นจริง
//  เพื่อไม่ให้ repaint/look-ahead ผิดจาก EA จริง เหมือนหลักการเดียวกับ HHLL_Lib)
// lookback จำกัดขอบเขตสแกน กันสแกนทั้งประวัติทุก tick แล้ว terminal ค้าง
void Fractals_MarkAll(const double &high[], const double &low[], const int n,
                       const int lookback, bool &isUp[], bool &isDown[])
  {
   ArrayResize(isUp, MathMax(n, 1));
   ArrayResize(isDown, MathMax(n, 1));
   ArrayInitialize(isUp, false);
   ArrayInitialize(isDown, false);

   if(n <= 0)
      return;

   int fromIdx = (lookback > 0) ? MathMax(2, n - (lookback + 4)) : 2;

   for(int i = fromIdx; i < n - 2; i++)
     {
      bool up = (high[i] > high[i + 1] && high[i] > high[i + 2] &&
                 high[i] >= high[i - 1] && high[i] >= high[i - 2]);
      bool dn = (low[i] < low[i + 1] && low[i] < low[i + 2] &&
                 low[i] <= low[i - 1] && low[i] <= low[i - 2]);
      if(!up && !dn)
         continue;

      int confirmIdx = i + 2;
      if(confirmIdx < 0 || confirmIdx >= n)
         continue;

      if(up)
         isUp[confirmIdx] = true;
      if(dn)
         isDown[confirmIdx] = true;
     }
  }

#endif
