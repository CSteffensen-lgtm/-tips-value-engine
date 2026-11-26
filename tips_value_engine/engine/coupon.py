from itertools import product
import math

def full_system_rows(halves: int, wholes: int) -> int:
    return (2 ** halves) * (3 ** wholes)

def max_full_system(half_candidates, whole_candidates, row_price, budget):
    """Find highest-value full-cover subset within budget.
    Candidate items: {'match': str, 'edge': float}; returns simple selected set.
    This is a transparent baseline, not an R/U guarantee engine.
    """
    if row_price <= 0 or budget < 0:
        raise ValueError("Rækkepris skal være positiv og budget ikke-negativt.")
    max_rows = int(budget // row_price)
    best = None
    # Enumerate counts; candidate sorting is a heuristic, not a global payout optimizer.
    hs = sorted(half_candidates, key=lambda x: x["edge"], reverse=True)
    ws = sorted(whole_candidates, key=lambda x: x["edge"], reverse=True)
    for h in range(len(hs)+1):
        for w in range(len(ws)+1):
            rows = 2**h * 3**w
            if rows <= max_rows:
                score = sum(x["edge"] for x in hs[:h]) + sum(x["edge"] for x in ws[:w])
                if best is None or score > best["score"]:
                    best = {"halves": hs[:h], "wholes": ws[:w], "rows": rows,
                            "cost": rows*row_price, "score": score}
    return best
