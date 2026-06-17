# Monthly Momentum Portfolio Lab

A rule-based monthly allocation for a basket picked by the desk's analysts.

The rule is time-series momentum: 12-1 month momentum divided by trailing
volatility, with a 2% floor and a 30% cap per asset. It is compared with equal
weight, inverse volatility and raw momentum on the same basket.

The study, the backtest and the allocation set on 15 June 2026 are in
[research/README.md](research/README.md).

```bash
pip install -r requirements-research.txt
python -m research.run_study
pytest
```

Educational project. Not investment advice.
