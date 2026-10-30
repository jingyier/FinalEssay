"""只读核验入口。检查既有结果文件，不重新生成结果 CSV。"""
from __future__ import annotations
import argparse, os, subprocess, sys
from pathlib import Path
CODE=Path(__file__).absolute().parent; PROJECT=CODE/"项目代码"
def main():
 ap=argparse.ArgumentParser(); ap.add_argument("--input-dir",type=Path,default=CODE/"03_原始附件"); ap.add_argument("--output-dir",type=Path,default=CODE/"repro_runs"); ap.add_argument("--seed",type=int,default=20261025); a=ap.parse_args()
 if a.seed!=20261025: raise SystemExit("--seed 必须保持 20261025")
 env=os.environ.copy(); env["MATHOR_INPUT_DIR"]=str(a.input_dir.resolve())
 cmds=[
  [sys.executable,str(CODE/"verify_q1.py"),"--input-dir",str(a.input_dir),"--output-dir",str(a.output_dir)],
  [sys.executable,str(PROJECT/"A_full_solution_v4/q2/src/verify_q2.py")],
  [sys.executable,str(PROJECT/"A_full_solution_v4/q3/src/verify_q3_v4.py")],]
 for c in cmds: print("+"," ".join(map(str,c))); subprocess.run(c,cwd=CODE,env=env,check=True)
 print("ALL VERIFICATIONS PASSED")
if __name__=="__main__": main()
