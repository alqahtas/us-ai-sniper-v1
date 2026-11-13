from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Mapping, Sequence


@dataclass(frozen=True)
class Bar:
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    complete: bool = True

    def __post_init__(self) -> None:
        if self.timestamp.tzinfo is None:
            object.__setattr__(self, "timestamp", self.timestamp.replace(tzinfo=timezone.utc))
        if self.high < max(self.open, self.close) or self.low > min(self.open, self.close):
            raise ValueError("invalid OHLC bar")
        if self.low > self.high or self.volume < 0:
            raise ValueError("invalid range or volume")


@dataclass(frozen=True)
class Instrument:
    symbol: str
    contract_id: int
    exchange: str = "SMART"


@dataclass(frozen=True)
class Signal:
    symbol: str
    side: str
    score: int
    setup: str
    reference_price: float
    invalidation: float
    observed_at: datetime
    reasons: Sequence[str] = field(default_factory=tuple)
    indicators: Mapping[str, float] = field(default_factory=dict)
    chart_indicators: Mapping = field(default_factory=dict)


