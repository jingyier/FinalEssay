"""运行完整赛道 A 解题流程的入口脚本。按固定顺序调用各题求解、核验和可视化步骤。"""
from __future__ import annotations
import argparse, hashlib, json, os, platform, subprocess, sys, time
from pathlib import Path
import pandas as pd

CODE = Path(__file__).absolute().parent
PROJECT = CODE / "项目代码"
INPUT_DEFAULT = CODE / "03_原始附件"
SEED_DEFAULT = 20261025
KEY_FILES = {
    "q1_scores": PROJECT / "A_problem1_v3_trees/results/A_problem1_v3_scores_52.csv",
    "q2_top3": PROJECT / "A_full_solution_v4/q2/results/q2_top3_per_dimension.csv",
    "q3_spectra": PROJECT / "A_full_solution_v4/q3/results/q3_generated_spectra.csv",
}

def sha256(path: Path) -> str:
    h=hashlib.sha256()
    with path.open("rb") as f:
        for b in iter(lambda:f.read(1024*1024), b""): h.update(b)
    return h.hexdigest()

def shape(path: Path):
    try:
        df=pd.read_csv(path)
        return [int(df.shape[0]), int(df.shape[1])]
    except Exception: return None

def git_commit():
    try: return subprocess.check_output(["git","rev-parse","HEAD"],cwd=CODE).decode().strip()
    except Exception: return None

def inputs_hashes(inp: Path):
    return {p.name:sha256(p) for p in sorted(inp.iterdir()) if p.is_file()}

def run(cmd, env=None):
    print("+", " ".join(map(str,cmd)), flush=True)
    subprocess.run(cmd, cwd=CODE, env=env, check=True)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--input-dir", type=Path, default=INPUT_DEFAULT)
    ap.add_argument("--output-dir", type=Path, default=CODE / "repro_runs")
    ap.add_argument("--seed", type=int, default=SEED_DEFAULT)
    ap.add_argument("--bootstrap", type=int, default=200)
    ap.add_argument("--skip-q1", action="store_true")
    args=ap.parse_args(); inp=args.input_dir.absolute()
    if args.seed != SEED_DEFAULT:
        raise SystemExit(f"为保持原随机算法不变，--seed 只能为 {SEED_DEFAULT}")
    if not inp.is_dir(): raise SystemExit(f"输入目录不存在: {inp}")
    before={k:{"sha256":sha256(p),"shape":shape(p)} for k,p in KEY_FILES.items() if p.exists()}
    t0=time.time(); env=os.environ.copy(); env["MATHOR_INPUT_DIR"]=str(inp); env["PYTHONHASHSEED"]=str(args.seed)
    if not args.skip_q1:
        run([sys.executable, str(PROJECT/"A_problem1_v3_trees/src/solve_problem1_v3.py")], env)
    run([sys.executable, str(PROJECT/"A_full_solution_v4/q2/src/solve_q2.py"), "--input-dir", str(inp), "--bootstrap", str(args.bootstrap)], env)
    run([sys.executable, str(PROJECT/"A_full_solution_v4/q3/src/solve_q3_v4.py")], env)
    after={k:{"sha256":sha256(p),"shape":shape(p)} for k,p in KEY_FILES.items() if p.exists()}
    diffs={k:{"before":before.get(k),"after":after.get(k)} for k in set(before)|set(after) if before.get(k)!=after.get(k)}
    args.output_dir.mkdir(parents=True, exist_ok=True)
    meta={"python":sys.version,"dependencies":{},"os":platform.platform(),"git_commit":git_commit(),"input_dir":str(inp),"input_sha256":inputs_hashes(inp),"seed":args.seed,"elapsed_seconds":time.time()-t0,"key_files_before":before,"key_files_after":after,"differences":diffs}
    try:
        import numpy,pandas,sklearn,scipy,openpyxl
        meta["dependencies"]={m:getattr(__import__(m),"__version__", "unknown") for m in ("numpy","pandas","sklearn","scipy","openpyxl")}
    except Exception as e: meta["dependencies_error"]=str(e)
    (args.output_dir/"run_metadata.json").write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding="utf-8")
    if diffs:
        raise SystemExit("检测到关键结果与运行前不同，已停止；差异见 " + str(args.output_dir/"run_metadata.json"))
    print(json.dumps(meta,ensure_ascii=False,indent=2))
if __name__=="__main__": main()
