"""将问题一连续预测整理为评分卡工作簿，并写入必要的格式和校验信息。"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from openpyxl import load_workbook


PROJECT = Path(__file__).resolve().parents[1]
DATA = PROJECT / "data"
OUT = PROJECT / "results"


def main():
    scores = pd.read_csv(OUT / "A_problem1_v3_scores_52.csv").set_index("Beer")
    mapping = pd.read_csv(DATA / "scorecard_mapping.csv")
    values = scores.to_numpy(float)
    assert list(scores.index) == list(range(1, 13))
    assert scores.shape == (12, 52) and len(mapping) == 52
    assert set(scores.columns) == set(mapping.dimension)
    assert np.isfinite(values).all() and np.equal(values, np.rint(values)).all()
    assert 0 <= values.min() <= values.max() <= 6
    wb = load_workbook(DATA / "3.xlsx", data_only=False)
    summary = wb["summary"]
    cols = {summary.cell(1, c).value: c for c in range(1, summary.max_column + 1)}
    supervised = list(scores.columns[:-2])
    assert all(name in cols for name in supervised)
    for beer in range(1, 13):
        row = beer + 1
        summary.cell(row, 1).value = beer
        for dim in supervised:
            summary.cell(row, cols[dim]).value = int(scores.loc[beer, dim])
        summary.cell(row, summary.max_column).value = (
            "Weighted ET/RF/GB ensemble 50 sensory scores; 238-beer training; "
            "acetaldehyde 10 mg/L threshold"
        )
        sheet = wb[f"beer_{beer}"]
        for item in mapping.itertuples(index=False):
            score = int(scores.loc[beer, item.dimension])
            sheet[f"{item.scorecard_column}{item.scorecard_row}"] = score
            marks = ["E", "G", "I", "K", "M", "O"] if item.scorecard_column == "Q" else [
                "U", "W", "Y", "AA", "AC", "AE"]
            for mark in marks:
                sheet[f"{mark}{item.scorecard_row}"] = None
            if score:
                sheet[f"{marks[score - 1]}{item.scorecard_row}"] = "x"
    wb.calculation.fullCalcOnLoad = True
    wb.calculation.forceFullCalc = True
    dest = OUT / "A_problem1_v3_scores.xlsx"
    wb.save(dest)

    check = load_workbook(dest, data_only=False, read_only=True)
    for beer in range(1, 13):
        sheet = check[f"beer_{beer}"]
        summ = check["summary"]
        assert summ.cell(beer + 1, 1).value == beer
        for dim in supervised:
            assert summ.cell(beer + 1, cols[dim]).value == int(scores.loc[beer, dim])
        for item in mapping.itertuples(index=False):
            score = int(scores.loc[beer, item.dimension])
            assert sheet[f"{item.scorecard_column}{item.scorecard_row}"].value == score
            marks = ["E", "G", "I", "K", "M", "O"] if item.scorecard_column == "Q" else [
                "U", "W", "Y", "AA", "AC", "AE"]
            picked = [j + 1 for j, mark in enumerate(marks)
                      if sheet[f"{mark}{item.scorecard_row}"].value == "x"]
            assert picked == ([] if score == 0 else [score])
    print(f"Verified 12×52 scores, 12×50 summary cells and all choice marks: {dest}")


if __name__ == "__main__":
    main()
