PR Summary

Scope
- Documentation overhaul and repository analysis outputs.
- No application logic changed.

Highlights
- Added a production-grade README with full sections (overview, features, architecture, run modes, testing, workflows, CLI, versioning, roadmap).
- Created developer documentation under `docs/`:
  - `architecture.md`, `backend.md`, `frontend.md`, `services.md`, `tests.md`, `api.md` (auto-derived from current routers)
- Generated Mermaid diagrams under `docs/diagrams/` (architecture, services, data flow, API routing).
- Summarized observed engine stability features and test-support behaviors:
  - JSONResponse normalization and header mirroring in test mode
  - ASGI wrapper for JSON body capture in tests
  - Session middleware with cookie management and CSRF-integrated UI flows
  - Tenant scoping via SQLAlchemy `with_loader_criteria`
  - Scheduler and worker guardrails (runtime limits, concurrency caps, failure counters)

Test & Import Cleanup (observed in repo)
- Dual import roots (`app.` vs `backend.app.`) handled gracefully across engine/services and tests to avoid metadata duplication.
- UI router provides JSON fallbacks for stable test assertions.
- Consistent JSONResponse usage across rule/scan/report APIs with mirrored JSON headers for ASGI client compatibility.

Engine & Middleware Stability
- RuleEngine command allow-list validation and expectation evaluation.
- ScanExecutor writes JSON artifacts and updates paths transactionally.
- Scheduler capacity checks and idempotent enqueue logic.
- Worker claim/run lifecycle with runtime enforcement and audit logging.

Notes
- No files were deleted. No business logic altered.

