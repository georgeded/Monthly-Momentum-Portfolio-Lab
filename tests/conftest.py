import numpy as np
import pandas as pd
import pytest


def make_prices(n=900, seed=3):
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2021-01-04", periods=n)
    drifts = {"AAA": 0.0008, "BBB": 0.0004, "CCC": 0.0, "DDD": -0.0003, "EEE": 0.0006}
    vols = {"AAA": 0.020, "BBB": 0.012, "CCC": 0.008, "DDD": 0.015, "EEE": 0.025}
    return pd.DataFrame({t: 100 * np.cumprod(1 + rng.normal(drifts[t], vols[t], n)) for t in drifts}, index=dates)


@pytest.fixture
def prices():
    return make_prices()
