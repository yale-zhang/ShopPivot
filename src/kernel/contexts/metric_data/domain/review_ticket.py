"""S05 评价巡检工单（BC-3 巡检读模型）。"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from uuid import uuid4


class TicketStatus(str, Enum):
    OPEN = "OPEN"
    ASSIGNED = "ASSIGNED"
    CLOSED = "CLOSED"


class Severity(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"


@dataclass(frozen=True, slots=True)
class ReviewRule:
    rating_threshold: int = 3
    high_severity_max: int = 2
    keywords: tuple[str, ...] = ("破损", "差评", "退货", "假货", "欺诈", "发错")

    def match(self, rating: int, content: str) -> str | None:
        """返回命中规则描述；未命中返回 None。"""
        if rating <= self.rating_threshold:
            return f"rating<={self.rating_threshold}"
        for keyword in self.keywords:
            if keyword and keyword in content:
                return f"keyword:{keyword}"
        return None


@dataclass
class ReviewTicket:
    ticket_id: str
    run_id: str
    platform: str
    shop_id: str
    review_id: str
    sku: str
    rating: int
    dsr: float | None
    content_masked: str
    hit_rule: str
    severity: Severity
    sla_due_at: datetime
    status: TicketStatus = TicketStatus.OPEN
    assignee: str | None = None
    created_at: datetime | None = None
    closed_at: datetime | None = None
    resolution: str | None = None
    evidence_ref: str | None = None

    @staticmethod
    def new_id() -> str:
        return f"rv_{uuid4().hex[:16]}"

    @classmethod
    def create(
        cls,
        *,
        run_id: str,
        platform: str,
        shop_id: str,
        review_id: str,
        sku: str,
        rating: int,
        dsr: float | None,
        content_masked: str,
        hit_rule: str,
        severity: Severity,
        sla_due_at: datetime,
        evidence_ref: str | None = None,
    ) -> "ReviewTicket":
        return cls(
            ticket_id=cls.new_id(),
            run_id=run_id,
            platform=platform,
            shop_id=shop_id,
            review_id=review_id,
            sku=sku,
            rating=rating,
            dsr=dsr,
            content_masked=content_masked,
            hit_rule=hit_rule,
            severity=severity,
            sla_due_at=sla_due_at,
            evidence_ref=evidence_ref,
        )

    def assign(self, assignee: str) -> None:
        if self.status is TicketStatus.CLOSED:
            raise ValueError("已关闭工单不能再派单")
        if not assignee.strip():
            raise ValueError("派单必须指定处理人")
        self.assignee = assignee
        self.status = TicketStatus.ASSIGNED

    def close(self, resolution: str) -> None:
        if self.status is TicketStatus.CLOSED:
            raise ValueError("工单已关闭")
        if not resolution.strip():
            raise ValueError("关闭工单必须填写处理结论")
        self.status = TicketStatus.CLOSED
        self.resolution = resolution

    def overdue(self, now: datetime) -> bool:
        return self.status is not TicketStatus.CLOSED and now > self.sla_due_at
