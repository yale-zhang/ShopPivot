"""幂等键（主文档表 3-10 / E-CMP-04）。

业务单号 / SKU+日期 / 评价ID / 活动+商品 四类组合键统一收敛到这里，
落库时唯一索引，Redis 侧 SETNX 只用于并发抢占。
"""
from __future__ import annotations

import re
from dataclasses import dataclass

_SCOPE_RE = re.compile(r"^[a-z][a-z0-9_]{1,31}$")


@dataclass(frozen=True, slots=True)
class IdempotencyKey:
    scope: str
    value: str

    def __post_init__(self) -> None:
        if not _SCOPE_RE.match(self.scope):
            raise ValueError(f"非法幂等键 scope: {self.scope!r}")
        if not self.value or len(self.value) > 200:
            raise ValueError("幂等键 value 不能为空且长度 <= 200")

    @property
    def as_key(self) -> str:
        return f"{self.scope}:{self.value}"

    @classmethod
    def business_order(cls, order_no: str) -> "IdempotencyKey":
        return cls("order", order_no)

    @classmethod
    def sku_daily(cls, sku: str, stat_date: str) -> "IdempotencyKey":
        return cls("sku_daily", f"{sku}@{stat_date}")

    @classmethod
    def review(cls, review_id: str) -> "IdempotencyKey":
        return cls("review", review_id)

    @classmethod
    def campaign_sku(cls, campaign_id: str, sku: str) -> "IdempotencyKey":
        return cls("campaign_sku", f"{campaign_id}#{sku}")
