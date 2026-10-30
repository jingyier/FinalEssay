"""核验问题二结果文件的结构、字段和关键数值。"""


from pathlib import Path

import numpy as np
import pandas as pd

root = Path(__file__).resolve().parents[1]
top = pd.read_csv(root / "results" / "q2_top3_per_dimension.csv")
stability = pd.read_csv(root / "results" / "q2_stability_summary.csv")
pool = pd.read_csv(root / "audit" / "q2_candidate_pool.csv")
boot = np.load(root / "audit" / "q2_bootstrap_selected_indices.npz")
features = list(map(str, boot["feature_names"]))
targets = list(map(str, boot["dimension_names"]))
full = boot["selected_full"]
fixed = boot["selected_fixed"]
assert top.shape[0] == 150 and len(targets) == 50
assert stability.shape[0] == 50 and len(features) == 231
assert full.shape == fixed.shape == (200, 50, 3)
assert (top.groupby("dimension").size() == 3).all()
assert top.groupby("dimension").feature.nunique().eq(3).all()
assert top.groupby("dimension")["rank"].apply(lambda r: set(r) == {1, 2, 3}).all()
allowed = set(pool.loc[pool.eligible, "feature"])
assert set(top.feature).issubset(allowed)
for row in top.itertuples(index=False):
    j, i = targets.index(row.dimension), features.index(row.feature)
    freq_full = np.mean((full[:, j, :] == i).any(axis=1))
    freq_fixed = np.mean((fixed[:, j, :] == i).any(axis=1))
    assert abs(freq_full - row.bootstrap_frequency_full_pipeline) < 1e-12
    assert abs(freq_fixed - row.bootstrap_frequency_fixed_network) < 1e-12
assert np.isfinite(top[["direct_spearman", "network_score", "integrated_score"]]).all().all()
assert ((top.bootstrap_frequency_full_pipeline >= 0) &
        (top.bootstrap_frequency_full_pipeline <= 1)).all()
print("Q2 structure, 150/150 results, eligibility, and both bootstrap frequencies: PASS")
