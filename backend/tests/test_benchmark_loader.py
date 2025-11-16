"""Tests for the PulseBenchmarkLoader."""

from __future__ import annotations

from pathlib import Path
import textwrap

import pytest
from sqlmodel import Session, SQLModel, create_engine, select

from app.models import Benchmark, Rule
from app.services.benchmark_loader import PulseBenchmarkLoader


def _bootstrap_memory_session() -> Session:
    """Create an in-memory SQLite session for the test run."""

    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(engine)
    return Session(engine)


def test_loader_persists_benchmark_and_rules(tmp_path: Path) -> None:
    """The loader should hydrate a benchmark document and its rules."""

    yaml_document = textwrap.dedent(
        """
        schema_version: "0.3"
        benchmark:
          id: "rocky-linux-level1"
          title: "Rocky Linux Level 1"
          description: "Test benchmark for loader"
          version: "1.0"
          os_target: "rocky-linux-9"
          metadata:
            maintainer: "QA"
            source: "unit-test"
            tags: ["level1"]
        rules:
          - id: "ensure-echo"
            title: "Ensure echo works"
            description: "Validates echo command"
            severity: "low"
            remediation: "Investigate shell"
            references: ["shell"]
            metadata:
              category: "shell"
            check:
              type: "shell"
              command: "echo pass"
              timeout: 5
              expect:
                type: "equals"
                value: "pass"
        """
    ).strip()
    yaml_path = tmp_path / "test_benchmark.yaml"
    yaml_path.write_text(yaml_document, encoding="utf-8")

    loader = PulseBenchmarkLoader(directory=tmp_path)
    with _bootstrap_memory_session() as session:
        benchmarks = loader.load_all(session)
        assert len(benchmarks) == 1

        benchmark = session.get(Benchmark, "rocky-linux-level1")
        assert benchmark is not None
        assert benchmark.title == "Rocky Linux Level 1"
        assert benchmark.schema_version == "0.3"

        rules = session.exec(select(Rule)).all()
        assert len(rules) == 1
        assert rules[0].command == "echo pass"
        assert rules[0].expect_type == "equals"


def test_loader_rejects_unsupported_expectations(tmp_path: Path) -> None:
    yaml_document = textwrap.dedent(
        """
        schema_version: "0.3"
        benchmark:
          id: "rocky-linux-level1"
          title: "Rocky Linux Level 1"
          description: "Test benchmark for loader"
          version: "1.0"
          os_target: "rocky-linux-9"
          metadata:
            maintainer: "QA"
            source: "unit-test"
            tags: ["level1"]
        rules:
          - id: "ensure-echo"
            title: "Ensure echo works"
            description: "Validates echo command"
            severity: "low"
            remediation: "Investigate shell"
            references: ["shell"]
            metadata:
              category: "shell"
            check:
              type: "shell"
              command: "echo pass"
              timeout: 5
              expect:
                type: "future_expectation"
                value: "pass"
        """
    ).strip()
    yaml_path = tmp_path / "invalid_benchmark.yaml"
    yaml_path.write_text(yaml_document, encoding="utf-8")

    loader = PulseBenchmarkLoader(directory=tmp_path)

    with pytest.raises(ValueError):
        loader.parse(yaml_path)
