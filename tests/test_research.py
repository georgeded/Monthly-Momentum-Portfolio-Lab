import json
from pathlib import Path

import pandas as pd
import pytest

from momentum.backtest import target_weights

ROOT = Path(__file__).resolve().parents[1] / "research"

# The weights the desk used on 2026-06-15, from the original run.
DESK_TSMOM = {"ONTO": 0.24467968719159358, "AVB": 0.02, "UEC": 0.12282407104093097, "VRTX": 0.02,
              "APO": 0.02716390676232009, "SGLD.L": 0.1074827156184082, "SOYB.L": 0.05976080142093937,
              "SIVR": 0.14624890738004317, "URNM": 0.07745228033817031, "DBB": 0.17438763024759435}


@pytest.fixture(scope="module")
def frozen():
    return pd.read_csv(ROOT / "data" / "prices.csv", index_col="date", parse_dates=True)


def test_reproduces_the_desk_allocation(frozen):
    w = target_weights("tsmom", frozen, "2026-06-15")
    for asset, expected in DESK_TSMOM.items():
        assert w[asset] == pytest.approx(expected, abs=1e-6)
    assert w["cash"] == pytest.approx(0)


def test_frozen_data_ends_on_the_decision_date(frozen):
    universe = json.loads((ROOT / "universe.json").read_text())
    assert frozen.index[-1] == pd.Timestamp(universe["decision_date"])
    assert list(frozen.columns) == [a["ticker"] for a in universe["assets"]]
