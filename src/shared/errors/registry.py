"""E001~E008 / LOG-01~05 注册表。

【重要】主文档反复引用 E001~E008 与 LOG-01~05，但定义在外部《RPA 应用项目方案（模板）》中，
本文档未展开。这里先按文档中出现的上下文（表 4-4 第 3 行、§8.9 代码骨架、R-08、表 6-9）
给出**临时映射**，作为唯一事实源；模板齐备后只改本文件，不改调用点。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class ErrorSpec:
    code: str
    name: str
    description: str
    default_layer: str
    retryable: bool
    http_status: int
    user_message: str


ERROR_SPECS: dict[str, ErrorSpec] = {
    "E001": ErrorSpec(
        "E001", "UI_ELEMENT", "页面结构改版 / 元素定位失败 / 控件树缺失",
        "UI", True, 502, "页面结构可能已改版，已保留现场截图，请转人工确认",
    ),
    "E002": ErrorSpec(
        "E002", "AUTH_SESSION", "登录态失效 / 验证码 / 2FA / 凭据轮换",
        "SYS", True, 401, "登录态失效或需人工验证，已停止自动执行",
    ),
    "E003": ErrorSpec(
        "E003", "PERMISSION", "权限不足 / 字段未授权",
        "SYS", False, 403, "该字段未授权，已跳过（不绕过鉴权补数）",
    ),
    "E004": ErrorSpec(
        "E004", "DATA_CONTRACT", "字段缺失 / 字段漂移 / 导出模板改版 / 数据不可用",
        "DATA", False, 422, "数据结构与数据合同不一致，已阻断并生成漂移待办",
    ),
    "E005": ErrorSpec(
        "E005", "TIMEOUT_NETWORK", "接口超时 / 网络异常 / 平台限流",
        "SYS", True, 504, "平台接口超时或限流，已退避重试",
    ),
    "E006": ErrorSpec(
        "E006", "BUSINESS_RULE", "业务规则校验失败（资格 / 价格 / 库存 / 重复）",
        "CODE", False, 409, "业务校验未通过，未提交任何写入",
    ),
    "E007": ErrorSpec(
        "E007", "GATE_APPROVAL", "闸门 / 审批 / WriteToken / 校验不一致",
        "CODE", False, 403, "审批或写入许可校验未通过",
    ),
    "E008": ErrorSpec(
        "E008", "SYSTEM_CONFIG", "系统配置 / 依赖 / 存储 / 模块装配不可用",
        "SYS", True, 503, "系统配置或依赖不可用，请联系运维",
    ),
}


@dataclass(frozen=True, slots=True)
class LogSpec:
    code: str
    name: str
    fields: tuple[str, ...]


LOG_SPECS: dict[str, LogSpec] = {
    "LOG-01": LogSpec("LOG-01", "module.boot", ("module", "version", "state")),
    "LOG-02": LogSpec("LOG-02", "fetch", ("run_id", "node_id", "channel", "cost_ms")),
    "LOG-03": LogSpec("LOG-03", "normalize", ("run_id", "node_id", "records", "cost_ms")),
    "LOG-04": LogSpec("LOG-04", "execute", ("run_id", "node_id", "status", "cost_ms")),
    "LOG-05": LogSpec("LOG-05", "archive", ("run_id", "report_id", "artifact_ref")),
}


@dataclass
class DomainError(Exception):
    """领域异常：错误码唯一，禁止只记「失败」不记层级（表 6-8）。"""

    code: str
    message: str
    layer: str | None = None
    details: dict[str, Any] = field(default_factory=dict)
    status_override: int | None = None

    def __post_init__(self) -> None:
        spec = ERROR_SPECS.get(self.code)
        if spec is None:
            raise ValueError(f"未登记的错误码: {self.code}")
        if self.layer is None:
            self.layer = spec.default_layer
        super().__init__(f"[{self.code}/{self.layer}] {self.message}")

    @property
    def spec(self) -> ErrorSpec:
        return ERROR_SPECS[self.code]

    @property
    def retryable(self) -> bool:
        return self.spec.retryable

    @property
    def http_status(self) -> int:
        return self.status_override or self.spec.http_status

    @property
    def user_message(self) -> str:
        return self.spec.user_message

    def to_payload(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "layer": self.layer,
            "message": self.message,
            "user_message": self.user_message,
            "retryable": self.retryable,
            "details": self.details,
        }
