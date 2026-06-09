"""Phase-2 Lane D recompute: pooled Vehicle vs (R)-DI-87 Welch's t-test per panel.

Reads tidy CSVs under `<kb>/elife-91157-stress/data/Fig4*.csv`, identifies
Vehicle and (R)-DI-87 replicates by substring match on the `group` column,
runs `scipy.stats.ttest_ind(equal_var=False)`, and emits one JSON line per
panel with:

    {"panel": "4A", "n_vehicle": N, "n_treatment": M,
     "mean_vehicle": ..., "mean_treatment": ...,
     "direction": "up|down|null", "p_value": ...,
     "p_lt_0_05": true|false, "notes": "..."}

"up"   = mean(treatment) > mean(control)
"down" = mean(treatment) < mean(control)
"null" = either group has < 2 observations after pooling (test undefined)

This is the deterministic basis for Lane D's `recomputed_direction` and
`recomputed_p_lt_0_05` fields. Pooling smears subgroup structure (e.g.,
strain × treatment in 4F-I); that caveat is recorded in `notes`.

Run:
    /opt/anaconda3/bin/python scripts/recompute_panel_stats.py
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import pandas as pd
from scipy import stats

DATA_DIR = Path("/Users/arnav/vaultlab-kb/elife-91157-stress/data")
PANELS = ["A", "B", "C", "D", "E", "F", "G", "H", "I"]

CONTROL_TOKEN = "Vehicle"
TREATMENT_TOKEN = "(R)-DI-87"


def _split_groups(df: pd.DataFrame) -> tuple[list[float], list[float]]:
    """Return (control_values, treatment_values), substring-matched on `group`."""
    group_col = df["group"].astype(str)
    vehicle_mask = group_col.str.contains(CONTROL_TOKEN, regex=False)
    treatment_mask = group_col.str.contains(TREATMENT_TOKEN, regex=False)
    # A row whose group label contains *both* tokens is ambiguous — exclude.
    ambiguous = vehicle_mask & treatment_mask
    if ambiguous.any():
        vehicle_mask &= ~ambiguous
        treatment_mask &= ~ambiguous
    control = df.loc[vehicle_mask & df["value"].notna(), "value"].astype(float).tolist()
    treatment = (
        df.loc[treatment_mask & df["value"].notna(), "value"].astype(float).tolist()
    )
    return control, treatment


def recompute_panel(panel_letter: str) -> dict:
    csv = DATA_DIR / f"Fig4{panel_letter}.csv"
    if not csv.exists():
        return {"panel": f"4{panel_letter}", "error": f"missing CSV: {csv}"}

    df = pd.read_csv(csv)
    control, treatment = _split_groups(df)

    n_v = len(control)
    n_t = len(treatment)
    notes = "pooled Vehicle vs (R)-DI-87 across all subgroups in the panel"

    if n_v < 2 or n_t < 2:
        return {
            "panel": f"4{panel_letter}",
            "n_vehicle": n_v,
            "n_treatment": n_t,
            "mean_vehicle": None if n_v == 0 else float(pd.Series(control).mean()),
            "mean_treatment": None if n_t == 0 else float(pd.Series(treatment).mean()),
            "direction": "null",
            "p_value": None,
            "p_lt_0_05": False,
            "notes": notes + f"; n_vehicle={n_v} or n_treatment={n_t} < 2 (test undefined)",
        }

    mean_v = float(pd.Series(control).mean())
    mean_t = float(pd.Series(treatment).mean())
    diff = mean_t - mean_v

    result = stats.ttest_ind(treatment, control, equal_var=False, nan_policy="omit")
    pval = float(result.pvalue)
    if math.isnan(pval):
        direction = "null"
        p_lt = False
        notes += "; t-test returned NaN"
    else:
        direction = "up" if diff > 0 else ("down" if diff < 0 else "null")
        p_lt = pval < 0.05

    return {
        "panel": f"4{panel_letter}",
        "n_vehicle": n_v,
        "n_treatment": n_t,
        "mean_vehicle": mean_v,
        "mean_treatment": mean_t,
        "direction": direction,
        "p_value": pval,
        "p_lt_0_05": p_lt,
        "notes": notes,
    }


def main() -> int:
    out = [recompute_panel(p) for p in PANELS]
    for row in out:
        print(json.dumps(row))
    return 0


if __name__ == "__main__":
    sys.exit(main())
