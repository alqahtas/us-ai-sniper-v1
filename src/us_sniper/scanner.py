"""Read-only H1 Fibonacci / M15 scanner. All returned prices are underlying prices."""
from dataclasses import asdict
from datetime import datetime, timezone
from decimal import Decimal as D
from zoneinfo import ZoneInfo

from .fib_h1_m15 import MODEL, select_setup


def market_open(now):
    local = now.astimezone(ZoneInfo("America/New_York"))
    return local.weekday()<5 and (9,30) <= (local.hour,local.minute) < (16,0)


def rows(bars, minutes):
    result = []
    for b in bars:
        if not b.complete:
            continue
        local = b.timestamp.astimezone(ZoneInfo("America/New_York"))
        # Keep full RTH bars; the final 15:30 hourly bar is only 30 minutes.
        if local.weekday()>=5 or not (9,30) <= (local.hour,local.minute) < (16,0):
            continue
        if minutes == 60 and (local.minute != 30 or local.hour>=15):
            continue
        start = int(b.timestamp.timestamp()*1000)
        result.append(dict(open_time=start,close_time=start+minutes*60_000-1,
                           open=b.open,high=b.high,low=b.low,close=b.close,volume=b.volume))
    return result


def analyze_h1_m15(symbol,hourly,fifteen,quote,now,*,fee_rate=D(".001"),slippage=D(".0002")):
    if not market_open(now):
        return None
    ms = int(now.timestamp()*1000)
    try:
        bid,ask = D(str(quote["84"])),D(str(quote["86"]))
        stamp = int(quote["_updated"])
        fee,slip = D(str(fee_rate)),D(str(slippage))
        if (not str(quote.get("6509","")).startswith("R") or not 0 <= ms-stamp <= 30_000
                or not all(p.is_finite() for p in (bid,ask,fee,slip))
                or not 0 < bid < ask or min(fee,slip)<0):
            return None
    except (KeyError,ValueError,TypeError,ArithmeticError):
        return None
    setup,_ = select_setup(rows(hourly,60),rows(fifteen,15),ms)
    if setup is None:
        return None
    mid=(bid+ask)/2
    if abs(mid/setup.entry-1)>D(".005") or (ask-bid)/mid>D(".0006"):
        return None
    sign=1 if setup.side=="LONG" else -1
    ratio,stop=setup.targets[0]/setup.entry,setup.stop/setup.entry
    reward=sign*(ratio-1)-fee*(1+ratio)-slip
    risk=sign*(1-stop)+fee*(1+stop)+slip
    if reward<=0 or risk<=0 or reward/risk<D("1.5"):
        return None
    return dict(symbol=symbol,side=setup.side,setup=MODEL,entry=str(setup.entry),
                stop=str(setup.stop),targets=[str(p) for p in setup.targets],
                confirmation_ms=setup.confirmation_ms,estimated_net_reward=str(reward),
                estimated_net_risk=str(risk),instrument="underlying_stock",
                drawing=asdict(setup.drawing),
                ema_hour=[str(p) for p in setup.ema_hour],
                ema_15m=[str(p) for p in setup.ema_15m])


def scan_cycle(client,watchlist,now,contract_cache,*,fee_rate=D(".001")):
    if not market_open(now):
        return dict(status="market_closed",signals=[])
    missing=[symbol for symbol in watchlist if symbol not in contract_cache]
    if missing:
        contract_cache.update(client.stock_contracts(missing))
    signals,holds=[],[]
    for symbol in watchlist:
        conid=contract_cache.get(symbol)
        if conid is None:
            holds.append(dict(symbol=symbol,reason="unresolved_or_ambiguous_US_contract"))
            continue
        try:
            hourly=client.history(conid,period="60d",bar="1h",now=now)
            fifteen=client.history(conid,period="10d",bar="15min",now=now)
            snapshots=client.snapshot([conid],fields="84,86,6509")
            quote=next((q for q in snapshots if int(q.get("conid",0))==conid),{})
            signal=analyze_h1_m15(symbol,hourly,fifteen,quote,now,fee_rate=fee_rate)
            if signal:
                signals.append(signal)
            else:
                holds.append(dict(symbol=symbol,reason="no_confirmed_setup_or_fresh_realtime_quote"))
        except Exception as exc:
            holds.append(dict(symbol=symbol,reason=type(exc).__name__))
    return dict(status="scanned",model=MODEL,observed_at=now.isoformat(),signals=signals,holds=holds)
