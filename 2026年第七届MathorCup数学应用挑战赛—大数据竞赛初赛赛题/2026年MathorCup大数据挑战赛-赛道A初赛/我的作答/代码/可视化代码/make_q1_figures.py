"""Rebuild the paper's Problem 1 figures from the frozen v3 tree outputs.

The figures are deliberately drawn from numbers, never from screenshots or
generated artwork.  Labels and legends are Chinese and sizes target A4 print.
"""
from __future__ import annotations

from pathlib import Path
import pandas as pd
from PIL import Image, ImageDraw, ImageFont
from matplotlib import colormaps

ROOT = Path(__file__).resolve().parents[1]
Q1 = ROOT / "项目代码" / "A_problem1_v3_trees"
OUT = Path(__file__).resolve().parent / "图表"
OUT.mkdir(parents=True, exist_ok=True)

# 论文图统一使用宋体；图中的英文、数字由系统回退到 Times New Roman。
FONT_CJK = Path("C:/Windows/Fonts/simsun.ttc")
# SimSun bold is not consistently populated on this Windows image; using the
# complete regular SimSun face avoids missing-glyph boxes in headings.
FONT_CJK_BOLD = Path("C:/Windows/Fonts/simsun.ttc")
FONT_LATIN = Path("C:/Windows/Fonts/times.ttf")
FONT_LATIN_BOLD = Path("C:/Windows/Fonts/timesbd.ttf")

def f(size: int, bold: bool = False, latin: bool = False):
    path = FONT_LATIN_BOLD if bold else FONT_LATIN
    if not latin:
        path = FONT_CJK_BOLD if bold else FONT_CJK
    return ImageFont.truetype(str(path), size)

INK = (32, 42, 54)
GRAY = (95, 105, 116)
LINE = (211, 217, 224)
BLUE = (44, 91, 137)
# 采用 matplotlib 的 YlOrBr 顺序色带并降低饱和度，
# 让0—6级有清晰的明暗梯度，同时避开整图深蓝/墨绿色。
# 参考优秀论文的蓝色等级热力图：浅色表示低等级，深蓝表示高等级。
# 使用 matplotlib 的连续色图后再与白色混合，避免高饱和色块影响数字辨识。
_cmap = colormaps["Blues"]
PALETTE = []
for _grade in range(7):
    _r, _g, _b, _ = _cmap(_grade / 6.0)
    # 与白色混合，适合论文打印和表内数字叠加。
    PALETTE.append(tuple(round(0.86 * v * 255 + 0.14 * 255) for v in (_r, _g, _b)))

LABELS = {
    "A_malt_all":"麦芽总", "A_malt_grain":"谷物香", "A_malt_bread":"面包香",
    "A_malt_cara":"焦糖香", "A_malt_burn":"焦糊香", "A_hops_all":"酒花总",
    "A_hops_citrus":"柑橘香", "A_hops_tropical":"热带果香", "A_hops_noble":"贵族酒花",
    "A_hops_woody":"木质香", "A_esters_all":"酯香总", "A_esters_ethac":"乙酸乙酯香",
    "A_esters_isoaa":"香蕉香", "A_esters_flower":"花香", "A_ester_fruity":"果香",
    "A_acetaldehyde":"乙醛香", "body":"酒体", "bitternes":"苦味",
    "co2":"气泡感", "aftertaste":"余味", "dms":"二甲硫醚",
    "metallic":"金属味", "4vg":"丁香酚味", "orange":"橙皮",
    "coriander":"芫荽", "clove":"丁香", "overall":"整体评价",
    "F_malt_all":"麦芽味总", "F_malt_grain":"谷物味", "F_malt_bread":"面包味",
    "F_malt_cara":"焦糖味", "F_malt_burn":"焦糊味", "F_hops_all":"酒花味总",
    "F_hops_citrus":"柑橘味", "F_hops_tropical":"热带果味", "F_hops_noble":"贵族酒花味",
    "F_hops_woody":"木质味", "F_esters_all":"酯味总", "F_esters_ethac":"乙酸乙酯味",
    "F_esters_isoaa":"香蕉味", "F_esters_flower":"花味", "F_ester_fruity":"果味",
    "F_acetaldehyde":"乙醛味", "alcohol":"酒精感", "sweetness":"甜味",
    "acidity":"酸味", "t2n":"陈旧纸味", "diacetyl":"双乙酰味",
    "stale_hops":"陈酒花味", "lactic":"乳酸味", "acetic":"乙酸味", "barnyard":"牲畜棚味",
}

def txt(draw, xy, value, size=32, fill=INK, bold=False, anchor=None):
    text = str(value)
    latin = any("A" <= c <= "z" for c in text) and all(ord(c) < 128 for c in text)
    draw.text(xy, text, font=f(size, bold, latin=latin), fill=fill, anchor=anchor)

