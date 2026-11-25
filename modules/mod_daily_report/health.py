"""mod_daily_report 健康检查：口径卡文件齐套（发布自检的最小版）。"""
from __future__ import annotations

from pathlib import Path

EXPECTED = [
    "uv.yaml",
    "pv.yaml",
    "paid_orders.yaml",
    "gmv.yaml",
    "refund_amount.yaml",
    "net_gmv.yaml",
    "aov.yaml",
    "cvr.yaml",
    "ad_cost.yaml",
    "roi.yaml",
    "dsr.yaml",
    "inventory_turnover.yaml",
]


def probe() -> tuple[bool, str]:
    base = Path(__file__).parent / "data" / "metric_cards"
    missing = [name for name in EXPECTED if not (base / name).is_file()]
    if missing:
        return False, f"口径卡缺失: {', '.join(missing)}"
    return True, ""
