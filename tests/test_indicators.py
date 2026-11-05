import unittest
from datetime import datetime, timedelta, timezone

from us_sniper.indicators import atr, bollinger, ema, rsi, vwap
from us_sniper.models import Bar


class IndicatorTests(unittest.TestCase):
    def bars(self, count=80):
        start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        return [Bar(start + timedelta(minutes=5*i), i+1, i+1.5, i+0.5, i+1.2, 100+i) for i in range(count)]

    def test_trend_indicators(self):
        bars = self.bars()
        closes = [b.close for b in bars]
        self.assertGreater(ema(closes, 9), ema(closes, 21))
        self.assertGreater(rsi(closes, 14), 90)
        self.assertGreater(atr(bars, 14), 0)

    def test_bollinger_and_vwap(self):
        bars = self.bars()
        low, mid, high = bollinger([b.close for b in bars])
        self.assertLess(low, mid)
        self.assertLess(mid, high)
        self.assertGreater(vwap(bars), 0)


if __name__ == "__main__":
    unittest.main()

