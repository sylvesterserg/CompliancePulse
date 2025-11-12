import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Sequence

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field as PydanticField, IPvAnyAddress
from sqlmodel import SQLModel, Field, Session, create_engine, select

app = FastAPI(
    title="CompliancePulse API",
    version="0.1.0",
    description="Compliance monitoring and scanning API"
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("compliancepulse")

default_origins = "http://localhost:3000,http://127.0.0.1:3000,http://0.0.0.0:3000"
allowed_origins = [
    origin.strip()
    for origin in os.getenv("FRONTEND_ORIGINS", default_origins).split(",")
    if origin.strip()
]

if not allowed_origins:
    allowed_origins = default_origins.split(",")

logger.info("Configured CORS origins: %s", allowed_origins)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
    max_age=600
)

DB_URL = os.getenv("DB_URL", "sqlite:////app/data/compliancepulse.db")


def _build_engine(database_url: str):
    connect_args: dict[str, Any] = {}
    if database_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False

    echo = os.getenv("SQL_ECHO", "false").lower() == "true"
    return create_engine(database_url, echo=echo, connect_args=connect_args)


engine = _build_engine(DB_URL)

class System(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    hostname: str = Field(index=True)
    ip: str | None = None
    os_version: str | None = None
    last_scan: str | None = None
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

class Report(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    system_id: int = Field(foreign_key="system.id")
    score: int = Field(ge=0, le=100)
    issues_json: str
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

class ScanRequest(BaseModel):
    hostname: str = PydanticField(min_length=1, max_length=255, pattern=r"^[a-zA-Z0-9._-]+$")
    ip: IPvAnyAddress | None = None

class ScanResponse(BaseModel):
    hostname: str
    score: int
    issues: list[str]
    scan_time: str

@app.on_event("startup")
def on_startup():
    SQLModel.metadata.create_all(engine)
    logger.info("Database initialized")

@app.get("/")
def root():
    return {"service": "CompliancePulse API", "version": "0.1.0", "status": "running"}

@app.get("/health")
def health():
    try:
        with Session(engine) as s:
            s.exec(select(System).limit(1))
        return {"status": "healthy", "database": "connected"}
    except Exception as e:
        logger.exception("Database health check failed")
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database connection error") from e

@app.get("/systems")
def get_systems():
    with Session(engine) as s:
        systems = s.exec(select(System)).all()
        return {"systems": systems, "count": len(systems)}

@app.get("/systems/{system_id}")
def get_system(system_id: int):
    with Session(engine) as s:
        system = s.get(System, system_id)
        if not system:
            raise HTTPException(status_code=404, detail="System not found")
        return system

def _serialize_issues(issues: Sequence[str]) -> str:
    return json.dumps(list(issues), ensure_ascii=False)


def _current_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


@app.post("/scan", response_model=ScanResponse)
def scan_system(request: ScanRequest):
    scan_time = _current_timestamp()
    scan_result = {
        "hostname": request.hostname,
        "score": 87,
        "issues": [
            "Password policy does not meet CIS standards",
            "Firewall not configured properly",
            "SSH root login enabled",
            "No automatic security updates configured"
        ],
        "scan_time": scan_time
    }

    with Session(engine) as s:
        existing = s.exec(select(System).where(System.hostname == request.hostname)).first()

        if existing:
            system = existing
            system.last_scan = scan_time
        else:
            system = System(
                hostname=request.hostname,
                ip=request.ip,
                last_scan=scan_time
            )
            s.add(system)

        s.commit()
        s.refresh(system)

        report = Report(
            system_id=system.id,
            score=scan_result["score"],
            issues_json=_serialize_issues(scan_result["issues"]),
            created_at=scan_time
        )
        s.add(report)
        s.commit()
    
    return scan_result

@app.get("/reports")
def get_reports(limit: int = 10):
    with Session(engine) as s:
        reports = s.exec(select(Report).limit(limit)).all()
        return {"reports": reports, "count": len(reports)}
