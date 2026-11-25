"""扩展点注册表（主文档表 9-9 / 表 9-15）。

Kernel 只通过注册表消费模块贡献：
- 每项贡献带 (kind, id) 稳定键，重复即拒绝加载；
- 模块被禁用/卸载时按模块名整体摘除，再按 ID 精确比对无残留；
- 注册表是进程内视图，持久化状态在 module_state 表。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


class DuplicateContribution(Exception):
    def __init__(self, kind: str, contribution_id: str, owner: str, previous: str) -> None:
        self.kind = kind
        self.contribution_id = contribution_id
        self.owner = owner
        self.previous = previous
        super().__init__(
            f"贡献 ID 重复: {kind}/{contribution_id} 已被 {previous} 注册（当前 {owner}）"
        )


@dataclass(frozen=True)
class RegisteredContribution:
    kind: str
    id: str
    module: str
    config: dict[str, Any]


@dataclass
class ExtensionPointRegistry:
    _items: dict[tuple[str, str], RegisteredContribution] = field(default_factory=dict)
    _disabled: set[str] = field(default_factory=set)
    _snapshot: dict[tuple[str, str], RegisteredContribution] = field(default_factory=dict)

    def register(
        self, module: str, kind: str, contribution_id: str, config: dict[str, Any] | None = None
    ) -> RegisteredContribution:
        key = (kind, contribution_id)
        existing = self._items.get(key)
        if existing is not None:
            raise DuplicateContribution(kind, contribution_id, module, existing.module)
        item = RegisteredContribution(kind=kind, id=contribution_id, module=module,
                                      config=dict(config or {}))
        self._items[key] = item
        return item

    def unregister_module(self, module: str) -> list[str]:
        removed: list[str] = []
        for key, item in list(self._items.items()):
            if item.module == module:
                removed.append(f"{item.kind}/{item.id}")
                del self._items[key]
        return removed

    def get(self, kind: str, contribution_id: str) -> RegisteredContribution | None:
        item = self._items.get((kind, contribution_id))
        if item is None or item.module in self._disabled:
            return None
        return item

    def require(self, kind: str, contribution_id: str) -> RegisteredContribution:
        item = self.get(kind, contribution_id)
        if item is None:
            raise KeyError(f"未注册的扩展点贡献: {kind}/{contribution_id}")
        return item

    def by_kind(self, kind: str) -> list[RegisteredContribution]:
        return [
            item
            for item in self._items.values()
            if item.kind == kind and item.module not in self._disabled
        ]

    def by_module(self, module: str) -> list[RegisteredContribution]:
        return [item for item in self._items.values() if item.module == module]

    def all_ids(self) -> dict[str, str]:
        return {f"{item.kind}/{item.id}": item.module for item in self._items.values()}

    def set_disabled(self, modules: set[str] | frozenset[str]) -> None:
        self._disabled = set(modules)

    def disabled_modules(self) -> set[str]:
        return set(self._disabled)

    def snapshot(self) -> None:
        self._snapshot = dict(self._items)

    def restore(self) -> None:
        self._items = dict(self._snapshot)

    def clear(self) -> None:
        self._items.clear()
        self._disabled.clear()
        self._snapshot.clear()

    def __len__(self) -> int:
        return len(self._items)
