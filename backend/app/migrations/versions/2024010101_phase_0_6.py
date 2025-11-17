"""Phase 0.6 authentication and multi-tenancy"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "2024010101"
down_revision = None
branch_labels = None
depends_on = None

TENANT_TABLES = [
    "rule",
    "rulegroup",
    "scan",
    "scanresult",
    "report",
    "schedule",
    "scanjob",
]


def upgrade() -> None:
    op.create_table(
        "organization",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("slug", sa.String(length=255), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
    )
    op.create_table(
        "user",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(length=255), nullable=False, unique=True),
        sa.Column("hashed_password", sa.String(length=512), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("1"), nullable=False),
        sa.Column("is_verified", sa.Boolean(), server_default=sa.text("0"), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
    )
    op.create_table(
        "userorganization",
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False, server_default="MEMBER"),
        sa.Column("joined_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["organization_id"], ["organization.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id", "organization_id"),
    )

    for table_name in TENANT_TABLES:
        op.add_column(
            table_name,
            sa.Column("organization_id", sa.Integer(), nullable=True),
        )

    bind = op.get_bind()
    organization_table = sa.Table(
        "organization",
        sa.MetaData(),
        sa.Column("id", sa.Integer()),
        sa.Column("name", sa.String()),
        sa.Column("slug", sa.String()),
        sa.Column("created_at", sa.DateTime()),
        sa.Column("updated_at", sa.DateTime()),
    )
    result = bind.execute(
        organization_table.insert().values(name="Default Organization", slug="default-org")
    )
    default_org_id = result.inserted_primary_key[0]

    for table_name in TENANT_TABLES:
        bind.execute(
            sa.text(
                f"UPDATE {table_name} SET organization_id = :org_id WHERE organization_id IS NULL"
            ),
            {"org_id": default_org_id},
        )
        op.alter_column(
            table_name,
            "organization_id",
            existing_type=sa.Integer(),
            nullable=False,
        )
        op.create_foreign_key(
            f"fk_{table_name}_organization",
            table_name,
            "organization",
            ["organization_id"],
            ["id"],
        )


def downgrade() -> None:
    for table_name in TENANT_TABLES:
        op.drop_constraint(f"fk_{table_name}_organization", table_name, type_="foreignkey")
        op.drop_column(table_name, "organization_id")

    op.drop_table("userorganization")
    op.drop_table("user")
    op.drop_table("organization")
