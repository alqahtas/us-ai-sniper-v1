import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from us_sniper.dashboard import DashboardHandler


class DashboardTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.handler = object.__new__(DashboardHandler)
        self.handler.snapshot = Path(directory.name) / "private-paper.json"
        self.handler.respond = Mock()

    def request(self, path):
        self.handler.path = path
        self.handler.do_GET()
        return self.handler.respond.call_args.args

    def test_page_and_missing_snapshot_are_separate(self):
        status, media, page = self.request("/")
        self.assertEqual((status, media), (200, "text/html; charset=utf-8"))
        self.assertIn(b"US AI Sniper", page)
        self.assertEqual(
            self.request("/api/snapshot"),
            (404, "application/json", b'{"error":"snapshot_missing"}'),
        )

    def test_api_reads_only_the_configured_snapshot(self):
        data = b'{"schema_version":1}'
        self.handler.snapshot.write_bytes(data)
        self.assertEqual(self.request("/api/snapshot?path=ignored"), (200, "application/json", data))
        self.assertEqual(self.request("/private-paper.json")[0], 404)
        self.assertFalse(hasattr(self.handler, "do_POST"))

    def test_oversized_snapshot_returns_an_error_without_leaking_contents(self):
        self.handler.snapshot.write_bytes(b"abcdef")
        with patch("us_sniper.dashboard.MAX_SNAPSHOT_BYTES", 5):
            self.assertEqual(
                self.request("/api/snapshot"),
                (503, "application/json", b'{"error":"snapshot_too_large"}'),
            )
