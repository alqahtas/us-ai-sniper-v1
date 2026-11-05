from __future__ import annotations

from math import sqrt
from typing import Iterable, Sequence

from .models import Bar


def _values(values: Iterable[float]) -> list[float]:
    result = [float(v) for v in values]
    if not result:
        raise ValueError("indicator input is empty")
    return result


def sma(values: Iterable[float], period: int) -> float:
    data = _values(values)
    if period <= 0 or len(data) < period:
        raise ValueError("insufficient data")
    return sum(data[-period:]) / period


def ema_series(values: Iterable[float], period: int) -> list[float]:
    data = _values(values)
    if period <= 0 or len(data) < period:
        raise ValueError("insufficient data")
    seed = sum(data[:period]) / period
    out = [seed]
    alpha = 2.0 / (period + 1.0)
    for value in data[period:]:
        out.append(alpha * value + (1.0 - alpha) * out[-1])
    return out


def ema(values: Iterable[float], period: int) -> float:
    return ema_series(values, period)[-1]


def rsi(values: Iterable[float], period: int = 14) -> float:
    data = _values(values)
    if len(data) < period + 1:
        raise ValueError("insufficient data")
    changes = [b - a for a, b in zip(data, data[1:])]
    gains = [max(change, 0.0) for change in changes[-period:]]
    losses = [max(-change, 0.0) for change in changes[-period:]]
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period
    if avg_loss == 0:
        return 100.0 if avg_gain else 50.0
    return 100.0 - 100.0 / (1.0 + avg_gain / avg_loss)


def true_ranges(bars: Sequence[Bar]) -> list[float]:
    if len(bars) < 2:
        raise ValueError("insufficient data")
    result = []
    for prev, current in zip(bars, bars[1:]):
        result.append(max(current.high - current.low, abs(current.high - prev.close), abs(current.low - prev.close)))
    return result


def atr(bars: Sequence[Bar], period: int = 14) -> float:
    return sma(true_ranges(bars), period)


def macd(values: Iterable[float], fast: int = 12, slow: int = 26, signal: int = 9) -> tuple[float, float, float]:
    data = _values(values)
    if len(data) < slow + signal:
        raise ValueError("insufficient data")
    fast_line = ema_series(data, fast)
    slow_line = ema_series(data, slow)
    offset = len(fast_line) - len(slow_line)
    macd_line = [f - s for f, s in zip(fast_line[offset:], slow_line)]
    signal_line = ema(macd_line, signal)
    return macd_line[-1], signal_line, macd_line[-1] - signal_line


def bollinger(values: Iterable[float], period: int = 20, deviations: float = 2.0) -> tuple[float, float, float]:
    data = _values(values)
    window = data[-period:]
    if len(window) < period:
        raise ValueError("insufficient data")
    middle = sum(window) / period
    std = sqrt(sum((value - middle) ** 2 for value in window) / period)
    return middle - deviations * std, middle, middle + deviations * std


def vwap(bars: Sequence[Bar], period: int = 30) -> float:
    window = list(bars[-period:])
    if len(window) < period:
        raise ValueError("insufficient data")
    volume = sum(bar.volume for bar in window)
    if volume <= 0:
        raise ValueError("zero volume")
    return sum(((bar.high + bar.low + bar.close) / 3.0) * bar.volume for bar in window) / volume


def obv(bars: Sequence[Bar]) -> float:
    if len(bars) < 2:
        raise ValueError("insufficient data")
    total = 0.0
    for prev, current in zip(bars, bars[1:]):
        total += current.volume if current.close > prev.close else -current.volume if current.close < prev.close else 0.0
    return total


def cci(bars: Sequence[Bar], period: int = 20) -> float:
    window = list(bars[-period:])
    if len(window) < period:
        raise ValueError("insufficient data")
    typical = [(bar.high + bar.low + bar.close) / 3.0 for bar in window]
    mean = sum(typical) / period
    deviation = sum(abs(value - mean) for value in typical) / period
    return 0.0 if deviation == 0 else (typical[-1] - mean) / (0.015 * deviation)


def williams_r(bars: Sequence[Bar], period: int = 14) -> float:
    window = list(bars[-period:])
    if len(window) < period:
        raise ValueError("insufficient data")
    high = max(bar.high for bar in window)
    low = min(bar.low for bar in window)
    return -50.0 if high == low else -100.0 * (high - window[-1].close) / (high - low)


def stochastic_rsi(values: Iterable[float], rsi_period: int = 14, stochastic_period: int = 14) -> float:
    data = _values(values)
    if len(data) < rsi_period + stochastic_period:
        raise ValueError("insufficient data")
    rsis = [rsi(data[:idx], rsi_period) for idx in range(rsi_period + 1, len(data) + 1)]
    window = rsis[-stochastic_period:]
    low, high = min(window), max(window)
    return 50.0 if high == low else 100.0 * (window[-1] - low) / (high - low)


def adx(bars: Sequence[Bar], period: int = 14) -> float:
    if len(bars) < period + 2:
        raise ValueError("insufficient data")
    plus_dm, minus_dm = [], []
    for prev, current in zip(bars, bars[1:]):
        up = current.high - prev.high
        down = prev.low - current.low
        plus_dm.append(up if up > down and up > 0 else 0.0)
        minus_dm.append(down if down > up and down > 0 else 0.0)
    tr = true_ranges(bars)
    tr_sum = sum(tr[-period:])
    if tr_sum == 0:
        return 0.0
    plus_di = 100.0 * sum(plus_dm[-period:]) / tr_sum
    minus_di = 100.0 * sum(minus_dm[-period:]) / tr_sum
    denom = plus_di + minus_di
    return 0.0 if denom == 0 else 100.0 * abs(plus_di - minus_di) / denom

