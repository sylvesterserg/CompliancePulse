# Contributing to CompliancePulse

Help us keep the repo organized by following these lightweight guidelines.

## Branches & Commits
- Use feature branches named `area/short-description` (e.g., `backend/scan-endpoint`).
- Keep commits scoped to a single logical change and write imperative commit messages ("Add healthcheck", not "Added").

## Pull Requests
- Link to any related issue and describe how to run tests (`make lint`, `make test`, or service-specific commands).
- Include screenshots for UI changes (frontend) and sample responses for API changes (backend).
- Request reviewers who own the area you touched (see `CODEOWNERS`).

## Testing & Linting
- Run `make lint` before opening a PR to catch syntax errors.
- Extend `make test` with backend/frontend/unit tests as they are added.
- Prefer adding service-level tests in `tests/<service>/` so CI can run them selectively.

## Documentation
- Update the relevant service README whenever you add new CLI flags, endpoints, or environment variables.
- Keep the root `README.md` accurate since it is the onboarding starting point.

Thanks for keeping CompliancePulse tidy!
