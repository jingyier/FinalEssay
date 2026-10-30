"""计算问题三迁移前后样本分布的分类器两样本检验指标。"""



from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, roc_auc_score
from sklearn.model_selection import StratifiedKFold

from solve_q3_v4 import DERIVED, fit_generator, encode, SEED


HERE = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = HERE.parents[2]
DATA = PACKAGE_ROOT / "03_原始附件"
RESULTS = HERE / "results"
AUDIT = HERE / "audit"


def main() -> None:
    chem = pd.read_csv(DATA / "1.csv").sort_values("beer").reset_index(drop=True)
    generated = pd.read_csv(RESULTS / "q3_generated_spectra.csv")
    all_features = list(chem.columns[3:])
    base_fields = [c for c in all_features if c not in DERIVED]
    model = fit_generator(chem[base_fields].to_numpy(float), chem["tasting_category_fine"].to_numpy(str))
    real_z = encode(model, chem[base_fields].to_numpy(float))
    gen_z = encode(model, generated[base_fields].to_numpy(float))
    rng = np.random.default_rng(SEED)
    gen_idx = rng.choice(len(gen_z), size=len(real_z), replace=False)
    x = np.vstack([real_z, gen_z[gen_idx]])
    y = np.r_[np.zeros(len(real_z), dtype=int), np.ones(len(real_z), dtype=int)]
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=SEED)
    aucs, accs = [], []
    for train, test in cv.split(x, y):
        clf = LogisticRegression(C=1.0, max_iter=2000, random_state=SEED)
        clf.fit(x[train], y[train])
        prob = clf.predict_proba(x[test])[:, 1]
        aucs.append(roc_auc_score(y[test], prob))
        accs.append(accuracy_score(y[test], prob >= 0.5))
    out = {
        "real_n": int(len(real_z)),
        "generated_n": int(len(gen_idx)),
        "latent_dimensions": int(real_z.shape[1]),
        "c2st_auc_mean": float(np.mean(aucs)),
        "c2st_auc_sd": float(np.std(aucs, ddof=1)),
        "c2st_accuracy_mean": float(np.mean(accs)),
        "fold_auc": [float(v) for v in aucs],
        "fold_accuracy": [float(v) for v in accs],
        "interpretation": "Internal two-sample diagnostic; AUC near 0.5 means the classifier cannot easily distinguish observed and generated spectra in this representation.",
    }
    (AUDIT / "q3_c2st_global.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    pd.DataFrame({"fold": np.arange(1, 6), "auc": aucs, "accuracy": accs}).to_csv(
        AUDIT / "q3_c2st_global.csv", index=False, encoding="utf-8-sig")
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
