"""1688 选品/采购提供方实现。

- `SkillCliSourcingProvider`：调用已安装的 1688-distribution Skill CLI（确定性 JSON），
  需要用户先通过 Skill Hub 安装技能并配置 AK；缺技能/AK 时 fail-closed。
- `UtpPurchaseProvider`：调用 UTP CLI 创建 checkout；**绝不调用 checkout_complete / 代付**，
  支付必须由人在 UTP 卡片或 1688 收银台完成。
- Mock 提供方只用于本地演示与测试。
"""
from __future__ import annotations

import json
import shutil
import subprocess
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import uuid4

from kernel.contexts.integration.domain.sourcing import (
    CheckoutResult,
    ProviderUnavailable,
)
from kernel.contexts.metric_data.domain.purchase import PurchaseItem, PurchaseStatus
from kernel.contexts.metric_data.domain.sourcing import SupplierOffer

# 1688-distribution Skill 的搜索 CLI 只允许这类商品筛选，避免把任意参数拼进命令
_ALLOWED_FILTERS = {
    "title",
    "cate_level1_name",
    "cate_level2_name",
    "cate_name",
    "is_free_post",
    "is_yjdf",
    "df_price",
    "df_post",
    "is_24hour_send_fx",
    "is_48hour_send_fx",
    "is_no_reason_to_return_7d_fx",
    "fx_ord_cnt_30d",
    "ord_cnt_30d",
    "is_shili_factory",
    "channels",
}


class Mock1688SourcingProvider:
    name = "mock-1688"

    def __init__(self, fixtures_path: str | Path) -> None:
        self.fixtures_path = Path(fixtures_path)

    def search(
        self, keyword: str, limit: int = 20, filters: list[dict[str, Any]] | None = None
    ) -> list[SupplierOffer]:
        if not self.fixtures_path.is_file():
            raise ProviderUnavailable(f"1688 演示数据不存在: {self.fixtures_path}")
        raw = json.loads(self.fixtures_path.read_text(encoding="utf-8"))
        tokens = [token for token in keyword.split() if token]
        offers: list[SupplierOffer] = []
        for item in raw:
            title = str(item["title"])
            if tokens and not any(token in title for token in tokens):
                continue
            offers.append(
                SupplierOffer(
                    offer_id=str(item["offer_id"]),
                    title=title,
                    price=Decimal(str(item["price"])),
                    post_fee=Decimal(str(item.get("post_fee", "0"))),
                    moq=int(item.get("moq", 1)),
                    sales_30d=int(item.get("sales_30d", 0)),
                    supplier=str(item.get("supplier", "")),
                    pic_url=str(item.get("pic_url", "")),
                    url=str(item.get("url", "")),
                    brand_authorized=bool(item.get("brand_authorized", True)),
                    raw=item,
                )
            )
            if len(offers) >= limit:
                break
        return offers


