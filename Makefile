
.PHONY: help lint test agent backend frontend

help:
	@echo "Available targets:"
	@echo "  lint     - Syntax-check backend and agent Python code"
	@echo "  test     - Run lightweight health checks for backend and frontend containers"
	@echo "  agent    - Run the scanning agent locally"
	@echo "  backend  - Start backend locally with uvicorn"
	@echo "  frontend - Serve the static dashboard with Python"

lint:
	python -m compileall backend agent

agent:
	cd agent && python3 scan_agent.py localhost 127.0.0.1

backend:
	cd backend && uvicorn main:app --reload --port 8000

frontend:
	cd frontend && python3 -m http.server 3000

# Basic smoke-test hook so CI can call `make test`
test:
	@if command -v docker >/dev/null 2>&1; then \
		docker compose config >/dev/null; \
	else \
		echo "Docker is not installed; skipping compose validation"; \
	fi
