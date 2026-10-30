"""共享的问题一树模型预测器实现。"""



from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.ensemble import ExtraTreesRegressor, GradientBoostingRegressor, RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.multioutput import MultiOutputRegressor


SEED = 20261024
FIXED_TRAIN_IDS = tuple(range(13, 251))
ENSEMBLE_WEIGHTS = {"extra_trees": 0.38, "random_forest": 0.17, "gradient_boosting": 0.45}


def _make_model(name: str):
    if name == "extra_trees":
        return ExtraTreesRegressor(n_estimators=150, min_samples_leaf=3, max_features=0.7,
                                   bootstrap=False, n_jobs=4, random_state=SEED)
    if name == "random_forest":
        return RandomForestRegressor(n_estimators=150, min_samples_leaf=3, max_features=0.7,
                                     bootstrap=True, n_jobs=4, random_state=SEED)
    if name == "gradient_boosting":
        return MultiOutputRegressor(GradientBoostingRegressor(
            n_estimators=120, learning_rate=0.05, max_depth=2,
            min_samples_leaf=5, max_features=0.7, random_state=SEED), n_jobs=4)
    raise ValueError(name)


@dataclass
class PanelPredictor:
    feature_cols: list[str]
    target_cols: list[str]
    imputer: SimpleImputer
    models: dict[str, object]
    weights: dict[str, float]
    grade_q01: np.ndarray
    grade_q99: np.ndarray
    train_ids: tuple[int, ...]

    def predict_components(self, chemistry: pd.DataFrame) -> dict[str, np.ndarray]:
        missing = set(self.feature_cols) - set(chemistry.columns)
        if missing:
            raise ValueError(f"Missing model inputs: {sorted(missing)[:5]}")
        x = chemistry.loc[:, self.feature_cols].apply(pd.to_numeric, errors="coerce")
        xp = self.imputer.transform(x.to_numpy())
        return {name: np.asarray(model.predict(xp), float) for name, model in self.models.items()}

    def predict_continuous(self, chemistry: pd.DataFrame) -> pd.DataFrame:
        components = self.predict_components(chemistry)
        pred = sum(self.weights[name] * components[name] for name in self.models)
        return pd.DataFrame(pred, index=chemistry.index, columns=self.target_cols)

    def predict_proxy_grades(self, chemistry: pd.DataFrame) -> pd.DataFrame:
        raw = self.predict_continuous(chemistry)
        span = np.maximum(self.grade_q99 - self.grade_q01, 1e-12)
        grades = np.rint(np.clip(6 * (raw.to_numpy() - self.grade_q01) / span, 0, 6)).astype(int)
        return pd.DataFrame(grades, index=chemistry.index, columns=self.target_cols)

    def proxy_grades_from_reference(self, sensory: pd.DataFrame) -> pd.DataFrame:
        y = sensory.loc[:, self.target_cols].to_numpy(float)
        span = np.maximum(self.grade_q99 - self.grade_q01, 1e-12)
        grades = np.rint(np.clip(6 * (y - self.grade_q01) / span, 0, 6)).astype(int)
        return pd.DataFrame(grades, index=sensory.index, columns=self.target_cols)


def fit_fixed_panel_predictor(chem: pd.DataFrame, sensory: pd.DataFrame,
                              train_ids: tuple[int, ...] = FIXED_TRAIN_IDS) -> PanelPredictor:
    if not chem.index.is_unique or not sensory.index.is_unique:
        raise ValueError("Beer indices must be unique")
    if tuple(sorted(train_ids)) != FIXED_TRAIN_IDS:
        raise ValueError("Only the frozen 238-beer training set is permitted")
    feature_cols = list(chem.columns[2:])
    target_cols = list(sensory.columns[2:])
    if len(feature_cols) != 231 or len(target_cols) != 50:
        raise ValueError((len(feature_cols), len(target_cols)))
    if set(train_ids) - set(chem.index) or set(train_ids) - set(sensory.index):
        raise ValueError("Some training Beer IDs are missing")
    x = chem.loc[list(train_ids), feature_cols].apply(pd.to_numeric, errors="coerce").to_numpy()
    y = sensory.loc[list(train_ids), target_cols].to_numpy(float)
    if not np.isfinite(y).all():
        raise ValueError("Training sensory targets must be complete")
    imputer = SimpleImputer(strategy="median", add_indicator=True, keep_empty_features=True)
    xp = imputer.fit_transform(x)
    models = {}
    for name in ENSEMBLE_WEIGHTS:
        model = _make_model(name)
        model.fit(xp, y)
        models[name] = model
    return PanelPredictor(feature_cols, target_cols, imputer, models,
                          dict(ENSEMBLE_WEIGHTS), np.quantile(y, .01, axis=0),
                          np.quantile(y, .99, axis=0), train_ids)
