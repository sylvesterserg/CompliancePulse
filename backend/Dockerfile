FROM node:20-alpine AS assets
WORKDIR /build
COPY package.json ./
COPY tailwind.config.js ./
COPY frontend ./frontend
RUN npm install && npm run build:css

FROM python:3.11-slim AS runtime
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH="/app:/app/backend:${PYTHONPATH}"

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy entire backend tree to preserve module paths
COPY backend /app/backend

# Keep top-level convenience paths for existing entrypoint commands
COPY backend/app ./app
COPY backend/engine ./engine
COPY backend/main.py ./main.py
COPY backend/worker.py ./worker.py
COPY backend/scheduler_service.py ./scheduler_service.py
COPY backend/benchmarks ./benchmarks
COPY frontend/templates ./frontend/templates
COPY --from=assets /build/frontend/static ./frontend/static

RUN mkdir -p /app/data /app/logs /app/artifacts

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
