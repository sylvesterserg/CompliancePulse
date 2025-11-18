Tests

- Running
  - `pytest -q` to run all tests in `tests` and `backend/tests` (see `pytest.ini`)
  - Markers: `integration`, `worker`, `smoke`, `acl`, `slow`

- Test Environment
  - SQLite DB created at `tests/test.db` via env override in `tests/conftest.py`
  - `SECURITY_TEST_MODE=1`: enables header-based auth and JSON mirroring for test ASGI client
  - Ensures a single import root (`app` alias to `backend.app`) to avoid SQLModel metadata duplication
  - Seeds an org/user and loads benchmarks before tests

- ASGI Test Client
  - Custom ASGI client sends requests directly to the app callable
  - JSON payloads are mirrored into the `x-test-json-body` header by app middleware/wrapper for stable parsing

- Useful Targets
  - Route presence: `tests/test_routes_map.py`
  - API basics: `tests/test_api_rules_reports.py`
  - Worker & scheduler: `tests/test_worker_scheduler.py`
  - Backend service tests: `backend/tests/*`

- Tips
  - If adding new routers, update tests to include route presence checks and basic JSON responses
  - Keep UI routes providing JSON fallbacks for `accept: application/json` in tests

