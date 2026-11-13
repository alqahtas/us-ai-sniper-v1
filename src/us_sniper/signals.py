from __future__ import annotations

from dataclasses import dataclass
from datetime import timezone
from typing import Sequence

from .indicators import adx, atr, bollinger, cci, ema, macd, obv, rsi, stochastic_rsi, vwap, williams_r
from .models import Bar, Signal
from .chart_indicators import analyze as chart_analysis


@dataclass(frozen=True)
class Regime:
    side: str
    strength: int


def completed(bars: Sequence[Bar]) -> list[Bar]:
    return [bar for bar in bars if bar.complete]


def market_regime(spy: Sequence[Bar], qqq: Sequence[Bar]) -> Regime:
    votes = 0
    for source in (completed(spy), completed(qqq)):
        closes = [bar.close for bar in source]
        if len(closes) < 50:
            raise ValueError("at least 50 completed bars are required")
        fast, slow = ema(closes, 9), ema(closes, 21)
        momentum = rsi(closes, 7)
        votes += 1 if fast > slow and momentum >= 50 else -1 if fast < slow and momentum <= 50 else 0
    return Regime("LONG" if votes > 0 else "SHORT" if votes < 0 else "NEUTRAL", abs(votes))


def analyze(symbol: str, bars: Sequence[Bar], regime: Regime, min_score: int = 70) -> Signal | None:
    source = completed(bars)
    if len(source) < 60:
        raise ValueError("at least 60 completed bars are required")
    closes = [bar.close for bar in source]
    latest = source[-1]
    context = chart_analysis([{"high": b.high, "low": b.low, "close": b.close} for b in source])
    fast, slow = ema(closes, 9), ema(closes, 21)
    rsi7 = rsi(closes, 7)
    macd_line, macd_signal, macd_hist = macd(closes)
    lower, middle, upper = bollinger(closes)
    current_atr = atr(source)
    current_vwap = vwap(source)
    current_cci = cci(source)
    current_wr = williams_r(source)
    current_stoch = stochastic_rsi(closes)
    current_adx = adx(source)
    recent_high = max(bar.high for bar in source[-13:-1])
    recent_low = min(bar.low for bar in source[-13:-1])
    avg_volume = sum(bar.volume for bar in source[-21:-1]) / 20.0
    volume_ratio = latest.volume / avg_volume if avg_volume else 0.0
    obv_now = obv(source[-30:])
    obv_prev = obv(source[-31:-1])

    long_score = short_score = 0
    long_reasons: list[str] = []
    short_reasons: list[str] = []

    if fast > slow:
        long_score += 18; long_reasons.append("EMA9 فوق EMA21")
    elif fast < slow:
        short_score += 18; short_reasons.append("EMA9 تحت EMA21")
    if macd_hist > 0:
        long_score += 12; long_reasons.append("زخم MACD موجب")
    else:
        short_score += 12; short_reasons.append("زخم MACD سالب")
    if latest.close > current_vwap:
        long_score += 12; long_reasons.append("السعر فوق VWAP")
    else:
        short_score += 12; short_reasons.append("السعر تحت VWAP")
    if obv_now > obv_prev:
        long_score += 8; long_reasons.append("OBV صاعد")
    elif obv_now < obv_prev:
        short_score += 8; short_reasons.append("OBV هابط")
    if latest.close > recent_high and volume_ratio >= 1.35:
        long_score += 24; long_reasons.append("اختراق بحجم مؤكد")
    if latest.close < recent_low and volume_ratio >= 1.35:
        short_score += 24; short_reasons.append("كسر بحجم مؤكد")
    if latest.low <= max(lower, current_vwap - current_atr * 0.35) and latest.close > latest.open and rsi7 < 48:
        long_score += 18; long_reasons.append("ارتداد دعم مكتمل")
    if latest.high >= min(upper, current_vwap + current_atr * 0.35) and latest.close < latest.open and rsi7 > 52:
        short_score += 18; short_reasons.append("رفض مقاومة مكتمل")
    if current_adx >= 18:
        (long_reasons if fast > slow else short_reasons).append("ADX يؤكد الحركة")
        if fast > slow: long_score += 8
        else: short_score += 8
    if regime.side == "LONG": long_score += 10 * regime.strength
    if regime.side == "SHORT": short_score += 10 * regime.strength
    if regime.side == "LONG": short_score -= 12
    if regime.side == "SHORT": long_score -= 12

    side = "LONG" if long_score >= short_score else "SHORT"
    score = max(long_score, short_score)
    reasons = long_reasons if side == "LONG" else short_reasons
    if score < min_score:
        return None
    invalidation = recent_low - 0.15 * current_atr if side == "LONG" else recent_high + 0.15 * current_atr
    setup = "breakout" if (latest.close > recent_high or latest.close < recent_low) else "support_resistance_reaction"
    return Signal(
        symbol=symbol,
        side=side,
        score=min(score, 100),
        setup=setup,
        reference_price=latest.close,
        invalidation=invalidation,
        observed_at=latest.timestamp.astimezone(timezone.utc),
        chart_indicators=context,
        reasons=tuple(reasons),
        indicators={
            **{f"ema{p}": value for p, value in context.get("ema", {}).items()},
            "ema9": fast, "ema21": slow, "rsi7": rsi7,
            "macd": macd_line, "macd_signal": macd_signal,
            "atr": current_atr, "boll_lower": lower, "boll_mid": middle,
            "boll_upper": upper, "vwap": current_vwap, "cci": current_cci,
            "williams_r": current_wr, "stoch_rsi": current_stoch,
            "adx": current_adx, "volume_ratio": volume_ratio,
        },
    )


