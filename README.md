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

## Paper results dashboard

From the repository root, run the independent, read-only dashboard:

```bash
PYTHONPATH=src python -m us_sniper.dashboard --snapshot /path/to/paper-snapshot.json
```

Open <http://127.0.0.1:8765>. The server listens on loopback. For an offline preview,
open `src/us_sniper/dashboard.html` in a browser and select **جرّب المحاكاة**. The four
simulated outcomes use fictitious symbols and a clearly labeled separate view.
The paper view starts empty and never falls back to simulation. **تحديث النتائج**
reads the latest snapshot. The paper view also refreshes every 30 seconds.

### Connect the scanner later

The dashboard reads a single JSON snapshot from the configured file. No broker
credentials, orders, or broker HTTP calls are handled by the dashboard. The
current scanner entry point reports connection status to its logs only. The
producer should write a complete snapshot to a temporary file in the same
directory and replace the target with `os.replace` after closing the file. Use a
path outside the repository or otherwise keep snapshots out of Git. Serve only
results from the read-only Paper integration under `ibkr_paper`.

This is the version 1 shape before the first scan. The producer can update the
connection fields independently while preserving the last scan:

```json
{
  "schema_version": 1,
  "source": "ibkr_paper",
  "mode": "paper",
  "read_only": true,
  "connection": {"state": "unknown", "checked_at": null},
  "scan": {
    "state": "not_run",
    "finished_at": null,
    "scanned_symbols": [],
    "valid_symbols": [],
    "opportunities": []
  }
}
```

- Connection states are `unknown`, `connected`, and `disconnected`. Report
  `connected` only after verifying the Paper session is authenticated, connected,
  and not competing. Include the check time for a known state. All timestamps are
  ISO 8601 with an explicit timezone. The UI shows Riyadh time and treats a
  reported connection check older than five minutes as stale.
- `not_run` has no scan timestamp or symbols. `no_valid_data` has a finish time
  and can list attempted symbols, but has no valid symbols or opportunities.
  `completed` has a finish time and at least one valid symbol. An empty
  opportunities array for a completed scan means no opportunity passed the filters.
  Keep both symbol arrays unique and include each valid symbol in the scanned array.
- Each accepted opportunity has `symbol`, `side` (`LONG` or `SHORT`), `entry`,
  `target`, `stop`, `score` (integer out of 100), and `reasons` (nonempty array
  of text). Use positive numeric USD prices with stop < entry < target for LONG
  and target < entry < stop for SHORT. Supply at most one opportunity per valid
  symbol. The existing `Signal` can provide symbol, side, score and reasons,
  while its `reference_price` and `invalidation` are candidates for entry and
  stop. The engine must provide a target under its paper strategy before the
  producer reports an opportunity. The UI never calculates a missing price.
- A missing file means no scan has been received. A malformed, mismatched or
  unreadable snapshot is shown as a separate read error and produces no cards.

Run dashboard tests with `PYTHONPATH=src python -m unittest discover -s tests -v`
and `node --test tests/dashboard.test.cjs`.
