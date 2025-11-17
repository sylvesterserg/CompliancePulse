from __future__ import annotations

import json
import re
import shutil
import socket
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Tuple

from backend.app.config import settings
from backend.app.models import Rule


@dataclass
class RuleEvaluation:
    rule_id: str
    passed: bool
    stdout: str | None
    stderr: str | None
    details: Dict[str, Any]
    started_at: datetime
    completed_at: datetime
    runtime_ms: int


class RuleEngine:
    """Evaluate compliance rules locally on the worker host."""

    def __init__(self, timeout: int | None = None):
        self.timeout = timeout or settings.shell_timeout

    def evaluate(self, rule: Rule) -> RuleEvaluation:
        metadata = self._load_metadata(rule)
        rule_type = (metadata.get("type") or rule.check_type or "shell").lower()
        handler = getattr(self, f"_handle_{rule_type}", None)
        if handler is None:
            handler = self._handle_shell
        started = datetime.utcnow()
        stdout = ""
        stderr = ""
        passed = False
        details: Dict[str, Any] = {"type": rule_type}
        try:
            stdout, stderr, passed, details = handler(rule, metadata)
        except Exception as exc:  # pragma: no cover - defensive logging
            stderr = str(exc)
            passed = False
            details["error"] = str(exc)
        completed = datetime.utcnow()
        runtime_ms = int((completed - started).total_seconds() * 1000)
        return RuleEvaluation(
            rule_id=rule.id,
            passed=passed,
            stdout=stdout,
            stderr=stderr,
            details=details,
            started_at=started,
            completed_at=completed,
            runtime_ms=runtime_ms,
        )

    def _handle_file_exists(self, rule: Rule, metadata: Dict[str, Any]) -> Tuple[str, str, bool, Dict[str, Any]]:
        target = metadata.get("path") or rule.command or rule.expect_value
        if not target:
            raise ValueError("file_exists rule requires a path")
        path = Path(target)
        exists = path.exists()
        details = {"path": str(path), "exists": exists}
        return "", "", exists, details

    def _handle_command_output_match(self, rule: Rule, metadata: Dict[str, Any]) -> Tuple[str, str, bool, Dict[str, Any]]:
        command = metadata.get("command") or rule.command
        if not command:
            raise ValueError("command_output_match requires a command")
        pattern = metadata.get("pattern") or rule.expect_value
        if not pattern:
            raise ValueError("command_output_match requires a pattern")
        match_type = metadata.get("match_type", "contains")
        completed = self._run_process(command, metadata)
        stdout = completed.stdout
        stderr = completed.stderr
        if match_type == "regex":
            passed = re.search(pattern, stdout or "") is not None
        else:
            passed = pattern in (stdout or "")
        details = {"pattern": pattern, "match_type": match_type, "exit_code": completed.returncode}
        return stdout, stderr, passed, details

    def _handle_port_open(self, rule: Rule, metadata: Dict[str, Any]) -> Tuple[str, str, bool, Dict[str, Any]]:
        host = metadata.get("host") or metadata.get("hostname") or rule.command or "127.0.0.1"
        port_value = metadata.get("port") or rule.expect_value or rule.command
        if port_value is None:
            raise ValueError("port_open rule requires a port")
        port = int(str(port_value))
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(metadata.get("timeout", self.timeout))
        try:
            sock.connect((host, port))
            passed = True
        except OSError as exc:
            passed = False
            stderr = str(exc)
            sock.close()
            return "", stderr, passed, {"host": host, "port": port}
        finally:
            try:
                sock.close()
            except OSError:
                pass
        return "", "", True, {"host": host, "port": port}

    def _handle_package_installed(self, rule: Rule, metadata: Dict[str, Any]) -> Tuple[str, str, bool, Dict[str, Any]]:
        package = metadata.get("package") or rule.command or rule.expect_value
        if not package:
            raise ValueError("package_installed rule requires a package name")
        checker = shutil.which("rpm")
        command = None
        if checker:
            command = f"rpm -q {package}"
        elif shutil.which("dpkg"):
            command = f"dpkg -s {package}"
        else:
            raise RuntimeError("No package manager found on host")
        completed = self._run_process(command, metadata)
        passed = completed.returncode == 0
        return completed.stdout, completed.stderr, passed, {"package": package, "exit_code": completed.returncode}

    def _handle_shell(self, rule: Rule, metadata: Dict[str, Any]) -> Tuple[str, str, bool, Dict[str, Any]]:
        command = rule.command or metadata.get("command")
        if not command:
            raise ValueError("shell rule requires a command")
        completed = self._run_process(command, metadata, timeout=rule.timeout_seconds)
        stdout = completed.stdout
        stderr = completed.stderr
        passed = self._evaluate_expectation(rule, completed.stdout or "", completed.stderr or "", completed.returncode)
        details = {
            "expectation": rule.expect_type,
            "expect_value": rule.expect_value,
            "exit_code": completed.returncode,
        }
        return stdout, stderr, passed, details

    def _run_process(self, command: str, metadata: Dict[str, Any], timeout: int | None = None) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout or metadata.get("timeout", self.timeout),
        )

    def _evaluate_expectation(self, rule: Rule, stdout: str, stderr: str, exit_code: int) -> bool:
        expectation = (rule.expect_type or "exit_code").lower()
        target = rule.expect_value or "0"
        if expectation == "exit_code":
            return exit_code == int(target)
        if expectation == "contains":
            return target in stdout
        if expectation == "not_contains":
            return target not in stdout
        if expectation == "equals":
            return stdout.strip() == str(target).strip()
        raise ValueError(f"Unsupported expectation type: {rule.expect_type}")

    def _load_metadata(self, rule: Rule) -> Dict[str, Any]:
        try:
            return json.loads(rule.metadata_json or "{}")
        except json.JSONDecodeError:
            return {}
