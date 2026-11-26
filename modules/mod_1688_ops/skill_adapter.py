"""1688 Skill 适配器：只做参数字段映射，执行/记录/闸门由 SkillRuntime 负责。"""
from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from typing import Any

from kernel.contexts.integration.domain.sourcing import ProviderUnavailable
from kernel.contexts.integration.infrastructure.sourcing_providers import (
    Mock1688SourcingProvider,
    MockPurchaseProvider,
    SkillCliSourcingProvider,
    UtpPurchaseProvider,
)
from kernel.contexts.metric_data.domain.purchase import PurchaseItem
from kernel.contexts.skill.domain.models import SkillInvocation, SkillOutput


class DistributionSourcingAdapter:
    def execute(self, invocation: SkillInvocation, payload: dict[str, Any]) -> SkillOutput:
        settings = invocation.settings
        mode = str(getattr(settings, "source_1688_mode", "mock"))
        keyword = str(payload.get("keyword", "")).strip()
        limit = int(payload.get("limit", 20))
        filters = list(payload.get("filters") or [])
        if not keyword:
            raise ProviderUnavailable("选品关键词不能为空")
        if mode == "cli":
            provider = SkillCliSourcingProvider(
                skill_dir=getattr(settings, "skill_1688_dir", ".agents/skills/1688-distribution")
            )
        else:
            fixtures = invocation.manifest.config.get(
                "fixtures", "modules/mod_1688_ops/fixtures/offers.json"
            )
            provider = Mock1688SourcingProvider(Path(fixtures))
        offers = provider.search(keyword, limit=limit, filters=filters)
        return SkillOutput(
            status="SUCCEEDED",
            data=offers,
            evidence=[
                {"kind": "skill", "ref": f"skill://{invocation.manifest.id}@{invocation.manifest.version}"},
                {"kind": "keyword", "ref": keyword},
            ],
            raw={"provider": provider.name, "count": len(offers)},
        )


_MOCK_PURCHASE = MockPurchaseProvider()


class UtpPurchaseAdapter:
    def _provider(self, invocation: SkillInvocation) -> Any:
        settings = invocation.settings
        if str(getattr(settings, "source_1688_mode", "mock")) == "mock":
            return _MOCK_PURCHASE
        return UtpPurchaseProvider(
            utp_bin=getattr(settings, "utp_bin", "utp"),
            host=getattr(settings, "utp_host", "https://ucp-b2b.com"),
        )

    def execute(self, invocation: SkillInvocation, payload: dict[str, Any]) -> SkillOutput:
        provider = self._provider(invocation)
        capability = invocation.capability
        if capability == "purchase.checkout":
            items = [
                PurchaseItem(
                    offer_id=str(item["offer_id"]),
                    title=str(item.get("title", "")),
                    quantity=int(item.get("quantity", 1)),
                    unit_price=Decimal(str(item.get("unit_price", "0"))),
                    post_fee=Decimal(str(item.get("post_fee", "0"))),
                    spec_id=str(item.get("spec_id", "")),
                )
                for item in (payload.get("items") or [])
            ]
            if not items:
                raise ProviderUnavailable("采购项为空")
            checkout = provider.create_checkout(
                items, buyer_note=str(payload.get("buyer_note", ""))
            )
            return SkillOutput(
                status="SUCCEEDED",
                data={
                    "checkout_id": checkout.checkout_id,
                    "status": checkout.status.value,
                    "continue_url": checkout.continue_url,
                    "total": str(checkout.total),
                    "details": checkout.details,
                },
                evidence=[
                    {"kind": "skill", "ref": f"skill://{invocation.manifest.id}@{invocation.manifest.version}"},
                    {"kind": "checkout", "ref": f"checkout://{checkout.checkout_id}"},
                ],
                raw={"provider": provider.name},
            )
        if capability == "purchase.status":
            checkout = provider.get_checkout(str(payload.get("checkout_id", "")))
            return SkillOutput(
                status="SUCCEEDED",
                data={
                    "checkout_id": checkout.checkout_id,
                    "status": checkout.status.value,
                    "continue_url": checkout.continue_url,
                },
                evidence=[{"kind": "checkout", "ref": f"checkout://{checkout.checkout_id}"}],
            )
        if capability == "purchase.cancel":
            cancelled = provider.cancel_checkout(str(payload.get("checkout_id", "")))
            return SkillOutput(
                status="SUCCEEDED",
                data={"checkout_id": payload.get("checkout_id"), "cancelled": cancelled},
                evidence=[{"kind": "checkout", "ref": f"checkout://{payload.get('checkout_id')}"}],
            )
        raise ProviderUnavailable(f"不支持的 UTP 能力: {capability}")
