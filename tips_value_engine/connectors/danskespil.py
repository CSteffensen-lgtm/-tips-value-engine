"""Parser and SQLite snapshot storage for observed Danske Spil Tips JSON."""
from __future__ import annotations
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import pandas as pd


def _as_dict(value: Any) -> dict:
    return value if isinstance(value, dict) else {}


def _pool_list(payload: dict) -> list[dict]:
    data = _as_dict(payload.get("data"))
    pools = data.get("pools", payload.get("pools", []))
    return pools if isinstance(pools, list) else []


def _event_list(payload: dict) -> list[dict]:
    """The observed events-by-ids response stores events at data.events."""
    data = _as_dict(payload.get("data"))
    events = data.get("events", payload.get("events", []))
    return events if isinstance(events, list) else []


def _number(value: Any):
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _decimal_odds(outcome: dict):
    prices = outcome.get("prices", [])
    if isinstance(prices, dict):
        prices = [prices]
    if not isinstance(prices, list):
        return None
    # Prefer the standard live price, falling back to the first usable price.
    prices = sorted(prices, key=lambda p: 0 if p.get("priceType") == "LP" else 1)
    for price in prices:
        if not isinstance(price, dict):
            continue
        decimal = _number(price.get("decimal", price.get("price")))
        if decimal is not None:
            return decimal
        numerator, denominator = _number(price.get("numerator")), _number(price.get("denominator"))
        if numerator is not None and denominator:
            return 1.0 + numerator / denominator
    return None


def parse_danskespil_payload(pool_payload: dict, events_payload: dict) -> tuple[dict, pd.DataFrame]:
    """Parse a pool response and its events-by-ids response into 1/X/2 rows."""
    pools = _pool_list(pool_payload)
    if not pools:
        raise ValueError("Kupondata mangler data.pools/pools.")
    pool = pools[0]
    pool_id = str(pool.get("id", ""))
    pool_markets = pool.get("poolMarkets", []) or []
    events = _event_list(events_payload)
    if not events:
        raise ValueError("Kampdata mangler data.events/events.")

    events_by_market = {}
    for event in events:
        if not isinstance(event, dict):
            continue
        for market in event.get("markets", []) or []:
            if isinstance(market, dict) and market.get("id") is not None:
                events_by_market[str(market["id"])] = (event, market)

    rows = []
    ordered_markets = sorted(
        [m for m in pool_markets if isinstance(m, dict)],
        key=lambda m: int(m.get("legNum") or 0),
    )
    for pool_market in ordered_markets:
        market_id = str(pool_market.get("marketId", ""))
        pair = events_by_market.get(market_id)
        if not pair:
            continue
        event, market = pair
        # Actual API uses groupCode=MATCH_RESULT, market type='-' and subType='MR'.
        if market.get("groupCode") != "MATCH_RESULT" and market.get("subType") != "MR":
            continue
        mapped = {}
        for outcome in market.get("outcomes", []) or []:
            if not isinstance(outcome, dict):
                continue
            # Actual API uses outcome.subType H/D/A; outcome.type is simply MR.
            subtype = str(outcome.get("subType", outcome.get("outcomeType", ""))).upper()
            key = {"H": "1", "D": "X", "A": "2", "1": "1", "X": "X", "2": "2"}.get(subtype)
            if not key:
                continue
            infos = outcome.get("poolsInfo", []) or []
            if isinstance(infos, dict):
                infos = [infos]
            info = next((x for x in infos if str(x.get("poolId", pool_id)) == pool_id), {}) if infos else {}
            mapped[key] = {
                "probability": _number(info.get("probability")),
                "popularity": _number(info.get("popularity")),
                "odds": _decimal_odds(outcome),
            }
        if not mapped:
            continue
        row = {
            "leg_num": pool_market.get("legNum"),
            "event_id": str(event.get("id", "")),
            "match": event.get("name", ""),
            "competition": _as_dict(event.get("type")).get("name", ""),
            "market_id": market_id,
            "pool_id": pool_id,
        }
        for key in ("1", "X", "2"):
            vals = mapped.get(key, {})
            row[f"ds_probability_{key}"] = vals.get("probability")
            row[f"ds_popularity_{key}"] = vals.get("popularity")
            row[f"odds_{key.lower()}"] = vals.get("odds")
        rows.append(row)

    if not rows:
        raise ValueError("Ingen 1/X/2-udfald fundet i data.events. Kontroller market groupCode og outcome subType.")
    metadata = {
        "id": pool.get("id"),
        "name": pool.get("name"),
        "type": pool.get("type"),
        "currency": pool.get("currencyCode"),
        "openTime": pool.get("openingTime"),
        "closeTime": pool.get("closingTime"),
        "poolPercentage": pool.get("percentage"),
        "poolPrizes": pool.get("poolPrizes", []),
        "leg_count": len(pool_markets),
    }
    return metadata, pd.DataFrame(rows).drop_duplicates(subset=["event_id", "market_id"]).sort_values("leg_num").reset_index(drop=True)


def save_snapshot(metadata: dict, matches: pd.DataFrame, db_path: str = "data/tips_history.sqlite") -> int:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    captured = datetime.now(timezone.utc).isoformat()
    with sqlite3.connect(path) as con:
        con.execute("CREATE TABLE IF NOT EXISTS coupon_snapshots (id INTEGER PRIMARY KEY, captured_at TEXT, coupon_id TEXT, coupon_name TEXT, coupon_type TEXT, close_time TEXT, payload TEXT)")
        con.execute("CREATE TABLE IF NOT EXISTS match_snapshots (id INTEGER PRIMARY KEY, snapshot_id INTEGER, event_id TEXT, match_name TEXT, payload TEXT)")
        cur = con.execute(
            "INSERT INTO coupon_snapshots(captured_at,coupon_id,coupon_name,coupon_type,close_time,payload) VALUES(?,?,?,?,?,?)",
            (captured, str(metadata.get("id", "")), metadata.get("name"), metadata.get("type"), str(metadata.get("closeTime", "")), json.dumps(metadata, ensure_ascii=False, default=str)),
        )
        sid = cur.lastrowid
        for _, row in matches.iterrows():
            con.execute(
                "INSERT INTO match_snapshots(snapshot_id,event_id,match_name,payload) VALUES(?,?,?,?)",
                (sid, str(row.get("event_id", "")), str(row.get("match", "")), row.to_json(force_ascii=False)),
            )
        return int(sid)


def snapshot_count(db_path: str = "data/tips_history.sqlite") -> int:
    path = Path(db_path)
    if not path.exists():
        return 0
    with sqlite3.connect(path) as con:
        return int(con.execute("SELECT COUNT(*) FROM coupon_snapshots").fetchone()[0])
