"""Independent, reproducible audit and solution for MathorCup A, Question 3.

The four OAV aggregates are reconstructed from calibrated concentrations and
the thresholds in 8.xlsx.  The fifth derived field, kcalperc, is estimated
from its four physical inputs using training-only least squares.  The
conditional generator acts on the remaining 226 base fields in a Gaussian
rank/PCA space.  All reported validation metrics are computed by this script.
"""

from __future__ import annotations

import json
import math
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd


HERE = Path(__file__).resolve().parents[1]
OUTPUTS = HERE.parents[1]
PACKAGE_ROOT = Path(__file__).resolve().parents[4]
DATA = Path(os.environ.get("MATHOR_INPUT_DIR", str(PACKAGE_ROOT / "03_原始附件")))
for name in ("results", "audit", "report"):
    (HERE / name).mkdir(parents=True, exist_ok=True)

SHARED = OUTPUTS / "A_full_solution_v4" / "shared"
sys.path.insert(0, str(SHARED))
from q1_tree_predictor import PanelPredictor, fit_fixed_panel_predictor  # noqa: E402
from q3_compat import SENSORY_COLUMNS, normal_cdf, normal_ppf  # noqa: E402

SEED = 20261025
GENERATE_N = 50
TARGET_STYLES = ("Tripel", "Kriek", "Lambic")
DERIVED = ("kcalperc", "esters_sum", "aroma_hops_sum", "acids_sum", "sulfur_sum")
OAV_GROUPS = {
    "esters_sum": ("ethyl_isovalerate", "ethyl_acetate", "ethyl_decanoate", "ethyl_hexanoate",
                   "ethyl_octanoate", "ethyl_propionate", "isopentyl_acetate", "phenethyl_acetate"),
    "aroma_hops_sum": ("alpha.humulene", "X1.alpha.terpineol", "E.caryophyllene",
                       "citronellol", "geraniol", "linalool"),
    "acids_sum": ("acetic_acid.g.L.", "lactic_acid.mg.L."),
    "sulfur_sum": ("CS2", "DES", "DMS", "H2S", "SO2.mg.L."),
}
KCAL_INPUTS = ("ethanol..v.v.", "GFS", "unfermentables", "protein.g.L.")
DEFECT_FIELDS = ("DMS", "X2.3.butanedione", "X4VG", "X.E..2.nonenal")
CLASSIFIER_FIELDS = ("ethanol..v.v.", "bitterness", "color.EBC.", "acetic_acid.g.L.",
                     "lactic_acid.mg.L.", "isoamyl_alcohol", "esters_sum", "GFS")


def physical_map(x: pd.DataFrame, calibrated: pd.DataFrame, thresholds: dict[str, float]) -> dict:
    """Identify raw versus log10 columns by matching the same beers in 8.xlsx."""
    mapping = {}
    xa = x.set_index("beer").sort_index()
    ca = calibrated.set_index("beer").sort_index()
    for col in set(thresholds) | set(KCAL_INPUTS):
        if col not in xa or col not in ca:
            continue
        a, b = xa[col].to_numpy(float), ca[col].to_numpy(float)
        valid = np.isfinite(a) & np.isfinite(b) & (b > 0)
        if valid.sum() < 10:
            continue
        raw_err = float(np.median(np.abs(a[valid] - b[valid])))
        log_err = float(np.median(np.abs(a[valid] - np.log10(b[valid]))))
        is_log = log_err < raw_err
        zero_encoded = None
        if is_log and np.any(b == 0):
            zero_encoded = float(np.median(a[b == 0]))
        mapping[col] = {"encoding": "log10" if is_log else "raw", "zero_encoded": zero_encoded,
                        "raw_error": raw_err, "log_error": log_err}
    return mapping


def to_physical(a: np.ndarray, info: dict) -> np.ndarray:
    arr = np.asarray(a, float)
    if info["encoding"] == "raw":
        return np.maximum(arr, 0.0)
    raw = np.power(10.0, arr)
    floor = info["zero_encoded"]
    if floor is not None:
        raw = np.where(np.isclose(arr, floor, rtol=0, atol=1e-9), 0.0, raw)
    return raw


def fit_kcal(x: pd.DataFrame, calibrated: pd.DataFrame, train_beers: set[int]) -> np.ndarray:
    c = calibrated.set_index("beer")
    x_by_beer = x.set_index("beer")
    beers = sorted(train_beers & set(c.index) & set(x_by_beer.index))
    inputs = np.column_stack([np.ones(len(beers))] + [c.loc[beers, col].to_numpy(float) for col in KCAL_INPUTS])
    kcal = np.power(10.0, x_by_beer.loc[beers, "kcalperc"].to_numpy(float))
    valid = np.isfinite(inputs).all(axis=1) & np.isfinite(kcal)
    return np.linalg.lstsq(inputs[valid], kcal[valid], rcond=None)[0]


