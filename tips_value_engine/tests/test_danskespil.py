import json
from pathlib import Path
from connectors.danskespil import parse_danskespil_payload

BASE = Path(__file__).resolve().parents[1]


def test_real_torsdagstips_payload():
    pool = json.loads(Path('/mnt/data/files/download - danske spil.json').read_text())
    events = json.loads(Path('/mnt/data/files/events-by-ids - danske spil.json').read_text())
    metadata, matches = parse_danskespil_payload(pool, events)
    assert metadata['id'] == '1020556'
    assert metadata['type'] == 'TF13'
    assert len(matches) == 13
    assert set(matches.columns) >= {'ds_probability_1', 'ds_probability_X', 'ds_probability_2', 'ds_popularity_1', 'odds_1'}
    assert matches.iloc[0]['leg_num'] == 1
    assert matches.iloc[0]['match']
    assert matches.iloc[0]['ds_probability_1'] is not None
    assert matches.iloc[0]['ds_popularity_1'] is not None
    assert matches.iloc[0]['odds_1'] is not None
