"""Code-generated, data-backed figures for the full Track A paper.

Every plotted datum is read from supplied attachments or v4 result files.
All labels are Chinese; plots are sized for an A4 single-column paper.
"""
from __future__ import annotations

from pathlib import Path
import json
import math
import pandas as pd
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(__file__).resolve().parent / "图表"
DATA = ROOT / "03_原始附件"
Q2 = ROOT / "项目代码" / "A_full_solution_v4" / "q2"
Q3 = ROOT / "项目代码" / "A_full_solution_v4" / "q3"
# 论文图统一使用宋体；数字与英文由字体回退到 Times New Roman。
FONT = "C:/Windows/Fonts/simsun.ttc"
BOLD = "C:/Windows/Fonts/simsun.ttc"
LATIN = "C:/Windows/Fonts/times.ttf"
LATIN_BOLD = "C:/Windows/Fonts/timesbd.ttf"
# 统计图保留低饱和彩色区分不同对象；流程图单独采用优秀论文常见的黑白线框风格。
INK=(48,54,61); MUTED=(103,108,114); BLUE=(78,121,167)
TEAL=(242,142,43); RUST=(176,122,161); LIGHT=(214,218,222); PALE=(249,249,248)
FLOW_INK=(55,55,55)

def ft(sz, bold=False, latin=False):
    if latin:
        return ImageFont.truetype(LATIN_BOLD if bold else LATIN, sz)
    return ImageFont.truetype(BOLD if bold else FONT, sz)
def canvas(w=2400,h=1350):
    im=Image.new("RGB",(w,h),"white"); return im,ImageDraw.Draw(im)
def tx(d,x,y,s,sz=32,color=INK,bold=False,anchor=None):
    text = str(s)
    latin = any("A" <= c <= "z" for c in text) and all(ord(c) < 128 for c in text)
    d.text((x,y),text,font=ft(sz,bold,latin=latin),fill=color,anchor=anchor)
