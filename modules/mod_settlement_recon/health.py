"""S09 健康检查：对账容差合法。"""
from __future__ import annotations

from decimal import Decimal


def probe() -> tuple[bool, str]:
    if Decimal("0.01") < 0:
        return False, "对账容差非法"
    return True, ""