class SkillCliSourcingProvider:
    """调用 1688-distribution Skill：python3 scripts/cli.py product_search_helper search ..."""

    name = "1688-distribution-skill"

    def __init__(
        self,
        *,
        skill_dir: str | Path,
        python_bin: str | None = None,
        timeout_seconds: int = 30,
    ) -> None:
        self.skill_dir = Path(skill_dir)
        self.python_bin = python_bin or "python3"
        self.timeout_seconds = timeout_seconds

    def _cli(self) -> Path:
        cli = self.skill_dir / "scripts" / "cli.py"
        if not cli.is_file():
            raise ProviderUnavailable(
                f"未找到 1688 Skill CLI: {cli}；请先从 1688 Skill Hub 安装 1688-distribution"
            )
        return cli

    def search(
        self, keyword: str, limit: int = 20, filters: list[dict[str, Any]] | None = None
    ) -> list[SupplierOffer]:
        cli = self._cli()
        conditions: list[dict[str, Any]] = [
            {"code": "title", "value": [keyword], "queryType": "contains_any"}
        ]
        for item in filters or []:
            if item.get("code") in _ALLOWED_FILTERS:
                conditions.append(item)
        command = [
            self.python_bin,
            str(cli),
            "product_search_helper",
            "search",
            f"--filters={json.dumps(conditions, ensure_ascii=False)}",
            f"--page_size={max(1, min(limit, 50))}",
            "--rank_type=DESC",
            "--rank_field=fx_ord_cnt_30d",
        ]
        try:
            completed = subprocess.run(
                command,
                cwd=str(self.skill_dir),
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise ProviderUnavailable(f"1688 Skill CLI 执行失败: {exc}") from exc
        if completed.returncode != 0:
            raise ProviderUnavailable(
                f"1688 Skill CLI 返回 {completed.returncode}: {completed.stderr.strip()[:300]}"
            )
        payload = _extract_json(completed.stdout)
        if not payload.get("success"):
            raise ProviderUnavailable(
                f"1688 Skill CLI 业务失败: {str(payload.get('error') or payload)[:300]}"
            )
        data = payload.get("data") or {}
        rows = data.get("data") if isinstance(data, dict) else data
        if not isinstance(rows, list):
            rows = []
        offers: list[SupplierOffer] = []
        for row in rows[:limit]:
            offer_id = str(row.get("offerId") or row.get("offer_id") or "")
            if not offer_id:
                continue
            offers.append(
                SupplierOffer(
                    offer_id=offer_id,
                    title=str(row.get("title", "")),
                    price=Decimal(str(row.get("dfPrice") or row.get("price") or "0")),
                    post_fee=Decimal(str(row.get("dfPost") or row.get("post_fee") or "0")),
                    moq=int(row.get("moq") or row.get("minOrder") or 1),
                    sales_30d=int(row.get("fxOrdCnt30d") or row.get("sales_30d") or 0),
                    supplier=str(
                        row.get("companyName")
                        or row.get("supplierName")
                        or row.get("sellerNick")
                        or ""
                    ),
                    pic_url=str(row.get("offerPic") or row.get("pic_url") or ""),
                    url=f"https://detail.1688.com/offer/{offer_id}.html",
                    brand_authorized=not (
                        bool(row.get("isBrandOffer")) and not bool(row.get("isBrandAuth"))
                    ),
                    raw=row,
                )
            )
        return offers


class MockPurchaseProvider:
    name = "mock-utp"

    def __init__(self) -> None:
        self._checkouts: dict[str, CheckoutResult] = {}

    def create_checkout(
        self, items: list[PurchaseItem], buyer_note: str = ""
    ) -> CheckoutResult:
        checkout_id = f"mockco_{uuid4().hex[:12]}"
        total = sum((item.subtotal for item in items), Decimal("0.00"))
        result = CheckoutResult(
            checkout_id=checkout_id,
            status=PurchaseStatus.AWAITING_PAYMENT,
            continue_url=f"https://ucp-b2b.com/mock-checkout/{checkout_id}",
            total=total,
            details={"buyer_note": buyer_note, "mock": True},
        )
        self._checkouts[checkout_id] = result
        return result

    def get_checkout(self, checkout_id: str) -> CheckoutResult:
        result = self._checkouts.get(checkout_id)
        if result is None:
            raise ProviderUnavailable(f"checkout 不存在: {checkout_id}")
        return result

    def cancel_checkout(self, checkout_id: str) -> bool:
        result = self._checkouts.get(checkout_id)
        if result is None:
            return False
        self._checkouts[checkout_id] = CheckoutResult(
            checkout_id=result.checkout_id,
            status=PurchaseStatus.CANCELLED,
            continue_url="",
            total=result.total,
            details=result.details,
        )
        return True


class UtpPurchaseProvider:
    """UTP CLI 采购：只创建/查询 checkout，绝不代提交、代支付。"""

    name = "utp-cli"

    def __init__(
        self,
        *,
        utp_bin: str | None = None,
        host: str = "https://ucp-b2b.com",
        timeout_seconds: int = 30,
    ) -> None:
        self.utp_bin = utp_bin or "utp"
        self.host = host
        self.timeout_seconds = timeout_seconds

    def _invoke(self, tool: str, args: dict[str, Any]) -> dict[str, Any]:
        if shutil.which(self.utp_bin) is None:
            raise ProviderUnavailable(
                "未找到 utp CLI；请安装 1688-utp-shopping Skill 并登录绑定买家身份"
            )
        command = [
            self.utp_bin,
            "invoke",
            tool,
            "--args",
            json.dumps(args, ensure_ascii=False),
        ]
        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise ProviderUnavailable(f"utp CLI 执行失败: {exc}") from exc
        if completed.returncode != 0:
            raise ProviderUnavailable(
                f"utp CLI 返回 {completed.returncode}: {completed.stderr.strip()[:300]}"
            )
        return _extract_json(completed.stdout)

    def create_checkout(
        self, items: list[PurchaseItem], buyer_note: str = ""
    ) -> CheckoutResult:
        if not items:
            raise ProviderUnavailable("采购项为空")
        # Normal 模式：product-id:spec-id:quantity；1688 offer id 作为 product_id
        encoded = [
            f"{item.offer_id}:{item.spec_id or item.offer_id}:{item.quantity}"
            for item in items
        ]
        self._invoke("utp_discover", {"host": self.host})
        payload = self._invoke(
            "utp_checkout_create", {"items": encoded, "currency": "CNY"}
        )
        return _checkout_from_payload(payload, items)

    def get_checkout(self, checkout_id: str) -> CheckoutResult:
        payload = self._invoke("utp_checkout_get", {"checkout_id": checkout_id})
        return _checkout_from_payload(payload, [])

    def cancel_checkout(self, checkout_id: str) -> bool:
        # utp_checkout_cancel 为 app-only，AI/CLI 不代取消；交由人在卡片/收银台操作
        return False


def _extract_json(stdout: str) -> dict[str, Any]:
    text = stdout.strip()
    if not text:
        raise ProviderUnavailable("提供方没有返回内容")
    try:
        payload = json.loads(text)
        if isinstance(payload, dict):
            return payload
    except json.JSONDecodeError:
        pass
    # 允许 CLI 在前置日志后输出 JSON：从最后一个 '{' 开始尝试
    for index in range(len(text) - 1, -1, -1):
        if text[index] != "{":
            continue
        try:
            payload = json.loads(text[index:])
            if isinstance(payload, dict):
                return payload
        except json.JSONDecodeError:
            continue
    raise ProviderUnavailable(f"提供方返回非 JSON: {text[:200]}")


def _checkout_from_payload(
    payload: dict[str, Any], items: list[PurchaseItem]
) -> CheckoutResult:
    raw_data = payload.get("data")
    data: dict[str, Any] = raw_data if isinstance(raw_data, dict) else payload
    checkout_id = str(
        data.get("checkout_id")
        or data.get("checkoutId")
        or data.get("id")
        or (data.get("checkout") or {}).get("id")
        or ""
    )
    if not checkout_id:
        raise ProviderUnavailable(f"checkout 创建失败: {str(payload)[:300]}")
    raw_status = str(data.get("status") or "ready_for_complete")
    status = _map_status(raw_status)
    if items:
        total = sum((item.subtotal for item in items), Decimal("0.00"))
    else:
        total_raw = data.get("total") or data.get("amount") or 0
        total = Decimal(str(total_raw))
    return CheckoutResult(
        checkout_id=checkout_id,
        status=status,
        continue_url=str(data.get("continue_url") or data.get("continueUrl") or ""),
        total=total,
        details=data,
    )


def _map_status(raw: str) -> PurchaseStatus:
    mapping = {
        "ready_for_complete": PurchaseStatus.AWAITING_PAYMENT,
        "awaiting_payment": PurchaseStatus.AWAITING_PAYMENT,
        "pending": PurchaseStatus.AWAITING_CONFIRMATION,
        "completed": PurchaseStatus.PAID,
        "paid": PurchaseStatus.PAID,
        "cancelled": PurchaseStatus.CANCELLED,
        "canceled": PurchaseStatus.CANCELLED,
        "failed": PurchaseStatus.FAILED,
    }
    return mapping.get(raw.lower(), PurchaseStatus.AWAITING_PAYMENT)
