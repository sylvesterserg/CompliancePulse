from __future__ import annotations

import subprocess
from dataclasses import dataclass
from typing import Tuple

from ..config import settings
from ..models import Rule


@dataclass
class ExecutionResult:
    stdout: str
    stderr: str
    exit_code: int
    passed: bool
    expectation_detail: str


class RuleExecutionEngine:
    """Executes compliance rules and evaluates expectations."""

    def __init__(self, timeout: int | None = None):
        self.timeout = timeout or settings.shell_timeout

    def execute(self, rule: Rule) -> ExecutionResult:
        stdout = ""
        stderr = ""
        exit_code = 0
        try:
            completed = subprocess.run(
                rule.command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=rule.timeout_seconds or self.timeout,
            )
            stdout = (completed.stdout or "").strip()
            stderr = (completed.stderr or "").strip()
            exit_code = completed.returncode
        except subprocess.TimeoutExpired as exc:
            stdout = (exc.stdout or "").strip()
            stderr = f"Timed out after {rule.timeout_seconds} seconds"
            exit_code = 124
        passed, expectation_detail = self._evaluate(rule, stdout, stderr, exit_code)
        return ExecutionResult(stdout=stdout, stderr=stderr, exit_code=exit_code, passed=passed, expectation_detail=expectation_detail)

    def _evaluate(self, rule: Rule, stdout: str, stderr: str, exit_code: int) -> Tuple[bool, str]:
        expectation = rule.expect_type
        target = rule.expect_value
        if expectation == "exit_code":
            expected_code = int(target)
            passed = exit_code == expected_code
            detail = f"exit_code == {expected_code}"
        elif expectation == "contains":
            passed = target in stdout
            detail = f"stdout contains '{target}'"
        elif expectation == "not_contains":
            passed = target not in stdout
            detail = f"stdout does not contain '{target}'"
        elif expectation == "equals":
            passed = stdout.strip() == target.strip()
            detail = f"stdout equals '{target}'"
        else:
            raise ValueError(f"Unsupported expectation type: {expectation}")
        return passed, detail
