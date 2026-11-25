"""口径定义、公式求值与指标计算（主文档表 3-20 / 表 3-26 / ADR-13 B1）。

要点：
- 公式来自配置（YAML→metric_definition），代码里不写死任何指标公式；
- 分母为零记「不适用」而不是 0；
- 比率类默认不可加，合计必须由服务端拒绝（见 API 层）。
"""
from __future__ import annotations

import ast
import operator
from dataclasses import dataclass
from decimal import Decimal, DivisionByZero, InvalidOperation, ROUND_HALF_UP
from typing import Any, Callable, Mapping, Sequence

from shared.errors.registry import DomainError
from shared.types.values import Additivity, NullReason

_ALLOWED_BINOPS: dict[type[ast.AST], Callable[[Decimal, Decimal], Decimal]] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
}
_ALLOWED_UNARY: dict[type[ast.AST], Callable[[Decimal], Decimal]] = {ast.USub: operator.neg, ast.UAdd: operator.pos}


def to_decimal(value: Any) -> Decimal:
    if isinstance(value, Decimal):
        return value
    if isinstance(value, bool):
        return Decimal(int(value))
    if isinstance(value, (int, float)):
        return Decimal(str(value))
    if isinstance(value, str):
        try:
            return Decimal(value)
        except InvalidOperation as exc:
            raise DomainError("E006", f"无法转换为数值: {value!r}") from exc
    raise DomainError("E006", f"不支持的数值类型: {type(value).__name__}")


def format_decimal(value: Decimal, precision: int) -> str:
    quantum = Decimal(1).scaleb(-precision)
    return f"{value.quantize(quantum, rounding=ROUND_HALF_UP):,}"


class FormulaEvaluator:
    """受限表达式求值：只允许四则运算与变量名，杜绝 eval 注入。"""

    @staticmethod
    def names(expression: str) -> set[str]:
        tree = ast.parse(expression, mode="eval")
        return {
            node.id
            for node in ast.walk(tree)
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load)
        }

    @staticmethod
    def evaluate(expression: str, variables: Mapping[str, Decimal]) -> Decimal:
        try:
            tree = ast.parse(expression, mode="eval")
        except SyntaxError as exc:
            raise DomainError("E006", f"公式语法错误: {expression!r}") from exc
        return FormulaEvaluator._eval(tree.body, variables)

    @staticmethod
    def _eval(node: ast.AST, variables: Mapping[str, Decimal]) -> Decimal:
        if isinstance(node, ast.Constant):
            if isinstance(node.value, bool) or not isinstance(node.value, (int, float)):
                raise DomainError("E006", "公式只允许数值常量")
            return Decimal(str(node.value))
        if isinstance(node, ast.Name):
            if node.id not in variables:
                raise DomainError("E006", f"公式引用了未定义的变量: {node.id}")
            return variables[node.id]
        if isinstance(node, ast.BinOp):
            bin_op = _ALLOWED_BINOPS.get(type(node.op))
            if bin_op is None:
                raise DomainError("E006", "公式只允许 + - * / 四则运算")
            left = FormulaEvaluator._eval(node.left, variables)
            right = FormulaEvaluator._eval(node.right, variables)
            return bin_op(left, right)
        if isinstance(node, ast.UnaryOp):
            unary_op = _ALLOWED_UNARY.get(type(node.op))
            if unary_op is None:
                raise DomainError("E006", "公式只允许一元正负号")
            return unary_op(FormulaEvaluator._eval(node.operand, variables))
        raise DomainError("E006", "公式包含不允许的语法")


@dataclass(frozen=True, slots=True)
class MetricDefinition:
    metric_code: str
    display_name: str
    version: str
    unit: str
    precision: int
    additivity: Additivity
    formula: str
    null_policy: NullReason = NullReason.NOT_APPLICABLE
    denominator: str | None = None
    platform: str = "demo"
    source_mapping: str = ""
    description: str = ""
    concept_uri: str = ""
    synonyms: tuple[str, ...] = ()
    probe_sql_template: str = ""
    quality_tests: tuple[str, ...] = ()
    display_order: int = 100
    effective_from: str = ""
    breaking_change: bool = False

    @property
    def is_ratio(self) -> bool:
        return self.additivity in {Additivity.RATIO, Additivity.NON_ADDITIVE}


@dataclass(frozen=True, slots=True)
class MetricValue:
    metric_code: str
    metric_version: str
    value: Decimal | None
    unit: str
    precision: int
    additivity: Additivity
    null_reason: NullReason | None = None
    display_name: str = ""

    @property
    def display(self) -> str:
        if self.value is None:
            return (self.null_reason or NullReason.NOT_APPLICABLE).value
        return format_decimal(self.value, self.precision)

    @property
    def is_missing(self) -> bool:
        return self.value is None


class MetricCalculator:
    """按口径配置计算指标；口径之间允许引用，顺序由 display_order 决定。"""

    def compute(
        self,
        definitions: Sequence[MetricDefinition],
        facts: Mapping[str, Any],
        missing_reasons: Mapping[str, NullReason] | None = None,
    ) -> list[MetricValue]:
        reasons = dict(missing_reasons or {})
        variables: dict[str, Decimal] = {}
        for name, value in facts.items():
            if value is None:
                reasons.setdefault(name, NullReason.PENDING)
                continue
            variables[name] = to_decimal(value)

        results: dict[str, MetricValue] = {}
        for definition in sorted(definitions, key=lambda d: (d.display_order, d.metric_code)):
            result = self._compute_one(definition, variables, reasons)
            results[definition.metric_code] = result
            if result.value is not None:
                variables[definition.metric_code] = result.value
        return list(results.values())

    def _compute_one(
        self,
        definition: MetricDefinition,
        variables: dict[str, Decimal],
        reasons: dict[str, NullReason],
    ) -> MetricValue:
        try:
            referenced = FormulaEvaluator.names(definition.formula)
        except DomainError:
            raise
        missing = [name for name in referenced if name not in variables and name in reasons]
        if missing:
            return MetricValue(
                metric_code=definition.metric_code,
                metric_version=definition.version,
                value=None,
                unit=definition.unit,
                precision=definition.precision,
                additivity=definition.additivity,
                null_reason=reasons[missing[0]],
                display_name=definition.display_name,
            )
        try:
            value = FormulaEvaluator.evaluate(definition.formula, variables)
        except ZeroDivisionError:
            return MetricValue(
                metric_code=definition.metric_code,
                metric_version=definition.version,
                value=None,
                unit=definition.unit,
                precision=definition.precision,
                additivity=definition.additivity,
                null_reason=definition.null_policy,
                display_name=definition.display_name,
            )
        except DivisionByZero:
            return MetricValue(
                metric_code=definition.metric_code,
                metric_version=definition.version,
                value=None,
                unit=definition.unit,
                precision=definition.precision,
                additivity=definition.additivity,
                null_reason=definition.null_policy,
                display_name=definition.display_name,
            )
        return MetricValue(
            metric_code=definition.metric_code,
            metric_version=definition.version,
            value=value,
            unit=definition.unit,
            precision=definition.precision,
            additivity=definition.additivity,
            display_name=definition.display_name,
        )
