"""Reproduce the desk study from the frozen data in research/data.

    python -m research.run_study

Writes tables and figures to research/results.
"""
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

from momentum import metrics  # noqa: E402
from momentum.backtest import run, target_weights  # noqa: E402
from momentum.strategies import CASH, LABELS, STRATEGIES  # noqa: E402

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
RESULTS = HERE / "results"

BACKTEST_START = "2021-01-15"  # first rebalance where every asset has 13 months of history
REBALANCE_DAY = 15
COLORS = {"tsmom": "#ae1f19", "equal_weight": "#6b7280", "inverse_vol": "#2a78d6", "momentum_only": "#f59e0b"}


def load():
    universe = json.loads((HERE / "universe.json").read_text())
    prices = pd.read_csv(DATA / "prices.csv", index_col="date", parse_dates=True)
    rates = pd.read_csv(DATA / "risk_free.csv", index_col="date", parse_dates=True)["dgs3mo"]
    month = pd.read_csv(DATA / "first_month.csv", index_col="date", parse_dates=True)
    return universe, prices, rates, month


def daily_cash(rates: pd.Series, index) -> pd.Series:
    annual = rates.reindex(index.union(rates.index)).ffill().reindex(index)
    return annual / 252


def backtest(prices, rates, decision_date):
    cash = daily_cash(rates, prices.index)
    results = {name: run(name, prices, BACKTEST_START, decision_date, REBALANCE_DAY, cash_returns=cash)
               for name in STRATEGIES}
    rf = float(rates.loc[BACKTEST_START:decision_date].mean())
    table = pd.DataFrame({LABELS[n]: metrics.summarize(r, rf) for n, r in results.items()}).T
    return results, table


def first_month(weights: pd.DataFrame, month: pd.DataFrame, rates: pd.Series):
    """Hold the June 15 weights to July 15 and let them drift."""
    assets = [c for c in weights.columns if c != CASH]
    growth = month[assets] / month[assets].iloc[0]
    cash_growth = (1 + daily_cash(rates, month.index).iloc[1:]).cumprod().reindex(month.index).fillna(1.0)
    paths = {}
    contributions = {}
    for name, w in weights.iterrows():
        paths[name] = growth.mul(w[assets]).sum(axis=1) + w[CASH] * cash_growth
        contributions[name] = (growth.iloc[-1] - 1) * w[assets]
    paths["SPY"] = month["SPY"] / month["SPY"].iloc[0]
    return pd.DataFrame(paths), pd.DataFrame(contributions)


def pct(x, digits=1):
    return f"{x * 100:+.{digits}f}%" if x == x else "-"


def figures(results, allocation, month_paths):
    plt.rcParams.update({"font.size": 9, "axes.spines.top": False, "axes.spines.right": False})
    figs = RESULTS / "figures"
    figs.mkdir(parents=True, exist_ok=True)

    fig, (top, bottom) = plt.subplots(2, 1, figsize=(10, 6.5), height_ratios=[2, 1], sharex=True)
    for name, res in results.items():
        top.plot(res.value.index, res.value, label=LABELS[name], color=COLORS[name], lw=1.6 if name == "tsmom" else 1.1)
        bottom.plot(res.value.index, metrics.drawdown(res.value), color=COLORS[name], lw=1.6 if name == "tsmom" else 1.1)
    top.set_title("Growth of 1, rebalanced on the 15th of each month")
    top.legend(frameon=False)
    bottom.set_title("Drawdown")
    bottom.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0))
    for ax in (top, bottom):
        ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(figs / "backtest.png", dpi=140)
    plt.close(fig)

    w = results["tsmom"].weights.drop(columns=CASH)
    fig, ax = plt.subplots(figsize=(10, 4.5))
    ax.stackplot(w.index, w.T.values, labels=w.columns, step="post")
    ax.set_title("TSMOM weights at each rebalance")
    ax.set_ylim(0, 1)
    ax.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0))
    ax.legend(loc="center left", bbox_to_anchor=(1.0, 0.5), frameon=False)
    fig.tight_layout()
    fig.savefig(figs / "tsmom_weights.png", dpi=140)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(10, 4.5))
    allocation.drop(columns=CASH).T.plot.bar(ax=ax, color=[COLORS[n] for n in allocation.index], width=0.8)
    ax.set_title("Allocation decided on 2026-06-15")
    ax.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0))
    ax.legend([LABELS[n] for n in allocation.index], frameon=False)
    ax.grid(axis="y", alpha=0.25)
    plt.xticks(rotation=0)
    fig.tight_layout()
    fig.savefig(figs / "allocation.png", dpi=140)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(10, 4.5))
    for name in month_paths.columns:
        color = COLORS.get(name, "#111827")
        ax.plot(month_paths.index, month_paths[name] - 1, label=LABELS.get(name, name), color=color,
                lw=1.8 if name == "tsmom" else 1.1, ls="--" if name == "SPY" else "-")
    ax.set_title("First month in practice, 2026-06-15 to 2026-07-15")
    ax.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0))
    ax.xaxis.set_major_formatter(matplotlib.dates.DateFormatter("%b %d"))
    ax.axhline(0, color="#9ca3af", lw=0.8)
    ax.legend(frameon=False)
    ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(figs / "first_month.png", dpi=140)
    plt.close(fig)


