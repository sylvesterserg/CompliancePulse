API Reference

Base URL: http://localhost:8000

- Service
  - GET `/api` → `{ service, version, status }`
  - GET `/health` → `{ status, database }`
  - GET `/api/version` → `{ version }`
  - GET `/api/ping` → `{ pong: true }`

- Benchmarks (`/benchmarks`)
  - GET `/benchmarks` → List[BenchmarkSummary]
  - GET `/benchmarks/{benchmark_id}` → BenchmarkDetail
  - GET `/benchmarks/{benchmark_id}/rules` → List[RuleDetail]
  - POST `/benchmarks/reload` (Admin) → List[BenchmarkSummary]

- Rules (`/rules`)
  - GET `/rules?severity={str}&benchmark_id={str}` → `{ page: "rules", count }` (JSONResponse)
  - GET `/rules/{rule_id}` → RuleDetail (JSONResponse)

- Scans (`/scans`)
  - POST `/scans` → ScanDetail
    - Body: `{ hostname: str, ip?: str, benchmark_id: str, tags?: string[] }`
  - GET `/scans` → List[ScanSummary] (JSONResponse)
  - GET `/scans/{scan_id}` → ScanDetail (JSONResponse)
  - GET `/scans/{scan_id}/report` → ReportView (JSONResponse)
  - POST `/scans/trigger/group/{group_id}` → ScanJobView

- Reports (`/reports`)
  - GET `/reports` → `{ page: "reports", count }` (JSONResponse)
  - GET `/reports/{report_id}` → ReportView

- Schedules (`/schedules`)
  - GET `/schedules` → List[ScheduleView]
  - POST `/schedules/create` → ScheduleView (Admin)
    - Body: `{ name, group_id, frequency: "hourly"|"daily"|"custom", interval_minutes?, enabled? }`
  - DELETE `/schedules/{schedule_id}` → `{ status: "deleted" }` (Admin)

- API Keys (`/settings/api-keys`)
  - GET `/settings/api-keys` → List[ApiKeyView]
  - POST `/settings/api-keys/create` → ApiKeyCreateResponse
    - Body: `{ name: string, organization_id?: string, scopes?: string[] }`
  - POST `/settings/api-keys/{api_key_id}/revoke` → ApiKeyView
  - GET `/settings/api-keys/{api_key_id}/show` → ApiKeyView

Auth & Org Context
- Most endpoints require authentication (`require_authenticated_user`) and organization context is set in session.
- Test mode supports headers: `x-test-user`, `x-test-org`.
- API Keys are accepted via `Authorization: Bearer <token>` or `X-API-Key`.

Examples
```bash
curl -H 'accept: application/json' http://localhost:8000/health

curl -H 'accept: application/json' \
     -H 'x-test-user: 1' -H 'x-test-org: 1' \
     -X POST http://localhost:8000/scans \
     -d '{"hostname":"demo","benchmark_id":"rocky_l1_foundation"}' \
     -H 'content-type: application/json'
```

