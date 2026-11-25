"""三级取数降级与 fail-closed 单测。"""
from __future__ import annotations

from datetime import date

import pytest

from kernel.contexts.integration.domain.fetch_strategy import FetchStrategyResolver
from kernel.contexts.integration.domain.models import FetchChannelUnavailable, FetchSpec
from kernel.contexts.metric_data.domain.ports import RawPayload
from shared.errors.registry import DomainError
from shared.types.values import Channel, StatWindow

SPEC = FetchSpec(
    platform="demo",
    shop_id="S1",
    dataset="order",
    window=StatWindow(date(2026, 11, 25), date(2026, 11, 25)),
)


class FakeAdapter:
    platform = "demo"

    def __init__(self, behavior: dict[Channel, object]) -> None:
        self.behavior = behavior
        self.calls: list[Channel] = []

    def fetch(self, spec: FetchSpec, channel: Channel) -> RawPayload:
        self.calls.append(channel)
        result = self.behavior[channel]
        if isinstance(result, Exception):
            raise result
        return result  # type: ignore[return-value]

    def to_canonical(self, raw: RawPayload):  # type: ignore[no-untyped-def]
        return []


def _payload(channel: Channel = Channel.BACKEND_EXPORT) -> RawPayload:
    return RawPayload(
        platform="demo", shop_id="S1", dataset="order", channel=channel,
        records=[{"order_id": "1"}], payload_hash="h",
    )


def test_falls_back_from_open_api_to_export() -> None:
    adapter = FakeAdapter(
        {
            Channel.OPEN_API: FetchChannelUnavailable("no api"),
            Channel.BACKEND_EXPORT: _payload(),
        }
    )
    payload = FetchStrategyResolver({"demo": adapter}).resolve(SPEC)
    assert payload.channel is Channel.BACKEND_EXPORT
    assert adapter.calls == [Channel.OPEN_API, Channel.BACKEND_EXPORT]


def test_rate_limit_is_retryable_and_falls_back() -> None:
    adapter = FakeAdapter(
        {
            Channel.OPEN_API: DomainError("E005", "限流"),
            Channel.BACKEND_EXPORT: _payload(),
        }
    )
    assert FetchStrategyResolver({"demo": adapter}).resolve(SPEC).channel is Channel.BACKEND_EXPORT


@pytest.mark.parametrize("code", ["E003", "E004"])
def test_non_retryable_errors_fail_closed(code: str) -> None:
    adapter = FakeAdapter(
        {Channel.OPEN_API: DomainError(code, "不可降级"), Channel.BACKEND_EXPORT: _payload()}
    )
    with pytest.raises(DomainError) as exc:
        FetchStrategyResolver({"demo": adapter}).resolve(SPEC)
    assert exc.value.code == code
    assert adapter.calls == [Channel.OPEN_API]


def test_all_channels_unavailable_raises_e004_not_silent() -> None:
    adapter = FakeAdapter(
        {
            Channel.OPEN_API: FetchChannelUnavailable("no api"),
            Channel.BACKEND_EXPORT: FetchChannelUnavailable("no export"),
        }
    )
    with pytest.raises(DomainError) as exc:
        FetchStrategyResolver({"demo": adapter}).resolve(SPEC)
    assert exc.value.code == "E004"
    assert "fail-closed" in exc.value.message


def test_gui_fallback_is_not_enabled_in_m0() -> None:
    adapter = FakeAdapter(
        {
            Channel.OPEN_API: FetchChannelUnavailable("no api"),
            Channel.BACKEND_EXPORT: FetchChannelUnavailable("no export"),
        }
    )
    with pytest.raises(DomainError) as exc:
        FetchStrategyResolver({"demo": adapter}, allow_gui=True).resolve(SPEC)
    assert exc.value.code == "E001"


def test_unknown_platform_fails_closed() -> None:
    with pytest.raises(DomainError) as exc:
        FetchStrategyResolver({}).resolve(SPEC)
    assert exc.value.code == "E008"
