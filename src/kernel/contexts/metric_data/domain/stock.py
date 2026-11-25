"""S07 三方可售库存对齐与补货建议（BC-3 对账域）。

要点（表 3-21）：
- 平台 / ERP / WMS 各自保留快照时间，时间窗不一致时分别标注，不强行合并；
- 只输出补货建议，不自动下单；
- 差异行必须能标注引用口径与跨库来源。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from uuid import uuid4


class DiffType(str, Enum):
    STOCKOUT = "STOCKOUT"      # 平台 0 可售，但仓库有货：断货
    OVERSELL = "OVERSELL"      # 平台有货，但仓库无货：超卖风险
    MISMATCH = "MISMATCH"      # 三方数量差超过容差
    STAGNANT = "STAGNANT"      # 库存偏高、动销慢
    CONSISTENT = "CONSISTENT"  # 一致

    @property
    def label(self) -> str:
        return {
            DiffType.STOCKOUT: "断货",
            DiffType.OVERSELL: "超卖风险",
            DiffType.MISMATCH: "三方差异",
            DiffType.STAGNANT: "滞销",
            DiffType.CONSISTENT: "一致",
        }[self]


class SuggestionAction(str, Enum):
    REPLENISH = "REPLENISH"
    PAUSE = "PAUSE"
    SYNC = "SYNC"
    NONE = "NONE"


@dataclass(frozen=True, slots=True)
class StockSnapshot:
    sku: str
    available: int | None
    snapshot_at: datetime | None
    source: str

    @property
    def display(self) -> str:
        return "—" if self.available is None else str(self.available)


@dataclass
class StockDiff:
    sku: str
    platform: StockSnapshot
    erp: StockSnapshot
    wms: StockSnapshot
    diff_type: DiffType
    delta: int = 0
    tolerance: int = 5

    @property
    def label(self) -> str:
        return self.diff_type.label

    @property
    def snapshot_times(self) -> dict[str, str | None]:
        return {
            "platform": self.platform.snapshot_at.isoformat() if self.platform.snapshot_at else None,
            "erp": self.erp.snapshot_at.isoformat() if self.erp.snapshot_at else None,
            "wms": self.wms.snapshot_at.isoformat() if self.wms.snapshot_at else None,
        }


@dataclass
class StockSuggestion:
    suggestion_id: str
    sku: str
    action: SuggestionAction
    quantity: int = 0
    reason: str = ""
    status: str = "OPEN"

    @staticmethod
    def new_id() -> str:
        return f"sg_{uuid4().hex[:16]}"


@dataclass(frozen=True, slots=True)
class StockReconResult:
    diffs: list[StockDiff] = field(default_factory=list)
    suggestions: list[StockSuggestion] = field(default_factory=list)

    @property
    def counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for diff in self.diffs:
            counts[diff.diff_type.value] = counts.get(diff.diff_type.value, 0) + 1
        return counts


class StockReconciler:
    def __init__(self, *, tolerance: int = 5, slow_threshold: int = 100, safety_stock: int = 20) -> None:
        self.tolerance = tolerance
        self.slow_threshold = slow_threshold
        self.safety_stock = safety_stock

    def reconcile(
        self,
        platform: dict[str, StockSnapshot],
        erp: dict[str, StockSnapshot],
        wms: dict[str, StockSnapshot],
        *,
        missing: StockSnapshot | None = None,
    ) -> StockReconResult:
        skus = sorted(set(platform) | set(erp) | set(wms))
        diffs: list[StockDiff] = []
        suggestions: list[StockSuggestion] = []
        for sku in skus:
            p = platform.get(sku, StockSnapshot(sku, None, None, "platform"))
            e = erp.get(sku, StockSnapshot(sku, None, None, "erp"))
            w = wms.get(sku, StockSnapshot(sku, None, None, "wms"))
            diff_type, delta, suggestion = self._classify(p, e, w)
            diffs.append(
                StockDiff(
                    sku=sku,
                    platform=p,
                    erp=e,
                    wms=w,
                    diff_type=diff_type,
                    delta=delta,
                    tolerance=self.tolerance,
                )
            )
            if suggestion is not None:
                suggestions.append(suggestion)
        return StockReconResult(diffs=diffs, suggestions=suggestions)

    def _classify(
        self, p: StockSnapshot, e: StockSnapshot, w: StockSnapshot
    ) -> tuple[DiffType, int, StockSuggestion | None]:
        platform_value = p.available
        warehouse = min(
            [value for value in (e.available, w.available) if value is not None],
            default=None,
        )
        if platform_value is None and warehouse is None:
            return DiffType.CONSISTENT, 0, None
        if platform_value is None:
            return DiffType.MISMATCH, 0, None
        if warehouse is None:
            # 缺少仓库数据：不猜，标差异待人工核对
            return DiffType.MISMATCH, 0, None
        if platform_value <= 0 and warehouse > 0:
            quantity = max(0, warehouse - platform_value) + self.safety_stock
            return (
                DiffType.STOCKOUT,
                warehouse - platform_value,
                StockSuggestion(
                    suggestion_id=StockSuggestion.new_id(),
                    sku=p.sku,
                    action=SuggestionAction.REPLENISH,
                    quantity=quantity,
                    reason=f"平台可售 {platform_value}，仓库可售 {warehouse}，建议补货",
                ),
            )
        if platform_value > 0 and warehouse <= 0:
            return (
                DiffType.OVERSELL,
                platform_value - warehouse,
                StockSuggestion(
                    suggestion_id=StockSuggestion.new_id(),
                    sku=p.sku,
                    action=SuggestionAction.PAUSE,
                    reason="平台有可售但仓库无货，建议先暂停推广/下架核对",
                ),
            )
        delta = abs(platform_value - warehouse)
        if delta > self.tolerance:
            return (
                DiffType.MISMATCH,
                delta,
                StockSuggestion(
                    suggestion_id=StockSuggestion.new_id(),
                    sku=p.sku,
                    action=SuggestionAction.SYNC,
                    quantity=delta,
                    reason=f"三方差异 {delta} 超过容差 {self.tolerance}，建议核对后同步",
                ),
            )
        if platform_value >= self.slow_threshold:
            return (
                DiffType.STAGNANT,
                platform_value,
                StockSuggestion(
                    suggestion_id=StockSuggestion.new_id(),
                    sku=p.sku,
                    action=SuggestionAction.PAUSE,
                    reason=f"可售 {platform_value} 高于滞销阈值 {self.slow_threshold}，建议评估动销",
                ),
            )
        return DiffType.CONSISTENT, 0, None
