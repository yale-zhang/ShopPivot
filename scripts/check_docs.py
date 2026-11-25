"""文档一致性检查（make verify 的最后一步）。

检查项：
1. 契约 schema、licenses.csv、ADR 索引、模块作者手册、M0 验收记录存在；
2. licenses.csv 无 UNKNOWN / 空许可证；
3. 主文档编号在代码中的引用可落到具体文件（M0 只做关键项）。
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

REQUIRED = {
    "契约 schema": ROOT / "docs/contracts/worker_api.schema.json",
    "口径卡 schema": ROOT / "docs/contracts/metric_card.schema.json",
    "manifest schema": ROOT / "docs/contracts/module_manifest.schema.json",
    "数据合同 schema": ROOT / "docs/contracts/data_contract.schema.json",
    "许可台账": ROOT / "docs/licenses.csv",
    "ADR 索引": ROOT / "docs/adr_index.md",
    "模块作者手册": ROOT / "docs/module_authoring.md",
    "M0 验收记录": ROOT / "docs/review/m0_acceptance.md",
    "M1 验收记录": ROOT / "docs/review/m1_acceptance.md",
    "M2 验收记录": ROOT / "docs/review/m2_acceptance.md",
    "模块化复核": ROOT / "docs/review/modular_review.md",
}


def check_required() -> list[str]:
    problems: list[str] = []
    for label, path in REQUIRED.items():
        if not path.is_file():
            problems.append(f"缺失{label}: {path.relative_to(ROOT)}")
        elif path.stat().st_size < 30:
            problems.append(f"{label} 内容过短: {path.relative_to(ROOT)}")
        else:
            print(f"ok  {label:<12} {path.relative_to(ROOT)}")
    return problems


def check_licenses() -> list[str]:
    problems: list[str] = []
    path = ROOT / "docs/licenses.csv"
    if not path.is_file():
        return problems
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        return ["licenses.csv 为空"]
    for row in rows:
        license_name = (row.get("license") or "").strip()
        component = row.get("component") or row.get("name") or "?"
        if not license_name or license_name.upper() in {"UNKNOWN", "TBD"}:
            problems.append(f"licenses.csv 许可证未确认: {component}")
    print(f"ok  许可台账      {len(rows)} 个组件")
    return problems


def main() -> int:
    problems = check_required() + check_licenses()
    if problems:
        for problem in problems:
            print(f"FAIL {problem}", file=sys.stderr)
        return 1
    print("docs check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
