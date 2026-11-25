"""S09 结算/毛利对账领域服务（BC-3 对账域）。

- 期望净额 = 支付金额 − 退款 − 佣金；
- 差异 = 结算金额 − 期望净额；
- 缺失结算/缺失订单单独分类，不强行合并；
- 财务写入属 L3，平台不提供自动化入口，只输出差异与双边凭据。
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum


class SettlementDiffType(str, Enum):
    MATCH = "MATCH"
    AMOUNT_DIFF = "AMOUNT_DIFF"
    MISSING_SETTLEMENT = "MISSING_SETTLEMENT"
    MISSING_ORDER = "MISSING_ORDER"

    @property
    def label(self) -> str:
        return {
            SettlementDiffType.MATCH: "一致",
            SettlementDiffType.AMOUNT_DIFF: "金额差异",
            SettlementDiffType.MISSING_SETTLEMENT: "缺结算单",
            SettlementDiffType.MISSING_ORDER: "缺订单",
        }[self]


@dataclass(frozen=True)
class SettlementOrder:
    order_id: str
    paid_amount: Decimal
    refund_amount: Decimal
    sku: str = ""
    ref: str = ""


@dataclass(frozen=True)
class SettlementRecord:
    order_id: str
    settlement_no: str
    settlement_amount: Decimal
    commission: Decimal
    settled_at: datetime | None = None
    ref: str = ""


@dataclass
class SettlementDiff:
    order_id: str
    expected_net: Decimal
    settled_amount: Decimal | None
    commission: Decimal | None
    delta: Decimal
    diff_type: SettlementDiffType
    order_ref: str = ""
    settlement_ref: str = ""

    @property
    def label(self) -> str:
        return self.diff_type.label


class SettlementReconciler:
    def __init__(self, tolerance: Decimal = Decimal("0.01")) -> None:
        self.tolerance = tolerance

    def reconcile(
        self, orders: list[SettlementOrder], settlements: list[SettlementRecord]
    ) -> list[SettlementDiff]:
        orders_by_id = {order.order_id: order for order in orders}
        settlements_by_id = {record.order_id: record for record in settlements}
        diffs: list[SettlementDiff] = []

        for order in orders:
            record = settlements_by_id.get(order.order_id)
            if record is None:
                expected = order.paid_amount - order.refund_amount
                diffs.append(
                    SettlementDiff(
                        order_id=order.order_id,
                        expected_net=_q(expected),
                        settled_amount=None,
                        commission=None,
                        delta=_q(-expected),
                        diff_type=SettlementDiffType.MISSING_SETTLEMENT,
                        order_ref=order.ref,
                        settlement_ref="",
                    )
                )
                continue
            expected = order.paid_amount - order.refund_amount - record.commission
            delta = record.settlement_amount - expected
            diff_type = (
                SettlementDiffType.MATCH
                if abs(delta) <= self.tolerance
                else SettlementDiffType.AMOUNT_DIFF
            )
            diffs.append(
                SettlementDiff(
                    order_id=order.order_id,
                    expected_net=_q(expected),
                    settled_amount=_q(record.settlement_amount),
                    commission=_q(record.commission),
                    delta=_q(delta),
                    diff_type=diff_type,
                    order_ref=order.ref,
                    settlement_ref=record.ref,
                )
            )

        for record in settlements:
            if record.order_id in orders_by_id:
                continue
            diffs.append(
                SettlementDiff(
                    order_id=record.order_id,
                    expected_net=Decimal("0.00"),
                    settled_amount=_q(record.settlement_amount),
                    commission=_q(record.commission),
                    delta=_q(record.settlement_amount),
                    diff_type=SettlementDiffType.MISSING_ORDER,
                    order_ref="",
                    settlement_ref=record.ref,
                )
            )
        return sorted(diffs, key=lambda diff: diff.order_id)


def _q(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"))
