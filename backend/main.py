from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlmodel import SQLModel, Field, create_engine, Session, select
import os
from datetime import datetime

app = FastAPI(
    title="CompliancePulse API",
    version="0.1.0",
    description="Compliance monitoring and scanning API"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_URL = os.getenv("DB_URL", "sqlite:////app/data/compliancepulse.db")
engine = create_engine(DB_URL, echo=True)

class System(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    hostname: str = Field(index=True)
    ip: str | None = None
    os_version: str | None = None
    last_scan: str | None = None
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())

class Report(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    system_id: int = Field(foreign_key="system.id")
    score: int = Field(ge=0, le=100)
    issues_json: str
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())

class ScanRequest(BaseModel):
    hostname: str
    ip: str | None = None

class ScanResponse(BaseModel):
    hostname: str
    score: int
    issues: list[str]
    scan_time: str

@app.on_event("startup")
def on_startup():
    SQLModel.metadata.create_all(engine)
    print("✓ Database initialized")

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
        raise HTTPException(status_code=503, detail=f"Database error: {str(e)}")

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

@app.post("/scan", response_model=ScanResponse)
def scan_system(request: ScanRequest):
    scan_result = {
        "hostname": request.hostname,
        "score": 87,
        "issues": [
            "Password policy does not meet CIS standards",
            "Firewall not configured properly",
            "SSH root login enabled",
            "No automatic security updates configured"
        ],
        "scan_time": datetime.now().isoformat()
    }
    
    with Session(engine) as s:
        existing = s.exec(select(System).where(System.hostname == request.hostname)).first()
        
        if existing:
            system = existing
            system.last_scan = scan_result["scan_time"]
        else:
            system = System(
                hostname=request.hostname,
                ip=request.ip,
                last_scan=scan_result["scan_time"]
            )
            s.add(system)
        
        s.commit()
        s.refresh(system)
        
        import json
        report = Report(
            system_id=system.id,
            score=scan_result["score"],
            issues_json=json.dumps(scan_result["issues"]),
            created_at=scan_result["scan_time"]
        )
        s.add(report)
        s.commit()
    
    return scan_result

@app.get("/reports")
def get_reports(limit: int = 10):
    with Session(engine) as s:
        reports = s.exec(select(Report).limit(limit)).all()
        return {"reports": reports, "count": len(reports)}