def summary(table, allocation, month_paths, contributions, universe):
    lines = ["# Results", "", "Generated by `python -m research.run_study`.", "",
             f"## Backtest, {BACKTEST_START} to {universe['decision_date']}", "",
             "| Strategy | Annual return | Volatility | Sharpe | Sortino | Max drawdown | Avg turnover |",
             "| --- | --- | --- | --- | --- | --- | --- |"]
    for name, row in table.iterrows():
        lines.append(f"| {name} | {pct(row.annualized_return)} | {row.annualized_volatility:.1%} | {row.sharpe:.2f} | "
                     f"{row.sortino:.2f} | {row.max_drawdown:.1%} | {row.avg_turnover:.1%} |")

    lines += ["", f"## Allocation on {universe['decision_date']}", "",
              "| Asset | " + " | ".join(LABELS[n] for n in allocation.index) + " |",
              "| --- " * (len(allocation.index) + 1) + "|"]
    for asset in allocation.columns.drop(CASH):
        lines.append(f"| {asset} | " + " | ".join(f"{allocation.loc[n, asset]:.1%}" for n in allocation.index) + " |")

    end = month_paths.iloc[-1] - 1
    lines += ["", f"## First month, {universe['decision_date']} to {universe['first_month_end']}", "",
              "| Strategy | Return | Versus SPY | Best contributor | Worst contributor |", "| --- | --- | --- | --- | --- |"]
    for name in allocation.index:
        c = contributions[name]
        lines.append(f"| {LABELS[name]} | {pct(end[name], 2)} | {pct(end[name] - end['SPY'], 2)} | "
                     f"{c.idxmax()} {pct(c.max(), 2)} | {c.idxmin()} {pct(c.min(), 2)} |")
    lines.append(f"| SPY | {pct(end['SPY'], 2)} | | | |")
    stand_ins = [a for a in universe["assets"] if a.get("first_month_source")]
    lines += ["", "Stand-ins for the first month: " + "; ".join(
        f"{a['ticker']} priced with {a['first_month_source']}" for a in stand_ins) + ". See research/README.md."]
    (RESULTS / "summary.md").write_text("\n".join(lines) + "\n")


def main():
    universe, prices, rates, month = load()
    decision = universe["decision_date"]
    RESULTS.mkdir(exist_ok=True)

    results, table = backtest(prices, rates, decision)
    table.to_csv(RESULTS / "backtest_metrics.csv", float_format="%.6f")

    allocation = pd.DataFrame({name: target_weights(name, prices, decision) for name in STRATEGIES}).T
    allocation.to_csv(RESULTS / "allocation.csv", float_format="%.6f")

    month_paths, contributions = first_month(allocation, month, rates)
    month_paths.to_csv(RESULTS / "first_month_value.csv", float_format="%.6f")
    contributions.to_csv(RESULTS / "first_month_contributions.csv", float_format="%.6f")

    figures(results, allocation, month_paths)
    summary(table, allocation, month_paths, contributions, universe)
    print((RESULTS / "summary.md").read_text())


if __name__ == "__main__":
    main()
