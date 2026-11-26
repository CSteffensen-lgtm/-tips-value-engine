import pandas as pd
from engine.value import analyze_matches, expected_value_fixed_odds
from engine.coupon import full_system_rows
from engine.backtest import brier_score

def test_coupon_rows():
    assert full_system_rows(2, 1) == 12

def test_fixed_odds_ev():
    assert round(expected_value_fixed_odds(0.5, 2.2), 2) == 0.10

def test_brier():
    df = pd.DataFrame({"p1":[1.0],"px":[0.0],"p2":[0.0],"result":["1"]})
    assert brier_score(df) == 0.0

def test_analyze():
    df = pd.DataFrame([{"match":"A-B","odds_1":2.0,"odds_x":3.5,"odds_2":4.0,
                        "players_1":0.6,"players_x":0.25,"players_2":0.15,
                        "p_1":0.5,"p_x":0.3,"p_2":0.2}])
    out = analyze_matches(df)
    assert "screening_score" in out.columns
