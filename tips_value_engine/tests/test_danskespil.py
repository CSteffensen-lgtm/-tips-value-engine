from connectors.danskespil import parse_danskespil_payload


def test_parse_observed_coupon_shape():
    pools = {"data": {"pools": [{"id": 1020585, "name": "Blandet fodbold", "type": "TF06",
             "poolMarkets": [{"legNum": 1}, {"legNum": 2}]}]}}
    events = {"events": [{"eventId": 123, "name": "Team A - Team B", "markets": [
        {"id": 999, "marketType": "MATCH_RESULT", "outcomes": [
            {"type": "H", "poolsInfo": [{"poolId": 1020585, "probability": 26, "popularity": 22.998}], "prices": [{"decimal": 3.5}]},
            {"type": "D", "poolsInfo": [{"poolId": 1020585, "probability": 25, "popularity": 11.088}], "prices": [{"decimal": 3.2}]},
            {"type": "A", "poolsInfo": [{"poolId": 1020585, "probability": 49, "popularity": 65.914}], "prices": [{"decimal": 2.0}]},
        ]}
    ]}]}
    meta, df = parse_danskespil_payload(pools, events)
    assert meta["name"] == "Blandet fodbold"
    assert len(df) == 1
    assert df.iloc[0]["ds_probability_1"] == 26
    assert df.iloc[0]["ds_popularity_X"] == 11.088
    assert df.iloc[0]["odds_2"] == 2.0
