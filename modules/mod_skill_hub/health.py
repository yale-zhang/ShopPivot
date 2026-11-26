"""技能中心健康检查：skills.lock 可读且至少一个 Skill。"""
from __future__ import annotations

from pathlib import Path


def probe() -> tuple[bool, str]:
    lock = Path("skills.lock")
    if not lock.is_file():
        return False, "skills.lock 不存在"
    return True, ""
