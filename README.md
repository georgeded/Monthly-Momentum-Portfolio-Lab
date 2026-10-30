# Monthly Momentum Portfolio Lab

![Python](https://img.shields.io/badge/python-3.12-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/api-FastAPI-009688?logo=fastapi&logoColor=white)
![Tests](https://img.shields.io/badge/tests-pytest-0A9EDC?logo=pytest&logoColor=white)
![License](https://img.shields.io/badge/license-MIT-lightgrey)

A rule-based monthly allocation for a basket picked by analysts, in two parts:

- **[Research](research/README.md)**: the desk study. Why we built a time-series
  momentum rule, how it backtested, the allocation it set on 15 June 2026 and how
  that allocation did in its first month.
- **Dashboard**: a web app that runs the same rules on any basket, from any start
  date, and shows the weights and performance of each one.

Both use the same allocation code in `momentum/`.

Educational project. Not investment advice.

## Strategies

| Strategy | Weight |
| --- | --- |
| TSMOM | 12-1 month momentum divided by 252-day volatility, negatives set to zero, 2% floor, 30% cap |
| Equal weight | Same weight in every asset |
| Inverse volatility | Proportional to 1 / volatility, 2% floor |
| Momentum only | 12-1 month momentum, negatives set to zero, 2% floor |

Weights are set on the rebalance date and drift with prices until the next one.
An asset joins once it has 13 months of history. If no asset qualifies, the
portfolio sits in cash.

## Research results

From the [desk study](research/README.md), rebalancing on the 15th of each month:

| Strategy | Backtest 2021-2026 Sharpe | First month (15 Jun - 15 Jul 2026) |
| --- | --- | --- |
| TSMOM | 0.96 | -8.59% |
| Equal weight | 1.06 | -5.74% |
| Inverse volatility | 1.13 | -3.20% |
| Momentum only | 0.79 | -10.29% |

SPY returned +0.25% over the same month. The study explains the result and its
limits.

## Dashboard

```bash
pip install -r requirements.txt
uvicorn dashboard.app:app --reload
```

Open http://127.0.0.1:8000. You can:

- build a basket by searching Yahoo Finance or loading a sample basket,
- choose the date of the first rebalance, and rebalance on that day of each month
  or on the last trading day,
- choose the base currency, cash rate and model settings,
- compare the strategies' returns, risk, drawdowns and turnover,
- see the latest weights and every past rebalance, and download them as CSV.

Prices are cached in `cache/` for 12 hours. The API is documented at `/docs`.

| Variable | Default | Purpose |
| --- | --- | --- |
| `CACHE_DIR` | `cache/` | Where prices and names are cached |
| `CACHE_TTL_HOURS` | `12` | How long cached prices are reused |
| `PRICES_CSV` | unset | Read prices from a local CSV instead of Yahoo |

### Deploy on Render

The repository includes `render.yaml`. In Render choose **New > Blueprint**,
connect this repository and apply. The free plan sleeps when idle, so the first
request after a break takes about a minute.

## Layout

```
momentum/     signals, strategies, backtest engine and metrics
research/     the desk study: frozen data, run_study.py, results and write-up
dashboard/    FastAPI app, Yahoo price loading and the web frontend
tests/        unit tests for all three
```

## Tests

```bash
pip install -r requirements-dev.txt
pytest
```

The tests use synthetic prices and need no network.

## License

MIT