def title(d,w,name,sub=""):
    # 标题与第一层流程框之间保留明显留白，避免版式拥挤。
    tx(d,w//2,45,name,52,bold=True,anchor="mm")
    if sub: tx(d,w//2,112,sub,29,MUTED,anchor="mm")
def save(im,name): im.save(OUT/name,dpi=(360,360))
def box(d,xy,header,body="",accent=BLUE):
    x0,y0,x1,y1=xy
    # 流程图采用参考论文的白底黑框、细线与紧凑排版；不使用彩色卡片。
    d.rectangle(xy,fill="white",outline=FLOW_INK,width=2)
    d.line((x0,y0,x1,y0),fill=FLOW_INK,width=3)
    tx(d,(x0+x1)//2,y0+39,header,32,FLOW_INK,True,anchor="mm")
    if body:
        lines=body.split("\n")
        for j,line in enumerate(lines):
            tx(d,(x0+x1)//2,y0+86+j*34,line,25,FLOW_INK,anchor="mm")
def arrow(d,x0,y0,x1,y1,color=MUTED,width=5):
    # 所有流程图箭头统一黑色，减少视觉噪声并贴近论文排版。
    color=FLOW_INK
    d.line([x0,y0,x1,y1],fill=color,width=width)
    a=math.atan2(y1-y0,x1-x0)
    r=21
    left=(x1-r*math.cos(a-0.45),y1-r*math.sin(a-0.45))
    right=(x1-r*math.cos(a+0.45),y1-r*math.sin(a+0.45))
    d.polygon([left,(x1,y1),right],fill=color)

def overview():
    W,H=2400,1560; im,d=canvas(W,H)
    title(d,W,"三问数据与计算路径","附件—模型—输出")
    # Repeat shared attachments in each lane so arrows do not imply a false input.
    box(d,(80,195,670,470),"问题一输入","1.csv＋4.csv：化学与感官\n3.xlsx：52位置评分卡\n8.xlsx：乙醛校准浓度",BLUE)
    box(d,(905,195,1495,470),"问题二输入","1.csv＋4.csv：直接关联\n2.csv：化学秩相关图\n6.csv、8.xlsx：核验与注释",TEAL)
    box(d,(1730,195,2320,470),"问题三输入","1.csv＋4.csv：化学与感官\n8.xlsx：阈值与校准\n问题一预测器：代理画像",RUST)
    # Three work lanes
    box(d,(80,640,670,875),"问题一：感官推定等级","238开发＋12留出；50项回归\n乙醛2项阈值外推→52项",BLUE)
    box(d,(905,640,1495,875),"问题二：统计关联候选","231节点共表达；217项候选\n50维×Top-3；200次重抽样",TEAL)
    box(d,(1730,640,2320,875),"问题三：风格条件谱","226基础＋5派生；22×50生成\n11款淡色艾尔/拉格→三料啤酒",RUST)
    arrow(d,375,470,375,635,BLUE)
    arrow(d,1200,470,1200,635,TEAL)
    arrow(d,2025,470,2025,635,RUST)
    # output/validation band
    for x0,x1,s,c in [(80,670,"12张回填评分卡\n50项留出对照",BLUE),(905,1495,"150条候选清单\n稳定性与化学审查",TEAL),(1730,2320,"1100条生成谱＋11条迁移\n风格/缺陷/派生式核验",RUST)]:
        d.rectangle((x0,1030,x1,1250),fill=PALE,outline=LIGHT,width=2)
        d.line((x0,1030,x1,1030),fill=FLOW_INK,width=3)
        for j,line in enumerate(s.split("\n")): tx(d,(x0+x1)//2,1090+j*64,line,31,INK,anchor="mm")
    for x in [375,1200,2025]: arrow(d,x,875,x,1022)
    tx(d,W//2,1385,"输出维数：问题一52项；问题二150条；问题三1100条生成谱与11条迁移谱。",28,MUTED,anchor="mm")
    save(im,"fig01_three_questions_route.png")

def missingness():
    chem=pd.read_csv(DATA/"1.csv")
    miss=chem.iloc[:,3:].isna().sum().sort_values(ascending=False)
    miss=miss[miss>0]
    assert int(miss.sum())==73 and len(miss)==9
    alias={"amyl.acetate":"戊醇乙酸酯","aroma_hops_sum":"酒花香气总指标","methylpyrazine":"甲基吡嗪",
           "X2.3.butanedione":"双乙酰","X3.methylbutanal":"3-甲基丁醛","ethyl.nicotinate":"烟酸乙酯",
           "furfural":"糠醛","phenylacetaldehyde":"苯乙醛","ethyl.isobutyrate":"异丁酸乙酯"}
    W,H=2400,1440; im,d=canvas(W,H)
    title(d,W,"化学特征缺失值分布","缺失数量（格）")
    x0,x1=660,2190; y0=260; row=112; xmax=30
    for tick in [0,5,10,15,20,25,30]:
        x=x0+(x1-x0)*tick/xmax
        d.line([x,y0-10,x,y0+len(miss)*row+5],fill=LIGHT,width=2)
        tx(d,x,y0-32,tick,27,MUTED,anchor="mb")
    for i,(name,value) in enumerate(miss.items()):
        y=y0+i*row+34
        tx(d,x0-24,y,alias.get(name,name),30,INK,anchor="rm")
        x=x0+(x1-x0)*value/xmax
        d.rectangle((x0,y-27,x,y+27),fill=BLUE)
        tx(d,x+14,y,int(value),30,INK,True,anchor="lm")
    save(im,"fig02_missingness.png")

def q1_pipeline():
    W,H=2600,1900; im,d=canvas(W,H)
    title(d,W,"问题一评分与核验流程")
    x0,x1=820,1780
    stages=[
        (120,270,"01  数据接入与主键对齐","1.csv 250×231；4.csv 250×50；按 beer 对齐",BLUE),
        (310,460,"02  字段分组与量纲统一","理化、半定量、校准、派生四组；逐列核验 log10/原始量",TEAL),
        (500,650,"03  异常、缺失与派生量处理","LOD/2；尾部断层识别；公式补全；风格内迭代插补",BLUE),
        (690,840,"04  风格分层与折外验证","22种风格；分层五折；预处理参数只在训练折估计",TEAL),
        (880,1030,"05  候选模型比较与冻结","14个候选模型；50个连续目标；OOF MAE 0.339",BLUE),
        (1070,1220,"06  重拟合与目标样本预测","冻结预处理与模型；啤酒1—12；输出50项连续感官量",TEAL),
        (1260,1410,"07  锚点映射与评分卡交付","分位锚点映射0—6级；方差匹配；乙醛2项阈值外推",BLUE),
    ]
    for y0,y1,h,b,c in stages: box(d,(x0,y0,x1,y1),h,b,c)
    for i in range(len(stages)-1):
        arrow(d,(x0+x1)//2,stages[i][1]+4,(x0+x1)//2,stages[i+1][0]-8,BLUE)
    # 侧向分支对应实际核验和辅助文件，主链仍保持单向。
    box(d,(70,310,630,460),"附件8：量纲校验","校准浓度、阈值、化合物名称\n不直接作为感官标签",RUST)
    arrow(d,630,385,x0-8,385,RUST)
    box(d,(1930,500,2530,650),"异常识别分支","上尾断层、倍数级跳变\n与风格内离群点复核",RUST)
    arrow(d,x1+8,575,1930,575,RUST)
    box(d,(1930,690,2530,840),"交叉验证边界","缺失填补、标准化、截尾\n均在训练折内拟合",RUST)
    arrow(d,x1+8,765,1930,765,RUST)
    box(d,(70,1260,630,1410),"附件3：评分卡模板","啤酒1—12；每张52个位置\n按原始行列顺序回填",RUST)
    arrow(d,630,1335,x0-8,1335,RUST)
    box(d,(1930,1260,2530,1410),"乙醛无标签处理","两项不参与有监督训练\n按校准阈值外推0—6级",RUST)
    arrow(d,x1+8,1335,1930,1335,RUST)
    tx(d,W//2,1665,"238款进入开发；12款作为目标样本；50项连续感官量映射为52个评分卡位置。",28,MUTED,anchor="mm")
    save(im,"fig03_q1_pipeline.png")

def q2_pipeline():
    W,H=2600,1850; im,d=canvas(W,H)
    title(d,W,"问题二关联候选的计算流程")
    x0,x1=820,1780
    stages=[
        (120,270,"01  统一样本与字段字典","1.csv×4.csv；231个化学节点；50个感官目标",BLUE),
        (310,460,"02  Spearman相关网络","保留符号与连续权重；|ρ|≥0.65；168条边",TEAL),
        (500,650,"03  候选资格与去冗余","剔除14项合计量、派生量与内标；保留217项候选",RUST),
        (690,840,"04  逐维解释模型","每个感官维度单独训练GBR；TreeSHAP得到化学贡献",BLUE),
        (880,1030,"05  直接关联与网络融合","0.70直接关联＋0.30网络信号；每维保留Top-3",TEAL),
        (1070,1220,"06  分层Bootstrap稳定性","按风格分层重抽样200次；记录入选频率与集合Jaccard",BLUE),
        (1260,1410,"07  来源审查与结果交付","化学来源、名称与阈值复核；输出50维×3项候选",TEAL),
    ]
    for y0,y1,h,b,c in stages: box(d,(x0,y0,x1,y1),h,b,c)
    for i in range(len(stages)-1):
        arrow(d,(x0+x1)//2,stages[i][1]+4,(x0+x1)//2,stages[i+1][0]-8,BLUE)
    box(d,(70,310,630,460),"2.csv核对结果","阈值|ρ|≥0.65：168条边\n167条正相关、1条负相关",RUST)
    arrow(d,630,385,x0-8,385,RUST)
    box(d,(1930,690,2530,840),"解释分支","完整化学输入训练GBR\nTreeSHAP、局部响应与方向核验",RUST)
    arrow(d,x1+8,765,1930,765,RUST)
    box(d,(1930,1070,2530,1220),"稳定性分支","入选频率、Top-3 Jaccard\n随机种子与风格层敏感性",RUST)
    arrow(d,x1+8,1145,1930,1145,RUST)
    box(d,(70,1260,630,1410),"8.xlsx后验解释","校准浓度、阈值与名称\n不作为相关网络标签",RUST)
    arrow(d,630,1335,x0-8,1335,RUST)
    tx(d,W//2,1665,"共表达网络168条边；候选池217项；最终交付50个感官维度的Top-3清单。",28,MUTED,anchor="mm")
    save(im,"fig08_q2_pipeline.png")

def q2_stability():
    df=pd.read_csv(Q2/"results/q2_stability_summary.csv")
    vals=df.mean_selection_frequency.sort_values().to_numpy()
    W,H=2400,1320; im,d=canvas(W,H)
    title(d,W,"50个感官维度的Top-3稳定度","横轴：平均入选频率")
    bins=[0,0.2,0.4,0.6,0.8,1.0001]
    counts=[int(((vals>=bins[i])&(vals<bins[i+1])).sum()) for i in range(5)]
    x0,yb=280,1030; bw=300; gap=100; maxn=max(counts)+2
    for tick in range(0,maxn+1,5):
        y=yb-650*tick/maxn
        d.line([x0-40,y,2200,y],fill=LIGHT,width=2)
        tx(d,x0-55,y,tick,28,MUTED,anchor="rm")
    for i,n in enumerate(counts):
        x=x0+i*(bw+gap)
        h=650*n/maxn
        d.rectangle((x,yb-h,x+bw,yb),fill=BLUE)
        tx(d,x+bw//2,yb-h-24,n,33,INK,True,anchor="mb")
        tx(d,x+bw//2,yb+28,f"{bins[i]:.1f}—{bins[i+1]:.1f}",29,INK,anchor="mt")
    mean=float(df.mean_selection_frequency.mean())
    j=float(df.mean_final_bootstrap_jaccard.mean())
    tx(d,W//2,1200,f"平均入选频率 {mean:.3f}；平均集合Jaccard {j:.3f}（200次完整流程重抽样）",31,MUTED,anchor="mm")
    save(im,"fig09_q2_stability.png")

def q2_named_anchors():
    df=pd.read_csv(Q2/"audit/q2_named_chemical_anchor_audit.csv")
    order=["alcohol","X4vg","lactic","acetic","co2","A_esters_ethac","F_esters_ethac","dms","diacetyl","t2n"]
    df=df.set_index("dimension").loc[order].reset_index()
    labels={"alcohol":"酒精感—乙醇","X4vg":"4VG感—4VG","lactic":"乳酸感—乳酸","acetic":"乙酸感—乙酸","co2":"气泡感—CO₂",
            "A_esters_ethac":"乙酸乙酯香—乙酸乙酯","F_esters_ethac":"乙酸乙酯味—乙酸乙酯","dms":"DMS感—DMS","diacetyl":"双乙酰感—双乙酰","t2n":"纸板陈味—反式壬烯醛"}
    W,H=2400,1650; im,d=canvas(W,H)
    title(d,W,"直接命名化合物与对应感官项的关联","蓝：进入Top-3；灰：未进入")
    x0=710; x1=2110; zero=1450; maxrho=0.9; top=260; row=125
    d.line([zero,top-25,zero,top+len(df)*row],fill=INK,width=3)
    for i,r in df.iterrows():
        y=top+i*row+45
        tx(d,x0-20,y,labels[r.dimension],30,INK,anchor="rm")
        rho=float(r.direct_spearman)
        xx=zero+(x1-zero)*rho/maxrho if rho>=0 else zero+(zero-x0)*rho/maxrho
        color=BLUE if bool(r.in_selected_top3) else (153,161,170)
        d.rectangle((min(xx,zero),y-21,max(xx,zero),y+21),fill=color)
        tx(d,xx+15 if rho>=0 else xx-15,y,f"{rho:+.3f}",29,INK,anchor="lm" if rho>=0 else "rm")
    tx(d,zero,top-55,"0",28,MUTED,anchor="mb")
    save(im,"fig10_q2_named_anchor.png")

def q3_pipeline():
    W,H=2600,2100; im,d=canvas(W,H)
    title(d,W,"问题三生成与迁移的可复现路径")
    x0,x1=820,1780
    stages=[
        (120,270,"01  样本矩阵与字段字典","250款×231列；226个基础变量＋5个派生变量",BLUE),
        (310,460,"02  编码、量纲与派生量重建","log10/原始量分组；LOD/2；派生变量按公式重算",TEAL),
        (500,650,"03  秩正态化与PCA潜空间","经验分布→高斯分数；65维保留90.15%方差",BLUE),
        (690,840,"04  风格条件分布估计","22种风格；均值与协方差收缩；控制小样本不稳定",TEAL),
    ]
    for y0,y1,h,b,c in stages: box(d,(x0,y0,x1,y1),h,b,c)
    for i in range(len(stages)-1):
        arrow(d,(x0+x1)//2,stages[i][1]+4,(x0+x1)//2,stages[i+1][0]-8,BLUE)
    # 共享潜空间之后分成“条件生成”和“风格迁移”两条支线。
    d.line([(x0+x1)//2,840,(x0+x1)//2,900],fill=FLOW_INK,width=3)
    d.line([(540,900),(2060,900)],fill=FLOW_INK,width=3)
    tx(d,795,930,"条件生成支线",30,FLOW_INK,True,anchor="mm")
    tx(d,1805,930,"风格迁移支线",30,FLOW_INK,True,anchor="mm")
    box(d,(80,970,1040,1130),"05A  风格条件抽样","22种风格分别抽取50个潜空间样本\n形成1100条候选化学谱",TEAL)
    box(d,(1560,970,2520,1130),"05B  目标风格定位","淡色艾尔/拉格源谱；估计目标三料啤酒\n方向由感官画像与化学层共同确定",RUST)
    arrow(d,540,900,540,962,TEAL)
    arrow(d,2060,900,2060,962,RUST)
    box(d,(80,1170,1040,1330),"06A  逆变换与统一评分","恢复原始量纲；重算5个派生量\n调用冻结评分器生成50维代理感官画像",TEAL)
    box(d,(1560,1170,2520,1330),"06B  潜空间迁移优化","高斯潜空间移动；距离、稀疏度与协同变化\nSLSQP求解并保留可解释改动",RUST)
    arrow(d,560,1130,560,1162,TEAL)
    arrow(d,2040,1130,2040,1162,RUST)
    box(d,(80,1370,1040,1530),"07A  生成谱筛选与检验","留出距离、风味指纹、多样性与约束核验\n输出可复现实验候选谱",TEAL)
    box(d,(1560,1370,2520,1530),"07B  缺陷约束与迁移检验","DMS、双乙酰、4VG等阈值约束\n逐样本复核感官改善与缺陷不恶化",RUST)
    arrow(d,560,1330,560,1362,TEAL)
    arrow(d,2040,1330,2040,1362,RUST)
    box(d,(80,1570,1040,1730),"08A  输出：风格候选谱","1100×231化学谱；50维感官画像\n生成结果与实测留出样本并列比较",TEAL)
    box(d,(1560,1570,2520,1730),"08B  输出：迁移方案","11×231迁移谱；目标距离、缺陷审计\n逐步记录迁移前后变化",RUST)
    arrow(d,560,1530,560,1562,TEAL)
    arrow(d,2040,1530,2040,1562,RUST)
    tx(d,W//2,1900,"共享输入：226个基础变量＋5个派生变量；生成支线覆盖22种风格，迁移支线覆盖11个源样本。",28,MUTED,anchor="mm")
    save(im,"fig12_q3_pipeline.png")

def q3_holdout():
    df=pd.read_csv(Q3/"results/q3_holdout_validation.csv")
    W,H=2400,1340; im,d=canvas(W,H)
    title(d,W,"三种目标风格的真实留出与生成谱检验")
    styles=["Tripel","Kriek","Lambic"]; style_cn={"Tripel":"三料啤酒","Kriek":"樱桃兰比克","Lambic":"兰比克"}; x0=290; group=650; yb=1020; top=295
    for tick in [0,.25,.5,.75,1.0]:
        y=yb-(yb-top)*tick
        d.line([x0-65,y,2300,y],fill=LIGHT,width=2)
        tx(d,x0-80,y,f"{tick:.2f}",27,MUTED,anchor="rm")
    for i,style in enumerate(styles):
        r=df[df["style"]==style].iloc[0]
        cx=x0+280+i*group
        for offset,val,color,label in [(-85,r.real_centroid_hit,BLUE,"真实留出"),(85,r.generated_centroid_hit,TEAL,"生成谱")]:
            h=(yb-top)*float(val)
            d.rectangle((cx+offset-58,yb-h,cx+offset+58,yb),fill=color)
            tx(d,cx+offset,yb-h-20,f"{val:.3f}",30,INK,True,anchor="mb")
        tx(d,cx,yb+27,f"{style_cn[style]}（真值{int(r.n_holdout)}款）",32,INK,anchor="mt")
    d.rectangle((570,166,605,201),fill=BLUE); tx(d,620,183,"真实留出谱",29,INK,anchor="lm")
    d.rectangle((915,166,950,201),fill=TEAL); tx(d,965,183,"模型生成谱",29,INK,anchor="lm")
    save(im,"fig13_q3_holdout.png")

def q3_migration():
    df=pd.read_csv(Q3/"results/q3_transfer_validation.csv")
    W,H=2400,1340; im,d=canvas(W,H)
    title(d,W,"11款淡色艾尔/拉格向三料啤酒迁移的模型内距离")
    x_before,x_after=620,1790; top,bottom=260,1090; vmin,vmax=6,18
    for tick in [6,8,10,12,14,16,18]:
        y=bottom-(tick-vmin)/(vmax-vmin)*(bottom-top)
        d.line([390,y,2020,y],fill=LIGHT,width=2)
        tx(d,370,y,tick,28,MUTED,anchor="rm")
    for r in df.itertuples():
        y0=bottom-(r.distance_to_Tripel_before-vmin)/(vmax-vmin)*(bottom-top)
        y1=bottom-(r.distance_to_Tripel_after-vmin)/(vmax-vmin)*(bottom-top)
        d.line([x_before,y0,x_after,y1],fill=(145,177,198),width=4)
        d.ellipse([x_before-11,y0-11,x_before+11,y0+11],fill=BLUE)
        d.ellipse([x_after-11,y1-11,x_after+11,y1+11],fill=TEAL)
    b=float(df.distance_to_Tripel_before.mean()); a=float(df.distance_to_Tripel_after.mean())
    for x,val,color in [(x_before,b,BLUE),(x_after,a,TEAL)]:
        y=bottom-(val-vmin)/(vmax-vmin)*(bottom-top)
        d.ellipse([x-25,y-25,x+25,y+25],fill=color,outline=INK,width=2)
        tx(d,x+36,y,f"均值 {val:.2f}",32,color,True,anchor="lm")
    tx(d,x_before,bottom+32,"来源谱",33,INK,anchor="mt")
    tx(d,x_after,bottom+32,"迁移谱",33,INK,anchor="mt")
    n_total = len(df)
    n_improved = int((df["distance_to_Tripel_after"] < df["distance_to_Tripel_before"] - 1e-10).sum())
    n_unchanged = n_total - n_improved
    mean_drop = 100.0 * (1.0 - a / b) if b else 0.0
    tx(d,W//2,1250,
       f"严格缩短：{n_improved}/{n_total}；均值降幅：{mean_drop:.2f}%；保持原谱：{n_unchanged}/{n_total}",
       28,MUTED,anchor="mm")
    save(im,"fig15_q3_migration.png")

def q3_markers():
    df=pd.read_csv(Q3/"results/q3_style_marker_summary.csv")
    chosen=[("Tripel","ethanol..v.v.","三料啤酒酒精度（%）"),
            ("Kriek","lactic_acid.mg.L.","樱桃兰比克乳酸（mg/L）"),
            ("Lambic","lactic_acid.mg.L.","兰比克乳酸（mg/L）")]
    W,H=2400,1020; im,d=canvas(W,H)
    title(d,W,"三种风格的实测与生成标志物中位数","单位见行标签")
    x0,x1=870,2100; row_y=[315,555,795]
    for idx,(sty,field,name) in enumerate(chosen):
        r=df[(df["style"]==sty)&(df["field"]==field)].iloc[0]
        a=float(r.observed_median_physical); b=float(r.generated_median_physical)
        xmax=max(a,b)*1.25
        y=row_y[idx]
        tx(d,x0-50,y,name,34,INK,True,anchor="rm")
        d.line([x0,y+77,x1,y+77],fill=LIGHT,width=2)
        for off,val,col,label in [(-43,a,BLUE,"实测"),(27,b,TEAL,"生成")]:
            x=x0+(x1-x0)*val/xmax
            d.rectangle((x0,y+off-20,x,y+off+20),fill=col)
            tx(d,x+15,y+off,f"{val:.1f}",30,INK,True,anchor="lm")
            tx(d,x0-15,y+off,label,27,MUTED,anchor="rm")
    save(im,"fig14_q3_markers.png")

def q3_sensitivity():
    df=pd.read_csv(Q3/"results/q3_noise_sensitivity.csv")
    W,H=2400,1200; im,d=canvas(W,H)
    title(d,W,"风格收缩强度的敏感性","蓝：质心命中率；红：距离比")
    styles=["Tripel","Kriek","Lambic"]; style_cn={"Tripel":"三料啤酒","Kriek":"樱桃兰比克","Lambic":"兰比克"}
    for sidx,sty in enumerate(styles):
        part=df[df["style"]==sty].sort_values("global_share")
        x0=145+sidx*760; x1=x0+600; y0=900; ytop=300
        tx(d,(x0+x1)//2,230,style_cn[sty],40,INK,True,anchor="mm")
        for tick in [0,.25,.5,.75,1]:
            y=y0-(y0-ytop)*tick
            d.line([x0,y,x1,y],fill=LIGHT,width=2)
            if sidx==0: tx(d,x0-13,y,f"{tick:.2f}",25,MUTED,anchor="rm")
        vals=part.global_share.to_list()
        xa=[x0+(x1-x0)*(v-min(vals))/(max(vals)-min(vals)) for v in vals]
        for field,col,dash in [("generated_centroid_hit",BLUE,False),("distance_ratio_generated_to_train_over_holdout_to_train",RUST,True)]:
            ys=[y0-(y0-ytop)*float(v) for v in part[field]]
            for i in range(len(xa)-1):
                if dash:
                    for f in [0,.5]:
                        xA=xa[i]+(xa[i+1]-xa[i])*f; xB=xa[i]+(xa[i+1]-xa[i])*(f+.25)
                        yA=ys[i]+(ys[i+1]-ys[i])*f; yB=ys[i]+(ys[i+1]-ys[i])*(f+.25)
                        d.line([xA,yA,xB,yB],fill=col,width=5)
                else: d.line([xa[i],ys[i],xa[i+1],ys[i+1]],fill=col,width=5)
            for x,y in zip(xa,ys): d.ellipse([x-9,y-9,x+9,y+9],fill=col)
        for x,v in zip(xa,vals): tx(d,x,y0+35,f"{v:.2f}",27,MUTED,anchor="mt")
    d.line([560,1055,650,1055],fill=BLUE,width=6); tx(d,660,1055,"生成质心命中率",28,INK,anchor="lm")
    d.line([1100,1055,1190,1055],fill=RUST,width=6); tx(d,1200,1055,"相对训练距离比",28,INK,anchor="lm")
    save(im,"fig14b_q3_sensitivity.png")

def q3_sensory_profile():
    df=pd.read_csv(Q3/"results/q3_target_style_sensory_summary.csv").set_index("style")
    fields=[("alcohol","酒精感"),("acidity","酸感"),("lactic","乳酸感"),
            ("bitternes","苦味"),("sweetness","甜味"),("body","酒体")]
    styles=[("Tripel","三料啤酒",BLUE),("Kriek","樱桃兰比克",RUST),("Lambic","兰比克",TEAL)]
    W,H=2400,1180; im,d=canvas(W,H)
    title(d,W,"三种风格生成谱的代理感官画像","横轴：0—6代理等级均值")
    x0,x1=610,2120; y0=295; row=126
    for tick in range(7):
        x=x0+(x1-x0)*tick/6
        d.line([x,y0-44,x,y0+5*row+85],fill=LIGHT,width=2)
        tx(d,x,y0-60,tick,27,MUTED,anchor="mb")
    for i,(field,label) in enumerate(fields):
        y=y0+i*row
        tx(d,x0-60,y,label,36,INK,True,anchor="rm")
        if i<5: d.line([180,y+row/2,2230,y+row/2],fill=LIGHT,width=1)
        for j,(style,_,color) in enumerate(styles):
            val=float(df.loc[style,"proxy_score_"+field]); yy=y+(j-1)*26
            x=x0+(x1-x0)*val/6
            d.ellipse([x-13,yy-13,x+13,yy+13],fill=color)
            tx(d,x+24,yy,f"{val:.2f}",28,color,anchor="lm")
    for j,(_,label,color) in enumerate(styles):
        x=475+j*630
        d.ellipse([x-12,1090-12,x+12,1090+12],fill=color)
        tx(d,x+26,1090,label,30,INK,anchor="lm")
    save(im,"fig14c_q3_sensory_profile.png")

def q3_defects():
    df=pd.read_csv(Q3/"results/q3_defect_audit.csv")
    alias={"DMS":"二甲基硫","X2.3.butanedione":"双乙酰","X4VG":"4VG","X.E..2.nonenal":"反式-2-壬烯醛","A_hops_stale":"陈腐酒花","stale_hops proxy score":"陈腐酒花代理评分"}
    W,H=2400,1050; im,d=canvas(W,H)
    title(d,W,"迁移前后缺陷超线数量","计数/可核查样本数")
    x0,x1=770,2060; y0=300; step=130
    for i,r in enumerate(df.itertuples()):
        y=y0+i*step
        tx(d,x0-40,y,alias.get(r.defect,r.defect),34,INK,anchor="rm")
        nobs=int(r.n_observed_source); before=round(float(r.source_over_rate)*nobs); after=round(float(r.migrated_over_rate)*nobs)
        for off,val,col,label in [(-32,before,BLUE,"迁移前"),(32,after,TEAL,"迁移后")]:
            x=x0+(x1-x0)*val/11
            d.rectangle((x0,y+off-17,max(x0+3,x),y+off+17),fill=col)
            tx(d,x+13,y+off,f"{val}/{nobs}",30,INK,True,anchor="lm")
    save(im,"fig16_q3_defects.png")

def main():
    overview(); missingness(); q1_pipeline(); q2_pipeline(); q2_stability(); q2_named_anchors()
    q3_pipeline(); q3_holdout(); q3_markers(); q3_sensory_profile(); q3_sensitivity(); q3_migration(); q3_defects()

if __name__=="__main__": main()

