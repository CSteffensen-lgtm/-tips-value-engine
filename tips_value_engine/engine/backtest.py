import numpy as np
import pandas as pd

def brier_score(df: pd.DataFrame) -> float:
    required = {"p1", "px", "p2", "result"}
    if not required.issubset(df.columns):
        raise ValueError(f"CSV skal indeholde: {sorted(required)}")
    probs = df[["p1", "px", "p2"]].astype(float).to_numpy()
    if np.any(probs < 0) or np.any(probs > 1) or not np.allclose(probs.sum(axis=1), 1, atol=0.02):
        raise ValueError("Sandsynligheder skal summere til 1.")
    actual = np.zeros_like(probs)
    mapping = {"1": 0, "X": 1, "2": 2}
    for i, result in enumerate(df["result"].astype(str).str.upper()):
        if result not in mapping:
            raise ValueError(f"Ugyldigt udfald: {result}")
        actual[i, mapping[result]] = 1
    return float(np.mean(np.sum((probs - actual) ** 2, axis=1)))
