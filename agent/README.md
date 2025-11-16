# CompliancePulse Agent

Lightweight Python script that simulates a compliance scan and posts mock data to the backend API. Use this when testing data ingest without provisioning remote machines.

## Layout

- `scan_agent.py` – CLI entry point. Accepts a hostname and optional IP address.

## Local Usage

```bash
cd agent
python3 scan_agent.py demo-host 10.0.0.10
```

The script prints simulated findings and exits with `0`. Add flags or network calls here when implementing the real SSH-based agent.

## Development Tips

- Keep dependencies standard library only until a packaging strategy is defined.
- Mirror any payload schema updates from `backend/main.py` so that reports deserialize correctly.
- Document new CLI arguments here to keep the repo organized.
