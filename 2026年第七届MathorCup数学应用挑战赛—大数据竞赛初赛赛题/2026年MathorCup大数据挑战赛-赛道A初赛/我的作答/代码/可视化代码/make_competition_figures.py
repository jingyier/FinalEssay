"""生成跨问题汇总图表，展示数据、模型和结果之间的衔接。"""

from pathlib import Path
import os, textwrap
import pandas as pd
from PIL import Image, ImageDraw, ImageFont

FIG = Path(os.environ['FIG_DIR'])
Q2 = Path(os.environ['Q2_RESULTS'])
FONT = Path('C:/Windows/Fonts/simsun.ttc')
FONT_LATIN = Path('C:/Windows/Fonts/times.ttf')
FONT_BOLD = Path('C:/Windows/Fonts/simhei.ttf') if Path('C:/Windows/Fonts/simhei.ttf').exists() else FONT

def font(size, bold=False, latin=False):
    path = FONT_LATIN if latin else (FONT_BOLD if bold else FONT)
    return ImageFont.truetype(str(path), size)

def wrap(s, width):
    s = str(s)
    return '\n'.join(textwrap.wrap(s, width=width, break_long_words=False, break_on_hyphens=False))

def color_for(v):
    # 颜色从蓝色过渡到青色再到黄色，输入 v 的范围为 [0, 1]。
    v=max(0,min(1,float(v)))
    stops=[(31,78,121),(31,145,140),(242,193,55)]
    if v<0.5:
        a,b=stops[0],stops[1]; t=v*2
    else:
        a,b=stops[1],stops[2]; t=(v-0.5)*2
    return tuple(round(a[i]*(1-t)+b[i]*t) for i in range(3))

def luminance(c):
    return 0.299*c[0]+0.587*c[1]+0.114*c[2]

LABELS={
    'A_malt_all':'麦芽总','A_malt_grain':'谷物香','A_malt_bread':'面包香','A_malt_cara':'焦糖香','A_malt_burn':'焦糊香','A_hops_all':'酒花总','A_hops_citrus':'柑橘香','A_hops_tropical':'热带果香','A_hops_noble':'贵族酒花','A_hops_woody':'木质香','A_esters_all':'酯香总','A_esters_ethac':'乙酸乙酯香','A_esters_isoaa':'香蕉香','A_esters_flower':'花香','A_ester_fruity':'果香','A_acetaldehyde':'乙醛香','body':'酒体','bitternes':'苦味','co2':'气泡感','aftertaste':'余味','dms':'二甲硫醚','metallic':'金属味','4vg':'丁香酚味','orange':'橙皮','coriander':'芫荽','clove':'丁香','overall':'整体评价','F_malt_all':'麦芽味总','F_malt_grain':'谷物味','F_malt_bread':'面包味','F_malt_cara':'焦糖味','F_malt_burn':'焦糊味','F_hops_all':'酒花味总','F_hops_citrus':'柑橘味','F_hops_tropical':'热带果味','F_hops_noble':'贵族酒花味','F_hops_woody':'木质味','F_esters_all':'酯味总','F_esters_ethac':'乙酸乙酯味','F_esters_isoaa':'香蕉味','F_esters_flower':'花味','F_ester_fruity':'果味','F_acetaldehyde':'乙醛味','alcohol':'酒精感','sweetness':'甜味','acidity':'酸味','t2n':'陈旧纸味','diacetyl':'双乙酰味','stale_hops':'陈酒花味','lactic':'乳酸味','acetic':'乙酸味','barnyard':'牲畜棚味'}

