"""迁移基线 up/down 验证（SQLite；PostgreSQL 由部署流水线另行验证）。"""
from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _alembic(db_path: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env.update(
        {
            "PYTHONPATH": "src:.",
            "SHOPPIVOT_DATABASE_URL": f"sqlite:///{db_path}",
            "SHOPPIVOT_STORAGE_DIR": str(db_path.parent / "storage"),
            "SHOPPIVOT_ENV": "test",
        }
    )
    return subprocess.run(
        [sys.executable, "-m", "alembic", "-c", "migrations/alembic.ini", *args],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )


def _tables(db_path: Path) -> set[str]:
    with sqlite3.connect(db_path) as connection:
        rows = connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    return {row[0] for row in rows}


@pytest.mark.integration
def test_alembic_upgrade_and_downgrade(tmp_path: Path) -> None:
    db_path = tmp_path / "mig.db"
    upgrade = _alembic(db_path, "upgrade", "head")
    assert upgrade.returncode == 0, upgrade.stderr
    tables = _tables(db_path)
    for required in [
        "run_instance",
        "approval_task",
        "metric_definition",
        "dws_daily_metric",
        "audit_log",
        "module_state",
        "outbox_event",
        "account",
    ]:
        assert required in tables, required

    downgrade = _alembic(db_path, "downgrade", "base")
    assert downgrade.returncode == 0, downgrade.stderr
    assert _tables(db_path) <= {"alembic_version"}
