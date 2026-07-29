# Monthly Momentum Portfolio Lab

A rule-based monthly allocation for a basket picked by the desk's analysts.

The rule is time-series momentum: 12-1 month momentum divided by trailing
volatility, with a 2% floor and a 30% cap per asset. It is compared with equal
weight, inverse volatility and raw momentum on the same basket.

The study, the backtest, the allocation set on 15 June 2026 and its first month
in practice are in [research/README.md](research/README.md).

| Strategy | Backtest 2021-2026 Sharpe | First month (15 Jun - 15 Jul 2026) |
| --- | --- | --- |
| TSMOM | 0.96 | -8.59% |
| Equal weight | 1.06 | -5.74% |
| Inverse volatility | 1.13 | -3.20% |
| Momentum only | 0.79 | -10.29% |

SPY returned +0.25% over the same month.

```bash
pip install -r requirements-research.txt
python -m research.run_study
pip install pytest
pytest
```

Educational project. Not investment advice.