def make_frequency():
    df=pd.read_csv(Q2/'q2_top3_per_dimension.csv')
    df['dimension_label']=df['dimension'].map(LABELS).fillna(df['dimension'])
    df=df.sort_values(['dimension']).reset_index(drop=True)
    W,H=3000,2220
    im=Image.new('RGB',(W,H),'white'); d=ImageDraw.Draw(im)
    ink=(30,42,54); muted=(95,105,116); line=(210,216,222)
    d.text((W//2,55),'问题二 Top-3 候选的重采样入选频率',font=font(58,True),fill=ink,anchor='mm')
    d.text((W//2,112),'每个单元格为 200 次完整 Bootstrap 流程中的入选频率；颜色越亮表示越稳定',font=font(28),fill=muted,anchor='mm')
    left=360; top=175; row_h=39; col_w=820; header_h=65
    d.rectangle((left,top,left+col_w*3,top+header_h),fill=(38,76,115),outline=ink,width=2)
    d.text((left-25,top+header_h//2),'感官维度',font=font(28,True),fill=ink,anchor='rm')
    for j,label in enumerate(['Top-1','Top-2','Top-3']):
        d.text((left+col_w*j+col_w/2,top+header_h/2),label,font=font(30,True),fill='white',anchor='mm')
    dims=list(df['dimension'].drop_duplicates())
    for i,dim in enumerate(dims):
        row=df[df['dimension']==dim].iloc[0]
        y=top+header_h+i*row_h
        if i==25:
            d.line((left-25,y-3,left+col_w*3,y-3),fill=(30,42,54),width=4)
        d.text((left-25,y+row_h/2),row.dimension_label,font=font(24,True),fill=ink,anchor='rm')
        for j in [1,2,3]:
            cell=df[(df.dimension==row.dimension)&(df['rank']==j)].iloc[0]
            val=float(cell.bootstrap_frequency_full_pipeline)
            c=color_for(val)
            x0=left+col_w*(j-1); y0=y
            d.rectangle((x0,y0,x0+col_w-3,y0+row_h-2),fill=c,outline='white',width=1)
            name=str(cell.feature)
            label=f'{name}  {val:.2f}'
            d.text((x0+col_w/2,y0+row_h/2),label,font=font(22,latin=True),fill='white' if luminance(c)<150 else 'black',anchor='mm')
    # 图例及说明文字。
    ly=top+header_h+50*row_h+35
    d.text((left,ly),'频率',font=font(24,True),fill=ink)
    for k in range(11):
        v=k/10; x=left+90+k*95; c=color_for(v); d.rectangle((x,ly+3,x+95,ly+34),fill=c)
        if k in (0,5,10): d.text((x+47,ly+52),f'{v:.1f}',font=font(19,latin=True),fill=muted,anchor='mm')
    d.text((left,ly+88),'维度顺序按附件 4.csv；化学项使用机器字段名，完整名称、来源和方向见 Top-3 清单。',font=font(22),fill=muted)
    im.save(FIG/'fig_q2_top3_frequency_heatmap.png',dpi=(220,220))

def box(d,xy,text,fill,outline=(60,60,60),fs=28,bold=False):
    x0,y0,x1,y1=xy; d.rounded_rectangle(xy,radius=12,fill=fill,outline=outline,width=3)
    lines=text.split('\n'); h=fs+8
    total=h*len(lines)
    for i,line in enumerate(lines):
        d.text(((x0+x1)//2,y0+(y1-y0-total)//2+i*h),line,font=font(fs,bold),fill=(30,30,30),anchor='mm')

def arrow(d,xy,fill=(60,60,60),width=6):
    x0,y0,x1,y1=xy; d.line((x0,y0,x1,y1),fill=fill,width=width)
    import math
    ang=math.atan2(y1-y0,x1-x0); L=22
    p1=(x1-L*math.cos(ang-0.45),y1-L*math.sin(ang-0.45)); p2=(x1-L*math.cos(ang+0.45),y1-L*math.sin(ang+0.45))
    d.polygon([(x1,y1),p1,p2],fill=fill)

def make_flow():
    W,H=3200,1780
    im=Image.new('RGB',(W,H),'white'); d=ImageDraw.Draw(im)
    ink=(35,45,55); blue=(37,91,161); red=(191,72,72); green=(75,125,67); pale=(246,248,250)
    d.text((W//2,60),'三问统一计算路径',font=font(62,True),fill=ink,anchor='mm')
    box(d,(360,120,2840,235),'附件 1.csv 化学谱  +  附件 4.csv 感官标签',pale,ink,34,True)
    arrow(d,(1600,235,1600,300))
    box(d,(190,300,3010,430),'共享预处理：beer 主键对齐　|　尺度与缺失核验　|　训练折内填补　|　派生字段重算', (247,247,247),ink,28,True)
    starts=[180,1120,2060]; colors=[blue,red,green]; titles=['问题一  感官评分','问题二  关键化合物','问题三  风格生成']
    steps=[
        ['238款开发 / 12款留出','ET + RF + GB 加权集成','0—6 映射 + 乙醛外推','12张评分卡'],
        ['217项合格候选','Spearman + 共表达网络','融合、去冗余、200次 Bootstrap','50×3 Top-3 候选'],
        ['226基础列 + 5派生列','分位数变换 + PCA','22风格生成 + 约束迁移','1100条谱 + 11条方案']]
    for x,c,title,st in zip(starts,colors,titles,steps):
        box(d,(x,500,x+760,590),title,c,ink,34,True)
        for j,text in enumerate(st):
            y0=640+j*190; box(d,(x+50,y0,x+710,y0+115),text,pale,ink,28,False)
            if j<3: arrow(d,(x+380,y0+115,x+380,y0+175))
    # 三个问题之间的数据接口。
    box(d,(620,1430,2580,1518),'跨题接口：问题一代理感官预测 → 问题三画像与陈酒花约束；8.xlsx 阈值与注释 → 问题二审查 / 问题三缺陷约束',(236,241,246),ink,26,False)
    d.text((W//2,1660),'主线只保留计算顺序，审计细节放入支撑材料。',font=font(24),fill=(100,108,116),anchor='mm')
    im.save(FIG/'fig21_three_questions_route_simple.png',dpi=(220,220))

if __name__=='__main__':
    make_flow()
    print('generated',FIG/'fig21_three_questions_route_simple.png')
