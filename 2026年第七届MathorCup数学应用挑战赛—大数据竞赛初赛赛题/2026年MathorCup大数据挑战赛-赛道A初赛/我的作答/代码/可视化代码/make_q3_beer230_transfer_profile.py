"""绘制代表性 Beer 230 的源样本、迁移样本和目标样本感官剖面。"""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

CODE_ROOT = Path(__file__).resolve().parents[1]
SHARED = CODE_ROOT / "项目代码" / "A_full_solution_v4" / "shared"
sys.path.insert(0, str(SHARED))
from q1_tree_predictor import fit_fixed_panel_predictor  # noqa: E402


PACKAGE = CODE_ROOT
DATA = PACKAGE / "03_原始附件"
Q3 = PACKAGE / "项目代码" / "A_full_solution_v4" / "q3"
OUT = PACKAGE / "可视化代码" / "图表" / "fig_q3_beer230_transfer_profile.png"
BEER = 230

DIMENSIONS = [
    ("A_esters_all", "酯香"),
    ("A_hops_all", "酒花香"),
    ("acidity", "酸度"),
    ("sweetness", "甜味"),
    ("alcohol", "酒精感"),
    ("body", "醇厚"),
    ("co2", "气泡"),
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
    feature_cols = predictor.feature_cols
    source = chem.loc[[BEER], feature_cols]
    transfer = pd.read_csv(Q3 / "results" / "q3_PilsLager_to_Tripel.csv")
    row = transfer.loc[transfer["source_beer"].eq(BEER)]
    if row.empty:
        raise ValueError(f"Beer {BEER} is not a Pils/Lager migration source")
    migrated = row.iloc[[0]][feature_cols]
    source_pred = predictor.predict_continuous(source).iloc[0]
    migrated_pred = predictor.predict_continuous(migrated).iloc[0]
    target_mean = sensory.loc[chem["tasting_category_fine"].eq("Tripel"), predictor.target_cols].mean()
    validation = pd.read_csv(Q3 / "results" / "q3_transfer_validation.csv")
    v = validation.loc[validation["source_beer"].eq(BEER)].iloc[0]
    values = pd.DataFrame({
        "source": [source_pred[d] for d, _ in DIMENSIONS],
        "transfer": [migrated_pred[d] for d, _ in DIMENSIONS],
        "target": [target_mean[d] for d, _ in DIMENSIONS],
    }, index=[label for _, label in DIMENSIONS])

    fig, ax = plt.subplots(figsize=(11.8, 6.4))
    x = np.arange(len(values))
    ax.plot(x, values["source"], marker="o", color="#5D7FA3", linewidth=2.0, label="源谱预测")
    ax.plot(x, values["transfer"], marker="s", color="#D97745", linewidth=2.0, linestyle="--", label="迁移谱预测")
    ax.plot(x, values["target"], marker="^", color="#2C8C83", linewidth=2.0, linestyle=":", label="Tripel观测均值")
    ax.axhline(0, color="#AAB4BF", linewidth=0.8)
    ax.set_xticks(x, values.index)
    ax.set_ylabel("标准化连续感官预测")
    ax.set_title(f"Beer {BEER}: Pils/Lager → Tripel")
    ax.grid(axis="y", color="#E1E7ED", linewidth=0.7)
    ax.legend(frameon=False, ncol=3, loc="upper center", bbox_to_anchor=(0.5, 1.02))
    fig.tight_layout()
    fig.savefig(OUT, bbox_inches="tight", facecolor="white")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
