from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    mode: str
    ibkr_base_url: str
    verify_tls: bool
    interval_seconds: int
    watchlist: tuple[str, ...]
    min_score: int

    @classmethod
    def from_env(cls) -> "Settings":
        mode = os.getenv("MODE", "paper").strip().lower()
        if mode not in {"paper", "read_only"}:
            raise RuntimeError("live execution is disabled; MODE must be paper or read_only")
        return cls(
            mode=mode,
            ibkr_base_url=os.getenv("IBKR_BASE_URL", "https://localhost:5000/v1/api"),
            verify_tls=os.getenv("IBKR_VERIFY_TLS", "true").lower() == "true",
            interval_seconds=max(15, int(os.getenv("SCAN_INTERVAL_SECONDS", "60"))),
            watchlist=tuple(s.strip().upper() for s in os.getenv(
                "WATCHLIST", "SPY,QQQ,AAPL,MSFT,NVDA,AMZN,META,GOOGL,TSLA,AMD,AVGO,PLTR"
            ).split(",") if s.strip()),
            min_score=min(100, max(50, int(os.getenv("MIN_SCORE", "70")))),
        )

