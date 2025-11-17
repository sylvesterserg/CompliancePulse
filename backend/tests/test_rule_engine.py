"""Tests for the RuleExecutionEngine."""

from __future__ import annotations

import pytest

from backend.app.models import Rule
from backend.app.services.rule_engine import RuleExecutionEngine


def _build_rule(**overrides):
    base = {
        "id": "rule-test",
        "organization_id": 1,
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


def test_exit_code_expectation_compares_process_status() -> None:
    rule = _build_rule(command="exit 0", expect_type="exit_code", expect_value="0")
    engine = RuleExecutionEngine(timeout=5)

    result = engine.execute(rule)

    assert result.passed is True
    assert result.expectation_detail == "exit_code == 0"


def test_not_contains_expectation_handles_absence() -> None:
    rule = _build_rule(command="echo rocky", expect_type="not_contains", expect_value="ubuntu")
    engine = RuleExecutionEngine(timeout=5)

    result = engine.execute(rule)

    assert result.passed is True
    assert "does not contain" in result.expectation_detail


def test_timeout_marks_failure_and_records_message() -> None:
    rule = _build_rule(
        command="python -c 'import time; time.sleep(2)'",
        expect_type="exit_code",
        expect_value="0",
        timeout_seconds=1,
    )
    engine = RuleExecutionEngine(timeout=1)

    result = engine.execute(rule)

    assert result.passed is False
    assert result.exit_code == 124
    assert "Timed out" in (result.stderr or "")


def test_execute_raises_for_unknown_expectation() -> None:
    rule = _build_rule(expect_type="unsupported", expect_value="")
    engine = RuleExecutionEngine(timeout=1)

    with pytest.raises(ValueError):
        engine.execute(rule)
