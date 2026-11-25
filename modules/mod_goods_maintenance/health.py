"""S02 健康检查：动作处理器可导入、价格状态目录可写。"""
from __future__ import annotations

from pathlib import Path


def probe() -> tuple[bool, str]:
    state = Path("./storage/platform_state")
    try:
        state.mkdir(parents=True, exist_ok=True)
        probe_file = state / ".health"
        probe_file.write_text("ok", encoding="utf-8")
        probe_file.unlink(missing_ok=True)
    except OSError as exc:
        return False, f"价格状态目录不可写: {exc}"
    return True, ""
