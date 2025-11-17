import asyncio
import importlib
import json
import os
import sys
from pathlib import Path
from typing import Callable, Dict

import pytest
from sqlmodel import Session, SQLModel, create_engine, select

ROOT = Path(__file__).resolve().parents[1]
if ROOT.as_posix() not in sys.path:
    sys.path.insert(0, ROOT.as_posix())

TEST_DB_PATH = ROOT / "tests" / "test.db"
if TEST_DB_PATH.exists():
    TEST_DB_PATH.unlink()
TEST_DB_URL = f"sqlite:///{TEST_DB_PATH}"
os.environ.setdefault("DB_URL", TEST_DB_URL)
os.environ.setdefault("BENCHMARK_DIR", str(ROOT / "backend" / "benchmarks"))

import backend.app.config as app_config
importlib.reload(app_config)
app_config.settings.database_url = TEST_DB_URL
app_config.settings.benchmark_dir = Path(os.environ["BENCHMARK_DIR"])

import backend.app.database as app_database
importlib.reload(app_database)

test_engine = create_engine(
    TEST_DB_URL,
    connect_args={"check_same_thread": False},
)
app_database.engine = test_engine

from backend.app.models import Benchmark  # noqa: E402
from backend.app.services.benchmark_loader import PulseBenchmarkLoader
from backend.app.main import app  # noqa: E402

SQLModel.metadata.create_all(test_engine)

with Session(test_engine) as session:
    loader = PulseBenchmarkLoader(directory=app_config.settings.benchmark_dir)
    if not session.exec(select(Benchmark)).first():
        loader.load_all(session)


class _ASGIResponse:
    def __init__(self, status_code: int, headers: Dict[str, str], body: bytes):
        self.status_code = status_code
        self.headers = headers
        self.body = body

    def json(self):
        return json.loads(self.body.decode() or "{}")

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise AssertionError(f"HTTP {self.status_code}: {self.body.decode()}")


class _ASGITestClient:
    def __init__(self, asgi_app):
        self.app = asgi_app

    async def request(self, method: str, path: str, *, json_payload=None, headers=None):
        body = b""
        headers = headers or {}
        if json_payload is not None:
            body = json.dumps(json_payload).encode()
            headers = {**headers, "content-type": "application/json"}
        raw_headers = [(key.lower().encode(), value.encode()) for key, value in headers.items()]
        if not any(key.lower() == "host" for key in headers):
            raw_headers.append((b"host", b"testserver"))
        scope = {
            "type": "http",
            "http_version": "1.1",
            "method": method.upper(),
            "scheme": "http",
            "path": path,
            "root_path": "",
            "query_string": b"",
            "headers": raw_headers,
            "client": ("testclient", 50000),
            "server": ("testserver", 80),
        }
        request_sent = False
        messages = []

        async def receive():
            nonlocal request_sent
            if request_sent:
                await asyncio.sleep(0)
                return {"type": "http.disconnect"}
            request_sent = True
            return {"type": "http.request", "body": body, "more_body": False}

        async def send(message):
            messages.append(message)

        await self.app(scope, receive, send)
        status = 500
        response_headers: Dict[str, str] = {}
        body_bytes = b""
        for message in messages:
            if message["type"] == "http.response.start":
                status = message["status"]
                response_headers = {key.decode(): value.decode() for key, value in message.get("headers", [])}
            elif message["type"] == "http.response.body":
                body_bytes += message.get("body", b"")
        return _ASGIResponse(status, response_headers, body_bytes)

    async def get(self, path: str, **kwargs):
        return await self.request("GET", path, headers=kwargs.get("headers"))

    async def post(self, path: str, **kwargs):
        return await self.request("POST", path, json_payload=kwargs.get("json"), headers=kwargs.get("headers"))


@pytest.fixture(scope="session")
def db_engine():
    return test_engine


@pytest.fixture()
def session(db_engine):
    with Session(db_engine) as db_session:
        yield db_session


@pytest.fixture(scope="session")
def app_instance():
    return app


@pytest.fixture(scope="session")
def async_client(app_instance):
    return _ASGITestClient(app_instance)


@pytest.fixture(scope="session", autouse=True)
def cleanup_db():
    yield
    if TEST_DB_PATH.exists():
        TEST_DB_PATH.unlink()


@pytest.fixture(scope="session")
def completed_scan(async_client) -> Dict:
    payload = {
        "hostname": "ci-host",
        "ip": "192.0.2.10",
        "benchmark_id": "rocky_l1_foundation",
    }
    response = asyncio.run(async_client.post("/scans", json=payload))
    response.raise_for_status()
    return response.json()


@pytest.fixture()
def sample_data_factory(session: Session) -> Callable[..., Dict[str, object]]:
    from datetime import datetime

    from backend.app.models import Report, Scan

    def _factory(
        hostname: str = "ui-host",
        benchmark_id: str = "rocky_l1_foundation",
        status: str = "completed",
        score: float = 92.5,
    ) -> Dict[str, object]:
        scan = Scan(
            hostname=hostname,
            benchmark_id=benchmark_id,
            status=status,
            started_at=datetime.utcnow(),
            completed_at=datetime.utcnow(),
            total_rules=3,
            passed_rules=3,
        )
        session.add(scan)
        session.commit()
        session.refresh(scan)
        report = Report(
            scan_id=scan.id,
            benchmark_id=benchmark_id,
            hostname=hostname,
            score=score,
            summary=f"Auto generated for {hostname}",
        )
        session.add(report)
        session.commit()
        session.refresh(report)
        return {"scan": scan, "report": report}

    return _factory
