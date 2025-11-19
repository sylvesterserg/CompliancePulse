#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import platform
import socket
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple

import requests


@dataclass
class AgentConfig:
    server: str
    uuid: str | None
    token: str | None
    version: str = "1.1.0"

    @classmethod
    def load(cls, path: Path) -> "AgentConfig":
        if not path.exists():
            return cls(server="", uuid=None, token=None)
        data = json.loads(path.read_text())
        return cls(server=data.get("server", ""), uuid=data.get("uuid"), token=data.get("token"), version=data.get("version", "1.1.0"))

    def save(self, path: Path) -> None:
        path.write_text(json.dumps({"server": self.server, "uuid": self.uuid, "token": self.token, "version": self.version}))


class RuleRunner:
    def __init__(self, timeout: int = 10):
        self.timeout = timeout

    def run_rule(self, rule: Dict[str, Any]) -> Dict[str, Any]:
        rtype = (rule.get("type") or "shell").lower()
        try:
            if rtype == "file_exists":
                return self._file_exists(rule)
            if rtype == "command_output_match":
                return self._command_output_match(rule)
            if rtype == "port_open":
                return self._port_open(rule)
            return self._shell(rule)
        except Exception as exc:  # pragma: no cover
            return {"id": rule.get("id"), "passed": False, "stderr": str(exc), "details": {"error": str(exc)}}

    def _file_exists(self, rule: Dict[str, Any]) -> Dict[str, Any]:
        path = rule.get("path") or rule.get("command") or rule.get("expect_value")
        ok = Path(str(path)).exists()
        return {"id": rule.get("id"), "passed": ok, "stdout": "", "stderr": "", "details": {"path": path}}

    def _port_open(self, rule: Dict[str, Any]) -> Dict[str, Any]:
        import socket as _s
        host = rule.get("host") or "127.0.0.1"
        port = int(rule.get("port") or rule.get("expect_value") or 0)
        s = _s.socket(_s.AF_INET, _s.SOCK_STREAM)
        s.settimeout(float(rule.get("timeout") or self.timeout))
        try:
            s.connect((host, port))
            return {"id": rule.get("id"), "passed": True, "stdout": "", "stderr": "", "details": {"host": host, "port": port}}
        except OSError as exc:
            return {"id": rule.get("id"), "passed": False, "stdout": "", "stderr": str(exc), "details": {"host": host, "port": port}}
        finally:
            try:
                s.close()
            except OSError:
                pass

    def _command_output_match(self, rule: Dict[str, Any]) -> Dict[str, Any]:
        import re, subprocess
        command = rule.get("command")
        pattern = rule.get("expect_value") or rule.get("pattern")
        cp = subprocess.run(command, shell=True, capture_output=True, text=True)
        out = cp.stdout or ""
        ok = re.search(pattern, out) is not None if rule.get("match_type") == "regex" else pattern in out
        return {"id": rule.get("id"), "passed": ok, "stdout": out, "stderr": cp.stderr, "details": {"exit_code": cp.returncode}}

    def _shell(self, rule: Dict[str, Any]) -> Dict[str, Any]:
        import subprocess
        command = rule.get("command") or ""
        cp = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=int(rule.get("timeout") or self.timeout))
        expect = (rule.get("expect_type") or "exit_code").lower()
        target = str(rule.get("expect_value") or "0")
        ok = cp.returncode == int(target) if expect == "exit_code" else (target in (cp.stdout or ""))
        return {"id": rule.get("id"), "passed": ok, "stdout": cp.stdout, "stderr": cp.stderr, "details": {"exit_code": cp.returncode}}


def _headers(token: str | None) -> Dict[str, str]:
    h = {"user-agent": "compliancepulse-agent/1.1"}
    if token:
        h["authorization"] = f"Bearer {token}"
    return h


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--config", default="/etc/compliancepulse-agent/conf.json")
    args = p.parse_args()
    cfg_path = Path(args.config)
    cfg = AgentConfig.load(cfg_path)
    if not cfg.server:
        print("[agent] Missing server in config")
        return

    # Register if needed
    if not cfg.token:
        payload = {
            "uuid": cfg.uuid,
            "hostname": socket.gethostname(),
            "os": f"{platform.system()} {platform.release()}",
            "version": cfg.version,
        }
        r = requests.post(f"{cfg.server}/api/agent/register", json=payload, timeout=10)
        r.raise_for_status()
        data = r.json()
        cfg.uuid = data.get("uuid")
        cfg.token = data.get("token")
        cfg.save(cfg_path)

    runner = RuleRunner()
    while True:
        try:
            # Heartbeat
            hb = requests.post(f"{cfg.server}/api/agent/heartbeat", json={"version": cfg.version}, headers=_headers(cfg.token), timeout=10)
            if hb.status_code == 401:
                # re-auth
                auth = requests.post(f"{cfg.server}/api/agent/auth", json={"uuid": cfg.uuid, "hostname": socket.gethostname(), "version": cfg.version})
                auth.raise_for_status()
                cfg.token = auth.json().get("token")
                cfg.save(cfg_path)
            # Next job
            j = requests.get(f"{cfg.server}/api/agent/jobs/next", headers=_headers(cfg.token), timeout=15)
            if j.status_code == 204:
                time.sleep(10)
                continue
            j.raise_for_status()
            job = j.json()
            results: List[Dict[str, Any]] = []
            for rule in job.get("rules", []):
                res = runner.run_rule(rule)
                # propagate meta
                res.update({
                    "title": rule.get("title"),
                    "severity": rule.get("severity", "info"),
                    "description": rule.get("description", ""),
                    "remediation": rule.get("remediation", ""),
                })
                results.append(res)
            upload = {"status": "completed", "results": results}
            ur = requests.post(f"{cfg.server}/api/agent/job/{job['id']}/result", json=upload, headers=_headers(cfg.token), timeout=30)
            ur.raise_for_status()
        except Exception:
            time.sleep(5)


if __name__ == "__main__":
    main()

