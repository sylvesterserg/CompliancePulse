from pathlib import Path


def test_requirements_versions_are_compatible():
    req = Path("backend/requirements.txt").read_text(encoding="utf-8")
    assert "sqlmodel" in req
    assert "pydantic" in req
    assert ">=0.0.16" in req or "sqlmodel==0.0.16" in req or "sqlmodel==0.0.17" in req
    # Ensure we are using Pydantic v2
    assert "pydantic>=" in req and ",<3" in req

