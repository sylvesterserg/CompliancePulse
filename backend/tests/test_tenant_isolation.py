from sqlmodel import Session, select

from app.models import Organization, Rule


def test_tenant_filter_blocks_cross_org_queries(session: Session) -> None:
    org_one = Organization(name="Alpha", slug="alpha")
    org_two = Organization(name="Beta", slug="beta")
    session.add(org_one)
    session.add(org_two)
    session.commit()
    rule_one = Rule(
        id="rule-alpha",
        organization_id=org_one.id,
        benchmark_id="bench",
        title="Alpha rule",
        description="",
        severity="low",
        remediation="",
        check_type="shell",
        command="echo alpha",
        expect_type="equals",
        expect_value="alpha",
        timeout_seconds=5,
    )
    rule_two = Rule(
        id="rule-beta",
        organization_id=org_two.id,
        benchmark_id="bench",
        title="Beta rule",
        description="",
        severity="low",
        remediation="",
        check_type="shell",
        command="echo beta",
        expect_type="equals",
        expect_value="beta",
        timeout_seconds=5,
    )
    session.add(rule_one)
    session.add(rule_two)
    session.commit()

    session.info["organization_id"] = org_one.id
    results = session.exec(select(Rule).order_by(Rule.id)).all()
    assert len(results) == 1
    assert results[0].id == "rule-alpha"

    session.info["organization_id"] = org_two.id
    results = session.exec(select(Rule).order_by(Rule.id)).all()
    assert len(results) == 1
    assert results[0].id == "rule-beta"
