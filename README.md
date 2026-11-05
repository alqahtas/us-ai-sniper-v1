# US AI Sniper v1

Northflank-ready US equity scanner. The service uses completed candles, a broad-market
regime filter (SPY/QQQ), and a confluence model built from EMA, RSI, MACD, ATR,
Bollinger Bands, VWAP, OBV, CCI, StochRSI, Williams %R and ADX.

## Safety defaults

- `MODE=paper` is the only enabled mode.
- Live order submission is intentionally not implemented.
- The IBKR Client Portal session and credentials stay outside this repository.
- Logs never print credentials, cookies or authorization headers.
- Signals are analysis records, not orders.

## Data

Set `IBKR_BASE_URL` to an authenticated IBKR Web API endpoint. For a Client Portal
Gateway this is normally `https://localhost:5000/v1/api`, which requires interactive
daily authentication on the same machine. For a remote Northflank deployment, use an
approved OAuth setup or a private gateway reachable through a secure tunnel.

## Run

```bash
python -m us_sniper.main
```

## Test

```bash
python -m unittest discover -s tests -v
```

## Environment

See `.env.example`. `WATCHLIST` defaults to liquid US names and ETFs. The service
will refuse to start when `MODE` is anything other than `paper` or `read_only`.

