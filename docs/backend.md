Backend

- App Entry
  - `backend/app/main.py`: FastAPI app with:
    - Session middleware (cookie-based, in-memory default, test-mode passthrough)
    - CORS, static files, JSON exception handling
    - Health endpoints: `/api`, `/health`, `/api/version`, `/api/ping`
    - Routers: `benchmarks`, `rules`, `scans`, `reports`, `schedules`, `security`, `ui_router`

- Configuration
  - `backend/app/config.py`: `Settings` via env (DB_URL, directories, frontend paths, session options)
  - `backend/app/security/config.py`: `SecuritySettings` via env (session secret, API key salt, limits, test mode)

- Database
  - `backend/app/database.py`: SQLModel engine and `with_loader_criteria` tenant scoping for tenant-aware models
  - Tenant-aware models: `Rule`, `RuleGroup`, `Scan`, `ScanResult`, `Report`, `Schedule`, `ScanJob`

- Models & Schemas
  - `backend/app/models/domain.py`: SQLModel tables and enums (Organization, User, Rule, Scan, Report, etc.)
  - `backend/app/schemas/*`: Pydantic models for API I/O (Scan*, ReportView, Benchmark*, Schedule*, Security*)

- Security
  - `backend/app/auth/*`: session resolution, org membership, role checks, CSRF verification
  - `backend/app/security/*`: API key mgmt, rate limiting, utils (masking, IP extraction)
  - Test mode: header-based auth (`x-test-user`, `x-test-org`) and ASGI JSON mirroring for tests

- Services
  - `ScanService`, `ScheduleService`, `PulseBenchmarkLoader` (see `docs/services.md`)

- Engine
  - `backend/engine/*`: `RuleEngine`, `ScanExecutor`, `ScheduleManager`, AI-like summarizer
  - Service shim `backend/app/services/scan_executor.py` delegates to engine implementation

