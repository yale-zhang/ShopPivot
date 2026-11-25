"""run_id：贯通 T0~T6、日志、报表与审计的唯一关联键（主文档 §8.4）。"""
from __future__ import annotations

import re
from dataclasses import dataclass
from uuid import uuid4

_RUN_ID_RE = re.compile(r"^run_[0-9a-f]{16}$")


@dataclass(frozen=True, slots=True)
class RunId:
    value: str

    def __post_init__(self) -> None:
        if not _RUN_ID_RE.match(self.value):
            raise ValueError(f"非法 run_id: {self.value!r}，期望 run_<16位小写hex>")

    @staticmethod
    def new() -> "RunId":
        return RunId(f"run_{uuid4().hex[:16]}")

    @classmethod
    def parse(cls, raw: str) -> "RunId":
        return cls(raw)

    def __str__(self) -> str:
        return self.value
