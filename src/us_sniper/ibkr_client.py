from __future__ import annotations

import logging
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

    def _get(self, path: str, **params: Any) -> Any:
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

    def history(self, contract_id: int, period: str = "2d", bar: str = "5min", outside_rth: bool = False) -> list[Bar]:
        payload = self._get("iserver/marketdata/history", conid=contract_id, period=period, bar=bar,
                            outsideRth=str(outside_rth).lower())
        result = []
        for row in payload.get("data", []):
            result.append(Bar(
                timestamp=datetime.fromtimestamp(row["t"] / 1000.0, tz=timezone.utc),
                open=float(row["o"]), high=float(row["h"]), low=float(row["l"]),
                close=float(row["c"]), volume=float(row.get("v", 0)), complete=True,
            ))
        return result

