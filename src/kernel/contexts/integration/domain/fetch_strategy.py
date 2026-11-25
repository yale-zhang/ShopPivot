"""三级取数策略（ADR-04 / 表 4-5 / E-CMP-01）。

M0 只实现前两级：官方接口 → 后台导出；第三级网页兜底在 M0 显式不可用，
避免"绕过鉴权补数"（C2）。任何一级失败都带错误码与层级，不静默降级。
"""
from __future__ import annotations

from typing import Mapping

from kernel.contracts.extension_points import PlatformAdapterPort
from kernel.contexts.integration.domain.models import FetchChannelUnavailable, FetchSpec
from kernel.contexts.metric_data.domain.ports import RawPayload
from shared.errors.registry import DomainError
from shared.types.values import Channel


class FetchStrategyResolver:
    def __init__(
        self,
        adapters: Mapping[str, PlatformAdapterPort],
        *,
        allow_gui: bool = False,
    ) -> None:
        self.adapters = dict(adapters)
        self.allow_gui = allow_gui

    def resolve(self, spec: FetchSpec) -> RawPayload:
        adapter = self.adapters.get(spec.platform)
        if adapter is None:
            raise DomainError(
                "E008",
                f"未注册平台适配器: {spec.platform}",
                details={"platform": spec.platform, "dataset": spec.dataset},
            )
        attempted: list[str] = []
        last_error: Exception | None = None
        for channel in (Channel.OPEN_API, Channel.BACKEND_EXPORT):
            attempted.append(channel.value)
            try:
                payload = adapter.fetch(spec, channel)
            except FetchChannelUnavailable:
                continue
            except DomainError as exc:
                # 限流/超时可降级；数据合同缺失/未授权必须 fail-closed
                if exc.code == "E005":
                    last_error = exc
                    continue
                raise
            if payload.records or payload.meta.get("empty_ok"):
                return payload
            last_error = DomainError(
                "E004",
                f"{channel.label} 通道未返回任何记录",
                details={"channel": channel.value, "dataset": spec.dataset},
            )
        if self.allow_gui:
            attempted.append(Channel.GUI_FALLBACK.value)
            raise DomainError(
                "E001",
                "网页兜底通道尚未实现（M2 按表 6-15 判据启用）",
                details={"attempted": attempted},
            )
        raise DomainError(
            "E004",
            "三级取数均未取到可用数据，已 fail-closed（不绕过鉴权、不改用网页抓取补数）",
            details={
                "attempted": attempted,
                "last_error": str(last_error) if last_error else None,
            },
        )
