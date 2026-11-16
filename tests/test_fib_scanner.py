from datetime import datetime,timedelta,timezone
from decimal import Decimal as D
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock
from zoneinfo import ZoneInfo

from fib_fixtures import frames
from us_sniper.models import Bar
from us_sniper.scanner import analyze_h1_m15, scan_cycle
from us_sniper.ibkr_client import IBKRClient
from us_sniper.main import save_results

NY=ZoneInfo("America/New_York")
NOW=datetime(2026,11,16,15,46,tzinfo=NY)


def equity_bars(short=False):
    data=frames(short)
    result={}
    for interval,minutes in (("1h",60),("15m",15)):
        times=[]
        for i in range(180):
            day=(NOW-timedelta(days=179-i)).replace(hour=9,minute=30,second=0,microsecond=0)
            if day.weekday()>=5:continue
            for n in range(6 if minutes==60 else 26):
                stamp=day+timedelta(minutes=n*minutes)
                if stamp+timedelta(minutes=minutes)<=NOW:
                    times.append(stamp)
        result[interval]=[Bar(t,r["open"],r["high"],r["low"],r["close"],r["volume"])
                          for t,r in zip(times[-498:],data[interval])]
    return result


def quote(short=False):
    return {"conid":123,"84":100.89 if short else 99.1,"86":100.90 if short else 99.11,
            "6509":"RpB","_updated":int(NOW.timestamp()*1000)}


class ScannerTests(unittest.TestCase):
    def test_underlying_long_and_short_have_hourly_drawings(self):
        for short in (False,True):
            bars=equity_bars(short)
            result=analyze_h1_m15("X",bars["1h"],bars["15m"],quote(short),NOW)
            self.assertIsNotNone(result)
            self.assertEqual(result["side"],"SHORT" if short else "LONG")
            self.assertEqual(result["entry"],"101.144" if short else "98.856")
            self.assertEqual(len(result["drawing"]["anchors"]),3)
            self.assertEqual(result["instrument"],"underlying_stock")

    def test_delayed_missing_crossed_and_stale_quotes_fail_closed(self):
        bars=equity_bars()
        for updates in ({"6509":"D"},{"6509":""},{"_updated":0},{"84":100,"86":99},{"84":"nan"}):
            with self.subTest(updates=updates):
                self.assertIsNone(analyze_h1_m15("X",bars["1h"],bars["15m"],dict(quote(),**updates),NOW))

    def test_costs_cannot_be_ignored(self):
        bars=equity_bars()
        self.assertIsNone(analyze_h1_m15("X",bars["1h"],bars["15m"],quote(),NOW,fee_rate=D(".02")))

    def test_cycle_fetches_both_timeframes_and_writes_reviewable_results(self):
        client=Mock();bars=equity_bars()
        client.stock_contracts.return_value={"X":123}
        client.history.side_effect=[bars["1h"],bars["15m"]]
        client.snapshot.return_value=[quote()]
        result=scan_cycle(client,["X"],NOW,{})
        self.assertEqual(len(result["signals"]),1)
        self.assertEqual([c.kwargs["bar"] for c in client.history.call_args_list],["1h","15min"])
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/"latest.json";save_results(result,p)
            self.assertEqual(json.loads(p.read_text())["signals"][0]["entry"],"98.856")

    def test_closed_market_does_not_call_provider(self):
        client=Mock()
        result=scan_cycle(client,["X"],NOW.replace(hour=17),{})
        self.assertEqual(result["status"],"market_closed")
        self.assertFalse(client.mock_calls)

    def test_unresolved_contract_does_not_request_history(self):
        client=Mock();client.stock_contracts.return_value={}
        self.assertFalse(scan_cycle(client,["X"],NOW,{})["signals"])
        client.history.assert_not_called()

    def test_contract_resolver_never_guesses_between_us_matches(self):
        client=IBKRClient("https://example.invalid")
        client._get=Mock(return_value={"X":[{"assetClass":"STK","contracts":[
            {"conid":1,"isUS":True},{"conid":2,"isUS":True}]}]})
        self.assertEqual(client.stock_contracts(["X"]),{})
        client._get.return_value["X"][0]["contracts"][1]["isUS"]=False
        self.assertEqual(client.stock_contracts(["X"]),{"X":1})

    def test_history_marks_forming_bar_incomplete(self):
        now_ms=int(NOW.timestamp()*1000)
        payload={"data":[dict(t=now_ms-30_000,o=100,h=101,l=99,c=100,v=10)]}
        response=Mock();response.json.return_value=payload
        client=IBKRClient("https://example.invalid",transport=Mock(return_value=response))
        bars=client.history(123,bar="15min",now=NOW)
        self.assertFalse(bars[0].complete)
