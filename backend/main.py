"""Entry point for the CompliancePulse FastAPI application."""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import SQLModel

from .api.dependencies import engine
from .api.models import Report, System  # noqa: F401 - models imported for metadata
from .api.routes import reports, root, scan, systems

app = FastAPI(
    title="CompliancePulse API",
    version="0.1.0",
    description="Compliance monitoring and scanning API",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(root.router)
app.include_router(systems.router)
app.include_router(scan.router)
app.include_router(reports.router)


@app.on_event("startup")
def on_startup() -> None:
    SQLModel.metadata.create_all(engine)
