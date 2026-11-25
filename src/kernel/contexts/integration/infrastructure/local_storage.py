"""本地对象存储（dev/测试默认）；生产可替换为 MinIO，端口不变。"""
from __future__ import annotations

from pathlib import Path

from shared.errors.registry import DomainError


class LocalReportStorage:
    def __init__(self, root: Path | str) -> None:
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _resolve(self, ref: str) -> Path:
        rel = ref.removeprefix("file://")
        target = (self.root / rel).resolve()
        if self.root not in target.parents and target != self.root:
            raise DomainError("E008", f"对象存储路径越界: {ref}")
        return target

    def put_bytes(self, key: str, data: bytes, content_type: str = "") -> str:
        target = self._resolve(f"file://{key}")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        return f"file://{target.relative_to(self.root).as_posix()}"

    def get_bytes(self, ref: str) -> bytes:
        target = self._resolve(ref)
        if not target.is_file():
            raise DomainError("E008", f"对象不存在: {ref}")
        return target.read_bytes()

    def exists(self, ref: str) -> bool:
        return self._resolve(ref).is_file()
