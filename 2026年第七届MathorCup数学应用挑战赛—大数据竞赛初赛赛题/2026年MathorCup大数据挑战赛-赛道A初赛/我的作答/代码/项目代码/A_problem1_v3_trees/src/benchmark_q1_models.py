"""Development-only model benchmark for Problem 1.

This script compares several fixed model families using only Beer 13--250 and
the same style-stratified five folds as the frozen Q1 route.  Beer 1--12 are
never read.  The benchmark includes the frozen weighted tree ensemble used in production.
The 12 holdout beers are never read.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.decomposition import PCA
from sklearn.ensemble import ExtraTreesRegressor, GradientBoostingRegressor, RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.multioutput import MultiOutputRegressor
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from solve_problem1_v3 import SEED, folds
from q1_tree_predictor import ENSEMBLE_WEIGHTS


PROJECT = Path(__file__).resolve().parents[1]
DATA = PROJECT / "data"
AUDIT = PROJECT / "audit"
AUDIT.mkdir(exist_ok=True)


def metric(y: np.ndarray, pred: np.ndarray) -> dict[str, float]:
    err = y - pred
    denom = float(np.sum((y - y.mean(axis=0, keepdims=True)) ** 2))
    return {
        "MAE": float(np.mean(np.abs(err))),
        "RMSE": float(np.sqrt(np.mean(err**2))),
        "pooled_centered_R2": float(1.0 - np.sum(err**2) / denom),
    }


def make_model(name: str):
    if name == "ridge":
        return Pipeline([
            ("impute", SimpleImputer(strategy="median", add_indicator=True, keep_empty_features=True)),
            ("scale", StandardScaler()),
            ("model", Ridge(alpha=10.0)),
        ])
    if name == "pcr":
        return Pipeline([
            ("impute", SimpleImputer(strategy="median", add_indicator=True, keep_empty_features=True)),
            ("scale", StandardScaler()),
            ("pca", PCA(n_components=50, random_state=SEED)),
            ("model", Ridge(alpha=1.0)),
        ])
    if name == "random_forest":
        return Pipeline([
            ("impute", SimpleImputer(strategy="median", add_indicator=True, keep_empty_features=True)),
            ("model", RandomForestRegressor(
                n_estimators=150, min_samples_leaf=3, max_features=0.7,
                n_jobs=4, random_state=SEED,
            )),
        ])
    if name == "extra_trees":
        return Pipeline([
            ("impute", SimpleImputer(strategy="median", add_indicator=True, keep_empty_features=True)),
            ("model", ExtraTreesRegressor(
                n_estimators=150, min_samples_leaf=3, max_features=0.7,
                n_jobs=4, random_state=SEED,
            )),
        ])
    if name == "gradient_boosting":
        base = GradientBoostingRegressor(
            n_estimators=120, learning_rate=0.05, max_depth=2,
            min_samples_leaf=5, max_features=0.7, random_state=SEED,
        )
        return Pipeline([
            ("impute", SimpleImputer(strategy="median", add_indicator=True, keep_empty_features=True)),
            ("model", MultiOutputRegressor(base, n_jobs=4)),
        ])
    raise ValueError(name)


def main() -> None:
    chem = pd.read_csv(DATA / "1.csv").set_index("beer").sort_index()
    sens = pd.read_csv(DATA / "4.csv").set_index("beer").sort_index()
    dev = np.arange(13, 251)
    feature_cols = list(chem.columns[2:])
    target_cols = list(sens.columns[2:])
    x = chem.loc[dev, feature_cols].apply(pd.to_numeric, errors="coerce").to_numpy(float)
    y = sens.loc[dev, target_cols].to_numpy(float)
    styles = chem.loc[dev, "tasting_category_fine"].astype(str).to_numpy()
    fold_list = list(folds(styles))

    names = ["mean_baseline", "ridge", "pcr", "random_forest", "extra_trees", "gradient_boosting"]
    rows = []
    oof_by_name = {}
    for name in names:
        oof = np.full_like(y, np.nan)
        for fold_no, (tr, va) in enumerate(fold_list, start=1):
            if name == "mean_baseline":
                oof[va] = y[tr].mean(axis=0)
            else:
                model = make_model(name)
                model.fit(x[tr], y[tr])
                oof[va] = np.asarray(model.predict(x[va]), float)
            print(f"{name}: fold {fold_no}/5", flush=True)
        m = metric(y, oof)
        oof_by_name[name] = oof
        rows.append({"model": name, "n_train": len(dev), "n_folds": len(fold_list), **m})

    ensemble_oof = sum(ENSEMBLE_WEIGHTS[name] * oof_by_name[name] for name in ENSEMBLE_WEIGHTS)
    rows.append({"model": "weighted_tree_ensemble", "n_train": len(dev), "n_folds": len(fold_list),
                 **metric(y, ensemble_oof), "weights": dict(ENSEMBLE_WEIGHTS)})

    out = pd.DataFrame([{k: v for k, v in row.items() if k != "weights"} for row in rows]).sort_values(["MAE", "RMSE"]).reset_index(drop=True)
    out.to_csv(AUDIT / "expanded_model_benchmark.csv", index=False, encoding="utf-8-sig")
    (AUDIT / "expanded_model_benchmark.json").write_text(
        json.dumps({
            "scope": "Beer 13--250 only; style-stratified 5-fold OOF; Beer 1--12 never read",
            "seed": SEED,
            "models": rows,
            "ranking_rule": "development OOF MAE, then RMSE",
            "production_model": "weighted_tree_ensemble",
            "ensemble_weights": dict(ENSEMBLE_WEIGHTS),
        }, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(out.to_string(index=False))


if __name__ == "__main__":
    main()
