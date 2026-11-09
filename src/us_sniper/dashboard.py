"""Serve the dashboard and its latest paper-scan snapshot on loopback."""
from __future__ import annotations

import argparse
from functools import partial
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

PAGE = Path(__file__).with_name("dashboard.html")
MAX_SNAPSHOT_BYTES = 1_000_000


class DashboardHandler(BaseHTTPRequestHandler):
    def __init__(self, *args, snapshot: Path, **kwargs):
        self.snapshot = snapshot
        super().__init__(*args, **kwargs)

    def do_GET(self) -> None:
        path = self.path.partition("?")[0]
        if path == "/":
            self.respond(200, "text/html; charset=utf-8", PAGE.read_bytes())
        elif path == "/api/snapshot":
            self.serve_snapshot()
        else:
            self.respond(404, "text/plain; charset=utf-8", b"Not found")

    def serve_snapshot(self) -> None:
        try:
            with self.snapshot.open("rb") as file:
                body = file.read(MAX_SNAPSHOT_BYTES + 1)
        except FileNotFoundError:
            self.respond(404, "application/json", b'{"error":"snapshot_missing"}')
            return
        except OSError:
            self.respond(503, "application/json", b'{"error":"snapshot_unavailable"}')
            return

        if len(body) > MAX_SNAPSHOT_BYTES:
            self.respond(503, "application/json", b'{"error":"snapshot_too_large"}')
            return
        self.respond(200, "application/json", body)

    def respond(self, status: int, content_type: str, body: bytes) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy",
                         "default-src 'none'; script-src 'unsafe-inline'; "
                         "style-src 'unsafe-inline'; connect-src 'self'; "
                         "frame-ancestors 'none'; base-uri 'none'; form-action 'none'")
        self.end_headers()
        self.wfile.write(body)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, default=Path("paper-snapshot.json"))
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    handler = partial(DashboardHandler, snapshot=args.snapshot)
    with ThreadingHTTPServer(("127.0.0.1", args.port), handler) as server:
        print(f"US AI Sniper dashboard: http://127.0.0.1:{server.server_port}", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
