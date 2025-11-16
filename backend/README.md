# CompliancePulse Backend

FastAPI + SQLModel application that exposes system + report endpoints and persists data to SQLite (mounted via Docker volumes).

## Service Layout

- `main.py` – FastAPI app with `/health`, `/systems`, `/reports`, `/scan`.
- `requirements.txt` – Python dependencies.
- `Dockerfile` – Production image served at port 8000.

## Local Development

```bash
# Install deps
pip install -r backend/requirements.txt sqlmodel uvicorn

# Start API with hot reload
uvicorn backend.main:app --reload --port 8000
```

SQLite lives at `./data/compliancepulse.db` when running through Docker Compose. Update `DB_URL` in `docker-compose.yml` or environment variables to swap databases.

## Testing

```bash
make lint
curl http://localhost:8000/health
```

Add FastAPI/SQLModel tests under `tests/backend/` and wire them to `make test` as the project grows.
