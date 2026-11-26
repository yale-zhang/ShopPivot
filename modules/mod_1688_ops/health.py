"""1688 模块健康检查：演示数据/技能目录至少有一个可用。"""
from __future__ import annotations

from pathlib import Path


def probe() -> tuple[bool, str]:
    fixtures = Path(__file__).parent / "fixtures" / "offers.json"
    skill_cli = Path(".agents/skills/1688-distribution/scripts/cli.py")
    if fixtures.is_file() or skill_cli.is_file():
        return True, ""
    return False, "既没有 1688 演示数据，也没有已安装的 1688 Skill"
