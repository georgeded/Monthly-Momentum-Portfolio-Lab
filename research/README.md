# Desk study: monthly momentum allocation, June 2026

This folder is the research record for the allocation the desk set on 15 June 2026.
The data is frozen so the decision can be reproduced exactly. The first month will
be reviewed on 15 July.

## The question

The desk's analysts picked ten assets for the portfolio: five equities and five
commodity products. The analysts chose *what* to hold. The open question was *how
much* of each to hold, and how to keep that up to date without a weekly debate.

We wanted a rule that:

- uses only prices, so it can be run the same way every month,
- leans towards assets that have been trending up,
- holds less of the assets that move the most,
- never drops an analyst pick entirely and never lets one dominate.

## The basket

| Ticker | Name | Class |
| --- | --- | --- |
| ONTO | Onto Innovation | Equity |
| AVB | AvalonBay Communities | Equity |
| UEC | Uranium Energy Corp | Equity |
| VRTX | Vertex Pharmaceuticals | Equity |
| APO | Apollo Global Management | Equity |
| SGLD.L | Invesco Physical Gold ETC | Commodity |
| SOYB.L | WisdomTree Soybeans ETC | Commodity |
| SIVR | abrdn Physical Silver Shares ETF | Commodity |
| URNM | Sprott Uranium Miners ETF | Commodity |
| DBB | Invesco DB Base Metals Fund | Commodity |

The list is in `universe.json`. London listings are converted to USD.

## The rule (TSMOM)

On each rebalance date:

1. Momentum is the return from 12 months ago to 1 month ago. The latest month is
   skipped because short-term moves tend to reverse.
2. Volatility is the annualized standard deviation of the last 252 daily returns.
3. The score is momentum divided by volatility. Negative scores count as zero.
4. Every asset gets a 2% floor. The rest is shared in proportion to the scores.
5. No asset can hold more than 30%. Any excess is spread over the others.

An asset needs 13 months of prices before it can be held. Weights are set on the
15th of each month (or the next trading day) and drift with prices until the next
rebalance.

We compared it against three simpler rules on the same basket:

- **Equal weight**: 10% each.
- **Inverse volatility**: weight proportional to 1 / volatility, with the 2% floor.
- **Momentum only**: the TSMOM score without the volatility scaling or the cap.

The code is in `momentum/` at the repository root.

## Backtest before the decision

Monthly rebalances from 15 January 2021 (the first date when every asset had 13
months of history) to 15 June 2026. Uninvested cash earns the 3-month Treasury
rate. Turnover is one-way and excludes the first purchase.

| Strategy | Annual return | Volatility | Sharpe | Max drawdown | Avg turnover |
| --- | --- | --- | --- | --- | --- |
| TSMOM | +25.3% | 23.0% | 0.96 | -26.2% | 14.8% |
| Equal weight | +25.9% | 21.2% | 1.06 | -21.9% | 3.4% |
| Inverse volatility | +21.6% | 16.1% | 1.13 | -20.0% | 3.1% |
| Momentum only | +27.6% | 30.5% | 0.79 | -32.5% | 17.1% |

![Backtest](results/figures/backtest.png)

What we took from this:

- TSMOM did not beat the simple rules on a risk-adjusted basis. Equal weight and
  inverse volatility had higher Sharpe ratios and smaller drawdowns.
- The volatility scaling and the cap did their job relative to raw momentum: a
  similar return with a third less volatility and a shallower drawdown.
- The test uses today's basket on past data. The analysts picked these names
  knowing how they had done, so every rule here looks better than it would have
  in real time.

The desk still chose TSMOM because it was the only rule that responds to trends in
the basket, which was the point of the exercise. The backtest was treated as a
sanity check, not as evidence of an edge.

![TSMOM weights](results/figures/tsmom_weights.png)

## The allocation on 15 June 2026

| Asset | TSMOM | Equal weight | Inverse volatility | Momentum only |
| --- | --- | --- | --- | --- |
| ONTO | 24.5% | 10.0% | 6.2% | 29.4% |
| AVB | 2.0% | 10.0% | 14.1% | 2.0% |
| UEC | 12.3% | 10.0% | 5.1% | 19.4% |
| VRTX | 2.0% | 10.0% | 9.2% | 2.0% |
| APO | 2.7% | 10.0% | 8.9% | 2.5% |
| SGLD.L | 10.7% | 10.0% | 11.5% | 6.8% |
| SOYB.L | 6.0% | 10.0% | 17.0% | 3.4% |
| SIVR | 14.6% | 10.0% | 6.1% | 18.1% |
| URNM | 7.7% | 10.0% | 6.6% | 8.4% |
| DBB | 17.4% | 10.0% | 15.3% | 8.0% |

![Allocation](results/figures/allocation.png)

TSMOM put about 70% into ONTO, DBB, SIVR, UEC and SGLD.L, the names with the
strongest trends. AVB and VRTX had negative momentum and sat at the 2% floor.

## Reproduce

```bash
pip install -r requirements-research.txt
python -m research.run_study
```

The script reads `data/prices.csv` (daily USD closes to 15 June 2026) and
`data/risk_free.csv` (3-month Treasury yield from FRED, as a decimal), and rewrites
everything in `results/`.
