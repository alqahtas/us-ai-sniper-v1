from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
import time

from .config import Settings
from .ibkr_client import IBKRClient
from .scanner import scan_cycle


def save_results(result,path):
    path=Path(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_suffix(".tmp")
    temp.write_text(json.dumps(result,default=str,ensure_ascii=False,indent=2))
    temp.replace(path)


def run() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
    settings=Settings.from_env()
    client=IBKRClient(settings.ibkr_base_url,verify_tls=settings.verify_tls)
    path=os.getenv("US_RESULTS_PATH","results/latest.json")
    contracts={}
    logging.info("RUNTIME HEARTBEAT | market=US model=fib_h1_m15_v2 execution=DISABLED watchlist=%s",len(settings.watchlist))
    while True:
        try:
            status=client.auth_status()
            if not status.get("authenticated") or not status.get("connected") or status.get("competing"):
                result=dict(status="IBKR_not_ready",signals=[])
            else:
                result=scan_cycle(client,settings.watchlist,datetime.now(timezone.utc),contracts,
                                  fee_rate=os.getenv("US_ESTIMATED_FEE_RATE","0.001"))
            save_results(result,path)
            logging.info("FIB SCAN | status=%s confirmed_signals=%d holds=%d",
                         result["status"],len(result["signals"]),len(result.get("holds",[])))
        except Exception as exc:
            logging.warning("IBKR UNAVAILABLE | type=%s",type(exc).__name__)
            save_results(dict(status="unavailable",reason=type(exc).__name__,signals=[]),path)
        time.sleep(settings.interval_seconds)


if __name__ == "__main__":
    run()
