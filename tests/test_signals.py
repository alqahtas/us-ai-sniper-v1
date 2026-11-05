import unittest
from datetime import datetime, timedelta, timezone

from us_sniper.models import Bar
from us_sniper.signals import Regime, analyze, completed, market_regime


def trend_bars(count=90, direction=1.0):
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    bars = []
    price = 100.0
    for i in range(count):
        price += 0.15 * direction
        volume = 1000.0 if i < count - 1 else 3000.0
        bars.append(Bar(start + timedelta(minutes=5*i), price-0.1, price+0.2, price-0.2, price, volume))
    return bars


class SignalTests(unittest.TestCase):
    def test_market_regime(self):
        self.assertEqual(market_regime(trend_bars(), trend_bars()).side, "LONG")

    def test_incomplete_bar_is_ignored(self):
        bars = trend_bars()
        incomplete = Bar(bars[-1].timestamp + timedelta(minutes=5), 1, 1000, 0.5, 999, 1_000_000, complete=False)
        self.assertEqual(completed(bars + [incomplete])[-1], bars[-1])
        a = analyze("TEST", bars, Regime("LONG", 2), min_score=50)
        b = analyze("TEST", bars + [incomplete], Regime("LONG", 2), min_score=50)
        self.assertEqual(a.reference_price, b.reference_price)
        self.assertEqual(a.score, b.score)


if __name__ == "__main__":
    unittest.main()

