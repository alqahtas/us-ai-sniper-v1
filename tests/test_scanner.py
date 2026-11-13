import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock

from us_sniper.config import Settings
from us_sniper.ibkr_client import IBKRClient
from us_sniper.models import Bar, Instrument
from us_sniper.scanner import scan_once

NOW = datetime(2026, 11, 13, 16, tzinfo=timezone.utc)


def bars(duration):
    return [Bar(NOW-timedelta(seconds=duration*(161-i)), 100+i*.15-.1,
                100+i*.15+.2, 100+i*.15-.2, 100+i*.15,
                3000 if i == 159 else 1000) for i in range(160)]


class ScannerTests(unittest.TestCase):
    def setUp(self):
        self.settings = Settings("read_only", "https://example.invalid", True, 60, ("AAPL",), 50)
        self.client = Mock()
        self.client.auth_status.return_value = {"authenticated": True, "connected": True, "competing": False}
        self.client.stocks.return_value = {s: Instrument(s, i+1) for i, s in enumerate(("SPY", "QQQ", "AAPL"))}
        self.client.history.side_effect = lambda *a, **kw: bars(3600 if kw["bar"] == "1h" else 900)

    def test_scans_both_frames_and_serializes_all_three_emas(self):
        report = scan_once(self.client, self.settings, NOW)
        self.assertEqual(report["execution"], "DISABLED")
        self.assertEqual(len(report["signals"]), 1)
        self.assertEqual(set(report["signals"][0]["chart_indicators"]), {"1h", "15m"})
        self.assertTrue({"ema25", "ema75", "ema140"} <= report["signals"][0]["indicators"].keys())
        self.assertEqual(self.client.history.call_count, 6)
        self.assertFalse(self.client.submit_order.called)

    def test_authentication_failure_prevents_all_market_calls(self):
        self.client.auth_status.return_value["authenticated"] = False
        report = scan_once(self.client, self.settings, NOW)
        self.assertEqual(report["signals"], [])
        self.client.stocks.assert_not_called()
        self.client.history.assert_not_called()

    def test_missing_market_leader_fails_closed(self):
        self.client.stocks.return_value.pop("SPY")
        report = scan_once(self.client, self.settings, NOW)
        self.assertEqual(report["holds"]["market"], "SPY_QQQ_history_unavailable")
        self.assertFalse(report["signals"])

    def test_insufficient_ema140_history_is_a_hold(self):
        self.client.history.side_effect = lambda *a, **kw: bars(900)[:139]
        report = scan_once(self.client, self.settings, NOW)
        self.assertFalse(report["signals"])
        self.assertEqual(report["analysis"], {})

    def test_stale_history_is_not_live_confirmation(self):
        old = [Bar(b.timestamp-timedelta(days=5), b.open, b.high, b.low, b.close, b.volume) for b in bars(900)]
        self.client.history.side_effect = lambda *a, **kw: old
        self.assertFalse(scan_once(self.client, self.settings, NOW)["signals"])

    def test_errors_do_not_disclose_exception_payloads(self):
        self.client.history.side_effect = RuntimeError("SENSITIVE_RESPONSE_MUST_NOT_LEAK")
        report = scan_once(self.client, self.settings, NOW)
        self.assertNotIn("SENSITIVE_RESPONSE", str(report))


class HistoryAdapterTests(unittest.TestCase):
    def client(self, payload):
        response = Mock()
        response.json.return_value = payload
        return IBKRClient("https://example.invalid", transport=Mock(return_value=response))

    def test_only_completed_bars_are_flagged_complete(self):
        rows = [{"t": int((NOW-timedelta(minutes=m)).timestamp()*1000),
                 "o": 100, "h": 101, "l": 99, "c": 100, "v": 1} for m in (30, 5)]
        result = self.client({"data": rows}).history(1, bar="15min", now=NOW)
        self.assertEqual([b.complete for b in result], [True, False])

    def test_delayed_and_duplicate_history_are_rejected(self):
        row = {"t": 1, "o": 100, "h": 101, "l": 99, "c": 100}
        for payload in ({"mktDataDelay": 15, "data": [row]}, {"data": [row, row]}):
            with self.assertRaises(ValueError):
                self.client(payload).history(1, now=NOW)

    def test_ambiguous_contract_is_never_guessed(self):
        payload = {"AAPL": [{"assetClass": "STK", "contracts": [
            {"isUS": True, "conid": 1}, {"isUS": True, "conid": 2}]}]}
        self.assertEqual(self.client(payload).stocks(["AAPL"]), {})

    def test_unique_us_contract_excludes_foreign_listing(self):
        payload = {"AAPL": [{"assetClass": "STK", "contracts": [
            {"isUS": True, "conid": 1, "exchange": "NASDAQ"}, {"isUS": False, "conid": 2}]}]}
        self.assertEqual(self.client(payload).stocks(["AAPL"])["AAPL"].contract_id, 1)
