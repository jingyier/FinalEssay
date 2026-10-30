"""用 Matplotlib 生成问题一 12×52 评分热力图。

数据按字段名读取，再按照 scorecard_mapping.csv 中的评分卡行号排序，
避免直接按 CSV 列位置绘图造成字段错位。脚本只生成图，不修改论文文件。
"""
from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import BoundaryNorm, ListedColormap
from matplotlib.font_manager import FontProperties


SCRIPT_DIR = Path(__file__).resolve().parent
CODE_ROOT = SCRIPT_DIR.parent
Q1_ROOT = CODE_ROOT / "项目代码" / "A_problem1_v3_trees"
SCORES_PATH = Q1_ROOT / "results" / "A_problem1_v3_scores_52.csv"
MAPPING_PATH = Q1_ROOT / "data" / "scorecard_mapping.csv"
OUTPUT_PATH = SCRIPT_DIR / "图表" / "fig_q1_scorecard_heatmap_matplotlib_v4.png"


LABELS = {
    "A_malt_all": "麦芽总", "A_malt_grain": "谷物香", "A_malt_bread": "面包香",
    "A_malt_cara": "焦糖香", "A_malt_burn": "焦糊香", "A_hops_all": "酒花总",
    "A_hops_citrus": "柑橘香", "A_hops_tropical": "热带果香", "A_hops_noble": "贵族酒花",
    "A_hops_woody": "木质香", "A_esters_all": "酯香总", "A_esters_ethac": "乙酸乙酯香",
    "A_esters_isoaa": "香蕉香", "A_esters_flower": "花香", "A_ester_fruity": "果香",
    "A_acetaldehyde": "乙醛香", "body": "酒体", "bitternes": "苦味",
    "co2": "气泡感", "aftertaste": "余味", "dms": "二甲硫醚",
    "metallic": "金属味", "4vg": "丁香酚味", "orange": "橙皮",
    "coriander": "芫荽", "clove": "丁香", "overall": "整体评价",
    "F_malt_all": "麦芽味总", "F_malt_grain": "谷物味", "F_malt_bread": "面包味",
    "F_malt_cara": "焦糖味", "F_malt_burn": "焦糊味", "F_hops_all": "酒花味总",
    "F_hops_citrus": "柑橘味", "F_hops_tropical": "热带果味", "F_hops_noble": "贵族酒花味",
    "F_hops_woody": "木质味", "F_esters_all": "酯味总", "F_esters_ethac": "乙酸乙酯味",
    "F_esters_isoaa": "香蕉味", "F_esters_flower": "花味", "F_ester_fruity": "果味",
    "F_acetaldehyde": "乙醛味", "alcohol": "酒精感", "sweetness": "甜味",
    "acidity": "酸味", "t2n": "陈旧纸味", "diacetyl": "双乙酰味",
    "stale_hops": "陈酒花味", "lactic": "乳酸味", "acetic": "乙酸味", "barnyard": "牲畜棚味",
}


def font_properties() -> tuple[FontProperties, FontProperties]:
    """优先使用 Windows 宋体；换机时回退到 Matplotlib 默认字体。"""
    cjk_path = Path(r"C:\Windows\Fonts\simsun.ttc")
    if cjk_path.exists():
        cn = FontProperties(fname=str(cjk_path))
    else:
        cn = FontProperties(family="DejaVu Sans")
    latin = FontProperties(family="Times New Roman")
    return cn, latin


def load_data() -> tuple[pd.DataFrame, list[str], list[str]]:
    scores = pd.read_csv(SCORES_PATH).set_index("Beer")
    mapping = pd.read_csv(MAPPING_PATH)
    aroma = (
        mapping.loc[mapping["scorecard_column"].eq("Q")]
        .sort_values("scorecard_row")["dimension"]
        .tolist()
    )
    flavour = (
        mapping.loc[mapping["scorecard_column"].eq("AG")]
        .sort_values("scorecard_row")["dimension"]
        .tolist()
    )
    assert len(aroma) == 27 and len(flavour) == 25
    fields = aroma + flavour
    assert set(fields) == set(scores.columns)
    assert scores.shape == (12, 52)
    return scores, aroma, flavour


def draw_panel(ax, values: pd.DataFrame, fields: list[str], title: str, cn: FontProperties) -> None:
    # 离散 0—6 等级色带；本批数据实际最大值可能小于 6，但保留完整量表。
    colors = plt.get_cmap("Blues")(np.linspace(0.05, 0.95, 7))
    cmap = ListedColormap(colors)
    norm = BoundaryNorm(np.arange(-0.5, 7.5, 1), cmap.N)
    image = ax.imshow(values.to_numpy(dtype=int), cmap=cmap, norm=norm, aspect="auto", interpolation="none")

    ax.set_title(title, fontproperties=cn, fontsize=16, pad=18)
    ax.set_xticks(np.arange(len(fields)))
    ax.set_xticklabels([LABELS.get(field, field) for field in fields], rotation=90,
                       ha="center", va="top", fontproperties=cn, fontsize=8.5)
    ax.set_yticks(np.arange(len(values)))
    ax.set_yticklabels([f"啤酒{i}" for i in values.index], fontproperties=cn, fontsize=9.5)
    ax.tick_params(axis="both", length=0, pad=4)
    ax.set_xlabel("")
    ax.set_ylabel("")

    # 白色细网格让每个字段和每个样本边界清楚可见，不添加组间竖线。
    ax.set_xticks(np.arange(-0.5, len(fields), 1), minor=True)
    ax.set_yticks(np.arange(-0.5, len(values), 1), minor=True)
    ax.grid(which="minor", color="white", linewidth=0.75)
    ax.tick_params(which="minor", bottom=False, left=False)
    for spine in ax.spines.values():
        spine.set_visible(False)

    for row in range(values.shape[0]):
        for col in range(values.shape[1]):
            value = int(values.iloc[row, col])
            color = "white" if value >= 4 else "#263746"
            ax.text(col, row, str(value), ha="center", va="center", color=color,
                    fontsize=8.5, fontproperties=cn)
    return image


def main() -> None:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    scores, aroma, flavour = load_data()
    cn, _ = font_properties()
    fig, axes = plt.subplots(1, 2, figsize=(20, 6.8),
                             gridspec_kw={"width_ratios": [27, 25], "wspace": 0.32})
    image = draw_panel(axes[0], scores[aroma], aroma, "香气 Aroma（27项）", cn)
    draw_panel(axes[1], scores[flavour], flavour, "口味 Flavour（25项）", cn)

    colorbar = fig.colorbar(image, ax=axes, ticks=range(7), fraction=0.022, pad=0.018)
    colorbar.set_label("感官等级", fontproperties=cn, rotation=90, labelpad=12)
    colorbar.ax.set_yticklabels([str(i) for i in range(7)], fontproperties=cn, fontsize=9)
    fig.patch.set_facecolor("white")
    fig.savefig(str(OUTPUT_PATH), dpi=360, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"saved: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
