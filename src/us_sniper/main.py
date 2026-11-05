from __future__ import annotations

import json
import logging
import time

from .config import Settings
from .ibkr_client import IBKRClient


def run() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
    settings = Settings.from_env()
    client = IBKRClient(settings.ibkr_base_url, verify_tls=settings.verify_tls)
    logging.info("RUNTIME HEARTBEAT | market=US mode=%s execution=DISABLED watchlist=%s",
                 settings.mode.upper(), len(settings.watchlist))
    while True:
        try:
            status = client.auth_status()
            logging.info("IBKR STATUS | authenticated=%s connected=%s competing=%s",
                         status.get("authenticated"), status.get("connected"), status.get("competing"))
        except Exception as exc:  # connection boundary; no secrets are logged
            logging.warning("IBKR UNAVAILABLE | type=%s", type(exc).__name__)
        time.sleep(settings.interval_seconds)


if __name__ == "__main__":
    run()

