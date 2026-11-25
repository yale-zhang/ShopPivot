"""写入分级 L0~L3（主文档表 3-8 / ADR-08）。

判定与门禁放在领域层：任何模块都不得绕过这里的顺序关系。
"""
from __future__ import annotations

from enum import Enum


class GateLevel(str, Enum):
    L0_READ_ONLY = "L0"
    L1_LOW_RISK = "L1"
    L2_MANUAL_APPROVAL = "L2"
    L3_FORBIDDEN = "L3"

    @property
    def rank(self) -> int:
        return {"L0": 0, "L1": 1, "L2": 2, "L3": 3}[self.value]

    @property
    def label(self) -> str:
        return {
            "L0": "只读自动",
            "L1": "低风险自动 + 抽检",
            "L2": "必须人工确认",
            "L3": "禁止自动化",
        }[self.value]

    @property
    def requires_human(self) -> bool:
        return self is GateLevel.L2_MANUAL_APPROVAL

    def at_most(self, ceiling: "GateLevel") -> bool:
        """本级别是否不超过给定上限。"""
        return self.rank <= ceiling.rank

    @classmethod
    def parse(cls, raw: str | "GateLevel" | None) -> "GateLevel":
        if isinstance(raw, GateLevel):
            return raw
        if raw is None:
            raise ValueError("gate level 不能为空")
        normalized = str(raw).strip().upper()
        for member in cls:
            if normalized in (member.value, member.name):
                return member
        raise ValueError(f"未知的闸门级别: {raw!r}（允许 L0/L1/L2/L3）")
