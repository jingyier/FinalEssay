from pathlib import Path
import os, textwrap
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.colors import LinearSegmentedColormap

FIG=Path(os.environ['FIG_DIR']); Q2=Path(os.environ['Q2_RESULTS'])
font_path='C:/Windows/Fonts/simsun.ttc'
font_manager.fontManager.addfont(font_path)
plt.rcParams['font.family']='SimSun'
plt.rcParams['axes.unicode_minus']=False

LABELS={
    'A_malt_all':'麦芽总','A_malt_grain':'谷物香','A_malt_bread':'面包香','A_malt_cara':'焦糖香','A_malt_burn':'焦糊香','A_hops_all':'酒花总','A_hops_citrus':'柑橘香','A_hops_tropical':'热带果香','A_hops_noble':'贵族酒花','A_hops_woody':'木质香','A_esters_all':'酯香总','A_esters_ethac':'乙酸乙酯香','A_esters_isoaa':'香蕉香','A_esters_flower':'花香','A_ester_fruity':'果香','A_acetaldehyde':'乙醛香','body':'酒体','bitternes':'苦味','co2':'气泡感','aftertaste':'余味','dms':'二甲硫醚','metallic':'金属味','4vg':'丁香酚味','orange':'橙皮','coriander':'芫荽','clove':'丁香','overall':'整体评价','F_malt_all':'麦芽味总','F_malt_grain':'谷物味','F_malt_bread':'面包味','F_malt_cara':'焦糖味','F_malt_burn':'焦糊味','F_hops_all':'酒花味总','F_hops_citrus':'柑橘味','F_hops_tropical':'热带果味','F_hops_noble':'贵族酒花味','F_hops_woody':'木质味','F_esters_all':'酯味总','F_esters_ethac':'乙酸乙酯味','F_esters_isoaa':'香蕉味','F_esters_flower':'花味','F_ester_fruity':'果味','F_acetaldehyde':'乙醛味','alcohol':'酒精感','sweetness':'甜味','acidity':'酸味','t2n':'陈旧纸味','diacetyl':'双乙酰味','stale_hops':'陈酒花味','lactic':'乳酸味','acetic':'乙酸味','barnyard':'牲畜棚味'}

df=pd.read_csv(Q2/'q2_top3_per_dimension.csv')
dims=list(df['dimension'].drop_duplicates())
rows=[]
for dim in dims:
  sub=df[df.dimension.eq(dim)].sort_values('rank')
  rows.append([(LABELS.get(dim,dim), str(r.feature), float(r.bootstrap_frequency_full_pipeline)) for r in sub.itertuples()])

fig,axes=plt.subplots(2,1,figsize=(12.4,14.6),gridspec_kw={'height_ratios':[1,1], 'hspace':0.30})
fig.patch.set_facecolor('white')
fig.suptitle('问题二 Top-3 候选入选频率',fontsize=20,fontweight='bold',y=0.992,color='#243447')
for panel,ax in enumerate(axes):
  subrows=rows[panel*25:(panel+1)*25]
  vals=np.array([[x[2] for x in row] for row in subrows])
  paper_cmap=LinearSegmentedColormap.from_list('paper_blue',['#EEF3F8','#C8D9E6','#8AAAC1','#4E789B','#1F4E79'])
  im=ax.imshow(vals,cmap=paper_cmap,vmin=0,vmax=1,aspect='auto')
  ax.set_xticks([0,1,2],['Top-1','Top-2','Top-3'],fontsize=11,fontweight='bold')
  ax.set_yticks(np.arange(len(subrows)),[r[0][0] for r in subrows],fontsize=9)
  ax.tick_params(axis='both',length=0,pad=5)
  ax.set_xticks(np.arange(-.5,3,1),minor=True); ax.set_yticks(np.arange(-.5,len(subrows),1),minor=True)
  ax.grid(which='minor',color='white',linewidth=1.5)
  ax.tick_params(which='minor',bottom=False,left=False)
  ax.set_title('香气与麦芽维度' if panel==0 else '口味与综合维度',loc='left',fontsize=12,fontweight='bold',color='#243447',pad=10)
  for i,row in enumerate(subrows):
    for j,(_,feature,val) in enumerate(row):
      label=f'{val:.2f}'
      color='white' if val>=0.56 else '#243447'
      ax.text(j,i,label,ha='center',va='center',fontsize=10.5,color=color,linespacing=1.05)
  for spine in ax.spines.values(): spine.set_visible(False)
cb=fig.colorbar(im,ax=axes.ravel().tolist(),fraction=0.022,pad=0.02,aspect=30)
cb.set_label('Bootstrap 入选频率',fontsize=10,labelpad=8)
cb.ax.tick_params(labelsize=9)
fig.savefig(FIG/'fig_q2_top3_frequency_heatmap.png',dpi=300,bbox_inches='tight',facecolor='white')
plt.close(fig)
print(FIG/'fig_q2_top3_frequency_heatmap.png')

