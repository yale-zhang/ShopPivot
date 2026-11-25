"""闸门分级规则（ADR-08 / 表 3-8 / 表 8-4 GatePolicy）。

默认值取 L2（未知动作必须人工确认），并且**只允许被平台上限收紧，不允许被模块放宽**。
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Mapping

from shared.gate_level import GateLevel


@dataclass(frozen=True, slots=True)
class GateDecision:
    action_code: str
    gate_level: GateLevel
    platform_ceiling: GateLevel
    allowed: bool
    reason: str = ""

    @property
    def requires_human(self) -> bool:
        return self.allowed and self.gate_level is GateLevel.L2_MANUAL_APPROVAL


class GatePolicyService:
    def __init__(
        self,
        rules: Mapping[str, GateLevel] | None = None,
        *,
        platform_ceiling: GateLevel = GateLevel.L0_READ_ONLY,
        default_level: GateLevel = GateLevel.L2_MANUAL_APPROVAL,
        effective_from: datetime | None = None,
    ) -> None:
        self.rules = dict(rules or {})
        self.platform_ceiling = platform_ceiling
        self.default_level = default_level
        self.effective_from = effective_from

    def declare(self, action_code: str, level: GateLevel) -> None:
        self.rules[action_code] = level

    def decide(self, action_code: str) -> GateDecision:
        declared = self.rules.get(action_code, self.default_level)
        if not declared.at_most(self.platform_ceiling):
            return GateDecision(
                action_code=action_code,
                gate_level=declared,
                platform_ceiling=self.platform_ceiling,
                allowed=False,
                reason=(
                    f"动作 {action_code} 需要 {declared.value}，"
                    f"平台当前上限为 {self.platform_ceiling.value}，已阻断"
                ),
            )
        return GateDecision(
            action_code=action_code,
            gate_level=declared,
            platform_ceiling=self.platform_ceiling,
            allowed=True,
        )
