"""1688 采购下单领域：采购项、采购单与结算状态。

注意：平台不代付、不代提交。UTP 的 HITL 规则要求用户在确认卡/1688 收银台点击确认，
本系统最多创建 checkout 并把 continue_url 交给人；支付状态只做回读。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any


class PurchaseStatus(str, Enum):
    AWAITING_CONFIRMATION = "AWAITING_CONFIRMATION"
    AWAITING_PAYMENT = "AWAITING_PAYMENT"
    PAID = "PAID"
    CANCELLED = "CANCELLED"
    FAILED = "FAILED"

    @property
    def label(self) -> str:
        return {
            PurchaseStatus.AWAITING_CONFIRMATION: "待确认",
            PurchaseStatus.AWAITING_PAYMENT: "待支付",
            PurchaseStatus.PAID: "已支付",
            PurchaseStatus.CANCELLED: "已取消",
            PurchaseStatus.FAILED: "失败",
        }[self]


@dataclass(frozen=True)
class PurchaseItem:
    offer_id: str
    title: str
    quantity: int
    unit_price: Decimal
    post_fee: Decimal = Decimal("0")
    spec_id: str = ""

    @property
    def subtotal(self) -> Decimal:
        return (self.unit_price * self.quantity).quantize(Decimal("0.01"))

    def to_dict(self) -> dict[str, Any]:
        return {
            "offer_id": self.offer_id,
            "title": self.title,
            "quantity": self.quantity,
            "unit_price": str(self.unit_price),
            "post_fee": str(self.post_fee),
            "spec_id": self.spec_id,
            "subtotal": str(self.subtotal),
        }


@dataclass
class PurchaseOrder:
    plan_id: str
    provider: str
    items: list[PurchaseItem]
    total: Decimal
    checkout_id: str
    status: PurchaseStatus
    continue_url: str = ""
    buyer_note: str = ""
    details: dict[str, Any] = field(default_factory=dict)
    created_at: datetime | None = None
    updated_at: datetime | None = None

    @property
    def quantity(self) -> int:
        return sum(item.quantity for item in self.items)

    def to_dict(self) -> dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "provider": self.provider,
            "items": [item.to_dict() for item in self.items],
            "total": str(self.total),
            "quantity": self.quantity,
            "checkout_id": self.checkout_id,
            "status": self.status.value,
            "status_label": self.status.label,
            "continue_url": self.continue_url,
            "buyer_note": self.buyer_note,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
