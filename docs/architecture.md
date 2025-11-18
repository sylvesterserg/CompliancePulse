Architecture

- Overview
  - Backend: FastAPI application (`backend/app`) serving JSON APIs and Jinja2 templates for the UI.
  - Engine: Execution components (`backend/engine`) implementing the rule engine, scan executor, and scheduler.
  - Worker: Background job runner (`backend/worker.py`) that processes queued scan jobs.
  - Scheduler: Periodic scheduler loop (`backend/engine/jobs.py` and `backend/engine/scheduler.py`).
  - Frontend: HTMX/Tailwind templates and static assets (`frontend/`).
  - Storage: SQLite DB by default, JSON artifacts/logs written to `backend/app/logs` and `backend/app/artifacts`.

- Core Flows
  - Benchmark ingestion: YAML benchmark files are validated and loaded into DB via `PulseBenchmarkLoader`.
  - Scan execution: `ScanService` triggers `ScanExecutor` which evaluates rules using `RuleEngine` with command allow-list.
  - Reporting: Results are aggregated into a `Report`; artifacts are persisted to disk and paths stored in DB.
  - Scheduling: `ScheduleService` defines schedules; `ScheduleManager` enqueues `ScanJob` records; Worker consumes jobs.
  - Security: Session middleware, CSRF, rate limiting, API keys, audit logging.

- Multi-tenancy
  - Tenant filtering enforced via SQLAlchemy `with_loader_criteria` in `database.py` for all tenant-aware models.
  - API dependencies (`deps.get_db_session`) inject `organization_id` onto session.

- Diagrams
  - See `docs/diagrams/architecture.mmd`, `services.mmd`, `data-flow.mmd`, `api-routing.mmd`.

