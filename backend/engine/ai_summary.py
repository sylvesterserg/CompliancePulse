from __future__ import annotations

from typing import Any, Dict, Iterable, List

from backend.app.models import ScanResult


def summarize_scan(results: Iterable[ScanResult]) -> Dict[str, Any]:
    """Generate a lightweight AI-style narrative for scan output.

    This placeholder implementation will later be replaced with real LLM calls,
    but it already delivers structured, human-readable insights.
    """

    result_list: List[ScanResult] = list(results)
    total = len(result_list)
    passed = sum(1 for result in result_list if result.passed)
    failed = total - passed
    summary = "All controls passed." if failed == 0 else f"{failed} of {total} controls require attention."

    key_findings = [
        f"{result.rule_title} ({result.severity}) {'passed' if result.passed else 'failed'}"
        for result in result_list
    ]
    remediations = [
        f"Review {result.rule_title} and apply remediation guidance." for result in result_list if not result.passed
    ]
    if not remediations and total:
        remediations.append("Maintain current hardening posture; no failed controls detected.")

    return {
        "summary": summary,
        "key_findings": key_findings,
        "remediations": remediations,
    }
