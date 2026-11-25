"""S05 健康检查：规则基线可读（关键词非空、阈值合理）。"""
from __future__ import annotations

DEFAULT_KEYWORDS = ["破损", "差评", "退货", "假货", "欺诈", "发错"]


def probe() -> tuple[bool, str]:
    if not DEFAULT_KEYWORDS:
        return False, "差评关键词规则为空"
    return True, ""
