# MathorCup 赛道 A 代码与复现说明

本文档是当前代码交付目录的总说明，描述项目结构、入口脚本、数据流、三个问题的计算逻辑、结果文件、审计文件、可视化流程和复现边界。项目保留原始论文、原始附件、既有 solve/verify 脚本、审计文件和正式结果文件；新增入口只负责编排和检查，不改变模型公式、随机种子或科学口径。

## 1. 项目定位与计算边界

本项目对应 MathorCup 大数据竞赛赛道 A 的三个问题：

- **问题一**：使用化学谱和感官连续标签训练树模型集成，输出 50 个感官维度的连续预测、0—6 代理等级和 52 项评分卡。
- **问题二**：从化学变量与感官维度之间的统计关联中筛选每个维度的 Top-3 候选，并通过 bootstrap、同源数据对照和来源审计检查稳定性。
- **问题三**：在化学谱的分位数/PCA 表示空间中进行风格条件生成，并对 Pils/Lager 到 Tripel 的迁移方案执行缺陷约束和独立审计。

以下口径属于项目定义的一部分：

1. 问题一的 0—6 分是由连续预测映射得到的代理评分，不是原始人工评分准确率。
2. 问题二的 Top-3 是统计关联候选，不代表因果化合物。
3. 问题三的生成谱和迁移谱是模型内候选，不等同于真实酿造、化学复测或盲评结果。
4. Beer 1—12 是事后留出核验对象；不能称为全新外部测试集。
5. `6.csv` 与 `2.csv` 属于同源或同研究数据核验，不能作为独立外部验证。

## 2. 目录结构

```text
代码/
├─ 03_原始附件/                         原始输入，只读
│  ├─ 1.csv                            化学特征数据
│  ├─ 2.csv                            化合物相关矩阵或题面提供的关联数据
│  ├─ 3.xlsx                           评分卡/模板相关工作簿
│  ├─ 4.csv                            感官连续标签
│  ├─ 5.csv、6.csv、7.csv              辅助关联、核验或说明数据
│  ├─ 8.xlsx                           阈值、字段元数据和校准信息
│  └─ 数据说明.txt
│
├─ 项目代码/
│  ├─ A_problem1_v3_trees/              问题一
│  │  ├─ data/                          Q1 旧脚本需要的兼容数据副本
│  │  ├─ src/                           Q1 solve、预测器、提取和评分卡脚本
│  │  ├─ results/                       Q1 最终结果
│  │  ├─ audit/                         Q1 模型比较、OOF 和留出审计
│  │  └─ run_problem1_v3.ps1            原始 PowerShell 入口，保留
│  │
│  └─ A_full_solution_v4/
│     ├─ shared/                        Q1 预测器和 Q3 兼容函数
│     ├─ q2/
│     │  ├─ src/                        Q2 solve、verify、网络图脚本
│     │  ├─ results/                     Q2 Top-3 和稳定性结果
│     │  └─ audit/                       Q2 bootstrap、网络和科学审计
│     └─ q3/
│        ├─ src/                        Q3 solve、verify、迁移和 C2ST 脚本
│        ├─ results/                     Q3 生成、迁移、缺陷和敏感性结果
│        ├─ audit/                       Q3 派生量、模型和独立检查
│        └─ audit/                       Q3 审计与复核文件
│
├─ 可视化代码/
│  ├─ make_heatmap_q1_matplotlib_v4.py  Q1 12×52 热力图
│  ├─ make_q1_dimension_audit.py        Q1 逐维审计图
│  ├─ make_q1_local_contribution_beeswarm.py
│  ├─ make_q2_frequency_matplotlib.py   Q2 Top-3 频率热力图
│  ├─ make_q3_beer230_transfer_profile.py
│  ├─ make_rest_figures.py               Q2/Q3 其余保留图表
│  └─ 图表/                     当前保留的图片输出
│
├─ run_all.py                            Q1/Q2/Q3 统一 solve 编排
├─ verify_all.py                         统一只读验证
├─ verify_q1.py                          Q1 评分卡和指标验证
├─ smoke_test.py                         Q2/Q3 最小规模真实重算
├─ run_visualizations_manual.ps1         手动可视化入口
├─ activate_mathorcup.ps1                环境激活入口
├─ requirements.txt                      固定 Python 依赖
├─ figures_manifest.csv                  图片路径、哈希和字节数
└─ README.md                             本总说明
```

