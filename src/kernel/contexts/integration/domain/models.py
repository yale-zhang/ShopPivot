"""集成适配上下文：取数、降级、脱敏、通知（主文档 §4.5 / 表 4-5 / E-CMP-01~05）。"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from shared.types.values import StatWindow


@dataclass(frozen=True, slots=True)
class FetchSpec:
    platform: str
    shop_id: str
    dataset: str
    window: StatWindow
    config: dict[str, Any] = field(default_factory=dict)

    def param(self, key: str, default: Any = None) -> Any:
        return self.config.get(key, default)


class FetchChannelUnavailable(Exception):
    """当前通道未配置/不可用：允许降级到下一级，不视为业务失败。"""
