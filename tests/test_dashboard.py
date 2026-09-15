from fastapi.testclient import TestClient

from dashboard.app import app

client = TestClient(app)
TICKERS = ["AAA", "BBB", "CCC", "DDD", "EEE"]


def backtest(**overrides):
    body = {"tickers": TICKERS, "start": "2022-03-15", **overrides}
    return client.post("/api/backtest", json=body)


def test_backtest_runs_every_strategy():
    r = backtest()
    assert r.status_code == 200
    body = r.json()
    assert set(body["strategies"]) == {"tsmom", "equal_weight", "inverse_vol", "momentum_only"}
    tsmom = body["strategies"]["tsmom"]
    assert tsmom["weights"]["dates"][0] == "2022-03-15"
    assert abs(sum(tsmom["current"]["weights"].values()) - 1) < 1e-6
    assert len(tsmom["value"]["dates"]) == len(tsmom["drawdown"])


def test_month_end_and_settings():
    r = backtest(rebalance="month_end", strategies=["tsmom"], settings={"lookback_months": 6, "max_weight": 0.25})
    body = r.json()
    assert r.status_code == 200 and list(body["strategies"]) == ["tsmom"]
    assert max(v for k, v in body["strategies"]["tsmom"]["current"]["weights"].items() if k != "cash") <= 0.25 + 1e-9


def test_bad_requests():
    assert backtest(tickers=["../etc"]).status_code == 400
    assert backtest(tickers=["ZZZ"]).status_code == 400
    assert backtest(end="2022-01-01").status_code == 400
    assert backtest(strategies=["magic"]).status_code == 400
    assert backtest(settings={"lookback_months": 2, "skip_months": 2}).status_code == 400
    assert backtest(start="2030-01-15").status_code == 400
    assert backtest(base_currency="euro").status_code == 422


def test_lookup_and_search():
    assert client.get("/api/lookup/aaa").json()["ticker"] == "AAA"
    assert client.get("/api/lookup/bad$").status_code == 400
    assert [x["ticker"] for x in client.get("/api/search?q=bb").json()["results"]] == ["BBB"]


def test_frontend_served():
    assert "Allocation dashboard" in client.get("/").text
