"""One bounded read-only watchlist scan. Historical analysis is never an order."""
from dataclasses import asdict
from datetime import datetime, timezone

from .chart_indicators import analyze as chart_analysis
from .signals import analyze, completed, market_regime


def scan_once(client, settings, now=None):
    now = now or datetime.now(timezone.utc)
    report = {"scanned_at": now.isoformat(), "execution": "DISABLED",
              "data_kind": "completed_historical_candles_not_live_quote",
              "signals": [], "analysis": {}, "holds": {}}
    status = client.auth_status()
    if status.get("authenticated") is not True or status.get("connected") is not True or status.get("competing"):
        report["holds"]["market"] = "ibkr_not_authenticated_connected"
        return report
    symbols = list(dict.fromkeys(("SPY", "QQQ", *settings.watchlist)))
    instruments = client.stocks(symbols)
    frames = {}
    for symbol in symbols:
        if symbol not in instruments:
            report["holds"][symbol] = "missing_or_ambiguous_US_contract"
            continue
        try:
            contract = instruments[symbol].contract_id
            frames[symbol] = {
                "1h": completed(client.history(contract, period="3m", bar="1h", now=now)),
                "15m": completed(client.history(contract, period="1m", bar="15min", now=now)),
            }
            if any(len(bars) < 140 for bars in frames[symbol].values()):
                raise ValueError("insufficient EMA140 history")
            if any((now-bars[-1].timestamp).total_seconds() > 3*86400 for bars in frames[symbol].values()):
                raise ValueError("stale history")
            report["analysis"][symbol] = {interval: chart_analysis([
                {"high": b.high, "low": b.low, "close": b.close} for b in bars])
                for interval, bars in frames[symbol].items()}
            if any(c["status"] != "ready" for c in report["analysis"][symbol].values()):
                raise ValueError("invalid indicator input")
        except Exception as exc:
            frames.pop(symbol, None)
            report["analysis"].pop(symbol, None)
            report["holds"][symbol] = type(exc).__name__  # never log credentials or response bodies
    if not all(symbol in frames for symbol in ("SPY", "QQQ")):
        report["holds"]["market"] = "SPY_QQQ_history_unavailable"
        return report
    regime = market_regime(frames["SPY"]["1h"], frames["QQQ"]["1h"])
    for symbol in settings.watchlist:
        if symbol not in frames:
            continue
        context = report["analysis"][symbol]
        if any(c["status"] != "ready" for c in context.values()):
            report["holds"][symbol] = "invalid_indicator_context"
            continue
        signal = analyze(symbol, frames[symbol]["15m"], regime, settings.min_score)
        if signal is None:
            report["holds"][symbol] = "existing_signal_rules_not_confirmed"
        elif any(c["ema_stack"] != signal.side for c in context.values()):
            report["holds"][symbol] = "EMA25_75_140_hourly_15m_not_aligned"
        else:
            record = asdict(signal)
            record["observed_at"] = signal.observed_at.isoformat()
            record["chart_indicators"] = context
            report["signals"].append(record)
    return report
