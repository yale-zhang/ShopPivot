"""1688 选品领域：供应商报价 → 候选评分（BC-3 选品读模型）。

评分只做可解释的规则排序，不替代人的选品判断：
- 价格（批次内相对）40 分
- 30 天分销单量 30 分
- 包邮 10 分、低起订 10 分
- 品牌未授权/无销量扣分并打风险标签
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any


@dataclass(frozen=True)
class SupplierOffer:
    offer_id: str
    title: str
    price: Decimal
    post_fee: Decimal = Decimal("0")
    moq: int = 1
    sales_30d: int = 0
    supplier: str = ""
    pic_url: str = ""
    url: str = ""
    brand_authorized: bool = True
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def landed_price(self) -> Decimal:
        return (self.price + self.post_fee).quantize(Decimal("0.01"))

    def total(self, quantity: int) -> Decimal:
        return (self.price * quantity + self.post_fee).quantize(Decimal("0.01"))


@dataclass(frozen=True)
class SourcingCandidate:
    offer: SupplierOffer
    score: float
    rank: int
    risk_flags: tuple[str, ...] = ()

    @property
    def risk_label(self) -> str:
        return "、".join(self.risk_flags) if self.risk_flags else "—"

    def to_dict(self) -> dict[str, Any]:
        return {
            "offer_id": self.offer.offer_id,
            "title": self.offer.title,
            "price": str(self.offer.price),
            "post_fee": str(self.offer.post_fee),
            "moq": self.offer.moq,
            "sales_30d": self.offer.sales_30d,
            "supplier": self.offer.supplier,
            "pic_url": self.offer.pic_url,
            "url": self.offer.url,
            "brand_authorized": self.offer.brand_authorized,
            "landed_price": str(self.offer.landed_price),
            "score": round(self.score, 2),
            "rank": self.rank,
            "risk_flags": list(self.risk_flags),
            "risk_label": self.risk_label,
        }


class SourcingScorer:
    def score(self, offers: list[SupplierOffer]) -> list[SourcingCandidate]:
        if not offers:
            return []
        prices = [offer.landed_price for offer in offers]
        high = max(prices)
        low = min(prices)
        span = high - low
        scored: list[tuple[float, tuple[str, ...], SupplierOffer]] = []
        for offer in offers:
            risks: list[str] = []
            price_score = (
                40.0
                if span == 0
                else float((high - offer.landed_price) / span) * 40.0
            )
            sales_score = min(offer.sales_30d / 1000.0, 1.0) * 30.0
            ship_score = 10.0 if offer.post_fee == 0 else 0.0
            moq_score = 10.0 if offer.moq <= 2 else max(0.0, 10.0 - offer.moq / 10.0)
            score = price_score + sales_score + ship_score + moq_score
            if not offer.brand_authorized:
                risks.append("品牌未授权")
                score -= 30.0
            if offer.sales_30d <= 0:
                risks.append("无近30天分销单")
                score -= 10.0
            if offer.moq > 50:
                risks.append("起订量偏高")
            if offer.post_fee > 0:
                risks.append("需邮费")
            scored.append((max(score, 0.0), tuple(risks), offer))
        scored.sort(key=lambda item: (-item[0], item[2].landed_price, item[2].offer_id))
        return [
            SourcingCandidate(offer=offer, score=score, rank=index + 1, risk_flags=risks)
            for index, (score, risks, offer) in enumerate(scored)
        ]
