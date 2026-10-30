"""问题二和问题三的最小化内存烟测脚本。仅检查核心计算链路，不写入正式结果文件。"""
from __future__ import annotations
import argparse, importlib.util, os, sys, pathlib
pathlib.Path.resolve = pathlib.Path.absolute
from pathlib import Path
import numpy as np, pandas as pd
pd.DataFrame.to_numpy = lambda self, dtype=None: self.values.astype(dtype) if dtype is not None else self.values
pd.Series.to_numpy = lambda self, dtype=None: self.values.astype(dtype) if dtype is not None else self.values
_nt = np.nan_to_num
def _compat_nan_to_num(x, *args, **kwargs):
    if "nan" in kwargs:
        v = kwargs.pop("nan"); arr = np.asarray(x); out = _nt(arr, *args, **kwargs)
        return np.where(np.isnan(arr), v, out)
    return _nt(x, *args, **kwargs)
np.nan_to_num = _compat_nan_to_num
class CompatRng:
    def __init__(self, seed): self.r=np.random.RandomState(seed)
    def integers(self, low, high=None, size=None): return self.r.randint(low, high, size=size)
    def uniform(self, *args, **kwargs): return self.r.uniform(*args, **kwargs)
    def normal(self, *args, **kwargs): return self.r.normal(*args, **kwargs)
CODE=Path(__file__).absolute().parent; PROJECT=CODE/"项目代码"; DEFAULT=CODE/"03_原始附件"
def load(path,name):
    spec=importlib.util.spec_from_file_location(name,path); mod=importlib.util.module_from_spec(spec); sys.modules[name]=mod; spec.loader.exec_module(mod); return mod
def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--input-dir",type=Path,default=DEFAULT); ap.add_argument("--output-dir",type=Path,default=CODE/"repro_runs"); ap.add_argument("--seed",type=int,default=20261025); a=ap.parse_args()
    if a.seed!=20261025: raise SystemExit("--seed 必须保持 20261025")
    inp=a.input_dir.absolute(); os.environ["MATHOR_INPUT_DIR"]=str(inp)
    q2=load(PROJECT/"A_full_solution_v4/q2/src/solve_q2.py","mathor_q2_smoke")
    chem=pd.read_csv(inp/"1.csv"); sens=pd.read_csv(inp/"4.csv")
    x=chem.iloc[:8,3:].apply(pd.to_numeric,errors="coerce").values.astype(float); y=sens.iloc[:8,3:].values.astype(float)
    rho,n=q2.spearman_xy(x,y); assert rho.shape==(x.shape[1],y.shape[1]) and np.isfinite(rho).all()
    eligible=np.ones(x.shape[1],bool); red=np.nan_to_num(np.abs(np.corrcoef(np.nan_to_num(x).T)),nan=0.0)
    selected,network,evidence=q2.selector(rho,np.eye(rho.shape[0]),red,eligible); assert selected.shape==(y.shape[1],3)
    import types
    stub=types.ModuleType("q1_tree_predictor"); stub.PanelPredictor=object; stub.fit_fixed_panel_predictor=lambda *x,**k: None; sys.modules["q1_tree_predictor"]=stub
    q3=load(PROJECT/"A_full_solution_v4/q3/src/solve_q3_v4.py","mathor_q3_smoke")
    q3=load(PROJECT/"A_full_solution_v4/q3/src/solve_q3_v4.py","mathor_q3_smoke")
    z=chem.iloc[:30,3:].values.astype(float); styles=chem.iloc[:30].tasting_category_fine.astype(str).values
    model=q3.fit_generator(z,styles); style=next(s for s in np.unique(styles) if (styles==s).sum()>=2); gen=q3.draw_conditional(model,style,2,CompatRng(a.seed))
    assert gen.shape==(2,z.shape[1]) and np.isfinite(gen).all()
    a.output_dir.mkdir(parents=True,exist_ok=True); (a.output_dir/"smoke_test.json").write_text('{"status":"PASS","q2":"recomputed Spearman + selector","q3":"recomputed PCA generator + 2 samples"}',encoding="utf-8")
    print("Q2/Q3 minimal recomputation smoke test: PASS")
if __name__=="__main__": main()
