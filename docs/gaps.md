Repository Gaps & Recommendations

Findings
- Missing modules
  - None blocking; all referenced modules resolved via dual import roots (`app.*` and `backend.app.*`).
- Incorrect imports
  - Dual root imports could still be a source of confusion; consider centralizing an import alias module to avoid try/except blocks.
- Dead code
  - `agent/scan_agent.py` is a mock; keep but mark as example. No clear dead modules found.
- Circular dependencies
  - Avoided via local imports in a few places (e.g., in services/auth). No active cycles detected at runtime.
- Incomplete schemas
  - Schemas are complete for exposed endpoints; consider explicit enums for `severity`, `status`, and `frequency` where free-form strings are used.
- Missing tests
  - Coverage for API keys endpoints is light; add create/list/revoke/show tests.
  - Add tests for schedule create/delete happy path and org scoping.
  - Add RuleEngine unit tests for helper handlers (`file_exists`, `port_open`, `package_installed`).
- Missing type hints
  - Most code is typed. A few functions in UI router and worker return `None` implicitly; consider explicit return types for clarity.
- Code smells
  - UI router is long and mixes responsibilities (auth resolution, JSON fallback, HTMX partials). Extract helpers or submodules.
  - Repeated JSON mirroring logic exists in multiple endpoints—could be centralized behind a small response helper.
  - ASGI wrapper in test mode replaces `app` in-place; keep isolated to tests if possible, or behind a factory.
  - String-typed `severity` across the system; consider a canonical enum + migration.

Recommendations
- Testing
  - Add API key lifecycle tests; add schedule CRUD tests; extend integration tests for `/benchmarks/reload` (admin-only).
  - Add RuleEngine “negative” tests (disallowed commands, timeouts).
- Architecture
  - Introduce a small `responses.py` helper for JSON+mirroring to reduce duplication.
  - Extract UI router into smaller modules (dashboard, rules, scans, schedules, reports) for maintainability.
  - Introduce a `settings.version` bump automation tied to release notes.
- Security
  - Optional: Integrate Redis-backed rate limiting in docker-compose default profile.
  - Consider HSTS and secure cookies by default in production mode.
- Data & Migrations
  - Add alembic migration scripts for future enum changes if Postgres support is added.
- Ops & DX
  - Add Makefile tasks (`make dev`, `make test`, `make build-css`, `make up/down`).
  - Add pre-commit hooks for formatting and basic linting (ruff/black).

