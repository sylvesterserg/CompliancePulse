from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
import json
import os
from pathlib import Path
from datetime import datetime

app = FastAPI(title="CompliancePulse API", version="0.3.0")
security = HTTPBearer()

# Load config
API_TOKEN = os.getenv("API_TOKEN", "")
DATA_DIR = Path(os.getenv("BASE_DIR", "/opt/compliancepulse")) / "data"

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Verify API token"""
    if not API_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="API token not configured"
        )
    if credentials.credentials != API_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token"
        )
    return credentials.credentials

@app.get("/health")
def health_check():
    """Health check endpoint (no auth required)"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "0.3.0"
    }

@app.get("/api/report")
def get_report(token: str = Depends(verify_token)):
    """Get latest compliance report"""
    report_path = DATA_DIR / "compliance_report.json"
    
    if not report_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No compliance report available yet. Run a scan first."
        )
    
    try:
        with open(report_path) as f:
            data = json.load(f)
        return data
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Report file is corrupted"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to read report: {str(e)}"
        )

@app.get("/api/reports/history")
def get_report_history(token: str = Depends(verify_token), limit: int = 10):
    """Get historical compliance reports"""
    try:
        reports = []
        for report_file in sorted(DATA_DIR.glob("compliance_report_*.json"), reverse=True)[:limit]:
            with open(report_file) as f:
                data = json.load(f)
                reports.append({
                    "filename": report_file.name,
                    "timestamp": data.get("metadata", {}).get("timestamp"),
                    "summary": data.get("summary", {})
                })
        return {"reports": reports, "count": len(reports)}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve history: {str(e)}"
        )
