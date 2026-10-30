"""核验问题三迁移结果、感官约束和输出文件的一致性。"""



from __future__ import annotations

import json
import os
from pathlib import Path

import numpy as np
import pandas as pd

BASE = Path(__file__).resolve().parents[1]
RESULTS = BASE / "results"
AUDIT = BASE / "audit"
PACKAGE_ROOT = Path(__file__).resolve().parents[4]
SOURCE = Path(os.environ.get("MATHOR_INPUT_DIR", str(PACKAGE_ROOT / "03_原始附件")))


def physical(values: np.ndarray, spec: dict) -> np.ndarray:
    if spec["kind"] == "raw":
        return np.maximum(values, 0)
    result = np.power(10.0, values)
    if spec["zero_encoded"] is not None:
        result = np.where(np.isclose(values, spec["zero_encoded"], atol=1e-9, rtol=0), 0, result)
    return result


def check_derived(table: pd.DataFrame, audit: dict) -> dict[str, float]:
    out = {}
    for aggregate, fields in audit["oav_groups"].items():
        total = sum(physical(table[f].to_numpy(float), audit["encoding"][f]) /
                    audit["thresholds"][f] for f in fields)
        expected = np.log10(np.maximum(total, 1e-12))
        out[aggregate] = float(np.max(np.abs(expected - table[aggregate].to_numpy(float))))
    raw = np.column_stack([np.ones(len(table))] + [physical(table[f].to_numpy(float), audit["encoding"][f])
                                                  for f in audit["kcal_inputs"]])
    expected = np.log10(np.maximum(raw @ np.asarray(audit["kcal_coefficients_intercept_then_inputs"]), 1e-6))
    out["kcalperc"] = float(np.max(np.abs(expected - table["kcalperc"].to_numpy(float))))
    return out


def main() -> None:
    source = pd.read_csv(SOURCE / "1.csv")
    generated = pd.read_csv(RESULTS / "q3_generated_spectra.csv")
    scores = pd.read_csv(RESULTS / "q3_generated_sensory_proxy.csv")
    migrated = pd.read_csv(RESULTS / "q3_PilsLager_to_Tripel.csv")
    transfer = pd.read_csv(RESULTS / "q3_transfer_validation.csv")
    defects = pd.read_csv(RESULTS / "q3_defect_audit.csv")
    style_discriminator = pd.read_csv(RESULTS / "q3_independent_style_discriminator.csv")
    classifier_audit = pd.read_csv(AUDIT / "independent_style_discriminator_audit.csv")
    migration_sensitivity = pd.read_csv(RESULTS / "q3_migration_sensitivity.csv")
    model = json.loads((AUDIT / "model_audit.json").read_text(encoding="utf-8"))
    features = list(source.columns[3:])
    score_cols = [c for c in scores if c.startswith("proxy_score_")]
    assert len(features) == 231 and len(score_cols) == 50
    assert len(generated) == 22 * 50 and generated.groupby("style").size().eq(50).all()
    assert generated[features].notna().all().all() and not generated[features].duplicated().any()
    assert scores[score_cols].notna().all().all()
    assert np.all((scores[score_cols].to_numpy() >= 0) & (scores[score_cols].to_numpy() <= 6))
    assert np.allclose(scores[score_cols].to_numpy(), np.rint(scores[score_cols].to_numpy()))
    assert len(migrated) == 11 and len(transfer) == 11
    assert set(migrated.source_beer) == set(source.loc[source.tasting_category_fine.eq("Pils/Lager"), "beer"])
    assert migrated[features].notna().all().all()
    improved = transfer.distance_to_Tripel_after < transfer.distance_to_Tripel_before - 1e-10
    assert (transfer.distance_to_Tripel_after <= transfer.distance_to_Tripel_before + 1e-10).all()
    assert int(improved.sum()) == int((transfer.shift_alpha > 0).sum())
    assert int(improved.sum()) == 10
    assert (transfer.stale_hops_score_after <= transfer.stale_hops_score_before).all()
    assert (transfer.stale_hops_continuous_after <= transfer.stale_hops_continuous_before + 1e-10).all()
    assert (defects.pointwise_nonincrease_fraction == 1).all()
    assert int(defects.loc[defects.defect.eq("X2.3.butanedione"), "n_imputed_source"].iloc[0]) == 2
    assert len(style_discriminator) == 11
    assert (style_discriminator.Tripel_probability_after >= style_discriminator.Tripel_probability_before - 1e-10).all()
    assert int(classifier_audit.migration_probability_increased_count.iloc[0]) == int(improved.sum())
    assert migration_sensitivity.grid_step.tolist() == [0.05, 0.1, 0.2]
    assert migration_sensitivity.strictly_improved_count.tolist() == [10, 10, 10]
    assert migration_sensitivity.unchanged_count.tolist() == [1, 1, 1]
    assert np.all((migration_sensitivity.mean_distance_reduction_pct >= 33.5) &
                  (migration_sensitivity.mean_distance_reduction_pct <= 33.7))
    assert np.allclose(migration_sensitivity.stale_hops_continuous_nonincrease, 1.0)
    assert any("Tripel has one correct real sample among six" in note for note in model["limitations"])
    residual_generated = check_derived(generated, model)
    residual_migrated = check_derived(migrated, model)
    assert max(residual_generated.values()) < 1e-8
    assert max(residual_migrated.values()) < 1e-8
    checks = [
        ("22 styles x 50 generated", True, len(generated)),
        ("231 chemical columns and 50 proxy sensory outputs", True, len(features)),
        ("generated spectra finite, unique", True, int(generated[features].duplicated().sum())),
        ("11 Pils/Lager migrations, source IDs match", True, len(migrated)),
        ("10 move closer; 1 held unchanged under continuous defect constraint", True, int(improved.sum())),
        ("all observed defects pointwise nonincreasing", True, int((defects.pointwise_nonincrease_fraction == 1).sum())),
        ("2 missing diacetyl source cells explicitly marked", True, 2),
        ("8-marker independent discriminator rises for 10 moved samples", True, int(improved.sum())),
        ("migration grid sensitivity remains 10/11 improved across 0.05/0.10/0.20", True,
         int(migration_sensitivity.strictly_improved_count.min())),
        ("limited Tripel holdout explicitly documented", True, 1),
        ("5 derived fields consistent in generated outputs", True, max(residual_generated.values())),
        ("5 derived fields consistent in migrated outputs", True, max(residual_migrated.values())),
    ]
    pd.DataFrame(checks, columns=["check", "passed", "value"]).to_csv(AUDIT / "verification_checks.csv", index=False, encoding="utf-8-sig")
    print("All independent output checks passed.")
    print("Derived residuals, generated:", residual_generated)
    print("Derived residuals, migrated:", residual_migrated)


if __name__ == "__main__":
    main()
