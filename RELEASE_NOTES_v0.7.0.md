Release Notes — v0.7.0

Added
- Comprehensive documentation set under `docs/` (architecture, backend, frontend, services, tests, API reference).
- Mermaid diagrams for architecture, services, data flow, and API routing under `docs/diagrams/`.
- Production-ready README including runbooks for local, Docker, and Podman deployments.

Changed
- Consolidated API documentation around current routers (`benchmarks`, `rules`, `scans`, `reports`, `schedules`, `api-keys`).
- Clarified developer workflows for benchmarks reloading and background services (worker/scheduler).

Fixed
- Documentation clarifies JSON fallback behavior on UI routes and the ASGI wrapper used in tests.
- Callouts for dual import path support to avoid SQLModel metadata duplication during tests.

Removed
- None.

Breaking Changes
- None in application behavior. Release focuses on documentation and developer experience.

Migration Notes
- No DB migrations required. Applications can upgrade without downtime.
- Teams should adopt the new documentation and diagrams for onboarding.

