"""绘制论文使用的问题一感官维度独立留出审计图。"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
from PIL import Image, ImageDraw, ImageFont

from make_q1_figures import FONT_CJK, FONT_CJK_BOLD, LABELS

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(__file__).resolve().parent / "图表"
DATA = ROOT / "项目代码" / "A_problem1_v3_trees" / "audit" / "q1_holdout_by_dimension.csv"


def font(size: int, bold: bool = False):
    return ImageFont.truetype(str(FONT_CJK_BOLD if bold else FONT_CJK), size)


def put(draw, xy, value, size=30, color="#25313d", bold=False, anchor=None):
    draw.text(xy, str(value), font=font(size, bold), fill=color, anchor=anchor)


def render(group: str, frame: pd.DataFrame, filename: str):
    frame = frame.sort_values("spearman", ascending=False).reset_index(drop=True)
    width, height = 2580, 258 + len(frame) * 57 + 175
    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)
    title = f"{group}维度的事后留出表现（每维12款）"
    put(draw, (width // 2, 60), title, 51, bold=True, anchor="mm")
    put(draw, (width // 2, 121), "Spearman ρ  /  MAE", 31,
        color="#59636e", anchor="mm")

    label_right = 460
    corr_left, corr_right = 515, 1565
    mae_left, mae_right = 1755, 2360
    top, step = 258, 57
    corr_zero = (corr_left + corr_right) / 2
    corr_scale = (corr_right - corr_left) / 2
    max_mae = max(0.8, float(frame.continuous_mae.max()) * 1.12)

    for val in (-1, -0.5, 0, 0.5, 1):
        x = corr_zero + val * corr_scale
        draw.line((x, top - 28, x, top + len(frame) * step - 11), fill="#dce0e4", width=2)
        put(draw, (x, top - 41), f"{val:g}", 25, color="#59636e", anchor="mb")
    for val in (0, 0.25, 0.5, 0.75, 1.0):
        x = mae_left + min(val, max_mae) / max_mae * (mae_right - mae_left)
        draw.line((x, top - 28, x, top + len(frame) * step - 11), fill="#e7e9ec", width=2)
        put(draw, (x, top - 41), f"{val:g}", 25, color="#59636e", anchor="mb")
    put(draw, (corr_zero, top - 85), "秩相关系数 ρ", 30, bold=True, anchor="mm")
    put(draw, ((mae_left + mae_right) / 2, top - 85), "平均绝对误差", 30, bold=True, anchor="mm")

    for i, row in frame.iterrows():
        y = top + i * step
        name = LABELS.get(row.dimension, row.dimension)
        put(draw, (label_right, y), name, 31, anchor="rm")
        corr = float(row.spearman)
        cx = corr_zero + corr * corr_scale
        draw.line((corr_zero, y, cx, y), fill="#335d83" if corr >= 0 else "#a55544", width=10)
        draw.ellipse((cx - 7, y - 7, cx + 7, y + 7), fill="#335d83" if corr >= 0 else "#a55544")
        put(draw, (corr_right + 23, y), f"{corr:+.2f}", 27, anchor="lm")
        mae = float(row.continuous_mae)
        mx = mae_left + mae / max_mae * (mae_right - mae_left)
        draw.ellipse((mx - 8, y - 8, mx + 8, y + 8), fill="#333c45")
        put(draw, (mae_right + 18, y), f"{mae:.2f}", 27, anchor="lm")
        if i % 5 == 4:
            draw.line((80, y + step / 2, width - 80, y + step / 2), fill="#e8eaec", width=1)

    image.save(OUT / filename, dpi=(360, 360))


def main():
    data = pd.read_csv(DATA)
    assert len(data) == 50 and data.dimension.is_unique
    aroma = data[data.dimension.str.startswith("A_")]
    other = data[~data.dimension.str.startswith("A_")]
    assert len(aroma) + len(other) == 50
    render("香气", aroma, "fig_q1_dimension_aroma.png")
    render("口味及综合", other, "fig_q1_dimension_flavour.png")
    print(f"已绘制：香气{len(aroma)}项，口味及综合{len(other)}项")


if __name__ == "__main__":
    main()
