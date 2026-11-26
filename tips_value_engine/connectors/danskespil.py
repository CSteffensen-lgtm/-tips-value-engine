"""Danske Spil Tips data parsing and storage.

The API host and coupon-discovery route are intentionally configurable: only the
pools and events response shapes have been observed so far, not a stable public API.
"""
from __future__ import annotations
import json, sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import pandas as pd


def _walk(obj: Any):
    if isinstance(obj, dict):
        yield obj
        for value in obj.values():
            yield from _walk(value)
    elif isinstance(obj, list):
        for value in obj:
            yield from _walk(value)


def parse_danskespil_payload(pool_payload: dict, events_payload: dict) -> tuple[dict, pd.DataFrame]:
    """Parse observed pools + events-by-ids payloads into coupon metadata and matches."""
    pools = pool_payload.get("data", {}).get("pools", [])
    if not pools and isinstance(pool_payload.get("pools"), list):
        pools = pool_payload["pools"]
    if not pools:
        raise ValueError("Kupondata mangler data.pools/pools. Responsen kan have ændret format.")
    pool = pools[0]
    pool_id = str(pool.get("id", ""))
    markets = pool.get("poolMarkets", [])
    event_objects = []
    for item in _walk(events_payload):
        if item.get("eventId") or (item.get("id") and (item.get("markets") or item.get("name"))):
            event_objects.append(item)
    # Keep likely event records only; deduplicate by event id.
    events = {}
    for ev in event_objects:
        eid = str(ev.get("eventId", ev.get("id", "")))
        if eid:
            events[eid] = ev
    rows = []
    for ev in events.values():
        event_name = ev.get("name") or ev.get("eventName") or ""
        competition = ev.get("competitionName") or ev.get("tournamentName") or ev.get("sportName") or ""
        event_markets = ev.get("markets", [])
        for market in event_markets:
            if market.get("marketType") not in ("MATCH_RESULT", None) and market.get("type") not in ("MATCH_RESULT", None):
                continue
            outcomes = market.get("outcomes", [])
            mapped = {}
            for outcome in outcomes:
                typ = str(outcome.get("type", "")).upper()
                key = {"H":"1", "D":"X", "A":"2", "1":"1", "X":"X", "2":"2"}.get(typ)
                if not key:
                    continue
                info = outcome.get("poolsInfo", [])
                if isinstance(info, dict): info = [info]
                info = next((x for x in info if str(x.get("poolId", pool_id)) == pool_id), info[0] if info else {})
                prices = outcome.get("prices", [])
                price = None
                if isinstance(prices, list) and prices:
                    p = prices[0]
                    try: price = float(p.get("decimal", p.get("price")))
                    except (TypeError, ValueError):
                        try: price = 1 + float(p["numerator"])/float(p["denominator"])
                        except (KeyError, TypeError, ValueError, ZeroDivisionError): pass
                elif isinstance(prices, dict):
                    try: price = float(prices.get("decimal", prices.get("price")))
                    except (TypeError, ValueError): pass
                mapped[key] = {"probability": info.get("probability"), "popularity": info.get("popularity"), "odds": price}
            if mapped:
                row = {"event_id": str(ev.get("eventId", ev.get("id", ""))), "match": event_name,
                       "competition": competition, "market_id": market.get("id"), "pool_id": pool_id}
                for key in ("1", "X", "2"):
                    vals = mapped.get(key, {})
                    row[f"ds_probability_{key}"] = vals.get("probability")
                    row[f"ds_popularity_{key}"] = vals.get("popularity")
                    row[f"odds_{key.lower()}"] = vals.get("odds")
                rows.append(row)
    if not rows:
        raise ValueError("Ingen 1/X/2-udfald fundet. Kontrollér events-responsens struktur.")
    metadata = {k: pool.get(k) for k in ("id", "name", "type", "currency", "openTime", "closeTime", "poolPercentage", "poolPrizes")}
    metadata["leg_count"] = len(markets)
    return metadata, pd.DataFrame(rows).drop_duplicates(subset=["event_id", "market_id"])


def save_snapshot(metadata: dict, matches: pd.DataFrame, db_path: str = "data/tips_history.sqlite") -> int:
    path = Path(db_path); path.parent.mkdir(parents=True, exist_ok=True)
    captured = datetime.now(timezone.utc).isoformat()
    with sqlite3.connect(path) as con:
        con.execute("CREATE TABLE IF NOT EXISTS coupon_snapshots (id INTEGER PRIMARY KEY, captured_at TEXT, coupon_id TEXT, coupon_name TEXT, coupon_type TEXT, close_time TEXT, payload TEXT)")
        con.execute("CREATE TABLE IF NOT EXISTS match_snapshots (id INTEGER PRIMARY KEY, snapshot_id INTEGER, event_id TEXT, match_name TEXT, payload TEXT)")
        cur = con.execute("INSERT INTO coupon_snapshots(captured_at,coupon_id,coupon_name,coupon_type,close_time,payload) VALUES(?,?,?,?,?,?)",
                          (captured, str(metadata.get("id", "")), metadata.get("name"), metadata.get("type"), str(metadata.get("closeTime", "")), json.dumps(metadata, ensure_ascii=False, default=str)))
        sid = cur.lastrowid
        for _, row in matches.iterrows():
            con.execute("INSERT INTO match_snapshots(snapshot_id,event_id,match_name,payload) VALUES(?,?,?,?)",
                        (sid, str(row.get("event_id", "")), str(row.get("match", "")), row.to_json(force_ascii=False)))
        return int(sid)


def snapshot_count(db_path: str = "data/tips_history.sqlite") -> int:
    path = Path(db_path)
    if not path.exists(): return 0
    with sqlite3.connect(path) as con:
        return int(con.execute("SELECT COUNT(*) FROM coupon_snapshots").fetchone()[0])
