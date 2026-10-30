"""汇总三个问题的既有 results 和 audit 文件，不重新计算模型。"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path


PROJECT = Path(__file__).absolute().parent
OUTPUT = PROJECT / "output"
SOURCES = {
    "Q1": PROJECT / "A_problem1_v3_trees",
    "Q2": PROJECT / "A_full_solution_v4" / "q2",
    "Q3": PROJECT / "A_full_solution_v4" / "q3",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def copy_group(question: str, source: Path, destination: Path) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    for group in ("results", "audit"):
        source_dir = source / group
        destination_dir = destination / question / group
        if not source_dir.is_dir():
            continue
        destination_dir.mkdir(parents=True, exist_ok=True)
        for source_file in sorted(source_dir.rglob("*")):
            if not source_file.is_file():
                continue
            relative = source_file.relative_to(source_dir)
            target = destination_dir / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_file, target)
            records.append({
                "question": question,
                "group": group,
                "path": str((Path(question) / group / relative).as_posix()),
                "bytes": target.stat().st_size,
                "sha256": sha256(target),
            })
    return records


def main() -> None:
    parser = argparse.ArgumentParser(
        description="将 Q1/Q2/Q3 的既有 results 和 audit 汇总到项目代码/output。"
    )
    parser.add_argument("--output-dir", type=Path, default=OUTPUT)
    args = parser.parse_args()

    output_dir = args.output_dir.absolute()
    output_dir.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, object]] = []
    for question, source in SOURCES.items():
        records.extend(copy_group(question, source, output_dir))

    manifest = {
        "description": "Q1/Q2/Q3 results and audit aggregation; no model recomputation performed.",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_directories": {q: str(path) for q, path in SOURCES.items()},
        "output_directory": str(output_dir),
        "file_count": len(records),
        "files": records,
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (output_dir / "README.md").write_text(
        "# 汇总结果接口\n\n"
        "本目录由 `项目代码/sync_outputs.py` 汇总生成。\n"
        "Q1、Q2、Q3 下分别保留原项目的 `results` 和 `audit` 文件；\n"
        "同步过程只复制文件，不重新运行模型。文件校验值见 `manifest.json`。\n",
        encoding="utf-8",
    )
    print(f"已汇总 {len(records)} 个文件到 {output_dir}")


if __name__ == "__main__":
    main()
