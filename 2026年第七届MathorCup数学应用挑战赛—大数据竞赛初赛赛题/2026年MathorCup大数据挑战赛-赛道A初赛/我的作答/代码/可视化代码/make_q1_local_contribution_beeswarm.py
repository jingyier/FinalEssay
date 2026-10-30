"""Create a SHAP-style sample-level contribution plot for Question 1.

The frozen model is explained with a transparent baseline perturbation:
replace one chemical feature by its development-set median and measure the
change in the ensemble prediction.  This is deliberately labelled as a
baseline perturbation contribution, not TreeSHAP, because the runtime does
not include a TreeSHAP implementation.
"""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import Normalize

CODE_ROOT = Path(__file__).resolve().parents[1]
SHARED = CODE_ROOT / "项目代码" / "A_full_solution_v4" / "shared"
sys.path.insert(0, str(SHARED))
from q1_tree_predictor import fit_fixed_panel_predictor  # noqa: E402


PACKAGE = CODE_ROOT
DATA = PACKAGE / "03_原始附件"
OUT = PACKAGE / "可视化代码" / "图表" / "fig_q1_local_contribution_beeswarm.png"

TARGETS = [
    ("A_esters_all", "香气·酯香总强度"),
    ("A_hops_all", "香气·酒花总强度"),
    ("F_esters_all", "风味·酯香总强度"),
    ("acidity", "酸味"),
    ("alcohol", "酒精感"),
    ("overall", "总体评价"),
]

plt.rcParams.update({
    "font.sans-serif": ["Noto Sans SC", "Microsoft YaHei", "SimHei", "DejaVu Sans"],
    "axes.unicode_minus": False,
    "figure.dpi": 150,
    "savefig.dpi": 300,
})


def main() -> None:
    chem = pd.read_csv(DATA / "1.csv").set_index("beer").sort_index()
    sensory = pd.read_csv(DATA / "4.csv").set_index("beer").sort_index()
    predictor = fit_fixed_panel_predictor(chem, sensory)
    train_ids = list(predictor.train_ids)
    x_train = chem.loc[train_ids, predictor.feature_cols].copy()
    base_pred = predictor.predict_continuous(x_train)

    # Aggregate the three tree components' importances and retain original
    # chemical fields (indicator columns are omitted from the visual).
    n_base = len(predictor.feature_cols)
    importance = np.zeros((len(predictor.target_cols), n_base), float)
    for name, model in predictor.models.items():
        if name == "gradient_boosting":
            values = np.vstack([m.feature_importances_[:n_base] for m in model.estimators_])
        else:
            values = np.asarray(model.feature_importances_[:n_base])
            if values.ndim == 1:
                values = np.repeat(values[None, :], len(predictor.target_cols), axis=0)
        importance += predictor.weights[name] * values

    top_by_target = {}
    needed = set()
    for target, _ in TARGETS:
        j = predictor.target_cols.index(target)
        order = np.argsort(importance[j])[::-1]
        features = [predictor.feature_cols[k] for k in order[:8]]
        top_by_target[target] = features
        needed.update(features)

    median = x_train.median(numeric_only=True)
    contribution = {}
    for feature in sorted(needed):
        perturbed = x_train.copy()
        perturbed[feature] = median[feature]
        pred = predictor.predict_continuous(perturbed)
        contribution[feature] = base_pred.to_numpy() - pred.to_numpy()

    fig, axes = plt.subplots(2, 3, figsize=(15.2, 8.8), sharex=False)
    fig.subplots_adjust(left=0.055, right=0.885, bottom=0.075, top=0.96, wspace=0.28, hspace=0.38)
    rng = np.random.default_rng(20261024)
    cmap = plt.get_cmap("coolwarm")
    all_abs = []
    for target, title in TARGETS:
        j = predictor.target_cols.index(target)
        rows = []
        for feature in top_by_target[target]:
            vals = contribution[feature][:, j]
            rows.append((feature, vals))
            all_abs.extend(np.abs(vals).tolist())
        rows.sort(key=lambda z: np.median(np.abs(z[1])))
        ax = axes.ravel()[TARGETS.index((target, title))]
        for y, (feature, vals) in enumerate(rows):
            raw = pd.to_numeric(x_train[feature], errors="coerce").to_numpy(float)
            fill = np.nanmedian(raw) if np.isfinite(raw).any() else 0.0
            raw = np.where(np.isfinite(raw), raw, fill)
            scale = np.nanpercentile(raw, [5, 95])
            norm = Normalize(vmin=scale[0], vmax=scale[1] if scale[1] > scale[0] else scale[0] + 1e-9)
            jitter = rng.normal(0, 0.055, size=len(vals))
            ax.scatter(vals, np.full(len(vals), y) + jitter, c=norm(raw), cmap=cmap,
                       s=13, alpha=0.58, edgecolors="none", rasterized=True)
        ax.axvline(0, color="#6B7280", linewidth=0.8)
        ax.set_yticks(range(len(rows)), [f for f, _ in rows], fontsize=7.5)
        ax.set_title(title, fontsize=11, pad=7)
        ax.grid(axis="x", color="#E4E9EF", linewidth=0.7)
        ax.set_axisbelow(True)
        ax.tick_params(axis="x", labelsize=8)
        ax.set_xlabel("基线扰动对预测的贡献 Δŷ", fontsize=8.5)

    sm = plt.cm.ScalarMappable(norm=Normalize(vmin=0, vmax=1), cmap=cmap)
    sm.set_array([])
    cax = fig.add_axes([0.905, 0.19, 0.016, 0.62])
    cbar = fig.colorbar(sm, cax=cax)
    cbar.set_ticks([0, 0.5, 1])
    cbar.set_ticklabels(["低", "中", "高"])
    cbar.set_label("特征值分位（面板内）", fontsize=9)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT, facecolor="white", bbox_inches="tight")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()

