import requests
import pandas as pd

BASE = "https://api.the-odds-api.com/v4"

def fetch_soccer_odds(api_key: str, sport_key: str, regions="uk,eu", markets="h2h"):
    """Fetch upcoming 1X2 odds from The Odds API.
    Requires a user-owned API key. Soccer h2h markets normally include draw.
    """
    if not api_key:
        raise ValueError("THE_ODDS_API_KEY mangler.")
    url = f"{BASE}/sports/{sport_key}/odds"
    params = {"apiKey": api_key, "regions": regions, "markets": markets, "oddsFormat": "decimal"}
    response = requests.get(url, params=params, timeout=25)
    response.raise_for_status()
    events = response.json()
    rows = []
    for event in events:
        best = {}
        for bookmaker in event.get("bookmakers", []):
            for market in bookmaker.get("markets", []):
                if market.get("key") != "h2h":
                    continue
                outcomes = {o["name"]: float(o["price"]) for o in market.get("outcomes", [])}
                home, away = event.get("home_team"), event.get("away_team")
                if home in outcomes and away in outcomes and "Draw" in outcomes:
                    # Keep best available price per outcome across listed bookmakers.
                    for k, v in [(home, outcomes[home]), ("Draw", outcomes["Draw"]), (away, outcomes[away])]:
                        best[k] = max(best.get(k, 0), v)
        if len(best) == 3:
            rows.append({
                "match": f'{event.get("home_team")} - {event.get("away_team")}',
                "commence_time": event.get("commence_time"),
                "home_team": event.get("home_team"),
                "away_team": event.get("away_team"),
                "odds_1": best[event.get("home_team")],
                "odds_x": best["Draw"],
                "odds_2": best[event.get("away_team")],
            })
    return pd.DataFrame(rows)
