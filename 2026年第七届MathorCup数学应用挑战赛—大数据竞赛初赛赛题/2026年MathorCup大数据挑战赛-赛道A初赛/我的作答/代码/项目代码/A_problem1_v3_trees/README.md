# 问题一：树模型修订工程

本工程从附带的原始 `1.csv`、`4.csv`、`3.xlsx`、`8.xlsx` 生成 12 张完整的 52 项评分卡，并输出可核查的连续预测、逐酒与逐维误差。原附件只复制到 `data/`；脚本不会修改它们。

## 一次运行

在 PowerShell 中执行 `./run_problem1_v3.ps1`。脚本依次核查 Excel 模板、拟合固定模型、回填工作簿。默认使用本机已具备 `pandas/openpyxl` 的 Python 3.12 及已具备 `numpy/pandas/scikit-learn` 的 Python 3.10；换机时可通过 `-PythonData` 和 `-PythonML` 传入相应解释器的完整路径。

## 固定分析规则

- 250 款啤酒；231 个输入字段；`4.csv` 中 50 个连续监督目标；12 张卡片每张 52 个位置。
- Beer 13—250 共 238 款是开发集。所有预处理、模型选择和等级锚点只在开发集或其五折折外预测上完成；Beer 1—12 的标签不参与拟合。
- 预先比较 ExtraTrees 与 Gradient Boosting。按开发集五折 OOF 的 MAE、再按合并 \(R^2\) 选择模型；当前选择 ExtraTrees。固定参数在 `src/solve_problem1_v3.py` 和 `src/q1_tree_predictor.py` 中显式列出。
- 化学缺失值在每个训练折拟合中位数并附加缺失指示。输入字段保持附件原有数值编码，不对所有列统一取指数或解释为浓度。
- 50 项连续预测不作方差匹配。整数代理等级采用238款训练标签逐维1%/99%分位点锚定、四舍五入并截断至0—6。此方式依据开发集 OOF 的代理等级一致性优于备选方差匹配后冻结。
- 香气和口味乙醛两个位置没有对应的感官监督标签，按 `8.xlsx` 校准浓度与10 mg/L阈值作 Fechner 外推；同时保存50 mg/L敏感性值。
- 12 款标签在先前研究迭代中已经被查看，故本项目虽排除了它们的拟合参与，相关性能仍标注为**事后留出核验**，不能称全新外部测试。原始评分员0—6逐项真值未给出，代理等级一致率不是人工卡片准确率。

## 主要输出

| 路径 | 内容 |
|:--|:--|
| `results/A_problem1_v3_scores.xlsx` | 回填的12张原格式评分卡与summary |
| `results/A_problem1_v3_scores_52.csv` | 12款×52项整数等级 |
| `results/A_problem1_v3_continuous_predictions.csv` | 12款×50项未校准连续预测 |
| `audit/model_comparison.json` | 固定五折与事后留出模型比较 |
| `audit/calibration_comparison.json` | 两种等级映射在开发集OOF的比较 |
| `audit/q1_holdout_by_beer.csv`、`audit/q1_holdout_by_dimension.csv`、`audit/q1_holdout_summary.json` | 事后逐酒、逐维与总体核验 |
| `audit/extra_trees_oof.csv` | 238款折外预测，便于复算等级校准 |

这里的 0—6 分是从标准化连续目标推得的**代理评分**。若能取得评分员原始记录，应重新校准并验证该整数映射。
