"""S04 健康检查：投放阈值配置合理。"""
from __future__ import annotations

ROI_MIN = 2.0
WATCH_MIN = 1.0


def probe() -> tuple[bool, str]:
    if not (0 < WATCH_MIN <= ROI_MIN):
        return False, "投产比阈值配置非法"
    return True, ""
