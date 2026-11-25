"""口径计算单测：配置驱动、零分母、缺失语义、比率不可加、公式安全。"""
from __future__ import annotations

from decimal import Decimal

import pytest

from kernel.contexts.metric_data.domain.metric_definition import (
    FormulaEvaluator,
    MetricCalculator,
    MetricDefinition,
    format_decimal,
)
from shared.errors.registry import DomainError
from shared.types.values import Additivity, NullReason


def _definition(
    code: str,
    formula: str,
    *,
    order: int = 10,
    additivity: Additivity = Additivity.ADDITIVE,
    null_policy: NullReason = NullReason.NOT_APPLICABLE,
    precision: int = 2,
) -> MetricDefinition:
    return MetricDefinition(
        metric_code=code,
        display_name=code.upper(),
        version="1.0",
        unit="",
        precision=precision,
        additivity=additivity,
        formula=formula,
        null_policy=null_policy,
        display_order=order,
    )


def _calc() -> MetricCalculator:
    return MetricCalculator()


def test_computes_configured_formulas_and_references() -> None:
    definitions = [
        _definition("gmv", "gmv"),
        _definition("paid_orders", "paid_orders"),
        _definition("aov", "gmv / paid_orders", order=20, additivity=Additivity.RATIO),
        _definition("net_gmv", "gmv - refund_amount", order=30),
    ]
    values = _calc().compute(
        definitions,
        {"gmv": Decimal("2460"), "paid_orders": 3, "refund_amount": Decimal("100")},
    )
    by_code = {value.metric_code: value for value in values}
    assert by_code["aov"].value == Decimal("820")
    assert by_code["net_gmv"].value == Decimal("2360")
    assert by_code["aov"].additivity is Additivity.RATIO
    assert by_code["aov"].display == "820.00"


def test_zero_denominator_is_not_applicable_never_zero() -> None:
    values = _calc().compute(
        [_definition("aov", "gmv / paid_orders", additivity=Additivity.RATIO)],
        {"gmv": Decimal("100"), "paid_orders": 0},
    )
    cell = values[0]
    assert cell.value is None
    assert cell.null_reason is NullReason.NOT_APPLICABLE
    assert cell.display == "不适用"
    assert cell.display != "0"


def test_missing_fact_uses_reason_from_pipeline() -> None:
    values = _calc().compute(
        [_definition("dsr", "dsr", additivity=Additivity.NON_ADDITIVE)],
        {"dsr": None},
        {"dsr": NullReason.UNAUTHORIZED},
    )
    assert values[0].null_reason is NullReason.UNAUTHORIZED
    assert values[0].display == "未授权"


def test_missing_variable_is_config_error() -> None:
    with pytest.raises(DomainError) as exc:
        _calc().compute([_definition("cvr", "paid_orders / uv")], {"paid_orders": 1})
    assert exc.value.code == "E006"


@pytest.mark.parametrize(
    "expression",
    ["__import__('os').system('echo hacked')", "open('/etc/passwd')", "a if b else c"],
)
def test_formula_rejects_unsafe_syntax(expression: str) -> None:
    with pytest.raises(DomainError):
        FormulaEvaluator.evaluate(expression, {"a": Decimal(1), "b": Decimal(1), "c": Decimal(1)})


def test_format_decimal_rounding_and_thousands() -> None:
    assert format_decimal(Decimal("1234567.891"), 2) == "1,234,567.89"
    assert format_decimal(Decimal("4.7666"), 2) == "4.77"
    assert format_decimal(Decimal("0.5"), 2) == "0.50"
