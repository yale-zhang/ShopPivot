"""S03 健康检查：活动台账目录可写。"""
from __future__ import annotations

from pathlib import Path


def probe() -> tuple[bool, str]:
    state = Path("./storage/platform_state")
    try:
        state.mkdir(parents=True, exist_ok=True)
        probe_file = state / ".campaign_health"
        probe_file.write_text("ok", encoding="utf-8")
        probe_file.unlink(missing_ok=True)
    except OSError as exc:
        return False, f"活动台账目录不可写: {exc}"
    return True, ""