def make_heatmap(part: str, columns: list[str], number: int):
    scores = pd.read_csv(Q1 / "results" / "A_problem1_v3_scores_52.csv").set_index("Beer")
    ncol = len(columns)
    W, H = 2450, 1530
    im = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(im)
    x0, y0, cw, ch = 315, 390, 145, 64
    title = f"{part}评分卡（第{number}组）"
    txt(d, (W//2, 72), title, 52, bold=True, anchor="mm")
    txt(d, (x0, 134), "等级：0—6", 31, GRAY)
    for j, col in enumerate(columns):
        x = x0 + j*cw + cw//2
        name = LABELS.get(col, col)
        # Rotate labels to retain legible Chinese in a fixed print width.
        lab = Image.new("RGBA", (125, 265), (255,255,255,0))
        ld = ImageDraw.Draw(lab)
        ld.text((62, 248), name, font=f(34), fill=INK, anchor="mb")
        rot = lab.rotate(90, expand=True)
        im.paste(rot, (x - rot.width//2, y0 - 185), rot)
    for i, beer in enumerate(scores.index.tolist()):
        y = y0 + i*ch
        txt(d, (x0-37, y+ch//2), f"啤酒{beer}", 36, anchor="rm")
        for j, col in enumerate(columns):
            grade = int(scores.loc[beer, col])
            x = x0 + j*cw
            d.rectangle([x+2,y+2,x+cw-2,y+ch-2], fill=PALETTE[grade], outline=LINE, width=1)
            luminance = sum(PALETTE[grade]) / 3
            txt(d, (x+cw//2,y+ch//2), grade, 36,
                fill="white" if luminance < 150 else INK, bold=True, anchor="mm")
    legend_y = y0 + len(scores)*ch + 70
    txt(d, (x0, legend_y+31), "图例：感官等级", 32, bold=True)
    for grade, color in enumerate(PALETTE):
        x = x0 + 280 + grade*150
        d.rectangle([x, legend_y, x+70, legend_y+66], fill=color, outline=LINE)
        txt(d, (x+90, legend_y+33), grade, 32, anchor="lm")
    im.save(OUT / f"fig_q1_scorecard_{part}_{number}.png", dpi=(360,360))

def make_holdout():
    df = pd.read_csv(Q1 / "audit" / "q1_holdout_by_beer.csv")
    W, H = 2450, 1350
    im = Image.new("RGB", (W,H), "white"); d=ImageDraw.Draw(im)
    txt(d,(W//2,70),"啤酒1—12的事后留出核验",52,bold=True,anchor="mm")
    x0,x1=190,2320
    chart_top=(240,655); chart_bottom=(790,1180)
    def axis(y0,y1, maxval, ticks, label):
        d.line([x0,y1,x1,y1],fill=INK,width=3)
        d.line([x0,y0,x0,y1],fill=INK,width=3)
        for val in ticks:
            y=y1-(y1-y0)*val/maxval
            d.line([x0,y,x1,y],fill=LINE,width=2)
            txt(d,(x0-14,y),f"{val:.1f}",25,GRAY,anchor="rm")
        txt(d,(x0,y0-44),label,30,bold=True)
    axis(*chart_top,0.9,[0,0.3,0.6,0.9],"平均绝对误差")
    axis(*chart_bottom,1.0,[0,0.25,0.5,0.75,1.0],"相差不超过一级")
    span=(x1-x0)/12
    for i,row in df.iterrows():
        cx=x0+(i+0.5)*span
        y=chart_top[1]-(chart_top[1]-chart_top[0])*row.continuous_mae/0.9
        d.rectangle([cx-35,y,cx+35,chart_top[1]-2],fill=BLUE)
        txt(d,(cx,y-14),f"{row.continuous_mae:.2f}",25,INK,anchor="mb")
        yy=chart_bottom[1]-(chart_bottom[1]-chart_bottom[0])*row.proxy_grade_within1_rate
        d.ellipse([cx-14,yy-14,cx+14,yy+14],fill=BLUE)
        txt(d,(cx,chart_bottom[1]+34),str(int(row.beer)),27,INK,anchor="mt")
    avg=df.proxy_grade_within1_rate.mean()
    yy=chart_bottom[1]-(chart_bottom[1]-chart_bottom[0])*avg
    d.line([x0,yy,x1,yy],fill=(169,77,54),width=3)
    txt(d,(x1-10,yy-14),f"12款平均 {avg:.1%}",29,(169,77,54),anchor="rb")
    im.save(OUT/"fig_q1_holdout_audit.png",dpi=(360,360))

def main():
    mp=pd.read_csv(Q1/"data"/"scorecard_mapping.csv")
    aroma=mp[mp.scorecard_column=="Q"].sort_values("scorecard_row").dimension.tolist()
    flavour=mp[mp.scorecard_column=="AG"].sort_values("scorecard_row").dimension.tolist()
    assert len(aroma)==27 and len(flavour)==25
    for part, cols in [("香气",aroma),("口味",flavour)]:
        mid=(len(cols)+1)//2
        make_heatmap(part,cols[:mid],1)
        make_heatmap(part,cols[mid:],2)
    make_holdout()

if __name__=="__main__":
    main()

