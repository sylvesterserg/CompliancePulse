from __future__ import annotations

import json
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, func, select

from ..auth.dependencies import require_authenticated_user, require_role
from ..models import Benchmark, MembershipRole, Rule
from ..schemas import BenchmarkDetail, BenchmarkSummary, RuleDetail, RuleSummary
from ..services.benchmark_loader import PulseBenchmarkLoader
from .deps import get_db_session

router = APIRouter(
    prefix="/benchmarks",
    tags=["benchmarks"],
    dependencies=[Depends(require_authenticated_user)],
)


def _build_summary(session: Session, benchmark: Benchmark) -> BenchmarkSummary:
    total_rules = session.exec(
        select(func.count(Rule.id)).where(Rule.benchmark_id == benchmark.id)
    ).one()
    tags = json.loads(benchmark.tags_json or "[]")
    return BenchmarkSummary(
        id=benchmark.id,
        title=benchmark.title,
        description=benchmark.description,
        version=benchmark.version,
        os_target=benchmark.os_target,
        maintainer=benchmark.maintainer,
        source=benchmark.source,
        tags=tags,
        total_rules=total_rules,
        updated_at=benchmark.updated_at,
    )


def _build_detail(session: Session, benchmark: Benchmark) -> BenchmarkDetail:
    summary = _build_summary(session, benchmark)
    return BenchmarkDetail(**summary.model_dump(), schema_version=benchmark.schema_version)


def _rule_to_summary(rule: Rule) -> RuleSummary:
    tags = json.loads(rule.tags_json or "[]")
    return RuleSummary(
        id=rule.id,
        benchmark_id=rule.benchmark_id,
        title=rule.title,
        severity=rule.severity,
        status=rule.status,
        tags=tags,
        last_run=rule.last_run,
    )


def _rule_to_detail(rule: Rule) -> RuleDetail:
    return RuleDetail(
        **_rule_to_summary(rule).model_dump(),
        description=rule.description,
        remediation=rule.remediation,
        references=json.loads(rule.references_json or "[]"),
        metadata=json.loads(rule.metadata_json or "{}"),
        check_type=rule.check_type,
        command=rule.command,
        expect_type=rule.expect_type,
        expect_value=rule.expect_value,
        timeout_seconds=rule.timeout_seconds,
    )


@router.get("", response_model=List[BenchmarkSummary])
def list_benchmarks(session: Session = Depends(get_db_session)) -> List[BenchmarkSummary]:
    benchmarks = session.exec(select(Benchmark)).all()
    return [_build_summary(session, benchmark) for benchmark in benchmarks]


@router.get("/{benchmark_id}", response_model=BenchmarkDetail)
def get_benchmark(benchmark_id: str, session: Session = Depends(get_db_session)) -> BenchmarkDetail:
    benchmark = session.get(Benchmark, benchmark_id)
    if not benchmark:
        raise HTTPException(status_code=404, detail="Benchmark not found")
    return _build_detail(session, benchmark)


@router.get("/{benchmark_id}/rules", response_model=List[RuleDetail])
def list_benchmark_rules(
    benchmark_id: str,
    session: Session = Depends(get_db_session),
) -> List[RuleDetail]:
    benchmark = session.get(Benchmark, benchmark_id)
    if not benchmark:
        raise HTTPException(status_code=404, detail="Benchmark not found")
    rules = session.exec(select(Rule).where(Rule.benchmark_id == benchmark_id)).all()
    return [_rule_to_detail(rule) for rule in rules]


@router.post(
    "/reload",
    response_model=List[BenchmarkSummary],
    dependencies=[Depends(require_role(MembershipRole.ADMIN))],
)
def reload_benchmarks(session: Session = Depends(get_db_session)) -> List[BenchmarkSummary]:
    loader = PulseBenchmarkLoader()
    organization_id = session.info.get("organization_id")
    if not organization_id:
        raise HTTPException(status_code=400, detail="Organization context missing")
    loader.load_all(session, organization_id)
    benchmarks = session.exec(select(Benchmark)).all()
    return [_build_summary(session, benchmark) for benchmark in benchmarks]
