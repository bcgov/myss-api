"""Create eligibility_rate_table and eligibility_asset_limit tables

Revision ID: 0003
Revises: 2208d981358e
Create Date: 2026-03-16
"""
from datetime import date

from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "2208d981358e"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "eligibility_rate_table",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("family_size", sa.Integer, nullable=False),
        sa.Column("type_a", sa.Numeric(10, 2), nullable=False),
        sa.Column("type_b", sa.Numeric(10, 2), nullable=False),
        sa.Column("type_c", sa.Numeric(10, 2), nullable=False),
        sa.Column("type_d", sa.Numeric(10, 2), nullable=False),
        sa.Column("type_e", sa.Numeric(10, 2), nullable=False),
        sa.Column("effective_from", sa.Date, nullable=False),
        sa.Column("notes", sa.Text, nullable=True),
        sa.UniqueConstraint("family_size", "effective_from", name="uq_rate_family_effective"),
    )

    op.create_table(
        "eligibility_asset_limit",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("limit_type", sa.String(1), nullable=False),
        sa.Column("limit", sa.Numeric(12, 2), nullable=False),
        sa.Column("effective_from", sa.Date, nullable=False),
        sa.Column("notes", sa.Text, nullable=True),
        sa.UniqueConstraint("limit_type", "effective_from", name="uq_asset_type_effective"),
    )

    # Seed FDD BR-D9-05 / BR-D9-06 rates (August 2023 values)
    op.bulk_insert(
        sa.table(
            "eligibility_rate_table",
            sa.column("family_size", sa.Integer),
            sa.column("type_a", sa.Numeric),
            sa.column("type_b", sa.Numeric),
            sa.column("type_c", sa.Numeric),
            sa.column("type_d", sa.Numeric),
            sa.column("type_e", sa.Numeric),
            sa.column("effective_from", sa.Date),
            sa.column("notes", sa.Text),
        ),
        [
            {"family_size": 1, "type_a": "1060.00", "type_b": "0.00",    "type_c": "1535.50", "type_d": "0.00",    "type_e": "0.00",    "effective_from": date(2023, 8, 1), "notes": "FDD BR-D9-05"},
            {"family_size": 2, "type_a": "1650.00", "type_b": "1405.00", "type_c": "2125.50", "type_d": "1880.50", "type_e": "2652.50", "effective_from": date(2023, 8, 1), "notes": "FDD BR-D9-05"},
            {"family_size": 3, "type_a": "1845.00", "type_b": "1500.00", "type_c": "2320.50", "type_d": "1975.50", "type_e": "2847.50", "effective_from": date(2023, 8, 1), "notes": "FDD BR-D9-05"},
            {"family_size": 4, "type_a": "1895.00", "type_b": "1550.00", "type_c": "2370.50", "type_d": "2025.50", "type_e": "2897.50", "effective_from": date(2023, 8, 1), "notes": "FDD BR-D9-05"},
            {"family_size": 5, "type_a": "1945.00", "type_b": "1600.00", "type_c": "2420.50", "type_d": "2075.50", "type_e": "2947.50", "effective_from": date(2023, 8, 1), "notes": "FDD BR-D9-05"},
            {"family_size": 6, "type_a": "1995.00", "type_b": "1650.00", "type_c": "2470.50", "type_d": "2125.50", "type_e": "2997.50", "effective_from": date(2023, 8, 1), "notes": "FDD BR-D9-05"},
            {"family_size": 7, "type_a": "2045.00", "type_b": "1700.00", "type_c": "2520.50", "type_d": "2175.50", "type_e": "3047.50", "effective_from": date(2023, 8, 1), "notes": "FDD BR-D9-05 (cap)"},
        ],
    )

    op.bulk_insert(
        sa.table(
            "eligibility_asset_limit",
            sa.column("limit_type", sa.String),
            sa.column("limit", sa.Numeric),
            sa.column("effective_from", sa.Date),
            sa.column("notes", sa.Text),
        ),
        [
            {"limit_type": "A", "limit": "5000.00",   "effective_from": date(2023, 8, 1), "notes": "Single, no dependants, not PWD"},
            {"limit_type": "B", "limit": "10000.00",  "effective_from": date(2023, 8, 1), "notes": "Married or at least one dependant"},
            {"limit_type": "C", "limit": "100000.00", "effective_from": date(2023, 8, 1), "notes": "At least one PWD (not both)"},
            {"limit_type": "D", "limit": "200000.00", "effective_from": date(2023, 8, 1), "notes": "Both KP and spouse are PWD"},
        ],
    )


def downgrade() -> None:
    op.drop_table("eligibility_asset_limit")
    op.drop_table("eligibility_rate_table")
