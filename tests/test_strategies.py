import numpy as np
import pandas as pd

from momentum.strategies import CASH, Params, allocate, apply_cap, apply_floor, tsmom


def test_floor_gives_every_asset_the_minimum():
    w = apply_floor(pd.Series({"A": 0.7, "B": 0.3, "C": 0.0}), 0.02)
    assert np.isclose(w.sum(), 1) and np.isclose(w["C"], 0.02)
    assert np.isclose(w["A"] / w["B"], (0.02 + 0.94 * 0.7) / (0.02 + 0.94 * 0.3))


def test_floor_falls_back_to_equal_weight():
    assert np.allclose(apply_floor(pd.Series({"A": 0.0, "B": 0.0}), 0.02), 0.5)


def test_cap_redistributes_excess():
    w = apply_cap(pd.Series({"A": 0.6, "B": 0.2, "C": 0.1, "D": 0.1}), 0.3)
    assert np.isclose(w.sum(), 1) and w.max() <= 0.3 + 1e-12
    assert np.isclose(w["C"], w["D"])


def test_cap_that_cannot_hold_everything_leaves_cash():
    w = apply_cap(pd.Series({"A": 0.5, "B": 0.5}), 0.3)
    assert np.allclose(w, 0.3)


def test_tsmom_prefers_strong_low_volatility_momentum(prices):
    w = tsmom(prices, prices.pct_change(), prices.index[-1], Params())
    assert np.isclose(w.sum(), 1) and (w >= 0.02 - 1e-12).all() and (w <= 0.30 + 1e-12).all()


def test_allocate_without_active_assets_is_all_cash(prices):
    w = allocate("tsmom", prices, prices.pct_change(), prices.index[-1], [], Params())
    assert w[CASH] == 1 and w.drop(CASH).sum() == 0
