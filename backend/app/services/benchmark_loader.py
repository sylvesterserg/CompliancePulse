from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable, List

import yaml
from sqlmodel import Session, delete, select

from datetime import datetime

from ..config import settings
from ..models import Benchmark, Rule
from ..schemas import BenchmarkDocument

SUPPORTED_EXPECTATIONS = {"exit_code", "contains", "not_contains", "equals"}
SUPPORTED_CHECK_TYPES = {"shell"}


class PulseBenchmarkLoader:
    """Loads and normalizes benchmark definitions from YAML files."""

    def __init__(self, directory: Path | None = None):
        self.directory = directory or settings.benchmark_dir

    def discover(self) -> List[Path]:
        return sorted(self.directory.glob("*.yaml"))

    def parse(self, path: Path) -> BenchmarkDocument:
        with path.open("r", encoding="utf-8") as handle:
            data = yaml.safe_load(handle)
        document = BenchmarkDocument.model_validate(data)
        self._validate_document(document)
        return document

    def load_all(self, session: Session) -> List[Benchmark]:
        """Load all benchmark files into the database."""
        benchmarks: List[Benchmark] = []
        for path in self.discover():
            document = self.parse(path)
            benchmark = self._upsert_benchmark(session, document)
            benchmarks.append(benchmark)
        session.commit()
        return benchmarks

    def _upsert_benchmark(self, session: Session, document: BenchmarkDocument) -> Benchmark:
        benchmark_data = document.benchmark
        benchmark = session.get(Benchmark, benchmark_data.id)
        tags_json = json.dumps(benchmark_data.metadata.tags)
        if not benchmark:
            benchmark = Benchmark(
                id=benchmark_data.id,
                title=benchmark_data.title,
                description=benchmark_data.description,
                version=benchmark_data.version,
                os_target=benchmark_data.os_target,
                maintainer=benchmark_data.metadata.maintainer,
                source=benchmark_data.metadata.source,
                tags_json=tags_json,
                schema_version=document.schema_version,
                updated_at=datetime.utcnow(),
            )
            session.add(benchmark)
        else:
            benchmark.title = benchmark_data.title
            benchmark.description = benchmark_data.description
            benchmark.version = benchmark_data.version
            benchmark.os_target = benchmark_data.os_target
            benchmark.maintainer = benchmark_data.metadata.maintainer
            benchmark.source = benchmark_data.metadata.source
            benchmark.tags_json = tags_json
            benchmark.schema_version = document.schema_version
            benchmark.updated_at = datetime.utcnow()
        self._replace_rules(session, document)
        return benchmark

    def _replace_rules(self, session: Session, document: BenchmarkDocument) -> None:
        session.exec(delete(Rule).where(Rule.benchmark_id == document.benchmark.id))
        for rule in document.rules:
            session.add(
                Rule(
                    id=rule.id,
                    benchmark_id=document.benchmark.id,
                    title=rule.title,
                    description=rule.description,
                    severity=rule.severity,
                    remediation=rule.remediation,
                    references_json=json.dumps(rule.references),
                    metadata_json=json.dumps(rule.metadata),
                    check_type=rule.check.type,
                    command=rule.check.command,
                    expect_type=rule.check.expect.type,
                    expect_value=str(rule.check.expect.value),
                    timeout_seconds=rule.check.timeout,
                )
            )

    def _validate_document(self, document: BenchmarkDocument) -> None:
        for rule in document.rules:
            if rule.check.type not in SUPPORTED_CHECK_TYPES:
                raise ValueError(f"Unsupported check type: {rule.check.type}")
            if rule.check.expect.type not in SUPPORTED_EXPECTATIONS:
                raise ValueError(
                    f"Unsupported expectation type: {rule.check.expect.type}"
                )

    def get_rules_for_benchmark(self, session: Session, benchmark_id: str) -> Iterable[Rule]:
        statement = select(Rule).where(Rule.benchmark_id == benchmark_id)
        return session.exec(statement).all()
