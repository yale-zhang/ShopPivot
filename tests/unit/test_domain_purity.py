"""领域层依赖方向检查：domain 不 import 框架、基础设施、应用层。"""
from __future__ import annotations

import ast
from pathlib import Path

FORBIDDEN_ROOTS = {
    "fastapi",
    "sqlalchemy",
    "celery",
    "httpx",
    "redis",
    "alembic",
    "pydantic",
    "bootstrap",
    "kernel.persistence",
}
FORBIDDEN_SEGMENTS = (".infrastructure", ".interfaces", ".application")

ROOT = Path(__file__).resolve().parents[2]
DOMAIN_DIRS = sorted(ROOT.glob("src/kernel/contexts/*/domain"))


def _imports(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            modules.append(node.module)
    return modules


def test_domain_dirs_exist() -> None:
    assert len(DOMAIN_DIRS) == 8, [str(p) for p in DOMAIN_DIRS]


def test_domain_does_not_import_frameworks_or_outer_layers() -> None:
    violations: list[str] = []
    for directory in DOMAIN_DIRS:
        for path in directory.glob("*.py"):
            for module in _imports(path):
                if module.split(".")[0] in FORBIDDEN_ROOTS or any(
                    module.startswith(root) for root in FORBIDDEN_ROOTS if "." in root
                ):
                    violations.append(f"{path.relative_to(ROOT)} -> {module}")
                if any(segment in module for segment in FORBIDDEN_SEGMENTS):
                    violations.append(f"{path.relative_to(ROOT)} -> {module}（反向依赖）")
    assert not violations, "\n".join(violations)
