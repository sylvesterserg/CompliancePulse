# Changelog

## v1.0.0-alpha

Highlights

- End-to-end MVP stabilized with UI + API parity
- Added AI summarize endpoint `/api/ai/summarize`
- Added ingest pipeline for JSON/CSV via `/api/ingest/upload`
- Added minimal agent ingestion `/api/agent/upload` + example `agent/cp_agent.sh`
- Added PDF download API `/api/reports/<id>/pdf` (also via UI)
- White-labeling: tenant logo + CSS upload endpoints and template injection
- NGINX hardened (CSP, rate limiting), secure middleware upgrades
- GitHub Actions CI: run tests on push; build Docker image on tags

Details

- Frontend
  - HTMX-lite endpoints aligned with backend routes
  - Dashboard, Rules, Scans, Reports views stable with modals
  - Tenant CSS and logo auto-injection when present
- Backend
  - Rule/scan/report engines finalized; scoring normalized
  - AI summary integrated into scan execution and standalone API
  - Ingestion creates synthetic scans from uploaded results
  - Report PDF generation via ReportLab
  - Theme upload APIs with per-tenant storage under `/static/tenants/<org_id>`
- DevOps
  - Installer v3 scripts present under `deployment/install/`
  - Systemd unit files for worker, scheduler, nginx

## v0.8.0
- Auth/UI fixes: forms to `/api/auth/*`, redirect UX, CSRF handling
- `/dashboard` alias added
- NGINX hardening: security headers, CSP, API rate limiting
- Rules UI: edit/delete modals, full HTMX CRUD
- Scans UI: details modal, improved table
- Reports UI: PDF download endpoint and link
- Smoke test: full UI + API validation
- CI: GitHub Actions (pytest + Docker build)

## v0.7.0
- Initial UI + API integration, seed data, basic dashboards
