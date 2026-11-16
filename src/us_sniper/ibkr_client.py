from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any, Callable

import requests

from .models import Bar

LOG = logging.getLogger(__name__)


class IBKRClient:
    """Read-only Client Portal adapter. It never submits, modifies or cancels orders."""

    def __init__(self, base_url: str, verify_tls: bool = True, timeout: float = 10.0,
                 transport: Callable[..., Any] | None = None) -> None:
        self.base_url = base_url.rstrip("/")
        self.verify_tls = verify_tls
        self.timeout = timeout
        self._transport = transport or requests.get
        self._last_request = 0.0

    def _get(self, path: str, **params: Any) -> Any:
        time.sleep(max(0, 0.12-(time.monotonic()-self._last_request)))
        self._last_request=time.monotonic()
        response = self._transport(
            f"{self.base_url}/{path.lstrip('/')}", params=params,
            timeout=self.timeout, verify=self.verify_tls,
        )
        response.raise_for_status()
        return response.json()

    def auth_status(self) -> dict[str, Any]:
        return self._get("iserver/auth/status")

    def snapshot(self, contract_ids: list[int], fields: str = "31,84,85,86,88,7059") -> list[dict[str, Any]]:
        return self._get("iserver/marketdata/snapshot", conids=",".join(map(str, contract_ids)), fields=fields)


    def stock_contracts(self, symbols: list[str]) -> dict[str,int]:
        payload=self._get("trsrv/stocks",symbols=",".join(symbols))
        result={}
        for symbol in symbols:
            candidates={int(c["conid"]) for item in payload.get(symbol,[])
                        if item.get("assetClass")=="STK"
                        for c in item.get("contracts",[])
                        if c.get("isUS") is True and int(c.get("conid",0))>0}
            if len(candidates)==1:
                result[symbol]=candidates.pop()
        return result

    def history(self, contract_id: int, period: str = "2d", bar: str = "5min", outside_rth: bool = False, *, now: datetime | None = None) -> list[Bar]:
        payload = self._get("iserver/marketdata/history", conid=contract_id, period=period, bar=bar,
                            outsideRth=str(outside_rth).lower())
        now = now or datetime.now(timezone.utc)
        duration = {"1h":3600,"15min":900,"5min":300}.get(bar)
        if duration is None:
            raise ValueError("unsupported intraday duration")
        result = []
        for row in payload.get("data", []):
            result.append(Bar(
                timestamp=datetime.fromtimestamp(row["t"] / 1000.0, tz=timezone.utc),
                open=float(row["o"]), high=float(row["h"]), low=float(row["l"]),
                close=float(row["c"]), volume=float(row.get("v", 0)), complete=row["t"] / 1000.0 + duration <= now.timestamp(),
            ))
        return result

