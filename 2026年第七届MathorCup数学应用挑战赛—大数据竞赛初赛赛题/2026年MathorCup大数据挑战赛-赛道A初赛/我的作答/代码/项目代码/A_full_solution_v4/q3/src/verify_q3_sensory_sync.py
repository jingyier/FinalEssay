"""Independently verify Q3's 50 proxy dimensions use the frozen Q1 scorer.

Requires numpy, pandas, and scikit-learn.  It reads the original contest CSVs
and the saved Q3 outputs, then refits Q1 on only Beer 13--250.  It does not
read or use Beer 1--12 sensory targets during fitting or calibration.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

Q3 = Path(__file__).resolve().parents[1]
PROJECT = Q3.parents[0]
sys.path.insert(0, str(PROJECT / "shared"))
from q1_tree_predictor import fit_fixed_panel_predictor  # noqa: E402

PACKAGE_ROOT = Path(__file__).resolve().parents[4]
DATA = Path(os.environ.get("MATHOR_INPUT_DIR", str(PACKAGE_ROOT / "03_原始附件")))


def main() -> None:
    chem = pd.read_csv(DATA / "1.csv").set_index("beer").sort_index()
    sensory = pd.read_csv(DATA / "4.csv").set_index("beer").sort_index()
    scorer = fit_fixed_panel_predictor(chem, sensory)
    assert len(scorer.train_ids) == 238
    features = scorer.feature_cols
    targets = scorer.target_cols

    generated = pd.read_csv(Q3 / "results" / "q3_generated_spectra.csv")
    saved = pd.read_csv(Q3 / "results" / "q3_generated_sensory_proxy.csv")
    expected = scorer.predict_proxy_grades(generated[features]).to_numpy(int)
    actual = saved[["proxy_score_" + col for col in targets]].to_numpy(int)
    assert np.array_equal(expected, actual)
    assert np.array_equal(generated[["style", "generated_id"]].to_numpy(),
                          saved[["style", "generated_id"]].to_numpy())

    migrated = pd.read_csv(Q3 / "results" / "q3_PilsLager_to_Tripel.csv")
    expected_migrated = scorer.predict_proxy_grades(migrated[features]).to_numpy(int)
    actual_migrated = migrated[["proxy_score_" + col for col in targets]].to_numpy(int)
    assert np.array_equal(expected_migrated, actual_migrated)

    q1_diff = None
    q1_output = os.environ.get("Q1_CONTINUOUS_CSV")
    if q1_output:
        q1 = scorer.predict_continuous(chem.loc[list(range(1, 13)), features]).to_numpy(float)
        q1_frame = pd.read_csv(q1_output)
        # The scorecard-facing Q1 CSV uses three display aliases while the
        # frozen predictor keeps the original 4.csv target names.
        aliases = {
            "A_esters_fruity": "A_ester_fruity",
            "F_esters_fruity": "F_ester_fruity",
            "X4vg": "4vg",
        }
        q1_columns = [aliases.get(col, col) for col in targets]
        q1_candidate = q1_frame[q1_columns].to_numpy(float)
        q1_diff = float(np.max(np.abs(q1 - q1_candidate)))
        assert q1_diff < 1e-12

    print({"q1_q3_max_abs_continuous_diff": q1_diff,
           "generated_proxy_cells_checked": int(expected.size),
           "migrated_proxy_cells_checked": int(expected_migrated.size),
           "training_beers": len(scorer.train_ids)})


if __name__ == "__main__":
    main()

