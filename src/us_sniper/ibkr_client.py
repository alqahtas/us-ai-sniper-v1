from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Callable

import requests

from .models import Bar, Instrument

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

    def stocks(self, symbols: list[str]) -> dict[str, Instrument]:
        """Resolve unique US equity contracts; never guess among duplicate listings."""
        payload = self._get("trsrv/stocks", symbols=",".join(symbols))
        resolved = {}
        for symbol in symbols:
            matches = {int(c["conid"]): c for row in payload.get(symbol, [])
                       if row.get("assetClass") == "STK"
                       for c in row.get("contracts", [])
                       if c.get("isUS") is True and isinstance(c.get("conid"), int)
                       and c["conid"] > 0}
            if len(matches) == 1:
                conid, contract = next(iter(matches.items()))
                resolved[symbol] = Instrument(symbol, conid, contract.get("exchange", "SMART"))
        return resolved

    def snapshot(self, contract_ids: list[int], fields: str = "31,84,85,86,88,7059") -> list[dict[str, Any]]:
        return self._get("iserver/marketdata/snapshot", conids=",".join(map(str, contract_ids)), fields=fields)

    def history(self, contract_id: int, period: str = "2d", bar: str = "5min", outside_rth: bool = False,
                now: datetime | None = None) -> list[Bar]:
        durations = {"5min": 300, "15min": 900, "1h": 3600}
        if bar not in durations:
            raise ValueError("unsupported completed-candle duration")
        payload = self._get("iserver/marketdata/history", conid=contract_id, period=period, bar=bar,
                            outsideRth=str(outside_rth).lower())
        if payload.get("mktDataDelay", 0) not in (0, "0", None):
            raise ValueError("delayed history cannot confirm an entry")
        now = now or datetime.now(timezone.utc)
        result = []
        for row in payload.get("data", []):
            result.append(Bar(
                timestamp=datetime.fromtimestamp(row["t"] / 1000.0, tz=timezone.utc),
                open=float(row["o"]), high=float(row["h"]), low=float(row["l"]),
                close=float(row["c"]), volume=float(row.get("v", 0)),
                complete=(datetime.fromtimestamp(row["t"] / 1000.0, tz=timezone.utc)
                          + timedelta(seconds=durations[bar]) <= now),
            ))
        if any(b.timestamp >= c.timestamp for b, c in zip(result, result[1:])):
            raise ValueError("duplicate or unordered history")
        return result


