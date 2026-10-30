"""问题一 v3 方案：使用冻结权重的树模型集成生成连续预测和评分卡。"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import ExtraTreesRegressor, GradientBoostingRegressor, RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.multioutput import MultiOutputRegressor

from q1_tree_predictor import ENSEMBLE_WEIGHTS, SEED, fit_fixed_panel_predictor


PROJECT = Path(__file__).resolve().parents[1]
DATA = PROJECT / "data"
OUT = PROJECT / "results"
AUDIT = PROJECT / "audit"
OUT.mkdir(exist_ok=True)
AUDIT.mkdir(exist_ok=True)
RENAMES = {"X4vg": "4vg", "A_esters_fruity": "A_ester_fruity", "F_esters_fruity": "F_ester_fruity"}


def folds(styles: np.ndarray):
    rng = np.random.default_rng(SEED)
    bins = [[] for _ in range(5)]
    for style in pd.unique(styles):
        ids = np.flatnonzero(styles == style)
        rng.shuffle(ids)
        for j, idx in enumerate(ids):
            bins[j % 5].append(int(idx))
    for val in bins:
        va = np.array(sorted(val), dtype=int)
        mask = np.ones(len(styles), dtype=bool)
        mask[va] = False
        yield np.flatnonzero(mask), va


def estimator(name: str):
    if name == "extra_trees":
        return ExtraTreesRegressor(n_estimators=150, min_samples_leaf=3,
                                   max_features=0.7, bootstrap=False, n_jobs=4, random_state=SEED)
    if name == "random_forest":
        return RandomForestRegressor(n_estimators=150, min_samples_leaf=3,
                                     max_features=0.7, bootstrap=True, n_jobs=4, random_state=SEED)
    if name == "gradient_boosting":
        return MultiOutputRegressor(GradientBoostingRegressor(
            n_estimators=120, learning_rate=0.05, max_depth=2,
            min_samples_leaf=5, max_features=0.7, random_state=SEED), n_jobs=4)
    raise ValueError(name)


def fit_predict(name: str, xtr: np.ndarray, ytr: np.ndarray, xva: np.ndarray):
    imputer = SimpleImputer(strategy="median", add_indicator=True, keep_empty_features=True)
    train = imputer.fit_transform(xtr)
    valid = imputer.transform(xva)
    model = estimator(name)
    model.fit(train, ytr)
    return np.asarray(model.predict(valid), float)


def metrics(y: np.ndarray, p: np.ndarray):
    err = y - p
    denom = float(np.sum((y - y.mean(axis=0, keepdims=True)) ** 2))
    return {"MAE": float(np.mean(np.abs(err))),
            "RMSE": float(np.sqrt(np.mean(err**2))),
            "pooled_centered_R2": float(1 - np.sum(err**2) / denom)}


def grade(values: np.ndarray, lo: np.ndarray, hi: np.ndarray):
    return np.rint(np.clip(6 * (values - lo) / np.maximum(hi - lo, 1e-12), 0, 6)).astype(int)


def grade_metrics(actual: np.ndarray, predicted: np.ndarray, lo: np.ndarray, hi: np.ndarray):
    truth = grade(actual, lo, hi)
    g = grade(predicted, lo, hi)
    unique, counts = np.unique(g, return_counts=True)
    return {"exact": float(np.mean(g == truth)),
            "within1": float(np.mean(np.abs(g - truth) <= 1)),
            "histogram": {str(int(v)): int(c) for v, c in zip(unique, counts)}}


def rank_corr(a: np.ndarray, b: np.ndarray):
    ra, rb = pd.Series(a).rank().to_numpy(), pd.Series(b).rank().to_numpy()
    return float(np.corrcoef(ra, rb)[0, 1]) if np.std(ra) > 0 and np.std(rb) > 0 else float("nan")


def main():
    chem = pd.read_csv(DATA / "1.csv").set_index("beer").sort_index()
    sens = pd.read_csv(DATA / "4.csv").set_index("beer").sort_index()
    assert list(chem.index) == list(sens.index) == list(range(1, 251))
    feature_cols = list(chem.columns[2:])
    target_cols = list(sens.columns[2:])
    assert len(feature_cols) == 231 and len(target_cols) == 50
    dev, hold = np.arange(13, 251), np.arange(1, 13)
    xdev = chem.loc[dev, feature_cols].apply(pd.to_numeric, errors="coerce").to_numpy()
    xhold = chem.loc[hold, feature_cols].apply(pd.to_numeric, errors="coerce").to_numpy()
    ydev = sens.loc[dev, target_cols].to_numpy(float)
    yhold = sens.loc[hold, target_cols].to_numpy(float)
    styles = chem.loc[dev, "tasting_category_fine"].astype(str).to_numpy()
    fold_list = list(folds(styles))
    fold_summary = [{"fold": j + 1, "train": int(len(tr)), "valid": int(len(va)),
                     "styles": int(len(np.unique(styles[va])))} for j, (tr, va) in enumerate(fold_list)]

    baseline_oof = np.full_like(ydev, np.nan)
    for tr, va in fold_list:
        baseline_oof[va] = ydev[tr].mean(axis=0)
    baseline_hold = np.repeat(ydev.mean(axis=0, keepdims=True), len(hold), axis=0)
    comparison = {"mean_baseline": {"dev_oof": metrics(ydev, baseline_oof),
                                    "holdout_posthoc": metrics(yhold, baseline_hold)}}
    model_oof = {}
    for name in ("extra_trees", "random_forest", "gradient_boosting"):
        oof = np.full_like(ydev, np.nan)
        for fold_no, (tr, va) in enumerate(fold_list, start=1):
            print(f"{name}: fold {fold_no}/5", flush=True)
            oof[va] = fit_predict(name, xdev[tr], ydev[tr], xdev[va])
        assert np.isfinite(oof).all()
        model_oof[name] = oof
        pd.DataFrame(oof, index=dev, columns=target_cols).rename_axis("beer").to_csv(
            AUDIT / f"{name}_oof.csv", encoding="utf-8-sig")
        comparison[name] = {"dev_oof": metrics(ydev, oof)}

    # 生产模型采用固定权重集成；权重由
    # 嵌套开发折 OOF 选择得到，并在冻结前完成舍入。
    selected = "weighted_tree_ensemble"
    ensemble_oof = sum(ENSEMBLE_WEIGHTS[name] * model_oof[name] for name in ENSEMBLE_WEIGHTS)
    model_oof[selected] = ensemble_oof
    comparison[selected] = {"dev_oof": metrics(ydev, ensemble_oof),
                            "weights": dict(ENSEMBLE_WEIGHTS),
                            "selection_note": "Nested OOF mean weights; Beer 1--12 never used."}
    predictor = fit_fixed_panel_predictor(chem, sens)
    pred = predictor.predict_continuous(chem.loc[hold]).to_numpy(float)
    oof = model_oof[selected]
    # 对生产集成所使用的 ExtraTrees 分量进行交叉核对。
    # 对外预测器会平均三个冻结分量，因此不应
    # 与仅使用 ExtraTrees 的预测逐位相同。
    predicted_et = fit_predict("extra_trees", xdev, ydev, xhold)
    component = predictor.predict_components(chem.loc[hold])["extra_trees"]
    assert np.max(np.abs(component - predicted_et)) < 1e-12

    lo, hi = np.quantile(ydev, [.01, .99], axis=0)
    mu_y, sd_y = ydev.mean(axis=0), ydev.std(axis=0)
    mu_o, sd_o = oof.mean(axis=0), oof.std(axis=0)
    scale = sd_y / np.maximum(sd_o, 1e-12)
    oof_cal = mu_y + (oof - mu_o) * scale
    pred_cal = mu_y + (pred - mu_o) * scale
    cal_dev = {"direct_training_anchors": grade_metrics(ydev, oof, lo, hi),
               "oof_variance_matched": grade_metrics(ydev, oof_cal, lo, hi)}
    selected_cal = max(cal_dev, key=lambda name: (cal_dev[name]["exact"], cal_dev[name]["within1"]))
    if selected_cal != "direct_training_anchors":
        raise RuntimeError(f"Frozen project expects direct anchoring; selected {selected_cal}")
    cal_hold = {"direct_training_anchors": grade_metrics(yhold, pred, lo, hi),
                "oof_variance_matched": grade_metrics(yhold, pred_cal, lo, hi)}
    (AUDIT / "calibration_comparison.json").write_text(json.dumps({
        "selection_rule": "maximize dev OOF exact proxy-grade agreement; then within-one agreement",
        "selected": selected_cal,
        "dev_oof": cal_dev,
        "holdout_posthoc": cal_hold,
        "variance_match_scale_min_mean_max": [float(scale.min()), float(scale.mean()), float(scale.max())],
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    grades = predictor.predict_proxy_grades(chem.loc[hold]).to_numpy(int)
    assert np.array_equal(grades, grade(pred, lo, hi))
    acet = pd.read_csv(AUDIT / "acetaldehyde_calibration.csv").set_index("beer").loc[hold, "acetaldehyde"].to_numpy(float)
    acet_score = np.rint(np.clip(6 * np.log10(np.maximum(acet, 1e-12) / 10), 0, 6)).astype(int)
    acet_50 = np.rint(np.clip(6 * np.log10(np.maximum(acet, 1e-12) / 50), 0, 6)).astype(int)
    pd.DataFrame({"beer": hold, "acetaldehyde_mg_L": acet,
                  "score_threshold_10": acet_score, "score_threshold_50": acet_50}).to_csv(
        AUDIT / "acetaldehyde_sensitivity.csv", index=False, encoding="utf-8-sig")
    score50 = pd.DataFrame(grades, index=hold, columns=target_cols).rename(columns=RENAMES)
    score52 = score50.copy()
    score52["A_acetaldehyde"] = acet_score
    score52["F_acetaldehyde"] = acet_score
    score50.rename_axis("Beer").to_csv(OUT / "A_problem1_v3_scores_50.csv", encoding="utf-8-sig")
    score52.rename_axis("Beer").to_csv(OUT / "A_problem1_v3_scores_52.csv", encoding="utf-8-sig")
    pd.DataFrame(pred, index=hold, columns=target_cols).rename(columns=RENAMES).rename_axis("Beer").to_csv(
        OUT / "A_problem1_v3_continuous_predictions.csv", encoding="utf-8-sig")
    comparison[selected]["holdout_posthoc"] = metrics(yhold, pred)
    # 另一个候选模型的留出结果仅用于补全本次审计；
    # 不参与上面的模型选择。
    for name in ("extra_trees", "random_forest", "gradient_boosting"):
        comparison[name]["holdout_posthoc"] = metrics(
            yhold, fit_predict(name, xdev, ydev, xhold))
    (AUDIT / "model_comparison.json").write_text(json.dumps({
        "selection_rule": "nested development OOF ensemble weights; MAE and pooled R2 reported; never Beer 1--12",
        "selected": selected,
        "folds": fold_summary,
        "models": comparison,
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    gtruth = grade(yhold, lo, hi)
    per_beer = []
    for row, beer in enumerate(hold):
        per_beer.append({"beer": int(beer), "style": str(chem.loc[beer, "tasting_category_fine"]),
                         "continuous_mae": float(np.mean(np.abs(yhold[row] - pred[row]))),
                         "proxy_grade_exact_rate": float(np.mean(grades[row] == gtruth[row])),
                         "proxy_grade_within1_rate": float(np.mean(np.abs(grades[row] - gtruth[row]) <= 1))})
    pd.DataFrame(per_beer).to_csv(AUDIT / "q1_holdout_by_beer.csv", index=False, encoding="utf-8-sig")
    per_dim = []
    for j, dim in enumerate(target_cols):
        denom = float(np.sum((yhold[:, j] - yhold[:, j].mean()) ** 2))
        per_dim.append({"dimension": RENAMES.get(dim, dim), "n_holdout": 12,
                        "r2": float(1 - np.sum((yhold[:, j] - pred[:, j]) ** 2) / denom) if denom else float("nan"),
                        "spearman": rank_corr(yhold[:, j], pred[:, j]),
                        "continuous_mae": float(np.mean(np.abs(yhold[:, j] - pred[:, j]))),
                        "proxy_grade_exact_rate": float(np.mean(grades[:, j] == gtruth[:, j])),
                        "proxy_grade_within1_rate": float(np.mean(np.abs(grades[:, j] - gtruth[:, j]) <= 1))})
    dim_df = pd.DataFrame(per_dim)
    dim_df.to_csv(AUDIT / "q1_holdout_by_dimension.csv", index=False, encoding="utf-8-sig")
    summary = {
        "holdout_beers": 12, "dimensions_with_continuous_labels": 50, "scorecard_positions": 52,
        "continuous_mae": metrics(yhold, pred)["MAE"],
        "pooled_within_dimension_r2": metrics(yhold, pred)["pooled_centered_R2"],
        "median_dimension_r2": float(np.nanmedian(dim_df.r2)),
        "median_dimension_spearman": float(np.nanmedian(dim_df.spearman)),
        "n_positive_dimension_r2": int((dim_df.r2 > 0).sum()),
        "proxy_grade_exact_rate": float(np.mean(grades == gtruth)),
        "proxy_grade_within1_rate": float(np.mean(np.abs(grades - gtruth) <= 1)),
        "proxy_grade_warning": "Based on standardized 4.csv and 238-train-only anchors, not observed raw 0--6 panel grades.",
        "audit_status": "Beer 1--12 labels were viewed before this model revision; post-hoc out-of-fit evaluation, not pristine external testing.",
    }
    (AUDIT / "q1_holdout_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"selected_model": selected, "selected_calibration": selected_cal,
                      "holdout": summary}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
