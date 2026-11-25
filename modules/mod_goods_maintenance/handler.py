"""价格批量维护动作：模拟商家后台页面写入（本地受控状态），带前后快照与回查。

真实平台接入时只需替换本文件的页面写入/回查实现，动作码与闸门契约不变。
"""
from __future__ import annotations

import json
import os
import threading
from decimal import Decimal
from pathlib import Path
from typing import Any

from kernel.contracts.extension_points import ActionResult, ActionPlan, WriteActionRequest
from shared.errors.registry import DomainError

_LOCK = threading.Lock()
_DEFAULT_PRICES = {
    "SKU-A": "89.00",
    "SKU-B": "129.00",
    "SKU-C": "59.00",
    "SKU-D": "199.00",
    "SKU-E": "39.00",
}


class PriceUpdateAction:
    action_code = "S02.price_update"

    def __init__(self, config: dict[str, Any]) -> None:
        state_dir = Path(config.get("_state_dir", "./storage/platform_state"))
        state_dir.mkdir(parents=True, exist_ok=True)
        self.state_path = state_dir / "demo_prices.json"
        if not self.state_path.is_file():
            self._write(dict(_DEFAULT_PRICES))

    # ------------------------------------------------------------------ plan
    def build(self, request: WriteActionRequest) -> ActionPlan:
        current = self._read()
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for raw in request.rows:
            sku = str(raw.get("sku", "")).strip()
            if not sku:
                raise DomainError("E006", "变更清单缺少 SKU")
            if sku in seen:
                raise DomainError("E006", f"变更清单存在重复 SKU: {sku}")
            seen.add(sku)
            if sku not in current:
                raise DomainError("E004", f"目标 SKU 不在平台商品清单: {sku}")
            after = _money(raw.get("after"), "目标价")
            before = _money(current[sku], "当前价")
            if after <= 0:
                raise DomainError("E006", f"目标价必须大于 0: {sku}")
            if after == before:
                raise DomainError("E006", f"{sku} 目标价与当前价相同，无需变更")
            if abs((after - before) / before) > Decimal("0.5"):
                raise DomainError("E006", f"价格变动超过 50%，禁止走批量维护: {sku}")
            rows.append(
                {
                    "target": sku,
                    "field": "price",
                    "before": f"{before:.2f}",
                    "after": f"{after:.2f}",
                    "impact": f"{sku} 活动价 {before:.2f} → {after:.2f}",
                }
            )
        if not rows:
            raise DomainError("E006", "变更清单为空")

        amount_before = sum(Decimal(row["before"]) for row in rows)
        amount_after = sum(Decimal(row["after"]) for row in rows)
        first_sku = rows[0]["target"]
        return ActionPlan(
            rows=rows,
            before_snapshot={
                "shot": f"shot://before/S02/{first_sku}",
                "prices": {row["target"]: row["before"] for row in rows},
                "state_path": str(self.state_path),
                "metric_version": "v1.0",
            },
            summary=f"商品价格批量维护 · {len(rows)} 个 SKU",
            impact_scope=(
                f"影响 {len(rows)} 个 SKU · 金额区间 ¥{amount_before:.2f}–{amount_after:.2f}"
            ),
            rollback_plan="按变更单前值逐条还原；执行后回查一致才归档",
            evidence=[
                {"kind": "snapshot", "ref": f"shot://before/S02/{first_sku}", "label": "变更前页面快照"},
                {"kind": "state", "ref": f"state://prices/{first_sku}", "label": "当前价格快照"},
                {"kind": "probe", "ref": "probe://price_batch", "label": "价格校验探针"},
                {"kind": "metric_card", "ref": "metric.gmv@1.0", "label": "影响评估口径"},
            ],
        )

    # ------------------------------------------------------------------ execute
    def apply(self, plan) -> ActionResult:  # type: ignore[no-untyped-def]
        with _LOCK:
            current = self._read()
            for row in plan.rows:
                sku = str(row["target"])
                if current.get(sku) != row["before"]:
                    raise DomainError(
                        "E006",
                        f"{sku} 当前价 {current.get(sku)} 与变更单前值 {row['before']} 不一致，"
                        "已停止执行（审批前参数变化必须重新走审批）",
                    )
            for row in plan.rows:
                current[str(row["target"])] = str(row["after"])
            self._write(current)
        return ActionResult(
            verified=True,
            applied_rows=[dict(row) for row in plan.rows],
            after_shot=f"shot://after/S02/{plan.plan_id}",
            details={"state_path": str(self.state_path), "rows": len(plan.rows)},
        )

    def verify(self, plan) -> bool:  # type: ignore[no-untyped-def]
        current = self._read()
        return all(current.get(str(row["target"])) == row["after"] for row in plan.rows)

    def compensate(self, plan) -> bool:  # type: ignore[no-untyped-def]
        with _LOCK:
            current = self._read()
            for row in plan.rows:
                current[str(row["target"])] = str(row["before"])
            self._write(current)
        return self.verify_restored(plan)

    def verify_restored(self, plan) -> bool:  # type: ignore[no-untyped-def]
        current = self._read()
        return all(current.get(str(row["target"])) == row["before"] for row in plan.rows)

    # ------------------------------------------------------------------ state
    def _read(self) -> dict[str, str]:
        try:
            return json.loads(self.state_path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return dict(_DEFAULT_PRICES)

    def _write(self, data: dict[str, str]) -> None:
        tmp = self.state_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, self.state_path)


def _money(value: Any, label: str) -> Decimal:
    try:
        return Decimal(str(value)).quantize(Decimal("0.01"))
    except Exception as exc:  # noqa: BLE001
        raise DomainError("E006", f"{label}不是合法金额: {value!r}") from exc
