"""活动提报动作：模拟活动报名页写入（本地受控台账），含重复提报与价格校验。"""
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


class CampaignApplyAction:
    action_code = "S03.campaign_apply"

    def __init__(self, config: dict[str, Any]) -> None:
        state_dir = Path(config.get("_state_dir", "./storage/platform_state"))
        state_dir.mkdir(parents=True, exist_ok=True)
        self.state_dir = state_dir
        self.signup_path = state_dir / "campaign_signups.json"
        self.price_path = state_dir / "demo_prices.json"
        if not self.signup_path.is_file():
            self._write(self.signup_path, {})

    # ------------------------------------------------------------------ plan
    def build(self, request: WriteActionRequest) -> ActionPlan:
        signups = self._read(self.signup_path)
        prices = self._read(self.price_path) if self.price_path.is_file() else {}
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for raw in request.rows:
            campaign = str(raw.get("campaign_id", "")).strip()
            sku = str(raw.get("sku", "")).strip()
            if not campaign or not sku:
                raise DomainError("E006", "提报清单缺少活动或 SKU")
            key = f"{campaign}:{sku}"
            if key in seen:
                raise DomainError("E006", f"提报清单重复: {key}")
            seen.add(key)
            if key in signups:
                raise DomainError("E006", f"{sku} 已在活动 {campaign} 中提报，禁止重复报名")
            price = _money(raw.get("activity_price"), "活动价")
            if price <= 0:
                raise DomainError("E006", f"活动价必须大于 0: {key}")
            base_raw = prices.get(sku)
            if base_raw is not None and price > Decimal(str(base_raw)):
                raise DomainError(
                    "E006",
                    f"活动价 {price:.2f} 高于日常价 {Decimal(str(base_raw)):.2f}，禁止提报: {sku}",
                )
            rows.append(
                {
                    "target": key,
                    "field": "activity_price",
                    "before": "未提报",
                    "after": f"{price:.2f}",
                    "impact": f"{sku} 报名活动 {campaign}，活动价 ¥{price:.2f}",
                }
            )
        if not rows:
            raise DomainError("E006", "提报清单为空")
        first = rows[0]["target"]
        return ActionPlan(
            rows=rows,
            before_snapshot={
                "shot": f"shot://before/S03/{first}",
                "signups": {row["target"]: None for row in rows},
                "state_path": str(self.signup_path),
                "metric_version": "v1.0",
            },
            summary=f"活动提报 · {len(rows)} 个商品",
            impact_scope=f"活动报名 {len(rows)} 行 · 需平台资格与库存校验",
            rollback_plan="撤销报名并删除本地提报台账记录；活动开始前人工复核",
            evidence=[
                {"kind": "snapshot", "ref": f"shot://before/S03/{first}", "label": "活动报名页快照"},
                {"kind": "rule", "ref": "rule://campaign/eligibility", "label": "资格与互斥校验"},
                {"kind": "state", "ref": "state://campaign/signups", "label": "提报台账快照"},
                {"kind": "probe", "ref": "probe://campaign/duplicate", "label": "重复提报探针"},
            ],
        )

    # ------------------------------------------------------------------ execute
    def apply(self, plan) -> ActionResult:  # type: ignore[no-untyped-def]
        with _LOCK:
            signups = self._read(self.signup_path)
            for row in plan.rows:
                if row["target"] in signups:
                    raise DomainError("E006", f"已存在提报记录: {row['target']}，禁止重复提交")
            for row in plan.rows:
                signups[row["target"]] = row["after"]
            self._write(self.signup_path, signups)
        return ActionResult(
            verified=True,
            applied_rows=[dict(row) for row in plan.rows],
            after_shot=f"shot://after/S03/{plan.plan_id}",
            details={"state_path": str(self.signup_path), "rows": len(plan.rows)},
        )

    def verify(self, plan) -> bool:  # type: ignore[no-untyped-def]
        signups = self._read(self.signup_path)
        return all(signups.get(row["target"]) == row["after"] for row in plan.rows)

    def compensate(self, plan) -> bool:  # type: ignore[no-untyped-def]
        with _LOCK:
            signups = self._read(self.signup_path)
            for row in plan.rows:
                signups.pop(row["target"], None)
            self._write(self.signup_path, signups)
        return all(row["target"] not in self._read(self.signup_path) for row in plan.rows)

    # ------------------------------------------------------------------ state
    @staticmethod
    def _read(path: Path) -> dict[str, Any]:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return {}

    @staticmethod
    def _write(path: Path, data: dict[str, Any]) -> None:
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, path)


def _money(value: Any, label: str) -> Decimal:
    try:
        return Decimal(str(value)).quantize(Decimal("0.01"))
    except Exception as exc:  # noqa: BLE001
        raise DomainError("E006", f"{label}不是合法金额: {value!r}") from exc
