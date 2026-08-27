"""Add per-user settings.

Revision ID: 20260825_add_user_settings
Revises: 20260825_add_password_reset_tokens
Create Date: 2026-08-25
"""

from alembic import op
import sqlalchemy as sa

revision = "20260825_add_user_settings"
down_revision = "20260825_add_password_reset_tokens"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_settings",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("profile_picture", sa.Text(), nullable=True),
        sa.Column("theme", sa.String(length=20), nullable=False, server_default="system"),
        sa.Column("ai_response_style", sa.String(length=20), nullable=False, server_default="balanced"),
        sa.Column("default_email_tone", sa.String(length=30), nullable=False, server_default="Professional"),
        sa.Column("email_notifications", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("workflow_notifications", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("document_notifications", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id"),
    )
    op.create_index("ix_user_settings_user_id", "user_settings", ["user_id"])
    op.execute("UPDATE user_settings SET theme = 'light'")


def downgrade() -> None:
    op.drop_index("ix_user_settings_user_id", table_name="user_settings")
    op.drop_table("user_settings")