`A_problem1_v3_trees/data/` 中的 1.csv、3.xlsx、4.csv、8.xlsx 与 `03_原始附件/` 内容相同，但它们是旧 Q1 脚本的相对路径依赖。为了保证原 PowerShell 入口和旧脚本仍可运行，暂不删除这些兼容副本。

## 3. 独立运行环境

项目代码与虚拟环境分离：

```text
项目代码：D:\MathorCup\...\我的作答\代码
虚拟环境：D:\MathorCup\_environments\mathorcup-venv
Python：D:\MathorCup\Python311
```

当前固定依赖见 `requirements.txt`：

```text
numpy==2.2.6
pandas==2.2.3
scipy==1.14.1
scikit-learn==1.5.2
openpyxl==3.1.5
matplotlib==3.11.2
```

激活环境：

```powershell
Set-ExecutionPolicy -Scope Process Bypass
Set-Location "D:\MathorCup\...\我的作答\代码"
.\activate_mathorcup.ps1
python --version
python -m pip check
```

应看到 Python 3.11.9 和 `No broken requirements found.`。如果不使用激活脚本，也可以直接调用：

```powershell
& "D:\MathorCup\_environments\mathorcup-venv\Scripts\python.exe" your_script.py
```

## 4. 统一入口和运行顺序

### 4.1 只读检查，推荐首先执行

```powershell
python verify_q1.py `
  --input-dir .\03_原始附件 `
  --output-dir .\repro_runs

python smoke_test.py `
  --input-dir .\03_原始附件 `
  --output-dir .\repro_runs `
  --seed 20261025
```

Q1 验证包括：12 个评分卡工作表、每表 52 个评分位置、50 个感官列、2 个乙醛外推列、0—6 范围和总体指标。smoke test 会真正调用 Q2 的 Spearman/selector 和 Q3 的 PCA/条件生成器，不只是读取已有 CSV。

### 4.2 完整 solve 编排

```powershell
python run_all.py `
  --input-dir .\03_原始附件 `
  --output-dir .\repro_runs `
  --seed 20261025
```

`run_all.py` 的执行顺序为：

1. 调用 Q1 `solve_problem1_v3.py`；
2. 调用 Q2 `solve_q2.py --bootstrap 200`；
3. 调用 Q3 `solve_q3_v4.py`；
4. 记录 Python、依赖、操作系统、Git commit、输入 SHA-256、种子和耗时；
5. 比较关键 CSV 的形状和 SHA-256。

如果重算结果发生变化，入口会报告差异。不要在未经确认时把重算结果覆盖为正式交付结果。

### 4.3 统一验证

```powershell
python verify_all.py `
  --input-dir .\03_原始附件 `
  --output-dir .\repro_runs `
  --seed 20261025
