"""问题二的审计版求解程序。完成化学指标筛选、感官关联分析、网络筛选及稳定性评估。"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from pathlib import Path

import numpy as np
import pandas as pd


PACKAGE_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_INPUT = PACKAGE_ROOT / "03_原始附件"
ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"
AUDIT = ROOT / "audit"
SEED = 20261025

# 候选因素必须是实测变量，主要对应单个化合物。直接
# 保留化学物质的直接理化测量值（例如
# 乙醇浓度和 CO2 压力）；这些变量并不都表示香气化合物
# 浓度。因此删除汇总指数、宽泛的非分子描述量
# 以及内标产生的伪变量。
NON_COMPOUND = {
    "color.EBC.", "betaglucan.mg.L.", "pH", "protein.g.L.",
    "bitterness", "GFS", "unfermentables", "kcalperc", "iron",
    "esters_sum", "aroma_hops_sum", "acids_sum", "sulfur_sum",
}


def norm(value: object) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value).lower())


def spearman_xy(x: np.ndarray, y: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """严格的成对完整 Spearman 相关：对每个有效样本对分别重新排序。

    The fast matrix path applies only when a chemical column has no missing
    value. For every partly missing chemical column, both X and each Y target
    are re-ranked on the joint valid rows. This matters especially in bootstrap
    samples where the number of valid rows changes.
    """
    x = np.asarray(x, float)
    y = np.asarray(y, float)
    if not np.isfinite(y).all():
        raise ValueError("spearman_xy currently requires fully observed sensory Y")
    xr = pd.DataFrame(x).rank(axis=0, method="average").to_numpy(float)
    yr = pd.DataFrame(y).rank(axis=0, method="average").to_numpy(float)
    mask = np.isfinite(xr).astype(float)
    xx = np.nan_to_num(xr, nan=0.0)
    n = mask.sum(axis=0)[:, None]
    sx = xx.sum(axis=0)[:, None]
    sx2 = (xx * xx).sum(axis=0)[:, None]
    sy = mask.T @ yr
    sy2 = mask.T @ (yr * yr)
    sxy = xx.T @ yr
    num = sxy - sx * sy / np.maximum(n, 1.0)
    den = np.sqrt(
        np.maximum(sx2 - sx * sx / np.maximum(n, 1.0), 0.0)
        * np.maximum(sy2 - sy * sy / np.maximum(n, 1.0), 0.0)
    )
    rho = np.divide(num, den, out=np.zeros_like(num), where=den > 1e-12)
    for i in np.flatnonzero(~np.isfinite(x).all(axis=0)):
        valid = np.isfinite(x[:, i])
        xv = pd.Series(x[valid, i]).rank(method="average").to_numpy(float).copy()
        yv = pd.DataFrame(y[valid]).rank(axis=0, method="average").to_numpy(float).copy()
        xv -= xv.mean()
        yv -= yv.mean(axis=0, keepdims=True)
        numerator = xv @ yv
        denominator = np.sqrt((xv @ xv) * np.sum(yv * yv, axis=0))
        rho[i] = np.divide(numerator, denominator,
                           out=np.zeros(y.shape[1], dtype=float), where=denominator > 1e-12)
        n[i] = int(valid.sum())
    return np.clip(rho, -1.0, 1.0), np.repeat(n, y.shape[1], axis=1)


def network_score(direct: np.ndarray, transition: np.ndarray) -> np.ndarray:
    first = transition @ direct
    second = transition @ first
    return 0.65 * direct + 0.25 * first + 0.10 * second


def scaled_abs(values: np.ndarray, eligible: np.ndarray) -> np.ndarray:
    a = np.abs(values)
    den = np.max(a[eligible], axis=0, keepdims=True)
    return a / np.maximum(den, 1e-12)


def selector(direct: np.ndarray, transition: np.ndarray, redundancy: np.ndarray,
             eligible: np.ndarray, direct_weight: float = 0.70) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """唯一的最终筛选器；每次 bootstrap 均不作改动地复用。"""
    network = network_score(direct, transition)
    evidence = (direct_weight * scaled_abs(direct, eligible)
                + (1.0 - direct_weight) * scaled_abs(network, eligible))
    evidence[~eligible, :] = -np.inf
    selected = np.empty((direct.shape[1], 3), dtype=int)
    for k in range(direct.shape[1]):
        chosen: list[int] = []
        for slot in range(3):
            score = evidence[:, k].copy()
            if chosen:
                score -= 0.15 * np.max(redundancy[:, chosen], axis=1)
            score[~eligible] = -np.inf
            score[chosen] = -np.inf
            idx = int(np.argmax(score))
            if not np.isfinite(score[idx]):
                raise RuntimeError(f"fewer than three eligible compounds for target {k}")
            chosen.append(idx)
            selected[k, slot] = idx
    return selected, network, evidence


def simple_top3(matrix: np.ndarray, eligible: np.ndarray,
                redundancy: np.ndarray) -> np.ndarray:
    """仅用于方法比较；最终筛选器为 `selector`。"""
    signal = scaled_abs(matrix, eligible)
    signal[~eligible, :] = -np.inf
    out = np.empty((matrix.shape[1], 3), dtype=int)
    for k in range(matrix.shape[1]):
        chosen: list[int] = []
        for j in range(3):
            score = signal[:, k].copy()
            if chosen:
                score -= 0.15 * np.max(redundancy[:, chosen], axis=1)
            score[~eligible] = -np.inf
            score[chosen] = -np.inf
            idx = int(np.argmax(score))
            chosen.append(idx)
            out[k, j] = idx
    return out


def jaccard(a: np.ndarray, b: np.ndarray) -> float:
    aa, bb = set(map(int, a)), set(map(int, b))
    return len(aa & bb) / len(aa | bb)


def bh_fdr(p: np.ndarray) -> np.ndarray:
    flat = np.asarray(p, float).ravel()
    order = np.argsort(flat)
    ranked = flat[order]
    q = np.minimum.accumulate((ranked * len(flat) / np.arange(1, len(flat) + 1))[::-1])[::-1]
    result = np.empty_like(q)
    result[order] = np.clip(q, 0, 1)
    return result.reshape(p.shape)


def source_flag(target: str, source: object) -> str:
    """粗粒度来源核验，不用于排名筛选。"""
    prefix = target.split("_")[1] if target.startswith(("A_", "F_")) else ""
    expected = {"malt": {"Malt"}, "hops": {"Hops"}, "esters": {"Yeast"}}.get(prefix)
    if expected is None:
        return "不适用"
    return "来源相符" if str(source) in expected else "需解释"


def workbook_metadata(input_dir: Path, features: list[str]) -> pd.DataFrame:
    tbl = pd.read_excel(input_dir / "8.xlsx", sheet_name="Sensory thresholds")
    tbl = tbl.dropna(subset=["field_name_R"]).drop_duplicates("field_name_R")
    by_name = tbl.set_index("field_name_R")
    missing = sorted(set(features) - set(by_name.index))
    if missing:
        raise RuntimeError(f"8.xlsx metadata missing feature names: {missing}")
    return by_name.loc[features].reset_index()


def same_source_check(input_dir: Path, direct: np.ndarray, features: list[str],
                      targets: list[str], meta: pd.DataFrame) -> dict:
    cross = pd.read_csv(input_dir / "6.csv")
    sensory = pd.read_excel(input_dir / "8.xlsx", sheet_name="Sensory names")
    sensory_alias = {norm(row["CleanName_PanelFeedback"]): str(row["R_name"])
                     for _, row in sensory[sensory.R_name.isin(targets)]
                     .dropna(subset=["CleanName_PanelFeedback"]).iterrows()}
    sensory_alias[norm("Overall appreciation (Trained panel)")] = "overall"
    chem_alias: dict[str, str] = {}
    for _, row in meta.iterrows():
        for col in ("field_name_R", "field_name_python", "chemical_name", "chemical_name_short"):
            if pd.notna(row[col]):
                chem_alias[norm(row[col])] = str(row["field_name_R"])
    records = []
    for _, row in cross.iterrows():
        raw_chem = str(row.iloc[0])
        chem = chem_alias.get(norm(raw_chem))
        if chem is None or chem not in features:
            raise RuntimeError(f"6.csv chemical not aligned: {raw_chem}")
        i = features.index(chem)
        for col in cross.columns[1:]:
            target = sensory_alias.get(norm(col))
            if target is None:
                raise RuntimeError(f"6.csv sensory label not aligned: {col}")
            j = targets.index(target)
            records.append((chem, target, float(row[col]), float(direct[i, j])))
    frame = pd.DataFrame(records, columns=["feature", "dimension", "supplied_6_spearman", "recomputed_spearman"])
    frame["absolute_difference"] = (frame.iloc[:, 2] - frame.iloc[:, 3]).abs()
    frame.to_csv(AUDIT / "q2_6csv_same_source_comparison.csv", index=False, encoding="utf-8-sig")
    return {"mapped_rows": len(cross), "mapped_columns": len(cross.columns)-1,
            "mapped_cells": len(frame), "mean_absolute_difference": float(frame.absolute_difference.mean()),
            "max_absolute_difference": float(frame.absolute_difference.max())}


def anchor_audit(direct: np.ndarray, selected: np.ndarray, counts: np.ndarray,
                 features: list[str], targets: list[str], eligible: np.ndarray,
                 n_boot: int) -> pd.DataFrame:
    """利用预先指定的化学—感官配对检验合理性，不强制纳入筛选结果。"""
    anchors = {
        "dms": "DMS", "diacetyl": "X2.3.butanedione", "t2n": "X.E..2.nonenal",
        "X4vg": "X4VG", "lactic": "lactic_acid.mg.L.",
        "acetic": "acetic_acid.g.L.", "alcohol": "ethanol..v.v.",
        "co2": "CO2.PSI.", "A_esters_ethac": "ethyl_acetate",
        "A_esters_isoaa": "isopentyl_acetate", "F_esters_ethac": "ethyl_acetate",
        "F_esters_isoaa": "isopentyl_acetate",
    }
    out = []
    for target, feature in anchors.items():
        j, i = targets.index(target), features.index(feature)
        eligible_abs = np.abs(direct[eligible, j])
        rank = int((eligible_abs > abs(direct[i, j])).sum() + 1)
        out.append({"dimension": target, "named_chemical": feature,
                    "direct_spearman": direct[i, j], "absolute_spearman_rank_among_candidates": rank,
                    "in_selected_top3": bool(i in selected[j]),
                    "bootstrap_frequency_full_pipeline": counts[j, i] / n_boot})
    return pd.DataFrame(out)


def workbook_gbm_comparison(input_dir: Path, target: str,
                            final: np.ndarray, features: list[str]) -> pd.DataFrame:
    """在同一研究数据内比较整体指标，仅作算法比较，不构成外部验证。"""
    mdi = pd.read_excel(input_dir / "8.xlsx", sheet_name="GBM importance MDI")
    mdi = mdi.rename(columns={mdi.columns[0]: "importance", mdi.columns[1]: "feature"})
    mdi["importance"] = pd.to_numeric(mdi.importance, errors="coerce")
    mdi_top = mdi.dropna(subset=["importance"]).sort_values("importance", ascending=False).feature.head(3).tolist()
    shap = pd.read_excel(input_dir / "8.xlsx", sheet_name="GBM SHAP Values")
    shap = shap[shap.iloc[:, 0].astype(str).str.upper().eq("SHAP")]
    shap_scores = {f: float(pd.to_numeric(shap[f], errors="coerce").abs().mean()) for f in features if f in shap}
    shap_top = sorted(shap_scores, key=shap_scores.get, reverse=True)[:3]
    final_names = {features[i] for i in final}
    out = []
    for method, names in (("GBM MDI，同一研究", mdi_top), ("GBM SHAP，同一研究", shap_top)):
        shared = len(final_names & set(names))
        out.append({"dimension": target, "method": method, "workbook_top3": "; ".join(names),
                    "our_top3": "; ".join(features[i] for i in final),
                    "shared_count": shared, "jaccard": shared / (6 - shared)})
    return pd.DataFrame(out)


def style_adjusted_check(x: np.ndarray, y: np.ndarray, chem: pd.DataFrame,
                         top3: pd.DataFrame, features: list[str], targets: list[str]) -> pd.DataFrame:
    """检验风格差异导致的混杂敏感性，不作为因果估计。"""
    style = chem.tasting_category_fine.astype(str)
    xr = pd.DataFrame(x, columns=features).rank(axis=0, method="average")
    yr = pd.DataFrame(y, columns=targets).rank(axis=0, method="average")
    xres = xr - xr.groupby(style).transform("mean")
    yres = yr - yr.groupby(style).transform("mean")
    out = []
    for row in top3.itertuples(index=False):
        adjusted = float(xres[row.feature].corr(yres[row.dimension]))
        out.append({"dimension": row.dimension, "rank": int(row.rank), "feature": row.feature,
                    "unadjusted_spearman": float(row.direct_spearman),
                    "style_demeaned_rank_correlation": adjusted,
                    "same_sign": bool(np.sign(adjusted) == np.sign(row.direct_spearman)),
                    "absolute_adjusted_at_least_0_20": bool(abs(adjusted) >= 0.20)})
    return pd.DataFrame(out)


def plausibility_review(direct: np.ndarray, top3: pd.DataFrame, meta: pd.DataFrame,
                        features: list[str], targets: list[str], eligible: np.ndarray) -> pd.DataFrame:
    """预先指定的命名锚点，加上仅基于源样本的类别核验。

    A source-matched Hops/Malt/Yeast compound is merely a contextual check;
    the source label does not establish a matching sensory mechanism.
    """
    named = {
        "dms": "DMS", "diacetyl": "X2.3.butanedione", "t2n": "X.E..2.nonenal",
        "X4vg": "X4VG", "lactic": "lactic_acid.mg.L.", "acetic": "acetic_acid.g.L.",
        "alcohol": "ethanol..v.v.", "co2": "CO2.PSI.",
        "A_esters_ethac": "ethyl_acetate", "A_esters_isoaa": "isopentyl_acetate",
        "F_esters_ethac": "ethyl_acetate", "F_esters_isoaa": "isopentyl_acetate",
    }
    source_only = {
        "A_hops_tropical": "Hops", "F_hops_tropical": "Hops",
        "A_hops_noble": "Hops", "A_malt_all": "Malt",
        "F_malt_all": "Malt", "A_esters_flower": "Yeast",
    }
    rows = []
    for target in [*named, *source_only]:
        j = targets.index(target)
        block = top3.loc[top3.dimension.eq(target)].sort_values("rank")
        if target in named:
            ref = named[target]
            basis = "感官维度直接命名或对应化合物；部分缺陷描述见8.xlsx"
        else:
            expected = source_only[target]
            idx = [i for i, f in enumerate(features) if eligible[i] and
                   str(meta.iloc[i].origin_paper) == expected]
            best = max(idx, key=lambda i: abs(direct[i, j]))
            ref = features[best]
            basis = f"8.xlsx来源为{expected}的最强样本关联；来源一致不等于致味证据"
        i = features.index(ref)
        rank_abs = int((np.abs(direct[eligible, j]) > abs(direct[i, j])).sum() + 1)
        in_top = bool(ref in set(block.feature))
        ref_freq = float(block.loc[block.feature.eq(ref), "bootstrap_frequency_full_pipeline"].iloc[0]) if in_top else np.nan
        if target in named:
            if abs(direct[i, j]) < 0.20 and not in_top:
                verdict = "化学锚点未获样本关联支持；Top-3只能视为风格相关标志"
            elif in_top and ref_freq >= 0.50:
                verdict = "名称及统计关联相符；仍不能推断因果"
            elif in_top:
                verdict = "名称对应但Top-3入选不稳"
            else:
                verdict = "化学锚点未入选；需谨慎解释统计代理"
        else:
            verdict = ("Top-3含同来源化学候选；具体致味联系尚需证据" if in_top else
                       "Top-3未含该类最强来源候选；可能是风格相关标志")
        rows.append({
            "dimension": target, "statistical_top3": "; ".join(block.feature),
            "top3_mean_bootstrap_frequency": float(block.bootstrap_frequency_full_pipeline.mean()),
            "top3_origins": "; ".join(block.chemical_origin),
            "chemical_reference": ref, "reference_origin": str(meta.iloc[i].origin_paper),
            "reference_basis": basis, "reference_spearman": float(direct[i, j]),
            "reference_absolute_rank_among_217": rank_abs,
            "reference_in_statistical_top3": in_top,
            "reference_bootstrap_frequency_if_selected": ref_freq,
            "review_verdict": verdict,
        })
    return pd.DataFrame(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--bootstrap", type=int, default=200)
    args = parser.parse_args()
    if args.bootstrap < 1:
        raise ValueError("bootstrap must be positive")
    RESULTS.mkdir(parents=True, exist_ok=True)
    AUDIT.mkdir(parents=True, exist_ok=True)
    chem = pd.read_csv(args.input_dir / "1.csv")
    sens = pd.read_csv(args.input_dir / "4.csv")
    assert chem.beer.astype(int).equals(sens.beer.astype(int)), "beer row order mismatch"
    # 4.csv 中多数 beer_id 以科学计数法保存并发生了舍入。
    # 与行顺序一一对应的唯一 beer 索引是可靠的连接键。
    assert chem.beer.is_unique and sens.beer.is_unique
    rounded_beer_id_disagreements = int((chem.beer_id.astype(str) !=
        sens.beer_id.astype("int64").astype(str)).sum())
    features = chem.columns[3:].tolist()
    targets = sens.columns[3:].tolist()
    assert len(features) == 231 and len(targets) == 50
    meta = workbook_metadata(args.input_dir, features)
    excluded = set(NON_COMPOUND)
    internal = meta.loc[meta.origin_paper.eq("Internal standard solution"), "field_name_R"].tolist()
    excluded.update(internal)
    eligible = np.array([f not in excluded for f in features], dtype=bool)
    assert eligible.sum() >= 200
    pd.DataFrame({"feature": features, "eligible": eligible,
                  "reason": ["eligible measured factor, mostly individual compounds" if ok else
                             "aggregate/non-molecular descriptor/internal standard"
                             for ok in eligible]}).to_csv(AUDIT / "q2_candidate_pool.csv", index=False, encoding="utf-8-sig")

    x = chem[features].apply(pd.to_numeric, errors="coerce").to_numpy(float)
    y = sens[targets].apply(pd.to_numeric, errors="coerce").to_numpy(float)
    if not np.isfinite(y).all():
        raise RuntimeError("4.csv contains missing sensory outcomes; revise pairwise estimator")
    direct, pair_n = spearman_xy(x, y)
    supplied = pd.read_csv(args.input_dir / "2.csv")
    if supplied.shape != (231, 232):
        raise RuntimeError(f"unexpected 2.csv shape {supplied.shape}")
    corr = supplied.iloc[:, 1:].to_numpy(float)
    raw_spearman = pd.DataFrame(x).corr(method="spearman").to_numpy(float)
    off_diag = ~np.eye(len(features), dtype=bool)
    network_mae = float(np.nanmean(np.abs(corr[off_diag] - raw_spearman[off_diag])))
    network_max = float(np.nanmax(np.abs(corr[off_diag] - raw_spearman[off_diag])))
    if network_mae > 0.01:
        raise RuntimeError("2.csv feature order or correlation definition conflicts with 1.csv")
    corr = np.nan_to_num((corr + corr.T) / 2, nan=0.0)
    np.fill_diagonal(corr, 1.0)
    adjacency = np.sign(corr) * np.abs(corr) ** 10
    np.fill_diagonal(adjacency, 0.0)
    transition = adjacency / np.maximum(np.abs(adjacency).sum(axis=1, keepdims=True), 1e-12)
    redundancy = np.abs(corr)
    final, network, evidence = selector(direct, transition, redundancy, eligible)
    direct_only = simple_top3(direct, eligible, redundancy)
    network_only = simple_top3(network, eligible, redundancy)
    sensitivity_rows = []
    for beta_test in (5, 10, 20):
        test_adj = np.sign(corr) * np.abs(corr) ** beta_test
        np.fill_diagonal(test_adj, 0.0)
        test_transition = test_adj / np.maximum(np.abs(test_adj).sum(axis=1, keepdims=True), 1e-12)
        for weight_test in (0.50, 0.70, 0.80):
            trial, _, _ = selector(direct, test_transition, redundancy, eligible, weight_test)
            sensitivity_rows.append({"network_exponent": beta_test,
                                     "direct_weight": weight_test,
                                     "mean_jaccard_with_main_top3": float(np.mean([
                                         jaccard(final[j], trial[j]) for j in range(len(targets))]))})
    sensitivity = pd.DataFrame(sensitivity_rows)
    sensitivity.to_csv(AUDIT / "q2_hyperparameter_sensitivity.csv", index=False, encoding="utf-8-sig")

    # 每次 bootstrap 都重新执行相同的直接关联、网络和 mRMR 筛选。主估计量
    # 同时根据抽样后的啤酒样本重建网络，因此能够反映
    # 直接感官关联和化学边两部分的不确定性。
    # 次级估计量以给定的 2.csv 观测网络为条件。
    rng = np.random.default_rng(SEED)
    counts = np.zeros((len(targets), len(features)), dtype=np.int32)
    counts_fixed = np.zeros_like(counts)
    boot_sets = np.empty((args.bootstrap, len(targets), 3), dtype=np.int16)
    boot_sets_fixed = np.empty_like(boot_sets)
    for b in range(args.bootstrap):
        rows = rng.integers(0, len(x), len(x))
        sampled_direct, _ = spearman_xy(x[rows], y[rows])
        sampled_corr = pd.DataFrame(x[rows]).corr(method="spearman").to_numpy(float)
        sampled_corr = np.nan_to_num((sampled_corr + sampled_corr.T) / 2, nan=0.0)
        np.fill_diagonal(sampled_corr, 1.0)
        sampled_adj = np.sign(sampled_corr) * np.abs(sampled_corr) ** 10
        np.fill_diagonal(sampled_adj, 0.0)
        sampled_transition = sampled_adj / np.maximum(np.abs(sampled_adj).sum(axis=1, keepdims=True), 1e-12)
        boot, _, _ = selector(sampled_direct, sampled_transition,
                              np.abs(sampled_corr), eligible)
        boot_fixed, _, _ = selector(sampled_direct, transition, redundancy, eligible)
        boot_sets[b] = boot
        boot_sets_fixed[b] = boot_fixed
        np.add.at(counts, (np.arange(len(targets))[:, None], boot), 1)
        np.add.at(counts_fixed, (np.arange(len(targets))[:, None], boot_fixed), 1)
    np.savez_compressed(AUDIT / "q2_bootstrap_selected_indices.npz", selected_full=boot_sets,
                        selected_fixed=boot_sets_fixed,
                        feature_names=np.array(features), dimension_names=np.array(targets))

    # 使用大样本正态近似描述 Spearman 相关系数的零分布。
    # 该结果仅用于标记探索性关联，不参与 Top-3 的定义。
    zstat = np.abs(direct) * np.sqrt(np.maximum(pair_n - 1, 1))
    pvals = np.vectorize(math.erfc)(zstat / math.sqrt(2.0))
    qvals = bh_fdr(np.where(np.isfinite(pvals), pvals, 1.0)[eligible])
    qall = np.full_like(pvals, np.nan)
    qall[eligible] = qvals

    selected_rows = []
    stability_rows = []
    for j, target in enumerate(targets):
        top = final[j]
        for rank, i in enumerate(top, 1):
            row = meta.iloc[i]
            selected_rows.append({
                "dimension": target, "rank": rank, "feature": features[i],
                "chemical_name": str(row.chemical_name_short) if pd.notna(row.chemical_name_short) else str(row.chemical_name),
                "chemical_origin": str(row.origin_paper), "source_consistency": source_flag(target, row.origin_paper),
                "association_direction": "正" if direct[i, j] >= 0 else "负",
                "direct_spearman": direct[i, j], "network_score": network[i, j],
                "integrated_score": evidence[i, j], "pairwise_n": int(pair_n[i, j]),
                "spearman_p_normal_approx": pvals[i, j], "bh_fdr_q_exploratory": qall[i, j],
                "bootstrap_frequency_full_pipeline": counts[j, i] / args.bootstrap,
                "bootstrap_frequency_fixed_network": counts_fixed[j, i] / args.bootstrap,
                "threshold_median": row.threshold_median,
                "unit": str(row.unit) if pd.notna(row.unit) else "未提供",
                "off_flavors": str(row.off_flavors) if pd.notna(row.off_flavors) else "未注明",
            })
        stability_rows.append({
            "dimension": target, "top3": "; ".join(features[i] for i in top),
            "mean_selection_frequency": float(np.mean(counts[j, top] / args.bootstrap)),
            "minimum_selection_frequency": float(np.min(counts[j, top] / args.bootstrap)),
            "direct_final_jaccard": jaccard(direct_only[j], top),
            "network_final_jaccard": jaccard(network_only[j], top),
            "direct_network_jaccard": jaccard(direct_only[j], network_only[j]),
            "mean_final_bootstrap_jaccard": float(np.mean([jaccard(top, boot_sets[b, j])
                                                               for b in range(args.bootstrap)])),
            "mean_fixed_network_bootstrap_jaccard": float(np.mean([jaccard(top, boot_sets_fixed[b, j])
                                                                   for b in range(args.bootstrap)])),
        })
    top3 = pd.DataFrame(selected_rows)
    stability = pd.DataFrame(stability_rows)
    top3.to_csv(RESULTS / "q2_top3_per_dimension.csv", index=False, encoding="utf-8-sig")
    stability.to_csv(RESULTS / "q2_stability_summary.csv", index=False, encoding="utf-8-sig")

    anchors = anchor_audit(direct, final, counts, features, targets, eligible, args.bootstrap)
    anchors.to_csv(AUDIT / "q2_named_chemical_anchor_audit.csv", index=False, encoding="utf-8-sig")
    gbm = workbook_gbm_comparison(args.input_dir, "overall", final[targets.index("overall")], features)
    gbm.to_csv(AUDIT / "q2_workbook_gbm_method_comparison.csv", index=False, encoding="utf-8-sig")
    adjusted = style_adjusted_check(x, y, chem, top3, features, targets)
    adjusted.to_csv(AUDIT / "q2_style_adjusted_sensitivity.csv", index=False, encoding="utf-8-sig")
    plausibility = plausibility_review(direct, top3, meta, features, targets, eligible)
    plausibility.to_csv(AUDIT / "q2_plausibility_review.csv", index=False, encoding="utf-8-sig")

    check6 = same_source_check(args.input_dir, direct, features, targets, meta)

    old_overlap = None

    manifest = {
        "n_beers": len(chem), "n_features": len(features), "n_eligible_measured_factors": int(eligible.sum()),
        "rounded_beer_id_disagreements": rounded_beer_id_disagreements,
        "n_targets": len(targets), "n_top3_rows": len(top3), "bootstrap_replicates": args.bootstrap,
        "bootstrap_condition": "primary: resample beers and rebuild chemical graph; secondary: fixed 2.csv graph",
        "network_2_vs_1_spearman_mae": network_mae, "network_2_vs_1_spearman_max": network_max,
        "six_csv_is_same_source_not_external": check6,
        "mean_final_bootstrap_jaccard": float(stability.mean_final_bootstrap_jaccard.mean()),
        "mean_final_top3_selection_frequency": float(stability.mean_selection_frequency.mean()),
        "top3_with_bh_q_below_0_05": int((top3.bh_fdr_q_exploratory < 0.05).sum()),
        "top3_source_consistent_eligible_groups": int((top3.source_consistency == "来源相符").sum()),
        "top3_source_needs_explanation_eligible_groups": int((top3.source_consistency == "需解释").sum()),
        "named_anchor_selected_count": int(anchors.in_selected_top3.sum()),
        "named_anchor_count": len(anchors),
        "gbm_method_jaccard": gbm.set_index("method").jaccard.to_dict(),
        "style_adjusted_same_sign_fraction": float(adjusted.same_sign.mean()),
        "style_adjusted_abs_at_least_0_20_fraction": float(adjusted.absolute_adjusted_at_least_0_20.mean()),
        "mean_overlap_with_previous_top3": old_overlap,
        "hyperparameter_mean_jaccard_range": [float(sensitivity.mean_jaccard_with_main_top3.min()),
                                              float(sensitivity.mean_jaccard_with_main_top3.max())],
        "input_sha256": {name: hashlib.sha256((args.input_dir / name).read_bytes()).hexdigest()
                         for name in ("1.csv", "2.csv", "4.csv", "6.csv", "8.xlsx")},
        "seed": SEED,
    }
    (AUDIT / "q2_run_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in manifest.items() if k != "input_sha256"}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
