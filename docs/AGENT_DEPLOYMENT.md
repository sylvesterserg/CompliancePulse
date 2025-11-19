# Agent Deployment at Scale

## Mass deployment

- Ansible: use the `deployment/agent/install-agent.sh` script via `script:` or `shell:` to register and start the agent on each host.
- Salt: download and run the installer with appropriate `--server` and `--org` parameters.

## Auto-registration

- Installer calls `/api/agent/register` to get a token and UUID.
- Tokens expire after 24h; agents re-authenticate via `/api/agent/auth` and token rotation.
- Tokens can be revoked by deleting rows in `AgentAuthToken` or extending API to revoke.

## Token Rotation

- Agents rotate tokens via `/api/agent/auth` when they get a 401 on heartbeat.

## Hardening

- Restrict CORS if agents connect from fixed subnets.
- Use TLS termination (nginx) and secure cookies disabled for agent paths.

