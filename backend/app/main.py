from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import Session, select

from .api import benchmarks, reports, rules, scans
from .config import settings
from .database import engine, init_db
from .models import Benchmark
from .services.benchmark_loader import PulseBenchmarkLoader

app = FastAPI(title=settings.app_name, version=settings.version, description="Compliance scanning service for Rocky Linux")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(benchmarks.router)
app.include_router(rules.router)
app.include_router(scans.router)
app.include_router(reports.router)


@app.on_event("startup")
def startup_event() -> None:
    init_db()
    loader = PulseBenchmarkLoader()
    Path(settings.benchmark_dir).mkdir(parents=True, exist_ok=True)
    if settings.database_url.startswith("sqlite"):
        db_path = settings.database_url.replace("sqlite:///", "")
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    with Session(engine) as session:
        if not session.exec(select(Benchmark)).first():
            loader.load_all(session)


@app.get("/")
def root() -> dict[str, str]:
    return {"service": settings.app_name, "version": settings.version, "status": "running"}


@app.get("/health")
def health() -> dict[str, str]:
    with Session(engine) as session:
        session.exec(select(Benchmark).limit(1))
    return {"status": "healthy", "database": "connected"}
