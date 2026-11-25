"""L2 四要素证据集（主文档表 3-10 / 表 3-23）。

四要素缺一不可归档；这是聚合不变量，不允许在接口层拼装。
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class EvidenceSet:
    operator: str
    decided_at: datetime
    change_order_no: str
    before_shot: str
    after_shot: str

    def _missing(self, include_after: bool) -> list[str]:
        checks = {
            "operator": self.operator,
            "decided_at": self.decided_at,
            "change_order_no": self.change_order_no,
            "before_shot": self.before_shot,
        }
        if include_after:
            checks["after_shot"] = self.after_shot
        return [name for name, value in checks.items() if not value]

    def missing_fields(self) -> list[str]:
        """归档口径：四要素 + 执行后截图。"""
        return self._missing(include_after=True)

    def approval_missing_fields(self) -> list[str]:
        """批准口径：操作人/确认时间/变更单/变更前截图；执行后截图在回查后补。"""
        return self._missing(include_after=False)

    def complete(self) -> bool:
        return not self.missing_fields()

    def approvable(self) -> bool:
        return not self.approval_missing_fields()
