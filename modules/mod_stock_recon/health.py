"""S07 健康检查：对账容差与滞销阈值合理。"""
from __future__ import annotations

DEFAULT_TOLERANCE = 5
DEFAULT_SLOW_THRESHOLD = 100


def probe() -> tuple[bool, str]:
    if DEFAULT_TOLERANCE < 0:
        return False, "对账容差不能为负"
    if DEFAULT_SLOW_THRESHOLD <= 0:
        return False, "滞销阈值必须为正"
    return True, ""
