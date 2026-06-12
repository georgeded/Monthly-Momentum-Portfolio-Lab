import numpy as np
import pandas as pd

from momentum import metrics
from momentum.backtest import active_assets, rebalance_dates, run, target_weights


def test_rebalance_dates_follow_the_start_day():
    idx = pd.bdate_range("2024-01-01", "2024-06-30")
    dates = rebalance_dates(idx, "2024-01-10", day=10)
    assert dates[0] == pd.Timestamp("2024-01-10")
    assert all(d.day <= 10 for d in dates) and len(dates) == 6


def test_start_on_a_weekend_uses_the_next_trading_day():
    idx = pd.bdate_range("2024-06-01", "2024-09-30")
    dates = rebalance_dates(idx, "2024-06-15", day=15)
    assert dates[0] == pd.Timestamp("2024-06-17")
    assert dates[1] == pd.Timestamp("2024-07-15")


def test_month_end_schedule():
    idx = pd.bdate_range("2024-01-01", "2024-04-30")
    dates = rebalance_dates(idx, "2024-01-01")
    assert list(dates.day) == [31, 29, 29, 30]


def test_assets_join_once_they_have_history(prices):
    late = prices.copy()
    late.loc[: late.index[400], "EEE"] = np.nan
    assert "EEE" not in active_assets(late, late.index[500])
    assert "EEE" in active_assets(late, late.index[-1])


def test_no_look_ahead(prices):
    as_of = prices.index[600]
    changed = prices.copy()
    changed.loc[changed.index > as_of] *= 3
    assert np.allclose(target_weights("tsmom", prices, as_of), target_weights("tsmom", changed, as_of))


def test_backtest_value_matches_period_returns(prices):
    res = run("tsmom", prices, prices.index[300], rebalance_day=15)
    assert np.isclose(res.value.iloc[-1], (1 + res.period_returns).prod())
    assert res.value.index[0] == res.weights.index[0]
    assert len(res.turnover) == len(res.weights) - 1


def test_equal_weight_drifts_between_rebalances(prices):
    res = run("equal_weight", prices, prices.index[300], rebalance_day=15)
    first, second = res.weights.index[:2]
    window = prices.loc[first:second]
    expected = (window.iloc[-1] / window.iloc[0]).mean()
    assert np.isclose(res.value.loc[second], expected)


def test_metrics_on_a_known_series():
    r = pd.Series([0.01] * 12)
    assert np.isclose(metrics.annualized_return(r), 1.01 ** 12 - 1)
    value = pd.Series([1.0, 1.2, 0.9, 1.1])
    assert np.isclose(metrics.max_drawdown(value), 0.9 / 1.2 - 1)
