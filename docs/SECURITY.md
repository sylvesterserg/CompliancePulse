# CompliancePulse Security Notes

## NGINX

- Rate limit on `/api/` location (10r/s with burst)
- Strict security headers (CSP, X-Frame-Options, X-Content-Type-Options, Referrer-Policy, Permissions-Policy)

## Cookies and sessions

- HTTP-only, SameSite=strict cookies
- Secure flag honored behind HTTPS via `X-Forwarded-Proto` or `SESSION_SECURE_COOKIE=true`
- CSRF protection validates token in header or form field

## API and UI

- Unauthenticated UI requests redirect to `/api/auth/login`
- API returns JSON 401/403 with consistent payloads

## Supply chain

- CI runs Bandit and Ruff checks
- Docker image builds as non-root `appuser`

