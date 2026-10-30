"""绘制问题二化学关联网络及阈值筛选结果。"""


from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


Q2_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = Q2_ROOT.parent
PACKAGE_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_MATRIX = PACKAGE_ROOT / "03_原始附件/2.csv"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--matrix", type=Path, default=DEFAULT_MATRIX)
    parser.add_argument("--threshold", type=float, default=0.65)
    parser.add_argument("--figure-dir", type=Path, default=PROJECT_ROOT / "figures")
    parser.add_argument("--audit-dir", type=Path, default=Q2_ROOT / "audit")
    args = parser.parse_args()
    if not 0 < args.threshold < 1:
        raise ValueError("threshold must be strictly between 0 and 1")
    args.figure_dir.mkdir(parents=True, exist_ok=True)
    args.audit_dir.mkdir(parents=True, exist_ok=True)

    source = pd.read_csv(args.matrix)
    names = source.iloc[:, 0].astype(str).tolist()
    assert len(names) == 231 and len(set(names)) == 231
    assert names == source.columns[1:].tolist()
    rho = source.iloc[:, 1:].to_numpy(float)
    assert rho.shape == (231, 231) and np.isfinite(rho).all()
    assert np.allclose(rho, rho.T) and np.allclose(np.diag(rho), 1)

    i, j = np.triu_indices(len(names), k=1)
    upper = rho[i, j]
    selected = np.abs(upper) >= args.threshold
    edge_i, edge_j, edge_rho = i[selected], j[selected], upper[selected]
    degree = np.zeros(len(names), dtype=int)
    np.add.at(degree, edge_i, 1)
    np.add.at(degree, edge_j, 1)
    n_positive, n_negative = int((edge_rho > 0).sum()), int((edge_rho < 0).sum())
    n_isolated = int((degree == 0).sum())
    n_nonisolated = int((degree > 0).sum())

    stem = f"q2_network_threshold_{str(args.threshold).replace('.', 'p')}"
    pd.DataFrame({
        "source": np.asarray(names)[edge_i], "target": np.asarray(names)[edge_j],
        "spearman_rho": edge_rho,
        "sign": np.where(edge_rho > 0, "正", "负"),
    }).to_csv(args.audit_dir / f"{stem}_edges.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame({
        "chemical_name": names, "degree": degree, "isolated": degree == 0,
    }).to_csv(args.audit_dir / f"{stem}_nodes.csv", index=False, encoding="utf-8-sig")

    plt.rcParams.update({
        "font.family": "Microsoft YaHei", "font.size": 9,
        "axes.unicode_minus": False, "svg.fonttype": "none",
        "axes.spines.top": False, "axes.spines.right": False,
    })
    fig, axes = plt.subplots(1, 2, figsize=(7.35, 3.05),
                             gridspec_kw={"width_ratios": [2.0, 1.0]})
    fig.subplots_adjust(left=0.075, right=0.975, top=0.87, bottom=0.17, wspace=0.30)
    fig.suptitle(f"Spearman 强关联骨架（|ρ| ≥ {args.threshold:.2f}）", fontsize=11, y=0.985)

    ax = axes[0]
    xs = np.arange(degree.max() + 1)
    counts = np.bincount(degree, minlength=len(xs))
    for value, count in enumerate(counts):
        ax.bar(value, count, width=0.78, color="white" if value == 0 else "0.55",
               edgecolor="black", linewidth=0.7, hatch="///" if value == 0 else None)
    ax.text(0, counts[0] + 3, str(n_isolated), ha="center", va="bottom", fontsize=9)
    ax.text(6.2, 103, f"有连边节点：{n_nonisolated} 个\n孤立节点：{n_isolated} 个",
            ha="center", va="center", fontsize=9,
            bbox={"facecolor": "white", "edgecolor": "0.55", "boxstyle": "square,pad=0.3"})
    ax.set_title("(a) 节点度数分布", fontsize=10)
    ax.set_xlabel("节点度数（条）")
    ax.set_ylabel("变量数（个）")
    ax.set_xlim(-0.6, degree.max() + 0.6)
    ax.set_ylim(0, max(140, counts.max() * 1.11))
    ax.set_xticks(xs)
    ax.set_yticks([0, 30, 60, 90, 120])
    ax.grid(axis="y", linestyle=":", linewidth=0.5, color="0.78")
    ax.set_axisbelow(True)

    ax = axes[1]
    bars = ax.bar([0, 1], [n_positive, n_negative], width=0.6,
                  color=["0.45", "white"], edgecolor="black",
                  linewidth=0.8)
    bars[1].set_hatch("///")
    for x, y in enumerate([n_positive, n_negative]):
        ax.text(x, y + 4, str(y), ha="center", va="bottom", fontsize=9)
    ax.set_title("(b) 边的相关方向", fontsize=10)
    ax.set_xticks([0, 1], ["正相关", "负相关"])
    ax.set_ylabel("无向边数（条）")
    ax.set_ylim(0, max(182, n_positive * 1.09))
    ax.set_yticks([0, 40, 80, 120, 160])
    ax.grid(axis="y", linestyle=":", linewidth=0.5, color="0.78")
    ax.set_axisbelow(True)
    base = args.figure_dir / f"fig_{stem}_topology"
    fig.savefig(base.with_suffix(".png"), dpi=320, facecolor="white")
    fig.savefig(base.with_suffix(".svg"), facecolor="white")
    plt.close(fig)
    print({"matrix": str(args.matrix), "threshold": args.threshold,
           "nodes": len(names), "nonisolated": n_nonisolated,
           "isolated": n_isolated, "edges": len(edge_rho),
           "positive": n_positive, "negative": n_negative,
           "figure": str(base.with_suffix('.png'))})


if __name__ == "__main__":
    main()
