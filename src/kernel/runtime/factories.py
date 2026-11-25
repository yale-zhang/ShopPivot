"""运行时工厂解析：manifest 里只写点分路径，装配时再导入。

这样模块可以声明"我提供什么"，而不必在 import 阶段就把执行面/数据库依赖拉起来。
"""
from __future__ import annotations

from typing import Any


def import_object(path: str) -> Any:
    """支持 "pkg.mod:attr" 与 "pkg.mod.attr" 两种写法。"""
    if not path or not isinstance(path, str):
        raise ValueError(f"非法的工厂路径: {path!r}")
    import importlib

    if ":" in path:
        module_path, _, attr = path.partition(":")
    else:
        module_path, _, attr = path.rpartition(".")
    if not module_path or not attr:
        raise ValueError(f"非法的工厂路径: {path!r}（需 a.b:C 形式）")
    module = importlib.import_module(module_path)
    try:
        return getattr(module, attr)
    except AttributeError as exc:
        raise ImportError(f"{module_path} 中不存在 {attr}") from exc


def build_object(path: str, **kwargs: Any) -> Any:
    factory = import_object(path)
    return factory(**kwargs)