def rebuild_derived(frame: pd.DataFrame, threshold: dict[str, float],
                    encoding: dict, kcal_coef: np.ndarray) -> pd.DataFrame:
    out = frame.copy()
    for field, members in OAV_GROUPS.items():
        oav = np.zeros(len(out), float)
        for chemical in members:
            oav += to_physical(out[chemical].to_numpy(float), encoding[chemical]) / threshold[chemical]
        out[field] = np.log10(np.maximum(oav, 1e-12))
    physical_kcal = np.column_stack([np.ones(len(out))] + [
        to_physical(out[col].to_numpy(float), encoding[col]) for col in KCAL_INPUTS
    ]) @ kcal_coef
    out["kcalperc"] = np.log10(np.maximum(physical_kcal, 1e-6))
    return out


def normal_scores(a: np.ndarray) -> np.ndarray:
    ranked = pd.DataFrame(a).rank(axis=0, method="average").to_numpy(float)
    return normal_ppf((ranked - 0.5) / len(a))


def fit_generator(x: np.ndarray, styles: np.ndarray) -> dict:
    x = np.asarray(x, float)
    med = np.nanmedian(x, axis=0)
    x = np.where(np.isfinite(x), x, med[None, :])
    latent = normal_scores(x)
    center = latent.mean(axis=0)
    u, s, vt = np.linalg.svd(latent - center, full_matrices=False)
    var = s ** 2 / max(len(x) - 1, 1)
    cumulative = np.cumsum(var) / np.sum(var)
    d90 = int(np.searchsorted(cumulative, 0.90) + 1)
    d = d90  # no cap below the claimed 90% threshold
    score = (latent - center) @ vt[:d].T
    return {"x": x, "median": med, "styles": np.asarray(styles), "center": center,
            "vt": vt[:d], "score": score, "d": d, "variance_retained": float(cumulative[d - 1]),
            "feature_count": x.shape[1]}


def encode(model: dict, x: np.ndarray) -> np.ndarray:
    x = np.asarray(x, float)
    reference = model["x"]
    result = np.empty_like(x)
    for j in range(x.shape[1]):
        vals = np.sort(reference[:, j])
        left = np.searchsorted(vals, x[:, j], side="left")
        right = np.searchsorted(vals, x[:, j], side="right")
        rank = (left + right + 1.0) / 2.0
        result[:, j] = normal_ppf(np.clip((rank - 0.5) / len(vals), 0.5 / len(vals), 1 - 0.5 / len(vals)))
    return (result - model["center"]) @ model["vt"].T


def decode(model: dict, scores: np.ndarray) -> np.ndarray:
    latent = np.asarray(scores, float) @ model["vt"] + model["center"]
    percentiles = normal_cdf(latent)
    base = model["x"]
    out = np.empty_like(latent)
    for j in range(base.shape[1]):
        vals = np.sort(base[:, j])
        out[:, j] = np.interp(percentiles[:, j] * (len(vals) - 1), np.arange(len(vals)), vals)
    return out


def draw_conditional(model: dict, style: str, count: int, rng: np.random.Generator,
                     global_share: float = 0.55) -> np.ndarray:
    pool = model["score"][model["styles"] == style]
    if len(pool) < 2:
        raise ValueError(f"style {style} has fewer than two examples")
    mu = pool.mean(axis=0)
    ids_a = rng.integers(0, len(pool), size=count)
    ids_b = rng.integers(0, len(pool), size=count)
    # Prevent exact self-mixes while retaining stochastic interpolation.
    ids_b = np.where(ids_b == ids_a, (ids_b + 1) % len(pool), ids_b)
    weight = rng.uniform(0.15, 0.85, size=(count, 1))
    expected_mix_variance = 0.5 + 2 * (0.7 ** 2 / 12)
    scale = 1 / math.sqrt(expected_mix_variance)
    pooled_sd = np.maximum(model["score"].std(axis=0), 1e-6)
    local = scale * (weight * (pool[ids_a] - mu) + (1 - weight) * (pool[ids_b] - mu))
    latent = mu + math.sqrt(1 - global_share ** 2) * local
    latent += rng.normal(0, global_share * pooled_sd, size=latent.shape)
    return decode(model, latent)


def centroid_labels(model: dict, test: np.ndarray) -> np.ndarray:
    labels = np.unique(model["styles"])
    centers = np.vstack([model["score"][model["styles"] == s].mean(axis=0) for s in labels])
    embedded = encode(model, test)
    distance = np.sum((embedded[:, None, :] - centers[None, :, :]) ** 2, axis=2)
    return labels[np.argmin(distance, axis=1)]


