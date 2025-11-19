# CompliancePulse Agent (Phase 1.1)

This document describes the agent-based scan engine.

- Registration: agent calls `/api/agent/register` with hostname, os, version → server issues token.
- Authentication: agent calls `/api/agent/auth` with uuid → rotated token.
- Heartbeat: agent posts `/api/agent/heartbeat` periodically to update last_seen and status.
- Job polling: agent calls `/api/agent/jobs/next` to fetch the next job (benchmark + rules).
- Execution: agent runs rules locally using the built-in evaluator.
- Result upload: agent posts `/api/agent/job/{id}/result` with per-rule outcomes.
- Reporting: backend processes results into Scan + Report artifacts.

## Installation

Use the universal installer:

```
curl -fsSL https://example.com/install-agent.sh | bash -s -- --server http://YOUR_SERVER --org 1
```

This installs a systemd unit `compliancepulse-agent.service`, writes `/etc/compliancepulse-agent/conf.json` with the UUID and token, and starts the agent.

## Job lifecycle

1. Admin triggers a scan (all agents/specific/tag) → backend creates `AgentJob` rows.
2. Agent polls `/jobs/next` → receives a job with rule set.
3. Agent executes rules → uploads results to `/job/{id}/result`.
4. Backend generates Scan + Report and updates dashboards.

## Debugging

Agent logs: journalctl -u compliancepulse-agent -f

Server logs: make prod-logs

## Compatibility

Linux (Rocky/RHEL/AlmaLinux/CentOS, Ubuntu/Debian variants, Amazon Linux) and macOS. Requires Python 3 installed on target hosts.

