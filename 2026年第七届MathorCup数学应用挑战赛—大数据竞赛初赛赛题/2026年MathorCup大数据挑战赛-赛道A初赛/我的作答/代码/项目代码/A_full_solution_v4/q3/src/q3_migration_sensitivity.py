"""问题三迁移敏感性分析脚本。比较不同搜索分辨率对迁移结果的影响。"""



from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pandas as pd

# 轻量本地 Python 环境提供 scikit-learn，但未提供
# openpyxl。待 NumPy
# 和 pandas 加载完成后，再加入主运行时的包目录，避免混用 NumPy 安装。
PRIMARY_SITE = Path(r"C:\Users\llxxz\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\Lib\site-packages")
if PRIMARY_SITE.exists() and str(PRIMARY_SITE) not in sys.path:
    sys.path.insert(0, str(PRIMARY_SITE))


HERE = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = Path(__file__).resolve().parents[4]
DATA = PACKAGE_ROOT / "03_原始附件"
SOLVER = HERE / "src" / "solve_q3_v4.py"
spec = importlib.util.spec_from_file_location("q3_solver", SOLVER)
assert spec and spec.loader
q3 = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = q3
spec.loader.exec_module(q3)


def main() -> None:
    chem = pd.read_csv(DATA / "1.csv").sort_values("beer").reset_index(drop=True)
    sensory = pd.read_csv(DATA / "4.csv").sort_values("beer").reset_index(drop=True)
    calibrated = pd.read_excel(DATA / "8.xlsx", sheet_name="Calibrated chemical dataset")
    threshold_table = pd.read_excel(DATA / "8.xlsx", sheet_name="Sensory thresholds")
    threshold = {str(row.field_name_R): float(row.threshold_median)
                 for _, row in threshold_table.iterrows() if pd.notna(row.threshold_median)}
    encoding = q3.physical_map(chem, calibrated, threshold)
    all_features = list(chem.columns[3:])
    base_fields = [col for col in all_features if col not in q3.DERIVED]
    sensory_fields = [col for col in q3.SENSORY_COLUMNS if col in sensory]
    styles = chem.tasting_category_fine.to_numpy(str)
    full_model = q3.fit_generator(chem[base_fields].to_numpy(float), styles)
    kcal_full = q3.fit_kcal(chem, calibrated, set(chem.beer.astype(int)))
    profile = q3.fit_sensory_predictor(chem, sensory, all_features, sensory_fields)

    src_idx = np.flatnonzero(styles == "Pils/Lager")
    src_observed = chem.loc[src_idx, all_features].reset_index(drop=True)
    src_base = src_observed[base_fields].to_numpy(float)
    src_missing = ~np.isfinite(src_base)
    style_median = np.nanmedian(chem.loc[styles == "Pils/Lager", base_fields].to_numpy(float), axis=0)
    style_median = np.where(np.isfinite(style_median), style_median, full_model["median"])
    src_base = np.where(src_missing, style_median[None, :], src_base)
    src_original = q3.rebuild_derived(pd.DataFrame(src_base, columns=base_fields), threshold, encoding, kcal_full)
    source_raw_prediction, source_scores = q3.predict_sensory(profile, src_original[all_features].to_numpy(float))
    stale_col = sensory_fields.index("stale_hops")
    src_z = full_model["score"][src_idx]
    center_src = full_model["score"][styles == "Pils/Lager"].mean(axis=0)
    center_target = full_model["score"][styles == "Tripel"].mean(axis=0)
    decoded_src = q3.decode(full_model, src_z)
    base_min, base_max = full_model["x"].min(axis=0), full_model["x"].max(axis=0)
    transport_scale = np.maximum(full_model["score"].std(axis=0), 1e-6)
    defect_indices = [base_fields.index(field) for field in q3.DEFECT_FIELDS]
    classifier_fields = list(q3.CLASSIFIER_FIELDS)
    two_styles = np.isin(styles, ("Pils/Lager", "Tripel"))
    real_x = chem.loc[two_styles, classifier_fields].to_numpy(float)
    real_y = (styles[two_styles] == "Tripel").astype(float)
    classifier = q3.fit_binary_classifier(real_x, real_y)
    before_probability = q3.predict_binary_classifier(classifier, src_original[classifier_fields].to_numpy(float))

    rows = []
    detail_rows = []
    for step in (0.05, 0.10, 0.20):
        alphas = np.round(np.arange(0.0, 1.0 + step / 2, step), 10)
        candidates = []
        for alpha in alphas:
            shifted = src_z + alpha * (center_target - center_src)
            shifted_decoded = q3.decode(full_model, shifted)
            candidate_base = np.clip(src_base + (shifted_decoded - decoded_src), base_min, base_max)
            for j in defect_indices:
                candidate_base[:, j] = np.minimum(candidate_base[:, j], src_base[:, j])
            c_frame = q3.rebuild_derived(pd.DataFrame(candidate_base, columns=base_fields), threshold, encoding, kcal_full)
            candidates.append(c_frame[all_features].to_numpy(float))
        flat = np.vstack(candidates)
        candidate_raw_pred, candidate_scores = q3.predict_sensory(profile, flat)
        accepted = []
        for i, source_row in enumerate(src_idx):
            valid = []
            for k, alpha in enumerate(alphas):
                pos = k * len(src_idx) + i
                if (candidate_raw_pred[pos, stale_col] <= source_raw_prediction[i, stale_col] + 1e-10
                        and candidate_scores[pos, stale_col] <= source_scores[i, stale_col]):
                    valid.append((pos, float(alpha)))
            source_dist = float(np.linalg.norm(src_z[i] - center_target))
            best = (source_dist, 0, 0.0)
            for pos, alpha in valid:
                emb = q3.encode(full_model, flat[pos:pos + 1, [all_features.index(c) for c in base_fields]])[0]
                distance = float(np.linalg.norm(emb - center_target))
                if distance < best[0] - 1e-10:
                    best = (distance, pos, alpha)

            # 保持生产流程中的回退逻辑不变，仅改变主网格的
            # 分辨率，用于本次审计。
            fallback_spectrum = None
            fallback_score = None
            fallback_raw = None
            stage = "primary_grid" if best[2] > 0 else "unchanged"
            if best[2] == 0.0:
                local_rng = np.random.default_rng(q3.SEED + int(chem.loc[source_row, "beer"]))
                trial_alpha = np.repeat(np.linspace(0.1, 1.0, 10), 40)
                trial_z = (src_z[i][None, :] + trial_alpha[:, None] * (center_target - center_src)[None, :]
                           + local_rng.normal(0.0, 0.15 * transport_scale, size=(400, len(center_target))))
                trial_decoded = q3.decode(full_model, trial_z)
                trial_base = np.clip(src_base[i][None, :] + (trial_decoded - decoded_src[i][None, :]), base_min, base_max)
                for j in defect_indices:
                    trial_base[:, j] = np.minimum(trial_base[:, j], src_base[i, j])
                trial_frame = q3.rebuild_derived(pd.DataFrame(trial_base, columns=base_fields), threshold, encoding, kcal_full)
                trial_flat = trial_frame[all_features].to_numpy(float)
                trial_raw, trial_grade = q3.predict_sensory(profile, trial_flat)
                admissible = ((trial_raw[:, stale_col] <= source_raw_prediction[i, stale_col] + 1e-10)
                              & (trial_grade[:, stale_col] <= source_scores[i, stale_col]))
                if np.any(admissible):
                    trial_emb = q3.encode(full_model, trial_base[admissible])
                    trial_dist = np.linalg.norm(trial_emb - center_target, axis=1)
                    candidates_ok = np.flatnonzero(admissible)
                    k_min = int(np.argmin(trial_dist))
                    if trial_dist[k_min] < source_dist - 1e-10:
                        k = int(candidates_ok[k_min])
                        best = (float(trial_dist[k_min]), -1, float(trial_alpha[k]))
                        fallback_spectrum, fallback_score, fallback_raw = trial_flat[k], trial_grade[k], trial_raw[k]
                        stage = "fixed_400_candidate_fallback"

            if fallback_spectrum is not None:
                new_spectrum, new_score, new_raw = fallback_spectrum, fallback_score, fallback_raw
            elif best[2] == 0.0:
                new_spectrum = src_original.loc[i, all_features].to_numpy(float)
                new_score, new_raw = source_scores[i], source_raw_prediction[i]
            else:
                new_spectrum = flat[best[1]]
                new_score, new_raw = candidate_scores[best[1]], candidate_raw_pred[best[1]]
            accepted.append(new_spectrum)
            detail_rows.append({"grid_step": step, "source_beer": int(chem.loc[source_row, "beer"]),
                                "shift_alpha": float(best[2]), "search_stage": stage,
                                "distance_before": source_dist, "distance_after": float(best[0]),
                                "stale_hops_before": float(source_raw_prediction[i, stale_col]),
                                "stale_hops_after": float(new_raw[stale_col])})

        migrated = pd.DataFrame(np.asarray(accepted), columns=all_features)
        after_probability = q3.predict_binary_classifier(classifier, migrated[classifier_fields].to_numpy(float))
        detail = pd.DataFrame([r for r in detail_rows if r["grid_step"] == step])
        rows.append({"grid_step": step, "n_sources": len(src_idx),
                     "mean_distance_before": float(detail.distance_before.mean()),
                     "mean_distance_after": float(detail.distance_after.mean()),
                     "mean_distance_reduction_pct": float(100 * (detail.distance_before.mean() - detail.distance_after.mean()) / detail.distance_before.mean()),
                     "strictly_improved_count": int((detail.distance_after < detail.distance_before - 1e-10).sum()),
                     "unchanged_count": int((detail.distance_after >= detail.distance_before - 1e-10).sum()),
                     "mean_selected_alpha": float(detail.shift_alpha.mean()),
                     "classifier_mean_before": float(before_probability.mean()),
                     "classifier_mean_after": float(after_probability.mean()),
                     "classifier_increased_count": int((after_probability > before_probability + 1e-12).sum()),
                     "stale_hops_continuous_nonincrease": float((detail.stale_hops_after <= detail.stale_hops_before + 1e-10).mean())})

    out = HERE / "results" / "q3_migration_sensitivity.csv"
    pd.DataFrame(rows).to_csv(out, index=False, encoding="utf-8-sig")
    pd.DataFrame(detail_rows).to_csv(HERE / "audit" / "q3_migration_sensitivity_by_beer.csv", index=False, encoding="utf-8-sig")
    print(pd.DataFrame(rows).to_string(index=False))
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
