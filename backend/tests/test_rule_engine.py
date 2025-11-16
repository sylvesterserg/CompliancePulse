"""Tests for the RuleExecutionEngine."""

from __future__ import annotations

from app.models import Rule
from app.services.rule_engine import RuleExecutionEngine


def _build_rule(**overrides):
    base = {
        "id": "rule-test",
        "benchmark_id": "benchmark",
        "title": "Test rule",
        "description": "",
        "severity": "low",
        "remediation": "",
        "check_type": "shell",
        "command": "echo ok",
        "expect_type": "equals",
        "expect_value": "ok",
        "timeout_seconds": 5,
    }
    base.update(overrides)
    return Rule(**base)


def test_execute_passes_when_expectation_met() -> None:
    rule = _build_rule(command="echo compliance", expect_type="contains", expect_value="compliance")
    engine = RuleExecutionEngine(timeout=5)

    result = engine.execute(rule)

    assert result.passed is True
    assert "stdout contains" in result.expectation_detail


def test_execute_fails_when_expectation_not_met() -> None:
    rule = _build_rule(command="echo compliance", expect_type="contains", expect_value="missing")
    engine = RuleExecutionEngine(timeout=5)

    result = engine.execute(rule)

    assert result.passed is False
    assert result.exit_code == 0
    assert "missing" in result.expectation_detail
