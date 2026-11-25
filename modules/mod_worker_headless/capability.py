"""无桌面能力声明：能力存在性检查，不做业务判断。"""
from __future__ import annotations


class HeadlessCapability:
    def __init__(self, config: dict[str, str] | None = None) -> None:
        self.config = config or {}
        self.capability = self.config.get("capability", "UNKNOWN")
        self.description = self.config.get("description", "")

    def check(self) -> tuple[bool, str]:
        if not self.capability:
            return False, "capability 为空"
        return True, ""
