Frontend

- Templates
  - Located in `frontend/templates/` with a `layout.html` and pages: `dashboard.html`, `rules.html`, `scans.html`, `reports.html`.
  - Partials for HTMX updates: `partials/*.html`, modals under `modals/*.html`, auth views under `auth/*.html`.

- Static Assets
  - `frontend/static/css/tailwind.css` (source) compiled to `frontend/static/css/app.css`.
  - `frontend/static/js/htmx.js` for interactivity.

- Build
  - Install: `npm install`
  - Build CSS: `npm run build:css` (or `docker compose --profile assets run --rm tailwind`)

- UI Router
  - `backend/app/api/ui_router.py` serves pages and HTMX partials.
  - In test mode or JSON-accepting requests, routes provide JSON fallbacks (status/count payloads) to ease testing.