def mse_standardized(a: np.ndarray, b: np.ndarray, scale: np.ndarray) -> float:
    return float(np.sqrt(np.mean(((a.mean(axis=0) - b.mean(axis=0)) / np.maximum(scale, 1e-8)) ** 2)))


def nearest_distance(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    dist2 = np.sum((a[:, None, :] - b[None, :, :]) ** 2, axis=2)
    return np.sqrt(np.min(dist2, axis=1))


def fit_binary_classifier(x: np.ndarray, y: np.ndarray, ridge: float = 0.20) -> dict:
    """Small ridge logistic model, separate from the generative PCA space."""
    x = np.asarray(x, float)
    y = np.asarray(y, float)
    med = np.nanmedian(x, axis=0)
    x = np.where(np.isfinite(x), x, med[None, :])
    mean = x.mean(axis=0)
    sd = np.maximum(x.std(axis=0), 1e-6)
    z = np.column_stack([np.ones(len(x)), (x - mean) / sd])
    coef = np.zeros(z.shape[1])
    penalty = np.diag(np.r_[0.0, np.repeat(ridge, z.shape[1] - 1)])
    for _ in range(80):
        logit = np.clip(z @ coef, -30, 30)
        prob = 1 / (1 + np.exp(-logit))
        grad = z.T @ (prob - y) / len(y) + penalty @ coef
        hess = z.T @ (z * (prob * (1 - prob))[:, None]) / len(y) + penalty
        step = np.linalg.solve(hess + np.eye(len(coef)) * 1e-9, grad)
        coef -= step
        if np.linalg.norm(step) < 1e-8:
            break
    return {"median": med, "mean": mean, "sd": sd, "coef": coef}


def predict_binary_classifier(model: dict, x: np.ndarray) -> np.ndarray:
    a = np.asarray(x, float)
    a = np.where(np.isfinite(a), a, model["median"][None, :])
    z = np.column_stack([np.ones(len(a)), (a - model["mean"]) / model["sd"]])
    return 1 / (1 + np.exp(-np.clip(z @ model["coef"], -30, 30)))


def fit_sensory_predictor(chem: pd.DataFrame, sensory: pd.DataFrame,
                          feature_cols: list[str], target_cols: list[str]) -> PanelPredictor:
    """Use the exact Q1 scorer, fitted on the frozen 238-beer development set."""
    profile = fit_fixed_panel_predictor(chem.set_index("beer"), sensory.set_index("beer"))
    assert profile.feature_cols == feature_cols
    assert profile.target_cols == target_cols
    development = sensory.set_index("beer").loc[list(profile.train_ids), target_cols].to_numpy(float)
    profile.development_target_sd = np.maximum(development.std(axis=0, ddof=0), 1e-8)
    return profile


def predict_sensory(profile: PanelPredictor, x: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    new = pd.DataFrame(np.asarray(x, float), columns=profile.feature_cols)
    raw = profile.predict_continuous(new).to_numpy(float)
    score = profile.predict_proxy_grades(new).to_numpy(int)
    return raw, score


def main() -> None:
    rng = np.random.default_rng(SEED)
    chem = pd.read_csv(DATA / "1.csv").sort_values("beer").reset_index(drop=True)
    sensory = pd.read_csv(DATA / "4.csv").sort_values("beer").reset_index(drop=True)
    assert chem.beer.tolist() == sensory.beer.tolist(), "1.csv and 4.csv beer IDs differ"
    calibrated = pd.read_excel(DATA / "8.xlsx", sheet_name="Calibrated chemical dataset")
    threshold_table = pd.read_excel(DATA / "8.xlsx", sheet_name="Sensory thresholds")
    threshold = {str(row.field_name_R): float(row.threshold_median) for _, row in threshold_table.iterrows()
                 if pd.notna(row.threshold_median)}
    encoding = physical_map(chem, calibrated, threshold)
    all_features = list(chem.columns[3:])
    base_fields = [col for col in all_features if col not in DERIVED]
    sensory_fields = [col for col in SENSORY_COLUMNS if col in sensory]
    assert len(all_features) == 231 and len(base_fields) == 226 and len(sensory_fields) == 50

    # Stratified 20% holdout, performed before learning either the copula or
    # the style means. It is a diagnostic, not an independent brewery cohort.
    styles = chem.tasting_category_fine.to_numpy(str)
    holdout = np.zeros(len(chem), bool)
    for style in np.unique(styles):
        idx = np.flatnonzero(styles == style)
        n_holdout = min(max(1, int(round(len(idx) * 0.2))), len(idx) - 2)
        holdout[rng.choice(idx, n_holdout, replace=False)] = True
    train = ~holdout
    train_model = fit_generator(chem.loc[train, base_fields].to_numpy(float), styles[train])
    kcal_cv = fit_kcal(chem, calibrated, set(chem.loc[train, "beer"].astype(int)))
    derived_rows = []
    for split_name, split_mask in (("train", train), ("holdout", holdout)):
        source = chem.loc[split_mask, all_features].copy()
        rebuilt = rebuild_derived(source, threshold, encoding, kcal_cv)
        for field in DERIVED:
            err = np.abs(rebuilt[field].to_numpy(float) - source[field].to_numpy(float))
            derived_rows.append({"split": split_name, "field": field, "n": int(np.isfinite(err).sum()),
                                 "MAE_log10": float(np.nanmean(err)), "max_abs_error_log10": float(np.nanmax(err))})
    pd.DataFrame(derived_rows).to_csv(HERE / "audit" / "derived_reconstruction.csv", index=False, encoding="utf-8-sig")

    holdout_rows = []
    global_scale = np.maximum(np.std(train_model["score"], axis=0), 1e-6)
    for style in TARGET_STYLES:
        real = chem.loc[holdout & (styles == style), base_fields].to_numpy(float)
        fit_real = chem.loc[train & (styles == style), base_fields].to_numpy(float)
        generated = draw_conditional(train_model, style, 120, rng)
        real_emb, fit_emb, gen_emb = encode(train_model, real), encode(train_model, fit_real), encode(train_model, generated)
        predicted_real, predicted_generated = centroid_labels(train_model, real), centroid_labels(train_model, generated)
        holdout_rows.append({"style": style, "n_train": len(fit_real), "n_holdout": len(real),
                             "n_generated": len(generated), "real_centroid_hit": float(np.mean(predicted_real == style)),
                             "generated_centroid_hit": float(np.mean(predicted_generated == style)),
                             "generated_to_train_trace_variance_ratio":
                                 float(np.sum(np.var(gen_emb, axis=0, ddof=1)) /
                                       max(np.sum(np.var(fit_emb, axis=0, ddof=1)), 1e-9)),
                             "mean_rmse_generated_vs_train": mse_standardized(gen_emb, fit_emb, global_scale),
                             "mean_rmse_holdout_vs_train": mse_standardized(real_emb, fit_emb, global_scale),
                             "DCR_generated_to_train_over_holdout_to_train":
                                 float(np.median(nearest_distance(gen_emb, fit_emb)) /
                                       max(np.median(nearest_distance(real_emb, fit_emb)), 1e-9)),
                             "duplicate_rate": float(pd.DataFrame(generated).duplicated().mean())})
    pd.DataFrame(holdout_rows).to_csv(HERE / "results" / "q3_holdout_validation.csv", index=False, encoding="utf-8-sig")
    sensitivity_rows = []
    for share in (0.35, 0.55, 0.75):
        sensitivity_rng = np.random.default_rng(SEED + round(share * 1000))
        for style in TARGET_STYLES:
            real = chem.loc[holdout & (styles == style), base_fields].to_numpy(float)
            fit_real = chem.loc[train & (styles == style), base_fields].to_numpy(float)
            generated_test = draw_conditional(train_model, style, 120, sensitivity_rng, share)
            real_z, fit_z, generated_z = (encode(train_model, a) for a in (real, fit_real, generated_test))
            sensitivity_rows.append({"global_share": share, "style": style,
                                     "generated_centroid_hit": float(np.mean(centroid_labels(train_model, generated_test) == style)),
                                     "distance_ratio_generated_to_train_over_holdout_to_train":
                                         float(np.median(nearest_distance(generated_z, fit_z)) /
                                               max(np.median(nearest_distance(real_z, fit_z)), 1e-9))})
    pd.DataFrame(sensitivity_rows).to_csv(HERE / "results" / "q3_noise_sensitivity.csv", index=False, encoding="utf-8-sig")

    full_model = fit_generator(chem[base_fields].to_numpy(float), styles)
    kcal_full = fit_kcal(chem, calibrated, set(chem.beer.astype(int)))
    generated_frames = []
    for style in sorted(np.unique(styles)):
        raw = draw_conditional(full_model, style, GENERATE_N, rng)
        frame = pd.DataFrame(raw, columns=base_fields)
        frame = rebuild_derived(frame, threshold, encoding, kcal_full)
        frame.insert(0, "generated_id", np.arange(1, GENERATE_N + 1))
        frame.insert(0, "style", style)
        generated_frames.append(frame)
    generated = pd.concat(generated_frames, ignore_index=True)
    generated[["style", "generated_id"] + all_features].to_csv(
        HERE / "results" / "q3_generated_spectra.csv", index=False, encoding="utf-8-sig")

    marker_rows = []
    marker_fields = ("ethanol..v.v.", "bitterness", "lactic_acid.mg.L.",
                     "acetic_acid.g.L.", "ethyl_acetate", "DMS")
    for style in TARGET_STYLES:
        for field in marker_fields:
            observed_values = to_physical(chem.loc[styles == style, field].to_numpy(float), encoding[field])
            generated_values = to_physical(generated.loc[generated["style"].eq(style), field].to_numpy(float), encoding[field])
            marker_rows.append({"style": style, "field": field, "n_observed": int(np.isfinite(observed_values).sum()),
                                "n_generated": len(generated_values),
                                "observed_median_physical": float(np.nanmedian(observed_values)),
                                "generated_median_physical": float(np.median(generated_values)),
                                "observed_q25_physical": float(np.nanquantile(observed_values, .25)),
                                "observed_q75_physical": float(np.nanquantile(observed_values, .75)),
                                "generated_q25_physical": float(np.quantile(generated_values, .25)),
                                "generated_q75_physical": float(np.quantile(generated_values, .75))})
    pd.DataFrame(marker_rows).to_csv(HERE / "results" / "q3_style_marker_summary.csv", index=False, encoding="utf-8-sig")

    profile = fit_sensory_predictor(chem, sensory, all_features, sensory_fields)
    sensory_raw, sensory_score = predict_sensory(profile, generated[all_features].to_numpy(float))
    predicted = generated[["style", "generated_id"]].copy()
    for j, col in enumerate(sensory_fields):
        predicted["proxy_score_" + col] = sensory_score[:, j]
    predicted.to_csv(HERE / "results" / "q3_generated_sensory_proxy.csv", index=False, encoding="utf-8-sig")
    summary = predicted[predicted["style"].isin(TARGET_STYLES)].groupby("style").mean(numeric_only=True)
    summary = summary.drop(columns="generated_id").reset_index()
    summary.to_csv(HERE / "results" / "q3_target_style_sensory_summary.csv", index=False, encoding="utf-8-sig")
    sensory_alignment = []
    for style in TARGET_STYLES:
        obs_mean = sensory.loc[styles == style, sensory_fields].apply(pd.to_numeric, errors="coerce").mean().to_numpy(float)
        gen_mean = sensory_raw[generated["style"].eq(style).to_numpy()].mean(axis=0)
        sensory_alignment.append({"style": style, "n_observed": int(np.sum(styles == style)),
                                  "mean_50_dimension_z_rmse": float(np.sqrt(np.mean(
                                      ((gen_mean - obs_mean) / profile.development_target_sd) ** 2)))})
    pd.DataFrame(sensory_alignment).to_csv(HERE / "results" / "q3_sensory_alignment.csv", index=False, encoding="utf-8-sig")

    # Target transport: retain each Pils/Lager sample's deviation from its
    # style center and move it toward the Tripel center. The decoded change
    # is anchored to the original raw sample, keeping alpha=0 exact.
    src_idx = np.flatnonzero(styles == "Pils/Lager")
    src_observed = chem.loc[src_idx, all_features].reset_index(drop=True)
    src_base = src_observed[base_fields].to_numpy(float)
    src_missing = ~np.isfinite(src_base)
    # Original missing values do not define a no-worsening baseline. Use the
    # Pils/Lager median for transport, and mark those cells unverifiable.
    style_median = np.nanmedian(chem.loc[styles == "Pils/Lager", base_fields].to_numpy(float), axis=0)
    style_median = np.where(np.isfinite(style_median), style_median, full_model["median"])
    src_base = np.where(src_missing, style_median[None, :], src_base)
    src_original = rebuild_derived(pd.DataFrame(src_base, columns=base_fields), threshold, encoding, kcal_full)
    src_z = full_model["score"][src_idx]
    center_src = full_model["score"][styles == "Pils/Lager"].mean(axis=0)
    center_target = full_model["score"][styles == "Tripel"].mean(axis=0)
    decoded_src = decode(full_model, src_z)
    source_raw_prediction, source_scores = predict_sensory(profile, src_original[all_features].to_numpy(float))
    stale_col = sensory_fields.index("stale_hops")
    alphas = np.linspace(0.0, 1.0, 11)
    candidates = []
    candidate_meta = []
    base_min, base_max = full_model["x"].min(axis=0), full_model["x"].max(axis=0)
    for alpha in alphas:
        shifted = src_z + alpha * (center_target - center_src)
        shifted_decoded = decode(full_model, shifted)
        candidate_base = np.clip(src_base + (shifted_decoded - decoded_src), base_min, base_max)
        for field in DEFECT_FIELDS:
            j = base_fields.index(field)
            candidate_base[:, j] = np.minimum(candidate_base[:, j], src_base[:, j])
        c_frame = rebuild_derived(pd.DataFrame(candidate_base, columns=base_fields), threshold, encoding, kcal_full)
        candidates.append(c_frame[all_features].to_numpy(float))
        candidate_meta.extend([(i, float(alpha)) for i in range(len(src_idx))])
    flat = np.vstack(candidates)
    candidate_raw_pred, candidate_scores = predict_sensory(profile, flat)
    accepted_rows, transfer_rows = [], []
    transport_scale = np.maximum(full_model["score"].std(axis=0), 1e-6)
    for i, source_row in enumerate(src_idx):
        valid = []
        for k, alpha in enumerate(alphas):
            pos = k * len(src_idx) + i
            # Comparing only rounded 0--6 levels can hide an increase inside
            # one level.  Constrain the continuous Q1 prediction as well.
            if (candidate_raw_pred[pos, stale_col] <= source_raw_prediction[i, stale_col] + 1e-10
                    and candidate_scores[pos, stale_col] <= source_scores[i, stale_col]):
                valid.append((pos, alpha))
        assert valid
        # Pick the admissible candidate closest to target centroid; if every
        # candidate worsens target distance, retain the source spectrum.
        source_dist = float(np.linalg.norm(src_z[i] - center_target))
        best = (source_dist, 0, 0.0)
        for pos, alpha in valid:
            emb = encode(full_model, flat[pos:pos + 1, [all_features.index(c) for c in base_fields]])[0]
            distance = float(np.linalg.norm(emb - center_target))
            if distance < best[0] - 1e-10:
                best = (distance, pos, alpha)
        fallback_spectrum = None
        fallback_score = None
        fallback_raw_pred = None
        search_stage = "primary_grid" if best[2] > 0 else "unchanged"
        if best[2] == 0.0:
            # Fixed second-stage search for sources blocked along the single
            # centroid direction.  Exactly 400 predeclared candidates: each
            # alpha on the 0.1--1.0 grid receives 40 Gaussian perturbations
            # with 0.15 global latent SD.  No sensory ground truth is used.
            local_rng = np.random.default_rng(SEED + int(chem.loc[source_row, "beer"]))
            trial_alpha = np.repeat(np.linspace(0.1, 1.0, 10), 40)
            trial_z = (src_z[i][None, :] +
                       trial_alpha[:, None] * (center_target - center_src)[None, :] +
                       local_rng.normal(0.0, 0.15 * transport_scale, size=(400, len(center_target))))
            trial_decoded = decode(full_model, trial_z)
            trial_base = np.clip(src_base[i][None, :] + (trial_decoded - decoded_src[i][None, :]),
                                 base_min, base_max)
            for field in DEFECT_FIELDS:
                j = base_fields.index(field)
                trial_base[:, j] = np.minimum(trial_base[:, j], src_base[i, j])
            trial_frame = rebuild_derived(pd.DataFrame(trial_base, columns=base_fields),
                                          threshold, encoding, kcal_full)
            trial_flat = trial_frame[all_features].to_numpy(float)
            trial_raw, trial_grade = predict_sensory(profile, trial_flat)
            admissible = ((trial_raw[:, stale_col] <= source_raw_prediction[i, stale_col] + 1e-10) &
                          (trial_grade[:, stale_col] <= source_scores[i, stale_col]))
            if np.any(admissible):
                trial_emb = encode(full_model, trial_base[admissible])
                trial_dist = np.linalg.norm(trial_emb - center_target, axis=1)
                candidates_ok = np.flatnonzero(admissible)
                k_min = int(np.argmin(trial_dist))
                if trial_dist[k_min] < source_dist - 1e-10:
                    k = int(candidates_ok[k_min])
                    best = (float(trial_dist[k_min]), -1, float(trial_alpha[k]))
                    fallback_spectrum = trial_flat[k]
                    fallback_score = trial_grade[k]
                    fallback_raw_pred = trial_raw[k]
                    search_stage = "fixed_400_candidate_fallback"
        chosen_pos = best[1]
        if fallback_spectrum is not None:
            new_spectrum = fallback_spectrum
            new_score = fallback_score
            new_raw_pred = fallback_raw_pred
        elif best[2] == 0.0:
            new_spectrum = src_original.loc[i, all_features].to_numpy(float)
            new_score = source_scores[i]
            new_raw_pred = source_raw_prediction[i]
        else:
            new_spectrum = flat[chosen_pos]
            new_score = candidate_scores[chosen_pos]
            new_raw_pred = candidate_raw_pred[chosen_pos]
        row = {"source_beer": int(chem.loc[source_row, "beer"]), "source_style": "Pils/Lager",
               "target_style": "Tripel", "shift_alpha": best[2], "search_stage": search_stage,
               "imputed_source_cells": int(src_missing[i].sum())}
        row.update({all_features[j]: float(new_spectrum[j]) for j in range(len(all_features))})
        row.update({"proxy_score_" + sensory_fields[j]: int(new_score[j]) for j in range(len(sensory_fields))})
        accepted_rows.append(row)
        transfer_rows.append({"source_beer": row["source_beer"], "shift_alpha": best[2],
                              "search_stage": search_stage,
                              "distance_to_Tripel_before": source_dist,
                              "distance_to_Tripel_after": best[0],
                              "stale_hops_score_before": int(source_scores[i, stale_col]),
                              "stale_hops_score_after": int(new_score[stale_col]),
                              "stale_hops_continuous_before": float(source_raw_prediction[i, stale_col]),
                              "stale_hops_continuous_after": float(new_raw_pred[stale_col])})
    migrated = pd.DataFrame(accepted_rows)
    transfer = pd.DataFrame(transfer_rows)
    migrated.to_csv(HERE / "results" / "q3_PilsLager_to_Tripel.csv", index=False, encoding="utf-8-sig")
    transfer.to_csv(HERE / "results" / "q3_transfer_validation.csv", index=False, encoding="utf-8-sig")

    # An independent, chemistry-marker-only ridge-logistic discriminator is
    # used as a secondary check. It is not calibrated on new breweries, so
    # probabilities are descriptive classifier outputs, not success rates.
    two_styles = np.isin(styles, ("Pils/Lager", "Tripel"))
    real_x = chem.loc[two_styles, CLASSIFIER_FIELDS].to_numpy(float)
    real_y = (styles[two_styles] == "Tripel").astype(float)
    cv_prob = np.empty(len(real_y), float)
    for j in range(len(real_y)):
        keep = np.ones(len(real_y), bool)
        keep[j] = False
        fold_model = fit_binary_classifier(real_x[keep], real_y[keep])
        cv_prob[j] = predict_binary_classifier(fold_model, real_x[j:j + 1])[0]
    classifier = fit_binary_classifier(real_x, real_y)
    before_probability = predict_binary_classifier(classifier, src_original[list(CLASSIFIER_FIELDS)].to_numpy(float))
    after_probability = predict_binary_classifier(classifier, migrated[list(CLASSIFIER_FIELDS)].to_numpy(float))
    classifier_details = pd.DataFrame({"source_beer": migrated.source_beer,
                                       "Tripel_probability_before": before_probability,
                                       "Tripel_probability_after": after_probability,
                                       "probability_change": after_probability - before_probability})
    classifier_details.to_csv(HERE / "results" / "q3_independent_style_discriminator.csv", index=False, encoding="utf-8-sig")
    cv_table = pd.DataFrame([{
        "model": "8-marker ridge logistic; original spectra only; leave-one-out CV",
        "n_real": len(real_y), "n_Tripel": int(real_y.sum()), "n_PilsLager": int(len(real_y) - real_y.sum()),
        "LOOCV_accuracy": float(np.mean((cv_prob >= .5) == real_y)),
        "LOOCV_Tripel_recall": float(np.mean(cv_prob[real_y == 1] >= .5)),
        "LOOCV_PilsLager_specificity": float(np.mean(cv_prob[real_y == 0] < .5)),
        "migration_probability_mean_before": float(np.mean(before_probability)),
        "migration_probability_mean_after": float(np.mean(after_probability)),
        "migration_probability_increased_count": int(np.sum(after_probability > before_probability)),
        "migration_classified_Tripel_before": int(np.sum(before_probability >= .5)),
        "migration_classified_Tripel_after": int(np.sum(after_probability >= .5)),
    }])
    cv_table.to_csv(HERE / "audit" / "independent_style_discriminator_audit.csv", index=False, encoding="utf-8-sig")

    migrated_base = migrated[base_fields].to_numpy(float)
    defects = []
    for field in DEFECT_FIELDS:
        col = base_fields.index(field)
        source = src_base[:, col]
        new = migrated_base[:, col]
        observed = ~src_missing[:, col]
        reference = threshold.get(field, np.nan)
        if field == "X.E..2.nonenal":
            reference = float(np.nanquantile(chem[field].to_numpy(float), 0.95))
            source_desc = "1.csv empirical 95th percentile (screening proxy, not sensory threshold)"
            source_physical, new_physical = source, new
        else:
            source_desc = "8.xlsx Sensory thresholds, threshold_median"
            source_physical = to_physical(source, encoding[field])
            new_physical = to_physical(new, encoding[field])
        defects.append({"defect": field, "n": len(source), "n_observed_source": int(observed.sum()),
                        "n_imputed_source": int((~observed).sum()), "threshold": reference,
                        "threshold_source": source_desc,
                        "pointwise_nonincrease_fraction": float(np.mean(new_physical[observed] <= source_physical[observed] + 1e-10)),
                        "source_over_rate": float(np.mean(source_physical[observed] > reference)),
                        "migrated_over_rate": float(np.mean(new_physical[observed] > reference)),
                        "max_increase": float(np.max(new_physical[observed] - source_physical[observed]))})
    defects.append({"defect": "stale_hops proxy score", "n": len(src_idx),
                    "n_observed_source": len(src_idx), "n_imputed_source": 0, "threshold": 5,
                    "threshold_source": "proxy 0–6 level; continuous prediction is constrained pointwise",
                    "pointwise_nonincrease_fraction": float(np.mean(
                        transfer.stale_hops_continuous_after <= transfer.stale_hops_continuous_before + 1e-10)),
                    "source_over_rate": float(np.mean(transfer.stale_hops_score_before >= 5)),
                    "migrated_over_rate": float(np.mean(transfer.stale_hops_score_after >= 5)),
                    "max_increase": float(np.max(
                        transfer.stale_hops_score_after - transfer.stale_hops_score_before)),
                    "max_continuous_increase": float(np.max(
                        transfer.stale_hops_continuous_after - transfer.stale_hops_continuous_before))})
    pd.DataFrame(defects).to_csv(HERE / "results" / "q3_defect_audit.csv", index=False, encoding="utf-8-sig")

    # Machine-readable conditions and independent checks for the paper.
    model_audit = {
        "input_beers": len(chem), "base_features": len(base_fields), "derived_features": len(DERIVED),
        "sensory_proxy_dimensions": len(sensory_fields), "styles": len(np.unique(styles)),
        "sensory_predictor": "Q1 frozen weighted tree ensemble (ET/RF/GB weights 0.38/0.17/0.45) on Beer 13--250 with training-only 1/99% grade anchors",
        "sensory_predictor_train_beers": len(profile.train_ids),
        "generated_per_style": GENERATE_N, "pca_components": full_model["d"],
        "pca_variance_retained": full_model["variance_retained"],
        "pca_components_holdout_train": train_model["d"],
        "pca_variance_retained_holdout_train": train_model["variance_retained"],
        "source_style": "Pils/Lager", "target_style": "Tripel",
        "migration_beers": len(src_idx), "random_seed": SEED,
        "oav_groups": {k: list(v) for k, v in OAV_GROUPS.items()},
        "kcal_coefficients_intercept_then_inputs": [float(x) for x in kcal_full],
        "kcal_inputs": list(KCAL_INPUTS),
        "thresholds": {k: threshold[k] for group in OAV_GROUPS.values() for k in group},
        "encoding": {k: {"kind": encoding[k]["encoding"], "zero_encoded": encoding[k]["zero_encoded"]}
                     for k in set(KCAL_INPUTS) | {k for group in OAV_GROUPS.values() for k in group}},
        "limitations": [
            "No ground-truth new-beer chemical spectra are supplied; generated spectra have only internal and held-out diagnostics.",
            "Tripel has one correct real sample among six in the centroid holdout; high generated centroid hit is not evidence of real-world style authenticity.",
            "Two Pils/Lager diacetyl source cells are missing; no-worsening is verified only for nine observed source values and relative to imputed baselines for two others.",
            "trans-2-nonenal has no numeric sensory threshold in 8.xlsx; its 95th percentile is a screening proxy.",
            "All sensory 0-6 values are model-derived proxies from standardized 4.csv, not independent panel ground truth.",
            "Stale-hops transport constrains the continuous Q1 prediction pointwise before rounding to 0--6 proxy levels.",
            "Source beer 124 remains unchanged because the fixed 400-candidate fallback found no move satisfying the continuous stale-hops and chemistry constraints.",
            "The eight-marker classifier is trained and leave-one-out checked on only 39 original beers; its probabilities are not externally calibrated.",
        ],
    }
    (HERE / "audit" / "model_audit.json").write_text(json.dumps(model_audit, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Q3 v4 completed", json.dumps({k: model_audit[k] for k in (
        "pca_components", "pca_variance_retained", "styles", "generated_per_style", "migration_beers")}, ensure_ascii=False))
    print("Holdout:\n", pd.DataFrame(holdout_rows).to_string(index=False))
    print("Migration:\n", transfer.describe().to_string())


if __name__ == "__main__":
    main()