```

该入口调用 Q1、Q2、Q3 的验证脚本，不负责重新训练模型。

## 5. 问题一：树模型、评分映射与评分卡

### 5.1 输入和样本划分

- `1.csv`：250 款啤酒的化学特征。
- `4.csv`：50 个连续感官目标。
- Beer 13—250：238 款开发集。
- Beer 1—12：12 款事后留出核验对象。
- 化学特征数：231。
- 感官连续目标数：50。
- 最终评分卡位置数：50 个感官位置 + 2 个乙醛外推位置 = 52。

### 5.2 模型和预处理

核心代码：

```text
项目代码/A_problem1_v3_trees/src/solve_problem1_v3.py
项目代码/A_problem1_v3_trees/src/q1_tree_predictor.py
```

主要流程：

1. 按 `beer` 主键对齐化学数据和感官数据。
2. 对开发集进行固定的风格分层五折划分。
3. 每个训练折独立拟合中位数填补和缺失指示变量。
4. 训练 ExtraTrees、RandomForest 和 GradientBoosting 三个树模型。
5. 使用固定随机种子和固定集成权重生成加权树模型预测。
6. 以开发集 OOF 结果计算 MAE、RMSE、合并中心化 R² 和代理等级一致性。
7. 使用开发集逐维 1%/99% 分位点作为 0—6 等级锚点。
8. 对 Beer 1—12 生成连续预测和代理整数评分。
9. 使用 `8.xlsx` 中的乙醛校准信息外推 `A_acetaldehyde` 和 `F_acetaldehyde`。
10. 由 `write_scorecards.py` 将 52 项分数回填到 Excel 模板。

### 5.3 Q1 主要文件

| 文件 | 作用 |
|---|---|
| `results/A_problem1_v3_continuous_predictions.csv` | 12 款啤酒的 50 个连续预测 |
| `results/A_problem1_v3_scores_50.csv` | 50 个感官代理评分 |
| `results/A_problem1_v3_scores_52.csv` | 50 个感官评分加 2 个乙醛评分 |
| `results/A_problem1_v3_scores.xlsx` | 12 张评分卡和 summary 工作表 |
| `audit/model_comparison.json` | 模型、五折和留出指标 |
| `audit/calibration_comparison.json` | 代理等级映射比较 |
| `audit/q1_holdout_summary.json` | Q1 总体指标 |
| `audit/q1_holdout_by_beer.csv` | 逐酒核验 |
| `audit/q1_holdout_by_dimension.csv` | 逐维核验 |
| `audit/acetaldehyde_sensitivity.csv` | 乙醛阈值敏感性 |

### 5.4 Q1 对账指标

当前审计基准包括：

```text
MAE                  0.37082957083529
合并中心化 R²        0.275857091297219
代理评分 ±1 级比例   83.00%
代理评分完全一致率   37.8333%
```

这些指标来自 `audit/q1_holdout_summary.json`，不能解释为原始人工评分准确率。

## 6. 问题二：统计关联、网络证据和 Top-3

核心代码：

```text
项目代码/A_full_solution_v4/q2/src/solve_q2.py
项目代码/A_full_solution_v4/q2/src/verify_q2.py
项目代码/A_full_solution_v4/q2/src/plot_q2_threshold_network.py
```

### 6.1 处理流程

1. 读取 `1.csv`、`4.csv`、`2.csv` 和 `8.xlsx` 元数据。
2. 按啤酒编号对齐 250 个样本；不使用经过浮点舍入的 `beer_id` 进行精确连接。
3. 排除汇总指标、非单体指标和内部标准，保留 217 个合格测量因素。
4. 计算化学变量与感官目标之间的逐维 Spearman 关联矩阵 `D`。
5. 从 `2.csv` 或重算相关矩阵建立带符号化合物网络。
6. 用网络传播证据和直接关联证据融合排序：

```text
N = 0.65D + 0.25PD + 0.10P²D
E = 0.70 × direct_evidence + 0.30 × network_evidence
```

7. 每个感官维度使用带冗余惩罚的贪心方法选出 3 个候选。
8. 进行 200 次 bootstrap：
   - 主流程：重采样啤酒、重建化合物图、重新执行完整选择；
   - 副流程：固定原始网络，只重算样本关联和选择。
9. 输出 Top-3、选择频率、Jaccard 稳定性、来源一致性和化学锚点审计。

### 6.2 Q2 主要文件

| 文件 | 作用 |
|---|---|
| `results/q2_top3_per_dimension.csv` | 50 个感官维度 × 3 个候选，共 150 行 |
| `results/q2_stability_summary.csv` | 逐维选择频率和 Jaccard |
| `audit/q2_candidate_pool.csv` | 候选因素和排除原因 |
| `audit/q2_bootstrap_selected_indices.npz` | bootstrap 选中索引 |
| `audit/q2_named_chemical_anchor_audit.csv` | DMS、二乙酰等命名锚点审计 |
| `audit/q2_6csv_same_source_comparison.csv` | `6.csv` 同源数值对照 |
| `audit/q2_style_adjusted_sensitivity.csv` | 风格调整敏感性 |
| `audit/q2_hyperparameter_sensitivity.csv` | 超参数敏感性 |
| `audit/q2_run_manifest.json` | 输入哈希、种子和汇总指标 |

典型核验结果为 150/150 Top-3 行、候选资格检查通过，平均最终 bootstrap Jaccard 约 0.358，平均 Top-3 选择频率约 0.475。

## 7. 问题三：PCA 条件生成和风格迁移

核心代码：

```text
项目代码/A_full_solution_v4/q3/src/solve_q3_v4.py
项目代码/A_full_solution_v4/q3/src/verify_q3_v4.py
项目代码/A_full_solution_v4/q3/src/q3_migration_sensitivity.py
项目代码/A_full_solution_v4/q3/src/q3_c2st_global.py
项目代码/A_full_solution_v4/shared/q1_tree_predictor.py
项目代码/A_full_solution_v4/shared/q3_compat.py
```

### 7.1 生成流程

1. 从 `1.csv` 读取 231 个化学字段。
2. 将 5 个派生字段与 226 个基础字段分开处理。
3. 用 `8.xlsx` 阈值和校准信息重建 OAV 聚合字段以及 `kcalperc`。
4. 对每个字段进行秩/分位数变换，再映射到近似正态空间。
5. 对训练数据执行 SVD/PCA，选择累计解释率达到 90% 的维数。
6. 按 Tripel、Kriek、Lambic 风格拟合条件分布。
7. 在每个风格内进行随机样本混合和受控噪声生成。
8. 生成 22 个风格 × 50 条谱，共 1100 条生成谱。
9. 对 Pils/Lager 样本执行到 Tripel 的约束迁移。
10. 检查派生字段重建、缺陷不增加、风格判别概率和距离变化。

### 7.2 Q3 主要文件

| 文件 | 作用 |
|---|---|
| `results/q3_generated_spectra.csv` | 1100 条生成化学谱 |
| `results/q3_generated_sensory_proxy.csv` | 生成谱的代理感官预测 |
| `results/q3_holdout_validation.csv` | 生成模型留出检查 |
| `results/q3_PilsLager_to_Tripel.csv` | 迁移后的 11 条候选方案 |
| `results/q3_transfer_validation.csv` | 迁移前后距离与缺陷对比 |
| `results/q3_defect_audit.csv` | 缺陷逐点不增加检查 |
| `results/q3_noise_sensitivity.csv` | 噪声强度敏感性 |
| `results/q3_migration_sensitivity.csv` | 迁移步长敏感性 |
| `audit/model_audit.json` | 模型设置和限制说明 |
| `audit/derived_reconstruction.csv` | 5 个派生字段重建误差 |
| `audit/verification_checks.csv` | 独立验证检查表 |
| `audit/q3_c2st_global.csv` | C2ST 全局分布检查 |

## 8. 可视化流程

可视化脚本只读取 `results`、`audit` 和 `03_原始附件`，不重新训练模型。推荐使用：

```powershell
.\run_visualizations_manual.ps1 -Clear
```

输出目录：

```text
可视化代码\图表
```

当前主要保留图表：

- `fig_q1_scorecard_heatmap_matplotlib_v4.png`：Q1 12×52 评分热力图。
- `fig_q1_dimension_aroma.png`、`fig_q1_dimension_flavour.png`：Q1 逐维审计。
- `fig_q1_local_contribution_beeswarm.png`：Q1 局部贡献。
- `fig_q2_top3_frequency_heatmap.png`：Q2 Top-3 频率。
- `fig09_q2_stability.png`、`fig10_q2_named_anchor.png`：Q2 稳定性和化学锚点。
- `fig13_q3_holdout.png`、`fig14_q3_markers.png`、`fig14b_q3_sensitivity.png`、`fig14c_q3_sensory_profile.png`、`fig16_q3_defects.png`：Q3 生成、敏感性、感官画像和缺陷。
- `fig_q3_beer230_transfer_profile.png`：Q3 Beer 230 迁移画像。

`figures_manifest.csv` 记录保留图片的相对路径、SHA-256 和文件大小。已移除的评分卡四张分图不应通过脚本重新生成。

## 9. Solve、Verify、Audit、Results 的区别

| 类型 | 含义 | 典型位置 |
|---|---|---|
| Solve | 重新计算模型和结果 | `src/solve_*.py`、`run_all.py` |
| Verify | 对已有结果执行结构和数值检查 | `verify_q1.py`、`verify_all.py`、`src/verify_*.py` |
| Audit | 解释模型边界、稳定性、输入和派生量 | `audit/` |
| Results | 论文和交付使用的正式结果 | `results/` |

验证脚本不应被误认为重新训练脚本；审计文件也不应被当作新的模型输出。

## 10. 随机性、可审计性与运行元数据

项目固定使用种子 `20261025`。Q1 的树模型、Q2 的 bootstrap、Q3 的 holdout 和条件生成均应保持既有种子和参数。`run_all.py` 的运行元数据包括：

- Python 版本；
- NumPy、Pandas、SciPy、scikit-learn、openpyxl 等依赖版本；
- 操作系统；
- Git commit；
- 原始输入文件 SHA-256；
- 随机种子；
- 运行耗时；
- 关键结果文件运行前后 SHA-256 和行列数。



## 


