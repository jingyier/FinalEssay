"""绘制问题二同一数据源上的 MDI 与 SHAP 特征重要性对照图。"""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT
DATA = PACKAGE / "03_原始附件"
Q2 = PACKAGE / "项目代码" / "A_full_solution_v4" / "q2"
OUT = ROOT / "可视化代码" / "图表" / "fig_q2_shap_method_comparison.png"

# 本地机器学习运行环境提供 scikit-learn 和 matplotlib，但未提供 openpyxl；
# 待 pandas 和 NumPy 加载完成后，再补充使用随环境提供的 openpyxl。
PRIMARY_SITE = Path(r"C:\Users\llxxz\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\Lib\site-packages")
if PRIMARY_SITE.exists() and str(PRIMARY_SITE) not in sys.path:
    sys.path.insert(0, str(PRIMARY_SITE))

plt.rcParams.update({
    "font.sans-serif": ["Noto Sans SC", "Microsoft YaHei", "SimHei", "DejaVu Sans"],
    "axes.unicode_minus": False,
    "figure.dpi": 160,
    "savefig.dpi": 300,
})

LABELS = {
    "ethyl_acetate": "乙酸乙酯",
    "ethanol..v.v.": "乙醇",
    "protein.g.L.": "蛋白质",
    "lactic_acid.mg.L.": "乳酸",
    "ethyl_octanoate": "辛酸乙酯",
    "ethyl.phenylacetate": "苯乙酸乙酯",
    "MeSH": "甲硫醇",
    "isopentyl.hexanoate": "己酸异戊酯",
    "X2.ethyl.3.methylpyrazine": "乙基甲基吡嗪",
    "kcalperc": "热量指标",
    "isopentyl_acetate": "乙酸异戊酯",
}


def main() -> None:
    workbook = DATA / "8.xlsx"
    mdi = pd.read_excel(workbook, sheet_name="GBM importance MDI", header=None)
    mdi.columns = ["importance", "feature"]
    mdi = mdi.iloc[1:].copy()
    mdi["importance"] = pd.to_numeric(mdi["importance"], errors="coerce")
    mdi = mdi.dropna(subset=["importance", "feature"])
    mdi = mdi.set_index("feature")["importance"].abs()

    shap = pd.read_excel(workbook, sheet_name="GBM SHAP Values")
    shap = shap[shap.iloc[:, 0].astype(str).str.upper().eq("SHAP")]
    shap_features = [c for c in shap.columns[4:] if c in mdi.index]
    shap_abs = shap[shap_features].apply(pd.to_numeric, errors="coerce").abs().mean().sort_values(ascending=False)

    overall = pd.read_csv(Q2 / "results" / "q2_top3_per_dimension.csv")
    our_top3 = overall.loc[overall["dimension"].eq("overall"), "feature"].tolist()
    comparison = pd.read_csv(Q2 / "audit" / "q2_workbook_gbm_method_comparison.csv")
    mdi_j = float(comparison.loc[comparison["method"].str.contains("MDI"), "jaccard"].iloc[0])
    shap_j = float(comparison.loc[comparison["method"].str.contains("SHAP"), "jaccard"].iloc[0])

    # 保留 SHAP 值最大的十个特征；若三个候选指标不在其中，则一并追加，
    # 使候选指标与 SHAP 排名的重合关系能够直接呈现。
    features = list(shap_abs.head(10).index)
    for feature in our_top3:
        if feature not in features:
            features.append(feature)
    features = features[:13]
    frame = pd.DataFrame({"feature": features})
    frame["shap"] = frame["feature"].map(shap_abs).fillna(0.0)
    frame["mdi"] = frame["feature"].map(mdi).fillna(0.0)
    frame["our"] = frame["feature"].isin(our_top3)
    frame = frame.sort_values("shap", ascending=True)
    frame["label"] = frame["feature"].map(lambda x: LABELS.get(x, x))
    frame["shap_norm"] = frame["shap"] / max(frame["shap"].max(), 1e-12)
    frame["mdi_norm"] = frame["mdi"] / max(frame["mdi"].max(), 1e-12)

    fig, (ax, ax2) = plt.subplots(1, 2, figsize=(11.2, 6.2), gridspec_kw={"width_ratios": [3.1, 1.25]})
    y = np.arange(len(frame))
    highlight_edge = np.where(frame["our"], "#D97745", "none")
    ax.barh(y + 0.18, frame["shap_norm"], height=0.30, color="#5D7FA3", edgecolor=highlight_edge,
            linewidth=2.2, alpha=0.95, label="同源 GBM |SHAP|（归一化）")
    ax.barh(y - 0.18, frame["mdi_norm"], height=0.30, color="#A7B1BC", edgecolor=highlight_edge,
            linewidth=2.2, alpha=0.95, label="同源 GBM MDI（归一化）")
    ax.set_yticks(y, frame["label"])
    ax.set_xlim(0, 1.12)
    ax.set_xlabel("相对重要度（各方法最大值=1）")
    ax.set_title("同源 GBM 的 MDI / SHAP 对照", fontsize=13, pad=10)
    ax.grid(axis="x", color="#DCE3EA", linewidth=0.7)
    ax.set_axisbelow(True)
    for yi, row in zip(y, frame.itertuples()):
        if row.our:
            ax.text(1.03, yi, "主 Top-3", va="center", fontsize=8.5, color="#B4532C", fontweight="bold")
    ax.legend(loc="lower right", frameon=False, fontsize=8.5)

    methods = ["MDI", "SHAP"]
    jaccard = [mdi_j, shap_j]
    colors = ["#A7B1BC", "#5D7FA3"]
    yy = np.arange(2)
    ax2.barh(yy, jaccard, color=colors, height=0.46)
    ax2.set_yticks(yy, methods)
    ax2.set_xlim(0, 1)
    ax2.set_xlabel("与我们 overall Top-3 的 Jaccard")
    ax2.set_title("集合重合度", fontsize=13, pad=10)
    ax2.grid(axis="x", color="#DCE3EA", linewidth=0.7)
    ax2.set_axisbelow(True)
    for yi, value in zip(yy, jaccard):
        ax2.text(value + 0.035, yi, f"{value:.2f}", va="center", fontsize=10, color="#334155")
    fig.suptitle("问题二：MDI / SHAP 与综合 Top-3 对照", fontsize=16, y=0.995, color="#20364D")
    fig.tight_layout(rect=[0, 0.02, 1, 0.96])
    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT, bbox_inches="tight", facecolor="white")
    print(f"wrote {OUT}")
    print(f"our overall top3={our_top3}; MDI Jaccard={mdi_j:.2f}; SHAP Jaccard={shap_j:.2f}")


if __name__ == "__main__":
    main()
