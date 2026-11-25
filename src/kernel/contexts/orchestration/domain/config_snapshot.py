"""配置快照：运行时固化口径版本、阈值、店铺清单，保证结果可复算、可审计。"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Mapping


@dataclass(frozen=True, slots=True)
class ConfigSnapshot:
    payload: Mapping[str, Any]
    hash: str

    @classmethod
    def build(cls, payload: Mapping[str, Any]) -> "ConfigSnapshot":
        serializable = json.loads(json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str))
        digest = hashlib.sha256(
            json.dumps(serializable, ensure_ascii=False, sort_keys=True).encode("utf-8")
        ).hexdigest()
        return cls(payload=MappingProxyType(serializable), hash=digest)

    def get(self, key: str, default: Any = None) -> Any:
        return self.payload.get(key, default)

    def to_dict(self) -> dict[str, Any]:
        return dict(self.payload)
