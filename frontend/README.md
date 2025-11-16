# CompliancePulse Frontend

Simple static dashboard that consumes backend APIs and renders the latest systems + reports.

## Files

- `index.html` – Single page app with vanilla JS fetch calls.
- `Dockerfile` – Serves the static files through a lightweight HTTP server on port 3000.

## Local Development

```bash
cd frontend
python3 -m http.server 3000
# Visit http://localhost:3000
```

Update API URLs inside `index.html` if you run the backend on a different host/port.

## Production Tips

- Keep the container stateless; all persistence lives in the backend service volumes.
- Run `docker compose up -d frontend --build` after HTML/JS changes to ensure the container rebuilds.
- Add screenshots of UI updates to PR descriptions when possible.
