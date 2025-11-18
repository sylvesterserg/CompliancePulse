Services

- ScanService (`backend/app/services/scan_service.py`)
  - start_scan(ScanRequest) -> ScanDetail
  - list_scans() -> List[ScanSummary]
  - get_scan(id) -> ScanDetail
  - list_reports() -> List[ReportView]
  - get_report(id) / get_report_for_scan(id) -> ReportView
  - enqueue_group_scan(group_id, ...) -> ScanJobView
  - Internals: builds views from SQLModel entities, delegates execution to `ScanExecutor`

- ScheduleService (`backend/app/services/schedule_service.py`)
  - list_rule_groups() -> List[RuleGroupView]
  - list_schedules() -> List[ScheduleView]
  - get_next_schedule() -> Optional[ScheduleView]
  - create_schedule(ScheduleCreate) -> ScheduleView
  - delete_schedule(id)
  - Interval derivation for hourly/daily/custom with minimal 5-minute guard

- PulseBenchmarkLoader (`backend/app/services/benchmark_loader.py`)
  - discover() -> List[Path]
  - parse(Path) -> BenchmarkDocument (validates rules and expectations)
  - load_all(session, org_id) -> List[Benchmark]
  - Upsert `Benchmark` and replace `Rule`s for the org; supports tags/metadata

- Engine (`backend/engine`)
  - RuleEngine: command allow-list, expectation evaluation (`exit_code`, `contains`, `not_contains`, `equals`), and helper checks
  - ScanExecutor: runs rules, aggregates results, computes weighted score, writes artifacts, returns `ScanExecutionResult`
  - ScheduleManager: enqueues `ScanJob`s when schedules are due; capacity checks per org
  - AI Summary: placeholder summarizer providing key findings and remediations

- Worker (`backend/worker.py`)
  - Claims and runs jobs with concurrency and runtime guardrails; updates job status; writes audit events

