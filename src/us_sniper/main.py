from __future__ import annotations

import json
import logging
import time
from pathlib import Path

from .config import Settings
from .ibkr_client import IBKRClient
from .scanner import scan_once


def run() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
    settings = Settings.from_env()
    client = IBKRClient(settings.ibkr_base_url, verify_tls=settings.verify_tls)
    logging.info("RUNTIME HEARTBEAT | market=US mode=%s execution=DISABLED watchlist=%s",
                 settings.mode.upper(), len(settings.watchlist))
    while True:
        try:
            report = scan_once(client, settings)
            output = Path("us_scan_result.json")
            temporary = output.with_suffix(".tmp")
            temporary.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
            temporary.replace(output)
            logging.info("US SCAN | analyzed=%s signals=%s holds=%s execution=DISABLED",
                         len(report["analysis"]), len(report["signals"]), report["holds"])
        except Exception as exc:  # connection boundary; no secrets are logged
            logging.warning("IBKR UNAVAILABLE | type=%s", type(exc).__name__)
        time.sleep(settings.interval_seconds)


if __name__ == "__main__":
    run()


