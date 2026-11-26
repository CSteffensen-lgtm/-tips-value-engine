import numpy as np
import pandas as pd

ODDS_COLS = ["odds_1", "odds_x", "odds_2"]
POP_COLS = ["players_1", "players_x", "players_2"]
PROB_COLS = ["p_1", "p_x", "p_2"]

def _normalize(values):
    arr = np.asarray(values, dtype=float)
    if np.any(~np.isfinite(arr)) or np.any(arr <= 0):
        raise ValueError("Odds skal være positive tal.")
    return arr / arr.sum()

def analyze_matches(df: pd.DataFrame) -> pd.DataFrame:
    """Fair market probabilities from decimal odds, plus crowd comparison.
    Does not claim pool EV; true pool EV needs payout and opponent-row modelling.
    """
    out = df.copy()
    missing = [c for c in ODDS_COLS if c not in out.columns]
    if missing:
        raise ValueError(f"Mangler odds-kolonner: {missing}")
    fair = np.vstack([_normalize(1.0 / row) for row in out[ODDS_COLS].to_numpy()])
    for i, c in enumerate(PROB_COLS):
        out[f"market_{c}"] = fair[:, i]

    # User/model probabilities; if absent, market is the transparent baseline.
    if not all(c in out.columns for c in PROB_COLS):
        for i, c in enumerate(PROB_COLS):
            out[c] = fair[:, i]

    p = out[PROB_COLS].astype(float).to_numpy()
    if np.any(p < 0) or np.any(p > 1) or not np.allclose(p.sum(axis=1), 1, atol=0.02):
        raise ValueError("p_1, p_x og p_2 skal være mellem 0 og 1 og summere til ca. 1 pr. kamp.")

    out["best_outcome"] = np.array(["1", "X", "2"])[p.argmax(axis=1)]
    out["best_probability"] = p.max(axis=1)
    out["best_market_probability"] = fair.max(axis=1)
    out["probability_edge_pp"] = (p - fair).max(axis=1) * 100

    if all(c in out.columns for c in POP_COLS):
        pop = out[POP_COLS].astype(float).to_numpy()
        if np.any(pop < 0) or not np.allclose(pop.sum(axis=1), 1, atol=0.02):
            raise ValueError("Spillerprocenter skal være mellem 0 og 1 og summere til ca. 1.")
        out["best_popularity"] = pop[np.arange(len(pop)), p.argmax(axis=1)]
        out["popularity_gap_pp"] = (p.max(axis=1) - out["best_popularity"]) * 100
        out["value_ratio"] = np.divide(p.max(axis=1), out["best_popularity"], out=np.full(len(p), np.nan), where=out["best_popularity"].to_numpy()!=0)
    else:
        out["best_popularity"] = np.nan
        out["popularity_gap_pp"] = np.nan
        out["value_ratio"] = np.nan

    # Heuristic ranking only, deliberately not called ROI.
    out["screening_score"] = (
        50
        + np.clip(out["probability_edge_pp"], -20, 20) * 1.5
        + np.clip(out["popularity_gap_pp"].fillna(0), -30, 30) * 0.8
    ).clip(0, 100)
    out["roi_status"] = "Ikke beregnet: kræver præmiepulje og model for øvrige vindere"
    return out

def expected_value_fixed_odds(probability: float, decimal_odds: float) -> float:
    """Net expected return per 1 unit stake for a fixed-odds bet, not Tips pool EV."""
    if not 0 <= probability <= 1 or decimal_odds <= 1:
        raise ValueError("Ugyldig sandsynlighed eller odds.")
    return probability * decimal_odds - 1
