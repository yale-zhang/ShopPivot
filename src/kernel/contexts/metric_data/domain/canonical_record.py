"""统一数据模型记录（BC-3 发布语言）。

平台报文只落 ODS；进入领域与 DWD 的只能是 CanonicalRecord。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class CanonicalRecord:
    platform: str
    shop_id: str
    dataset: str
    business_key: str
    fields: dict[str, Any] = field(default_factory=dict)
    raw_ref: str = ""
    status_enum: str | None = None
    desensitized: bool = True

    def value(self, key: str, default: Any = None) -> Any:
        return self.fields.get(key, default)
