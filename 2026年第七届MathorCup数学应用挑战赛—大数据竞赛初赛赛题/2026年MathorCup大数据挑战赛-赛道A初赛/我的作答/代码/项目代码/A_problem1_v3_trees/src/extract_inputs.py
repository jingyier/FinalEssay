"""Extract only workbook fields required by the frozen Q1 scoring route."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd
from openpyxl import load_workbook


PROJECT = Path(__file__).resolve().parents[1]
DATA = PROJECT / "data"
AUDIT = PROJECT / "audit"


def main():
    AUDIT.mkdir(parents=True, exist_ok=True)
    cal = pd.read_excel(DATA / "8.xlsx", sheet_name="Calibrated chemical dataset")
    acet = cal[["beer", "acetaldehyde"]].copy()
    acet["beer"] = pd.to_numeric(acet["beer"], errors="raise").astype(int)
    acet["acetaldehyde"] = pd.to_numeric(acet["acetaldehyde"], errors="raise")
    if acet.beer.duplicated().any() or len(acet) != 250 or acet.acetaldehyde.isna().any():
        raise ValueError("Invalid calibrated acetaldehyde table")
    acet.sort_values("beer").to_csv(AUDIT / "acetaldehyde_calibration.csv", index=False, encoding="utf-8-sig")

    mapping = pd.read_csv(DATA / "scorecard_mapping.csv")
    if len(mapping) != 52 or mapping.dimension.duplicated().any():
        raise ValueError("Invalid 52-position template mapping")
    book = load_workbook(DATA / "3.xlsx", data_only=False, read_only=True)
    count = {}
    for beer in range(1, 13):
        sheet = book[f"beer_{beer}"]
        cells = [sheet[f"{row.scorecard_column}{row.scorecard_row}"].value
                 for row in mapping.itertuples(index=False)]
        count[str(beer)] = sum(isinstance(x, str) and x.startswith("=IF(ISBLANK(") for x in cells)
    if list(count.values()) != [52] * 12:
        raise ValueError("Template cells differ from the audited 12x52 layout")

    hashes = {name: hashlib.sha256((DATA / name).read_bytes()).hexdigest()
              for name in ("1.csv", "4.csv", "3.xlsx", "8.xlsx", "scorecard_mapping.csv")}
    (AUDIT / "input_workbook_audit.json").write_text(json.dumps({
        "blank_formula_cells_by_beer": count,
        "input_sha256": hashes,
        "source": "Bundled original MathorCup Track A attachments; no source edits",
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Excel inputs and 12 blank scorecards audited")


if __name__ == "__main__":
    main()
