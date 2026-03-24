"""Create registration domain tables

Revision ID: 0004
Revises: 0003
Create Date: 2026-03-16

Tables:
  - users                     (identity; created at BCeID link step 6)
  - profiles                  (ICM-linked identity; one per user)
  - registration_sessions     (wizard state, token-keyed; replaces Session["RegistrationID"])
  - power_of_attorney         (representative details; replaces TAAPOA_AAE_POWER_OF_ATTORNEY)
  - portal_requests           (ICM SR tracking; replaces TAAPRQ_AAE_PORTAL_REQ)
"""
from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("bceid_guid", sa.String(36), nullable=False, unique=True),
        sa.Column("bceid_username", sa.String(100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    op.create_table(
        "profiles",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("first_name", sa.String(50), nullable=False),
        sa.Column("middle_name", sa.String(50), nullable=True),
        sa.Column("last_name", sa.String(50), nullable=False),
        sa.Column("sin", sa.String(9), nullable=False),
        sa.Column("phn", sa.String(10), nullable=True),
        sa.Column("date_of_birth", sa.Date, nullable=False),
        sa.Column("gender", sa.String(10), nullable=False),
        sa.Column("email", sa.String(250), nullable=False),
        sa.Column("phone_number", sa.String(20), nullable=True),
        sa.Column("phone_type", sa.String(20), nullable=True),
        sa.Column("link_status", sa.String(20), nullable=False, server_default="UNLINKED"),
        sa.Column("portal_id", sa.Integer, nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    op.create_table(
        "registration_sessions",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("token", sa.String(36), nullable=False, unique=True, index=True),
        sa.Column("account_creation_type", sa.String(20), nullable=False),
        sa.Column("step_reached", sa.Integer, nullable=False, server_default="1"),
        sa.Column("poa_data", sa.JSON, nullable=True),
        sa.Column("registrant_data", sa.JSON, nullable=True),
        sa.Column("spouse_data", sa.JSON, nullable=True),
        sa.Column("invite_token", sa.String(36), nullable=True, unique=True),
        sa.Column("invite_token_used", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("pin_hash", sa.String(200), nullable=True),
        sa.Column("pin_salt", sa.String(100), nullable=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "power_of_attorney",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("registration_session_id", sa.Integer, sa.ForeignKey("registration_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("representative_first_name", sa.String(50), nullable=False),
        sa.Column("representative_last_name", sa.String(50), nullable=False),
        sa.Column("representative_phone", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "portal_requests",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("profile_id", sa.Integer, sa.ForeignKey("profiles.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("icm_sr_number", sa.String(50), nullable=True),
        sa.Column("status", sa.String(30), nullable=False, server_default="PENDING"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("portal_requests")
    op.drop_table("power_of_attorney")
    op.drop_table("registration_sessions")
    op.drop_table("profiles")
    op.drop_table("users")
