"""跨上下文共享的基础值类型：非数值语义、可加性、取数通道、时间窗。"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import Enum


class NullReason(str, Enum):
    """非数值语义。禁止用 0 或空串顶替（表 3-28 / 表 3-20）。"""

    NOT_APPLICABLE = "不适用"
    PENDING = "待补"
    UNAUTHORIZED = "未授权"
    NO_DATA = "无数据"
    NOT_SUPPORTED = "—"


class Additivity(str, Enum):
    ADDITIVE = "ADDITIVE"
    RATIO = "RATIO"
    NON_ADDITIVE = "NON_ADDITIVE"

    @property
    def label(self) -> str:
        if self is Additivity.ADDITIVE:
            return "可加"
        if self is Additivity.RATIO:
            return "不可加（比率类）"
        return "不可加"


class Channel(str, Enum):
    """三级取数通道（表 4-5）。"""

    OPEN_API = "OPEN_API"
    BACKEND_EXPORT = "BACKEND_EXPORT"
    GUI_FALLBACK = "GUI_FALLBACK"

    @property
    def label(self) -> str:
        return {
            Channel.OPEN_API: "官方接口",
            Channel.BACKEND_EXPORT: "后台导出",
            Channel.GUI_FALLBACK: "网页兜底",
        }[self]


@dataclass(frozen=True, slots=True)
class StatWindow:
    start: date
    end: date

    def __post_init__(self) -> None:
        if self.end < self.start:
            raise ValueError("时间窗结束日不能早于开始日")

    @property
    def days(self) -> int:
        return (self.end - self.start).days + 1

    @property
    def label(self) -> str:
        if self.start == self.end:
            return self.start.isoformat()
        return f"{self.start.isoformat()} ~ {self.end.isoformat()}"

    def contains(self, day: date) -> bool:
        return self.start <= day <= self.end
