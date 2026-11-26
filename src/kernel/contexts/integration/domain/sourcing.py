"""选品与采购提供方端口（1688 Skill / UTP / mock）。"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Protocol

from kernel.contexts.metric_data.domain.purchase import PurchaseItem, PurchaseStatus
from kernel.contexts.metric_data.domain.sourcing import SupplierOffer


class ProviderUnavailable(Exception):
    """提供方未安装/未授权/不可用；fail-closed，不编造数据。"""


@dataclass(frozen=True)
class CheckoutResult:
    checkout_id: str
    status: PurchaseStatus
    continue_url: str = ""
    total: Decimal = Decimal("0")
    details: dict[str, Any] = field(default_factory=dict)


class SourcingProvider(Protocol):
    name: str

    def search(
        self, keyword: str, limit: int = 20, filters: list[dict[str, Any]] | None = None
    ) -> list[SupplierOffer]: ...


class PurchaseProvider(Protocol):
    name: str

    def create_checkout(
        self, items: list[PurchaseItem], buyer_note: str = ""
    ) -> CheckoutResult: ...

    def get_checkout(self, checkout_id: str) -> CheckoutResult: ...

    def cancel_checkout(self, checkout_id: str) -> bool: ...
