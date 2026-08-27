"""Add admin automations tables.

Revision ID: 20260825_add_admin_automations
Revises: 20260825_add_user_settings
Create Date: 2026-08-25
"""

from alembic import op
import sqlalchemy as sa

revision = "20260825_add_admin_automations"
down_revision = "20260825_add_user_settings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "admin_automations",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("trigger_type", sa.String(length=100), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("email_subject", sa.String(length=500), nullable=False),
        sa.Column("email_template", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("trigger_type"),
    )
    op.create_index("ix_admin_automations_trigger_type", "admin_automations", ["trigger_type"])

    op.create_table(
        "admin_automation_runs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("automation_id", sa.Integer(), nullable=False),
        sa.Column("triggered_user_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("result", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["automation_id"], ["admin_automations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["triggered_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_admin_automation_runs_automation_id", "admin_automation_runs", ["automation_id"])


def downgrade() -> None:
    op.drop_index("ix_admin_automation_runs_automation_id", table_name="admin_automation_runs")
    op.drop_table("admin_automation_runs")
    op.drop_index("ix_admin_automations_trigger_type", table_name="admin_automations")
    op.drop_table("admin_automations")
