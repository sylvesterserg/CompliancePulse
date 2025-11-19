# CompliancePulse Configuration

## Core settings (env)

- `DB_URL`: Database URL (SQLite default). For Postgres: `postgresql+psycopg2://user:pass@host/db`.
- `APP_VERSION`: Overrides default version for API and UI.
- `SESSION_SECRET_KEY`: Secret for session HMAC/signing.
- `ALLOWED_ORIGINS`: CORS, comma-separated.
- `FRONTEND_TEMPLATES`, `FRONTEND_STATIC`: override host paths.
- `DATA_DIR`, `LOGS_DIR`, `ARTIFACTS_DIR`: host paths mounted in containers.

## Security tuning

- `SESSION_SECURE_COOKIE`: `true` to always mark cookies Secure (default honors proxy HTTPS).
- `CSRF_HEADER_NAME`: Header name for CSRF token (default `X-CSRF-Token`).
- Rate limiting and keys are configured in security settings and via Redis (optional).

